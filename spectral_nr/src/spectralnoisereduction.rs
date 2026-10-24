use std::collections::VecDeque;
use std::sync::Arc;

use rustfft::num_complex::Complex;
use rustfft::{FftPlanner, Fft};

/*

#define FFT_FULL  512
#define FFT_HALF  256

const static arm_cfft_instance_f32 *NR_FFT = &arm_cfft_sR_f32_len512;
const static arm_cfft_instance_f32 *NR_iFFT = &arm_cfft_sR_f32_len512;

const f32_t psthr = 0.99;   // threshold for smoothed speech probability [0.99]
const f32_t pnsaf = 0.01;   // noise probability safety value [0.01]
const f32_t psini = 0.5;    // initial speech probability [0.5]
const f32_t pspri = 0.5;    // prior speech probability [0.5]

struct nr_spectral_t {
    bool init;
    u1_t init_counter;
    u1_t first_time;

    f32_t final_gain;
    f32_t alpha;
    f32_t asnr;

    f32_t xih1;
    f32_t xih1r;
    f32_t pfac;

    TYPECPX FFT_buffer[FFT_FULL];
    f32_t last_sample_buffer[FFT_HALF];
    f32_t last_iFFT_result[FFT_HALF];

    f32_t NR_Nest[FFT_HALF];
    f32_t xt[FFT_HALF];
    f32_t pslp[FFT_HALF];
    f32_t NR_SNR_post[FFT_HALF];
    f32_t NR_SNR_prio[FFT_HALF];
    f32_t NR_Hk_old[FFT_HALF];
    f32_t NR_G[FFT_HALF];   // preliminary gain factors (before time smoothing) and after that contains the frequency smoothed gain factors

    f32_t last_norm_locut, last_norm_hicut;
};
static nr_spectral_t nr_spectral[MAX_RX_CHANS];

// array of squareroot von Hann coefficients [256]
const f32_t sqrtHann_256[256] = {0, 0.01231966, 0.024637449, 0.036951499, 0.049259941, 0.061560906, 0.073852527, 0.086132939, 0.098400278, 0.110652682, 0.122888291, 0.135105247, 0.147301698, 0.159475791, 0.171625679, 0.183749518, 0.195845467, 0.207911691, 0.219946358, 0.231947641, 0.24391372, 0.255842778, 0.267733003, 0.279582593, 0.291389747, 0.303152674, 0.314869589, 0.326538713, 0.338158275, 0.349726511, 0.361241666, 0.372701992, 0.384105749, 0.395451207, 0.406736643, 0.417960345, 0.429120609, 0.440215741, 0.451244057, 0.462203884, 0.473093557, 0.483911424, 0.494655843, 0.505325184, 0.515917826, 0.526432163, 0.536866598, 0.547219547, 0.557489439, 0.567674716, 0.577773831, 0.587785252, 0.597707459, 0.607538946, 0.617278221, 0.626923806, 0.636474236, 0.645928062, 0.65528385, 0.664540179, 0.673695644, 0.682748855, 0.691698439, 0.700543038, 0.709281308, 0.717911923, 0.726433574, 0.734844967, 0.743144825, 0.75133189, 0.759404917, 0.767362681, 0.775203976, 0.78292761, 0.790532412, 0.798017227, 0.805380919, 0.812622371, 0.819740483, 0.826734175, 0.833602385, 0.840344072, 0.846958211, 0.853443799, 0.859799851, 0.866025404, 0.872119511, 0.878081248, 0.88390971, 0.889604013, 0.895163291, 0.900586702, 0.905873422, 0.911022649, 0.916033601, 0.920905518, 0.92563766, 0.930229309, 0.934679767, 0.938988361, 0.943154434, 0.947177357, 0.951056516, 0.954791325, 0.958381215, 0.961825643, 0.965124085, 0.968276041, 0.971281032, 0.974138602, 0.976848318, 0.979409768, 0.981822563, 0.984086337, 0.986200747, 0.988165472, 0.989980213, 0.991644696, 0.993158666, 0.994521895, 0.995734176, 0.996795325, 0.99770518, 0.998463604, 0.999070481, 0.99952572, 0.99982925, 0.999981027, 0.999981027, 0.99982925, 0.99952572, 0.999070481, 0.998463604, 0.99770518, 0.996795325, 0.995734176, 0.994521895, 0.993158666, 0.991644696, 0.989980213, 0.988165472, 0.986200747, 0.984086337, 0.981822563, 0.979409768, 0.976848318, 0.974138602, 0.971281032, 0.968276041, 0.965124085, 0.961825643, 0.958381215, 0.954791325, 0.951056516, 0.947177357, 0.943154434, 0.938988361, 0.934679767, 0.930229309, 0.92563766, 0.920905518, 0.916033601, 0.911022649, 0.905873422, 0.900586702, 0.895163291, 0.889604013, 0.88390971, 0.878081248, 0.872119511, 0.866025404, 0.859799851, 0.853443799, 0.846958211, 0.840344072, 0.833602385, 0.826734175, 0.819740483, 0.812622371, 0.805380919, 0.798017227, 0.790532412, 0.78292761, 0.775203976, 0.767362681, 0.759404917, 0.75133189, 0.743144825, 0.734844967, 0.726433574, 0.717911923, 0.709281308, 0.700543038, 0.691698439, 0.682748855, 0.673695644, 0.664540179, 0.65528385, 0.645928062, 0.636474236, 0.626923806, 0.617278221, 0.607538946, 0.597707459, 0.587785252, 0.577773831, 0.567674716, 0.557489439, 0.547219547, 0.536866598, 0.526432163, 0.515917826, 0.505325184, 0.494655843, 0.483911424, 0.473093557, 0.462203884, 0.451244057, 0.440215741, 0.429120609, 0.417960345, 0.406736643, 0.395451207, 0.384105749, 0.372701992, 0.361241666, 0.349726511, 0.338158275, 0.326538713, 0.314869589, 0.303152674, 0.291389747, 0.279582593, 0.267733003, 0.255842778, 0.24391372, 0.231947641, 0.219946358, 0.207911691, 0.195845467, 0.183749518, 0.171625679, 0.159475791, 0.147301698, 0.135105247, 0.122888291, 0.110652682, 0.098400278, 0.086132939, 0.073852527, 0.061560906, 0.049259941, 0.036951499, 0.024637449, 0.01231966, 0};

// NB: assumes same sample rate for all channels
static f32_t tinc;  // frame time e.g. 42.666 ms for 12 kHz (0.042666 = 1/(12k/512)
static f32_t tax;   // noise output smoothing time constant
static f32_t tap;   // speech prob smoothing time constant
static f32_t ax;    // noise output smoothing factor
static f32_t ap;    // noise output smoothing factor


*/

// use vectors

const FFT_FULL: usize = 512;
const FFT_HALF: usize = 256;

#[allow(dead_code)]
pub struct SpectralNoiseReduction {
    init: bool,
    init_counter: u8,
    first_time: u8,
    snd_rate: u32,

    final_gain: f32,
    alpha: f32,
    asnr: f32,

    xih1: f32,
    xih1r: f32,
    pfac: f32,

    ring_buf: VecDeque<f32>,
    fft_buffer: Vec<Complex<f32>>,
    last_sample_buffer: Vec<f32>,
    last_ifft_result: Vec<f32>,

    nr_nest: Vec<f32>,
    xt: Vec<f32>,
    pslp: Vec<f32>,
    nr_snr_post: Vec<f32>,
    nr_snr_prio: Vec<f32>,
    nr_hk_old: Vec<f32>,
    nr_g: Vec<f32>, // preliminary gain factors (before time smoothing) and after that contains the frequency smoothed gain factors

    norm_hicut: f32,
    norm_locut: f32,
    last_norm_locut: f32,
    last_norm_hicut: f32,

    tinc: f32, // frame time e.g. 42.666 ms for 12 kHz (0.042666 = 1/(12k/512)
    tax: f32,  // noise output smoothing time constant
    tap: f32,  // speech prob smoothing time constant
    ax: f32,   // noise output smoothing factor
    ap: f32,   // noise output smoothing factor

    nr_fft: Arc<dyn Fft<f32>>,
    nr_ifft: Arc<dyn Fft<f32>>,

    psthr: f32,   // threshold for smoothed speech probability [0.99]
    pnsaf: f32,   // noise probability safety value [0.01]
    psini: f32,   // initial speech probability [0.5]
    pspri: f32,   // prior speech probability [0.5]
}

const SQRT_HANN_256: [f32; 256] = [
    0.0,
    0.01231966,
    0.024637449,
    0.036951499,
    0.049259941,
    0.061560906,
    0.073852527,
    0.086132939,
    0.098400278,
    0.110652682,
    0.122888291,
    0.135105247,
    0.147301698,
    0.159475791,
    0.171625679,
    0.183749518,
    0.195845467,
    0.207911691,
    0.219946358,
    0.231947641,
    0.24391372,
    0.255842778,
    0.267733003,
    0.279582593,
    0.291389747,
    0.303152674,
    0.314869589,
    0.326538713,
    0.338158275,
    0.349726511,
    0.361241666,
    0.372701992,
    0.384105749,
    0.395451207,
    0.406736643,
    0.417960345,
    0.429120609,
    0.440215741,
    0.451244057,
    0.462203884,
    0.473093557,
    0.483911424,
    0.494655843,
    0.505325184,
    0.515917826,
    0.526432163,
    0.536866598,
    0.547219547,
    0.557489439,
    0.567674716,
    0.577773831,
    0.587785252,
    0.597707459,
    0.607538946,
    0.617278221,
    0.626923806,
    0.636474236,
    0.645928062,
    0.65528385,
    0.664540179,
    0.673695644,
    0.682748855,
    0.691698439,
    0.700543038,
    0.709281308,
    0.717911923,
    0.726433574,
    0.734844967,
    0.743144825,
    0.75133189,
    0.759404917,
    0.767362681,
    0.775203976,
    0.78292761,
    0.790532412,
    0.798017227,
    0.805380919,
    0.812622371,
    0.819740483,
    0.826734175,
    0.833602385,
    0.840344072,
    0.846958211,
    0.853443799,
    0.859799851,
    0.866025404,
    0.872119511,
    0.878081248,
    0.88390971,
    0.889604013,
    0.895163291,
    0.900586702,
    0.905873422,
    0.911022649,
    0.916033601,
    0.920905518,
    0.92563766,
    0.930229309,
    0.934679767,
    0.938988361,
    0.943154434,
    0.947177357,
    0.951056516,
    0.954791325,
    0.958381215,
    0.961825643,
    0.965124085,
    0.968276041,
    0.971281032,
    0.974138602,
    0.976848318,
    0.979409768,
    0.981822563,
    0.984086337,
    0.986200747,
    0.988165472,
    0.989980213,
    0.991644696,
    0.993158666,
    0.994521895,
    0.995734176,
    0.996795325,
    0.99770518,
    0.998463604,
    0.999070481,
    0.99952572,
    0.99982925,
    0.999981027,
    0.999981027,
    0.99982925,
    0.99952572,
    0.999070481,
    0.998463604,
    0.99770518,
    0.996795325,
    0.995734176,
    0.994521895,
    0.993158666,
    0.991644696,
    0.989980213,
    0.988165472,
    0.986200747,
    0.984086337,
    0.981822563,
    0.979409768,
    0.976848318,
    0.974138602,
    0.971281032,
    0.968276041,
    0.965124085,
    0.961825643,
    0.958381215,
    0.954791325,
    0.951056516,
    0.947177357,
    0.943154434,
    0.938988361,
    0.934679767,
    0.930229309,
    0.92563766,
    0.920905518,
    0.916033601,
    0.911022649,
    0.905873422,
    0.900586702,
    0.895163291,
    0.889604013,
    0.88390971,
    0.878081248,
    0.872119511,
    0.866025404,
    0.859799851,
    0.853443799,
    0.846958211,
    0.840344072,
    0.833602385,
    0.826734175,
    0.819740483,
    0.812622371,
    0.805380919,
    0.798017227,
    0.790532412,
    0.78292761,
    0.775203976,
    0.767362681,
    0.759404917,
    0.75133189,
    0.743144825,
    0.734844967,
    0.726433574,
    0.717911923,
    0.709281308,
    0.700543038,
    0.691698439,
    0.682748855,
    0.673695644,
    0.664540179,
    0.65528385,
    0.645928062,
    0.636474236,
    0.626923806,
    0.617278221,
    0.607538946,
    0.597707459,
    0.587785252,
    0.577773831,
    0.567674716,
    0.557489439,
    0.547219547,
    0.536866598,
    0.526432163,
    0.515917826,
    0.505325184,
    0.494655843,
    0.483911424,
    0.473093557,
    0.462203884,
    0.451244057,
    0.440215741,
    0.429120609,
    0.417960345,
    0.406736643,
    0.395451207,
    0.384105749,
    0.372701992,
    0.361241666,
    0.349726511,
    0.338158275,
    0.326538713,
    0.314869589,
    0.303152674,
    0.291389747,
    0.279582593,
    0.267733003,
    0.255842778,
    0.24391372,
    0.231947641,
    0.219946358,
    0.207911691,
    0.195845467,
    0.183749518,
    0.171625679,
    0.159475791,
    0.147301698,
    0.135105247,
    0.122888291,
    0.110652682,
    0.098400278,
    0.086132939,
    0.073852527,
    0.061560906,
    0.049259941,
    0.036951499,
    0.024637449,
    0.01231966,
    0.0,
];

/*
void nr_spectral_init(int rx_chan, TYPEREAL nr_param[NOISE_PARAMS])
{
    nr_spectral_t *s = &nr_spectral[rx_chan];

    if (!s->init) {
        s->init = true;
        s->first_time = 1;

        tinc = 1.0 / ((f32_t) snd_rate / FFT_FULL * 2);
        tax = -tinc / logf(0.8);
        tap = -tinc / logf(0.9);
        ax = expf(-tinc / tax);
        ap = expf(-tinc / tap);

        for (int bindx = 0; bindx < FFT_HALF; bindx++) {
            s->last_sample_buffer[bindx] = 0.1;
            s->NR_Hk_old[bindx] = 0.1;      // old gain
            s->NR_SNR_post[bindx] = 2.0;
            s->NR_SNR_prio[bindx] = 1.0;
        }
    }

    s->final_gain = nr_param[NR_S_GAIN];
    s->alpha = nr_param[NR_ALPHA];
    s->asnr = nr_param[NR_ASNR];
    s->xih1 = s->asnr;
    s->xih1r = 1.0 / (1.0 + s->xih1) - 1.0;
    s->pfac = (1.0 / pspri - 1.0) * (1.0 + s->xih1);
    //printf("nr_spectral_init: final_gain=%f alpha=%.2f asnr=%.3f\n", s->final_gain, s->alpha, s->asnr);
}
*/

impl SpectralNoiseReduction {
    pub fn new(snd_rate: u32, nr_s_gain: f32, nr_alpha: f32, nr_asnr: f32) -> Self {
        let tinc = 1.0/( snd_rate as f32 / FFT_FULL as f32 * 2.0);
        let tax = -tinc / (0.8_f32).ln();
        let tap = -tinc / (0.9_f32).ln();
        let xih1r = 1.0 / (1.0 + nr_asnr) - 1.0;
        let pfac = (1.0 / 0.5 - 1.0) * (1.0 + nr_asnr);

        let nr_fft = FftPlanner::new().plan_fft_forward(FFT_FULL);
        let nr_ifft = FftPlanner::new().plan_fft_inverse(FFT_FULL);
        Self {
            init: true,
            init_counter: 0,
            first_time: 1,
            snd_rate,
            final_gain: nr_s_gain,
            alpha: nr_alpha,
            asnr: nr_asnr,
            xih1: nr_asnr,
            xih1r,
            pfac,
            ring_buf: VecDeque::new(),
            fft_buffer: vec![Complex { re: 0.0, im: 0.0 }; FFT_FULL],
            last_sample_buffer: vec![0.1; FFT_HALF],
            last_ifft_result: vec![0.1; FFT_HALF],
            nr_nest: vec![0.0; FFT_HALF],
            xt: vec![0.0; FFT_HALF],
            pslp: vec![0.0; FFT_HALF],
            nr_snr_post: vec![2.0; FFT_HALF],
            nr_snr_prio: vec![1.0; FFT_HALF],
            nr_hk_old: vec![0.0; FFT_HALF],
            nr_g: vec![0.0; FFT_HALF],
            norm_hicut: 3000.0,
            norm_locut: 300.0,
            last_norm_locut: 0.0,
            last_norm_hicut: 0.0,
            tinc,
            tax,
            tap,
            ax: (-tinc / tax).exp(),
            ap: (-tinc / tap).exp(),
            nr_fft,
            nr_ifft,
            psthr: 0.99,
            pnsaf: 0.01,
            psini: 0.5,
            pspri: 0.5,
        }
    }

    pub fn process(&mut self, buf: &mut Vec<f32>) {
        let ret = self.process_part(buf);
        buf.clear();
        buf.extend_from_slice(&ret);
    }
    pub fn process_part(&mut self, buf: &mut[f32]) -> Vec<f32> {
        // insert all into self.ringbuf
        for i in 0..buf.len() {
            self.ring_buf.push_back(buf[i]);
        }
        let mut ret = Vec::new();
        // process_chunks in chunks of FFT_FULL
        while self.ring_buf.len() >= FFT_FULL {
            let mut chunk = [0.0; FFT_FULL];
            for i in 0..FFT_FULL {
                let Some(sample) = self.ring_buf.pop_front() else {
                    return Vec::new();
                };
                chunk[i] = sample;
            }
            self.process_chunk(&mut chunk);
            ret.extend_from_slice(&chunk);
        }
        ret
    }
    /*
    void nr_spectral_process(int rx_chan, int nsamps, TYPEMONO16 *inputsamples, TYPEMONO16 *outputsamples )
    {
        nr_spectral_t *s = &nr_spectral[rx_chan];
        snd_t *snd = &snd_inst[rx_chan];
        if nsamps != FFT_FULL {
            return;
        }

        int ai;
        int VAD_low = 0, VAD_high = 0;

        const f32_t snr_prio_min_dB = -30;
        const f32_t snr_prio_min = powf(10, snr_prio_min_dB / 10.0);
        const int NR_width = 4;

        // INITIALIZATION ONCE 1
        if (s->first_time == 1) {
            for (int bindx = 0; bindx < FFT_HALF; bindx++) {
                s->last_sample_buffer[bindx] = 0.0;
                s->NR_G[bindx] = 1.0;
                s->NR_Hk_old[bindx] = 1.0;
                s->NR_Nest[bindx] = 0.0;
                s->pslp[bindx] = 0.5;
            }
            s->first_time = 2;  // we need to do some more a bit later down
        }
    */
    pub fn process_chunk(&mut self, buf: &mut [f32]) {
        let mut ai;
        let mut vad_low = 0;
        let mut vad_high = 0;

        const SNR_PRIO_MIN_DB: f32 = -30.0;
        let snr_prio_min: f32 = 10.0_f32.powf(SNR_PRIO_MIN_DB / 10.0);
        const NR_WIDTH: usize = 4;

        // INITIALIZATION ONCE 1
        if self.first_time == 1 {
            for bindx in 0..FFT_HALF {
                self.last_sample_buffer[bindx] = 0.0;
                self.nr_g[bindx] = 1.0;
                self.nr_hk_old[bindx] = 1.0;
                self.nr_nest[bindx] = 0.0;
                self.pslp[bindx] = 0.5;
            }
            self.first_time = 2;  // we need to do some more a bit later down
        }

    /*
        for (int k = 0; k < 2; k++) {   // start of loop which repeats the FFT_iFFT_chain two times

            // fill first half of FFT_buffer with last events audio samples
            for (int i = 0; i < FFT_HALF; i++) {
                s->FFT_buffer[i].re = s->last_sample_buffer[i];
                s->FFT_buffer[i].im = 0.0;
            }

            for (int i = 0; i < FFT_HALF; i++) {
                ai = i + k * FFT_HALF;
                assert_array_dim(ai, nsamps);
                f32_t f_samp = (f32_t) inputsamples[ai];

                // copy recent samples to last_sample_buffer for next time
                s->last_sample_buffer[i] = f_samp;

                // now fill recent audio samples into second half of FFT_buffer
                s->FFT_buffer[FFT_HALF + i].re = f_samp;
                s->FFT_buffer[FFT_HALF + i].im = 0.0;
            }

            // perform windowing on samples in the FFT_buffer
            for (int i = 0; i < FFT_FULL; i++) {
                s->FFT_buffer[i].re *= sqrtHann_256[i/2];
            }

            // FFT calculation is performed in-place, FFT_buffer: [re, im, re, im, re, im . . .]
            arm_cfft_f32(NR_FFT, (TYPEREAL*) s->FFT_buffer, 0, 1);
        */
        for k in 0..2 {
            // fill first half of FFT_buffer with last events audio samples
            for i in 0..FFT_HALF {
                self.fft_buffer[i].re = self.last_sample_buffer[i];
                self.fft_buffer[i].im = 0.0;
            }

            for i in 0..FFT_HALF {
                ai = i + k * FFT_HALF;
                //assert_array_dim(ai, buf.len());
                let f_samp = buf[ai];

                // copy recent samples to last_sample_buffer for next time
                self.last_sample_buffer[i] = f_samp;

                // now fill recent audio samples into second half of FFT_buffer
                self.fft_buffer[FFT_HALF + i].re = f_samp;
                self.fft_buffer[FFT_HALF + i].im = 0.0;
            }

            // perform windowing on samples in the FFT_buffer
            for i in 0..FFT_FULL {
                self.fft_buffer[i].re *= SQRT_HANN_256[i / 2];
            }

            self.nr_fft.process(&mut self.fft_buffer);
        /*
            f32_t NR_X[FFT_HALF];

            for (int bindx = 0; bindx < FFT_HALF; bindx++) {
                f32_t re = s->FFT_buffer[bindx].re, im = s->FFT_buffer[bindx].im;
                NR_X[bindx] = re*re + im*im;    // squared magnitude for the current frame
            }

            if (s->first_time == 2) {
                for (int bindx = 0; bindx < FFT_HALF; bindx++) {

                    // we do it 20 times to average over 20 frames for approx 100 ms only on NR_on/bandswitch/modeswitch ...
                    s->NR_Nest[bindx] = s->NR_Nest[bindx] + 0.05 * NR_X[bindx];
                    s->xt[bindx] = psini * s->NR_Nest[bindx];
                }

                s->init_counter++;
                if (s->init_counter > 19) {     // average over 20 frames for approx 100 ms
                    s->init_counter = 0;
                    s->first_time = 3;  // now we did all the necessary initialization to actually start the noise reduction
                }
            }
        */
            let mut nr_x = [0.0; FFT_HALF];

            for bindx in 0..FFT_HALF {
                let re = self.fft_buffer[bindx].re;
                let im = self.fft_buffer[bindx].im;
                nr_x[bindx] = re * re + im * im;    // squared magnitude for the current frame
            }

            if self.first_time == 2 {
                for bindx in 0..FFT_HALF {
                    // we do it 20 times to average over 20 frames for approx 100 ms only on NR_on/bandswitch/modeswitch ...
                    self.nr_nest[bindx] = self.nr_nest[bindx] + 0.05 * nr_x[bindx];
                    self.xt[bindx] = self.psini * self.nr_nest[bindx];
                }

                self.init_counter += 1;
                if self.init_counter > 19 {     // average over 20 frames for approx 100 ms
                    self.init_counter = 0;
                    self.first_time = 3;  // now we did all the necessary initialization to actually start the noise reduction
                }
            }

        /*
            if (s->first_time == 3) {

                // new noise estimate MMSE based

                for (int bindx = 0; bindx < FFT_HALF; bindx++) {    // 1. Step of NR - calculate the SNR's
                    f32_t ph1y[FFT_HALF];

                    ph1y[bindx] = 1.0 / (1.0 + s->pfac * expf(s->xih1r * NR_X[bindx] / s->xt[bindx]));
                    s->pslp[bindx] = ap * s->pslp[bindx] + (1.0 - ap) * ph1y[bindx];

                    if (s->pslp[bindx] > psthr)
                        ph1y[bindx] = 1.0 - pnsaf;
                    else
                        ph1y[bindx] = fmin(ph1y[bindx], 1.0);

                    f32_t xtr = (1.0 - ph1y[bindx]) * NR_X[bindx] + ph1y[bindx] * s->xt[bindx];
                    s->xt[bindx] = ax * s->xt[bindx] + (1.0 - ax) * xtr;
                }


                for (int bindx = 0; bindx < FFT_HALF; bindx++) {    // 1. Step of NR - calculate the SNR's
                    // limited to +30 dB / snr_prio_min_dB, might be still too much of reduction, let's try it?
                    s->NR_SNR_post[bindx] = fmax(fmin(NR_X[bindx] / s->xt[bindx], 1000.0), snr_prio_min);
                    s->NR_SNR_prio[bindx] = fmax(s->alpha * s->NR_Hk_old[bindx] + (1.0 - s->alpha) * fmax(s->NR_SNR_post[bindx] - 1.0, 0.0), 0.0);
                }
                
                VAD_low  = (int) floorf(snd->norm_locut / ((f32_t) snd_rate / FFT_FULL));
                VAD_high = (int) ceilf(snd->norm_hicut / ((f32_t) snd_rate / FFT_FULL));
        */
            if self.first_time == 3 {

                // new noise estimate MMSE based

                for bindx in 0..FFT_HALF {    // 1. Step of NR - calculate the SNR's
                    let mut ph1y: f32;

                    ph1y = 1.0 / (1.0 + self.pfac * (self.xih1r * nr_x[bindx] / self.xt[bindx]).exp());
                    self.pslp[bindx] = self.ap * self.pslp[bindx] + (1.0 - self.ap) * ph1y;

                    if self.pslp[bindx] > self.psthr {
                        ph1y = 1.0 - self.pnsaf;
                    } else {
                        ph1y = ph1y.min(1.0);
                    }

                    let xtr = (1.0 - ph1y) * nr_x[bindx] + ph1y * self.xt[bindx];
                    self.xt[bindx] = self.ax * self.xt[bindx] + (1.0 - self.ax) * xtr;
                }

                for bindx in 0..FFT_HALF {    // 1. Step of NR - calculate the SNR's
                    // limited to +30 dB / snr_prio_min_dB, might be still too much of reduction, let's try it?
                    self.nr_snr_post[bindx] = (nr_x[bindx] / self.xt[bindx]).max(snr_prio_min).min(1000.0);
                    self.nr_snr_prio[bindx] = (self.alpha * self.nr_hk_old[bindx] + (1.0 - self.alpha) * (self.nr_snr_post[bindx] - 1.0).max(0.0)).max(0.0);
                }

                vad_low = (self.norm_locut / (self.snd_rate as f32 / FFT_FULL as f32)).floor() as usize;
                vad_high = (self.norm_hicut / (self.snd_rate as f32 / FFT_FULL as f32)).ceil() as usize;
        /*
                #if 0
                    if (s->last_norm_locut != snd->norm_locut || s->last_norm_hicut != snd->norm_hicut) {
                        printf("nr_spectral_process: locut=%.3f(%d) hicut=%.3f(%d) ", snd->norm_locut, VAD_low, snd->norm_hicut, VAD_high);
                    }
                #endif

                if (VAD_low == VAD_high) VAD_high++;

                if (VAD_low < 1) {
                    VAD_low = 1;
                } else {
                    if (VAD_low > FFT_HALF - 2)
                        VAD_low = FFT_HALF - 2;
                }

                if (VAD_high < 2) {
                    VAD_high = 2;
                } else {
                    if (VAD_high > FFT_HALF) {
                        VAD_high = FFT_HALF;
                    }
                }

                assert_array_dim(VAD_low, FFT_HALF + 1);
                assert_array_dim(VAD_high, FFT_HALF + 1);

                #if 0
                    if (s->last_norm_locut != snd->norm_locut || s->last_norm_hicut != snd->norm_hicut) {
                        printf("FINAL %d, %d\n", VAD_low, VAD_high);
                        s->last_norm_locut = snd->norm_locut;
                        s->last_norm_hicut = snd->norm_hicut;
                    }
                #endif

            */
                if vad_low == vad_high {
                    vad_high += 1;
                }

                if vad_low < 1 {
                    vad_low = 1;
                } else if vad_low > FFT_HALF - 2 {
                    vad_low = FFT_HALF - 2;
                }

                if vad_high < 2 {
                    vad_high = 2;
                } else if vad_high > FFT_HALF {
                    vad_high = FFT_HALF;
                }
            /*
                // 4. calculate v = SNRprio(n, bin[i]) / (SNRprio(n, bin[i]) + 1) * SNRpost(n, bin[i]) (eq. 12 of Schmitt et al. 2002, eq. 9 of Romanin et al. 2009)
                //    and calculate the HK's

                for (int bindx = VAD_low; bindx < VAD_high; bindx++) {  // maybe we should limit this to the signal containing bins (filtering)
                    assert_array_dim(bindx, FFT_HALF);
                    f32_t v = s->NR_SNR_prio[bindx] * s->NR_SNR_post[bindx] / (1.0 + s->NR_SNR_prio[bindx]);
                    #define GAIN_LIMIT 0.001
                    s->NR_G[bindx] = fmax(1.0 / s->NR_SNR_post[bindx] * sqrtf(0.7212 * v + v * v), GAIN_LIMIT);
                    s->NR_Hk_old[bindx] = s->NR_SNR_post[bindx] * s->NR_G[bindx] * s->NR_G[bindx];
                }

                // MUSICAL NOISE TREATMENT HERE, DL2FW
                // musical noise "artifact" reduction by dynamic averaging - depending on SNR ratio
                f32_t pre_power = 0.0;
                f32_t post_power = 0.0;

                for (int bindx = VAD_low; bindx < VAD_high; bindx++) {
                    pre_power += NR_X[bindx];
                    post_power += s->NR_G[bindx] * s->NR_G[bindx]  * NR_X[bindx];
                }

                int NN;
                f32_t power_ratio = post_power / pre_power;
                const f32_t power_threshold = 0.4;

                if (power_ratio > power_threshold) {
                    power_ratio = 1.0;
                    NN = 1;
                } else {
                    NN = 1 + 2 * (int)(0.5 + NR_width * (1.0 - power_ratio / power_threshold));
                }
            */
                // 4. calculate v = SNRprio(n, bin[i]) / (SNRprio(n, bin[i]) + 1) * SNRpost(n, bin[i]) (eq. 12 of Schmitt et al. 2002, eq. 9 of Romanin et al. 2009)
                //    and calculate the HK's

                for bindx in vad_low..vad_high {
                    //assert_array_dim!(bindx, FFT_HALF);
                    let v = self.nr_snr_prio[bindx] * self.nr_snr_post[bindx] / (1.0 + self.nr_snr_prio[bindx]);
                    let gain_limit = 0.001;
                    self.nr_g[bindx] = f32::max(1.0 / self.nr_snr_post[bindx] * (0.7212 * v + v * v).sqrt(), gain_limit);
                    self.nr_hk_old[bindx] = self.nr_snr_post[bindx] * self.nr_g[bindx] * self.nr_g[bindx];
                }

                // MUSICAL NOISE TREATMENT HERE, DL2FW
                // musical noise "artifact" reduction by dynamic averaging - depending on SNR ratio
                let mut pre_power: f32 = 0.0;
                let mut post_power: f32 = 0.0;

                for bindx in vad_low..vad_high {
                    pre_power += nr_x[bindx];
                    post_power += self.nr_g[bindx] * self.nr_g[bindx] * nr_x[bindx];
                }
                
                let nn: usize;
                let power_ratio = post_power / pre_power;
                let power_threshold: f32 = 0.4;

                if power_ratio > power_threshold {
                    nn = 1;
                } else {
                    nn = 1 + 2 * (0.5 + NR_WIDTH as f32 * (1.0 - power_ratio / power_threshold)) as usize;
                }

            /* 
                for (int bindx = VAD_low + NN / 2; bindx < VAD_high - NN / 2; bindx++) {
                    assert_array_dim(bindx, FFT_HALF);
                    s->NR_Nest[bindx] = 0.0;
                    for (int m = bindx - NN / 2; m <= bindx + NN / 2; m++) {
                        assert_array_dim(m, FFT_HALF);
                        s->NR_Nest[bindx] += s->NR_G[m];
                    }
                    s->NR_Nest[bindx] /= (f32_t) NN;
                }

                // and now the edges - only going NN steps forward and taking the average lower edge
                for (int bindx = VAD_low; bindx < VAD_low + NN / 2; bindx++) {
                    assert_array_dim(bindx, FFT_HALF);
                    s->NR_Nest[bindx] = 0.0;
                    for (int m = bindx; m < (bindx + NN); m++) {
                        assert_array_dim(m, FFT_HALF);
                        s->NR_Nest[bindx] += s->NR_G[m];
                    }
                    s->NR_Nest[bindx] /= (f32_t) NN;
                }

                // upper edge - only going NN steps backward and taking the average
                for (int bindx = VAD_high - NN; bindx < VAD_high; bindx++) {
                    assert_array_dim(bindx, FFT_HALF);
                    s->NR_Nest[bindx] = 0.0;
                    for (int m = bindx; m > (bindx - NN); m--) {
                        assert_array_dim(m, FFT_HALF);
                        s->NR_Nest[bindx] += s->NR_G[m];
                    }
                    s->NR_Nest[bindx] /= (f32_t) NN;
                }
                // end of edge treatment

                for (int bindx = VAD_low + NN / 2; bindx < VAD_high - NN / 2; bindx++) {
                    assert_array_dim(bindx, FFT_HALF);
                    s->NR_G[bindx] = s->NR_Nest[bindx];
                }

            }   // end of "if s->first_time == 3"
            */
                    
                for bindx in vad_low + nn / 2..vad_high - nn / 2 {
                    //assert_array_dim!(bindx, FFT_HALF);
                    self.nr_nest[bindx] = 0.0;
                    for m in bindx - nn / 2..=bindx + nn / 2 {
                        //assert_array_dim!(m, FFT_HALF);
                        self.nr_nest[bindx] += self.nr_g[m];
                    }
                    self.nr_nest[bindx] /= nn as f32;
                }

                // and now the edges - only going NN steps forward and taking the average lower edge
                for bindx in vad_low..vad_low + nn / 2 {
                    //assert_array_dim!(bindx, FFT_HALF);
                    self.nr_nest[bindx] = 0.0;
                    for m in bindx..bindx + nn {
                        //assert_array_dim!(m, FFT_HALF);
                        self.nr_nest[bindx] += self.nr_g[m];
                    }
                    self.nr_nest[bindx] /= nn as f32;
                }

                // upper edge - only going NN steps backward and taking the average
                for bindx in vad_high - nn..vad_high {
                    //assert_array_dim!(bindx, FFT_HALF);
                    self.nr_nest[bindx] = 0.0;
                    for m in (bindx - nn + 1..bindx + 1).rev() {
                        //assert_array_dim!(m, FFT_HALF);
                        self.nr_nest[bindx] += self.nr_g[m];
                    }
                    self.nr_nest[bindx] /= nn as f32;
                }
                // end of edge treatment

                for bindx in vad_low + nn / 2..vad_high - nn / 2 {
                    //assert_array_dim!(bindx, FFT_HALF);
                    self.nr_g[bindx] = self.nr_nest[bindx];
                }

            } 
            /*
            // end of "if s.first_time == 3"
            // FINAL SPECTRAL WEIGHTING: Multiply current FFT results with FFT_buffer for all bins with the bin-specific gain factors G
            // only do this for the bins inside the filter passband
            // if you do this for all the bins you will get distorted audio

            //for (int bindx = 0; bindx < FFT_HALF; bindx++) {
            for (int bindx = VAD_low; bindx < VAD_high; bindx++) {
                s->FFT_buffer[bindx].re = s->FFT_buffer [bindx].re * s->NR_G[bindx];
                s->FFT_buffer[bindx].im = s->FFT_buffer [bindx].im * s->NR_G[bindx];

                // make conjugate symmetric
                ai = FFT_FULL - bindx - 1;
                assert_array_dim(ai, FFT_FULL);
                s->FFT_buffer[ai].re = s->FFT_buffer[ai].re * s->NR_G[bindx];
                s->FFT_buffer[ai].im = s->FFT_buffer[ai].im * s->NR_G[bindx];
            }

            // perform iFFT (in-place)
            arm_cfft_f32(NR_iFFT, (TYPEREAL*) s->FFT_buffer, 1, 1);
            */
            for bindx in vad_low..vad_high {
                self.fft_buffer[bindx].re = self.fft_buffer [bindx].re * self.nr_g[bindx];
                self.fft_buffer[bindx].im = self.fft_buffer [bindx].im * self.nr_g[bindx];

                // make conjugate symmetric
                let ai = FFT_FULL - bindx - 1;
                //assert_array_dim!(ai, FFT_FULL);
                self.fft_buffer[ai].re = self.fft_buffer[ai].re * self.nr_g[bindx];
                self.fft_buffer[ai].im = self.fft_buffer[ai].im * self.nr_g[bindx];
            }

            // perform iFFT (in-place)
            self.nr_ifft.process(&mut self.fft_buffer);
            /*
            // perform windowing after iFFT
            for (int i = 0; i < FFT_FULL; i++) {
                s->FFT_buffer[i].re *= sqrtHann_256[i/2];
            }

            // do the overlap & add
            for (int i = 0; i < FFT_HALF; i++) {
                // take real part of first half of current iFFT result and add to 2nd half of last iFFT_result
                outputsamples[i + k * FFT_HALF] = roundf((s->FFT_buffer[i].re + s->last_iFFT_result[i]) * s->final_gain);
            }

            // save 2nd half of iFFT result
            for (int i = 0; i < FFT_HALF; i++) {
                s->last_iFFT_result[i] = s->FFT_buffer[FFT_HALF + i].re;
            }
        }   // end of loop which repeats the FFT_iFFT_chain two times
    }
    */
            for i in 0..FFT_FULL {
                self.fft_buffer[i].re *= SQRT_HANN_256[i/2];
            }

            // do the overlap & add
            for i in 0..FFT_HALF {
                // take real part of first half of current iFFT result and add to 2nd half of last iFFT_result
                buf[i + k * FFT_HALF] = (self.fft_buffer[i].re + self.last_ifft_result[i]) * self.final_gain;
            }

            // save 2nd half of iFFT result
            for i in 0..FFT_HALF {
                self.last_ifft_result[i] = self.fft_buffer[FFT_HALF + i].re;
            }
        }   // end of loop which repeats the FFT_iFFT_chain two times
    }
}
