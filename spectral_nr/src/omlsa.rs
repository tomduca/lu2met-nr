// OM-LSA speech enhancement with IMCRA noise estimation.
//
// Written from the published descriptions of the algorithms:
// - I. Cohen and B. Berdugo, "Speech enhancement for non-stationary noise
//   environments", Signal Processing 81(11), 2001 (OM-LSA gain).
// - I. Cohen, "Noise spectrum estimation in adverse environments: improved
//   minima controlled recursive averaging", IEEE Trans. Speech and Audio
//   Processing 11(5), 2003 (IMCRA noise estimate and speech absence
//   probability).
//
// Frames are 32 ms with 75 % overlap (8 ms hop), the timing used in those
// papers, so their smoothing constants apply unchanged at any sample rate.

use std::collections::VecDeque;
use std::sync::Arc;

use rustfft::num_complex::Complex;
use rustfft::{Fft, FftPlanner};

const FRAME_SECONDS: f64 = 0.032;

// IMCRA (Cohen 2003, section IV).
const ALPHA_S: f64 = 0.9; // recursive smoothing of the power spectrum
const ALPHA_D: f64 = 0.85; // noise update smoothing
const BETA: f64 = 1.47; // bias compensation of the noise estimate
const B_MIN: f64 = 1.66; // bias of the minimum noise estimate
const GAMMA0: f64 = 4.6;
const GAMMA1: f64 = 3.0;
const ZETA0: f64 = 1.67;
const SUBWINDOWS: usize = 8; // U
const SUBWINDOW_FRAMES: usize = 15; // V; U * V frames = about 1 s
const FREQ_SMOOTHING: [f64; 3] = [0.25, 0.5, 0.25]; // Hann window, w = 1

// OM-LSA gain.
const ALPHA_DD: f64 = 0.92; // decision-directed a priori SNR
const XI_MIN: f64 = 0.003_162_277_7; // -25 dB
const EPS: f64 = 1e-12;

/// Exponential integral E1(x) for x > 0 (Abramowitz and Stegun 5.1.53 and 5.1.56).
fn expint_e1(x: f64) -> f64 {
    if x <= 0.0 {
        return f64::INFINITY;
    }
    if x <= 1.0 {
        -x.ln() - 0.577_215_66
            + x * (0.999_991_93
                + x * (-0.249_910_55 + x * (0.055_199_68 + x * (-0.009_760_04 + x * 0.001_078_57))))
    } else {
        let num = x * (x * (x * (x + 8.573_328_740_1) + 18.059_016_973) + 8.634_760_892_5) + 0.267_773_734_3;
        let den = x * (x * (x * (x + 9.573_322_345_4) + 25.632_956_148_6) + 21.099_653_082_7) + 3.958_496_922_8;
        num / den * (-x).exp() / x
    }
}

/// Running minimum over U subwindows of V frames each.
struct MinimumTracker {
    minimum: Vec<f64>,
    current: Vec<f64>,
    history: VecDeque<Vec<f64>>,
}

impl MinimumTracker {
    fn new(initial: &[f64]) -> Self {
        Self {
            minimum: initial.to_vec(),
            current: initial.to_vec(),
            history: VecDeque::from(vec![initial.to_vec(); SUBWINDOWS]),
        }
    }

    fn update(&mut self, value: &[f64]) {
        for k in 0..value.len() {
            self.minimum[k] = self.minimum[k].min(value[k]);
            self.current[k] = self.current[k].min(value[k]);
        }
    }

    /// Called every V frames: forget the oldest subwindow.
    fn end_subwindow(&mut self, value: &[f64]) {
        self.history.pop_front();
        self.history.push_back(std::mem::replace(&mut self.current, value.to_vec()));
        for k in 0..value.len() {
            self.minimum[k] = self.history.iter().fold(f64::INFINITY, |m, h| m.min(h[k]));
        }
    }
}

struct State {
    smoothed: Vec<f64>,         // S
    smoothed_speechless: Vec<f64>, // S~ (second iteration, speech bins excluded)
    min_first: MinimumTracker,
    min_second: MinimumTracker,
    noise_raw: Vec<f64>,        // lambda~_d
    noise: Vec<f64>,            // lambda_d = beta * lambda~_d
    gain_h1_prev: Vec<f64>,
    gamma_prev: Vec<f64>,
}

pub struct OmlsaNoiseReduction {
    frame_len: usize,
    hop: usize,
    bins: usize,
    gain_floor: f64,
    window: Vec<f32>,
    fft: Arc<dyn Fft<f32>>,
    ifft: Arc<dyn Fft<f32>>,
    frame: Vec<f32>,
    overlap: Vec<f32>,
    spectrum: Vec<Complex<f32>>,
    input: VecDeque<f32>,
    output: VecDeque<f32>,
    frame_count: usize,
    state: Option<State>,
}

impl OmlsaNoiseReduction {
    /// `gain_floor_db` is the gain applied where speech is absent (Gmin), e.g. -25.0.
    pub fn new(sample_rate: u32, gain_floor_db: f32) -> Self {
        let frame_len = ((sample_rate as f64 * FRAME_SECONDS / 4.0).round() as usize).max(16) * 4;
        let hop = frame_len / 4;
        // Square-root periodic Hann for analysis and synthesis; with 75 %
        // overlap the product sums to 2, so the synthesis side scales by 1/2.
        let window = (0..frame_len)
            .map(|n| (0.5 - 0.5 * (2.0 * std::f64::consts::PI * n as f64 / frame_len as f64).cos()).sqrt() as f32)
            .collect();
        let mut planner = FftPlanner::new();
        Self {
            frame_len,
            hop,
            bins: frame_len / 2 + 1,
            gain_floor: 10f64.powf(gain_floor_db as f64 / 20.0),
            window,
            fft: planner.plan_fft_forward(frame_len),
            ifft: planner.plan_fft_inverse(frame_len),
            frame: vec![0.0; frame_len],
            overlap: vec![0.0; frame_len],
            spectrum: vec![Complex::new(0.0, 0.0); frame_len],
            input: VecDeque::new(),
            // One hop of priming keeps the output exactly as long as the input.
            output: VecDeque::from(vec![0.0; hop]),
            frame_count: 0,
            state: None,
        }
    }

    /// Delay between input and output, in samples.
    pub fn latency(&self) -> usize {
        self.frame_len
    }

    /// Filters `buf` in place; the output is delayed by `latency()` samples.
    pub fn process(&mut self, buf: &mut [f32]) {
        self.input.extend(buf.iter().copied());
        while self.input.len() >= self.hop {
            self.frame.copy_within(self.hop.., 0);
            let tail = self.frame_len - self.hop;
            for (dst, src) in self.frame[tail..].iter_mut().zip(self.input.drain(..self.hop)) {
                *dst = src;
            }
            self.process_frame();
        }
        for sample in buf.iter_mut() {
            *sample = self.output.pop_front().unwrap_or(0.0);
        }
    }

    fn process_frame(&mut self) {
        for n in 0..self.frame_len {
            self.spectrum[n] = Complex::new(self.frame[n] * self.window[n], 0.0);
        }
        self.fft.process(&mut self.spectrum);

        let power: Vec<f64> = self.spectrum[..self.bins]
            .iter()
            .map(|c| c.norm_sqr() as f64 + EPS)
            .collect();
        let gains = self.compute_gains(&power);

        for k in 0..self.bins {
            let g = gains[k] as f32;
            self.spectrum[k] *= g;
            if k > 0 && k < self.frame_len - k {
                self.spectrum[self.frame_len - k] *= g;
            }
        }
        self.ifft.process(&mut self.spectrum);

        let scale = 0.5 / self.frame_len as f32;
        for n in 0..self.frame_len {
            self.overlap[n] += self.spectrum[n].re * self.window[n] * scale;
        }
        self.output.extend(self.overlap[..self.hop].iter().copied());
        self.overlap.copy_within(self.hop.., 0);
        let len = self.frame_len;
        self.overlap[len - self.hop..].fill(0.0);
    }

    fn smooth_frequency(values: &[f64], weights: Option<&[f64]>) -> (Vec<f64>, Vec<f64>) {
        let n = values.len();
        let mut sum = vec![0.0; n];
        let mut weight_sum = vec![0.0; n];
        for k in 0..n {
            for (i, b) in FREQ_SMOOTHING.iter().enumerate() {
                let j = (k + i).saturating_sub(1).min(n - 1);
                let w = b * weights.map_or(1.0, |w| w[j]);
                sum[k] += w * values[j];
                weight_sum[k] += w;
            }
        }
        (sum, weight_sum)
    }

    fn compute_gains(&mut self, power: &[f64]) -> Vec<f64> {
        let bins = self.bins;
        let state = self.state.get_or_insert_with(|| {
            let (smoothed, _) = Self::smooth_frequency(power, None);
            State {
                min_first: MinimumTracker::new(&smoothed),
                min_second: MinimumTracker::new(&smoothed),
                smoothed_speechless: smoothed.clone(),
                smoothed,
                noise_raw: power.to_vec(),
                noise: power.to_vec(),
                gain_h1_prev: vec![1.0; bins],
                gamma_prev: vec![1.0; bins],
            }
        });

        // A posteriori and a priori SNR, conditional LSA gain.
        let mut gamma = vec![0.0; bins];
        let mut xi = vec![0.0; bins];
        let mut v = vec![0.0; bins];
        let mut gain_h1 = vec![0.0; bins];
        for k in 0..bins {
            gamma[k] = power[k] / state.noise[k].max(EPS);
            let dd = ALPHA_DD * state.gain_h1_prev[k].powi(2) * state.gamma_prev[k]
                + (1.0 - ALPHA_DD) * (gamma[k] - 1.0).max(0.0);
            xi[k] = dd.max(XI_MIN);
            v[k] = gamma[k] * xi[k] / (1.0 + xi[k]);
            gain_h1[k] = (xi[k] / (1.0 + xi[k]) * (0.5 * expint_e1(v[k].max(1e-10))).exp()).min(1.0);
        }

        // IMCRA, first iteration: rough speech/noise decision from minima.
        let (sf, _) = Self::smooth_frequency(power, None);
        for k in 0..bins {
            state.smoothed[k] = ALPHA_S * state.smoothed[k] + (1.0 - ALPHA_S) * sf[k];
        }
        state.min_first.update(&state.smoothed);
        let noise_like: Vec<f64> = (0..bins)
            .map(|k| {
                let floor = B_MIN * state.min_first.minimum[k].max(EPS);
                let is_noise = power[k] / floor < GAMMA0 && state.smoothed[k] / floor < ZETA0;
                if is_noise { 1.0 } else { 0.0 }
            })
            .collect();

        // Second iteration: smoothing restricted to noise-only bins.
        let (num, den) = Self::smooth_frequency(power, Some(&noise_like));
        for k in 0..bins {
            let sf2 = if den[k] > 0.0 { num[k] / den[k] } else { state.smoothed_speechless[k] };
            state.smoothed_speechless[k] = ALPHA_S * state.smoothed_speechless[k] + (1.0 - ALPHA_S) * sf2;
        }
        state.min_second.update(&state.smoothed_speechless);

        let mut gains = vec![0.0; bins];
        for k in 0..bins {
            let floor = B_MIN * state.min_second.minimum[k].max(EPS);
            let gamma_min = power[k] / floor;
            let zeta = state.smoothed[k] / floor;
            // A priori speech absence probability.
            let q = if gamma_min <= 1.0 && zeta < ZETA0 {
                1.0
            } else if gamma_min < GAMMA1 && zeta < ZETA0 {
                (GAMMA1 - gamma_min) / (GAMMA1 - 1.0)
            } else {
                0.0
            };
            // Speech presence probability.
            let p = if q >= 1.0 {
                0.0
            } else {
                1.0 / (1.0 + q / (1.0 - q) * (1.0 + xi[k]) * (-v[k]).exp())
            };

            gains[k] = gain_h1[k].powf(p) * self.gain_floor.powf(1.0 - p);

            let alpha = ALPHA_D + (1.0 - ALPHA_D) * p;
            state.noise_raw[k] = alpha * state.noise_raw[k] + (1.0 - alpha) * power[k];
            state.noise[k] = BETA * state.noise_raw[k];
        }

        self.frame_count += 1;
        if self.frame_count % SUBWINDOW_FRAMES == 0 {
            state.min_first.end_subwindow(&state.smoothed);
            state.min_second.end_subwindow(&state.smoothed_speechless);
        }

        state.gain_h1_prev = gain_h1;
        state.gamma_prev = gamma;
        gains
    }
}
