import unittest

import numpy as np

try:
    import spectral_nr
except ImportError:
    spectral_nr = None


SAMPLE_RATE = 48000
BLOCK_SIZE = 2048
BLOCKS = 40

# (gain, alpha, asnr) for the SSB presets, and the RMS output of the
# reference build (commit ee03043, used for the stable April releases).
SSB_PRESETS = [
    ((1 / 1024, 0.98, 20.0), 0.011291),
    ((1 / 2048, 0.98, 10.0), 0.00581381),
    ((1 / 8192, 0.99, 2.0), 0.00136625),
    ((1 / 16384, 0.99, 1.0), 0.000669876),
]


def test_signal():
    rng = np.random.default_rng(7)
    t = np.arange(BLOCK_SIZE * BLOCKS) / SAMPLE_RATE
    tone = 0.05 * np.sin(2 * np.pi * 700 * t)
    return (tone + rng.normal(0, 0.02, t.size)).astype(np.float32)


def run_filter(signal, gain, alpha, asnr):
    processor = spectral_nr.SpectralNoiseReduction(SAMPLE_RATE, gain, alpha, asnr)
    blocks = np.split(signal, BLOCKS)
    return np.concatenate([processor.process(block) for block in blocks])


@unittest.skipIf(spectral_nr is None, 'spectral_nr extension is not installed')
class SpectralNrTests(unittest.TestCase):
    def test_output_length_matches_input(self):
        signal = test_signal()
        output = run_filter(signal, *SSB_PRESETS[0][0])
        self.assertEqual(output.shape, signal.shape)

    def test_output_matches_reference_build(self):
        signal = test_signal()
        for params, expected_rms in SSB_PRESETS:
            with self.subTest(gain=params[0]):
                output = run_filter(signal, *params)[BLOCK_SIZE:]
                rms = float(np.sqrt(np.mean(output.astype(np.float64) ** 2)))
                self.assertAlmostEqual(rms, expected_rms, delta=expected_rms * 0.01)

    def test_every_sample_is_scaled_by_preset_gain(self):
        # A regression once wrote both FFT halves to the first half of the
        # buffer, leaving every second half as unfiltered, unscaled input.
        signal = test_signal()
        low = run_filter(signal, 1 / 16384, 0.99, 1.0)[BLOCK_SIZE:]
        self.assertLess(float(np.max(np.abs(low))), 0.01)


def keyed_tone_in_noise(seconds=6, snr_db=0.0):
    """700 Hz tone keyed 200 ms on / 300 ms off in white noise, plus the key."""
    rng = np.random.default_rng(3)
    t = np.arange(SAMPLE_RATE * seconds) / SAMPLE_RATE
    key = (t % 0.5) < 0.2
    tone = np.sin(2 * np.pi * 700 * t) * key
    noise = rng.normal(0, 1, t.size)
    noise *= np.sqrt(0.5) / 10 ** (snr_db / 20)  # tone RMS while keyed is sqrt(0.5)
    return (0.05 * (tone + noise)).astype(np.float32), key


def run_nr2(signal, block_size=BLOCK_SIZE):
    processor = spectral_nr.OmlsaNoiseReduction(SAMPLE_RATE)
    blocks = [signal[i:i + block_size] for i in range(0, signal.size, block_size)]
    return np.concatenate([processor.process(block) for block in blocks]), processor.latency


@unittest.skipIf(spectral_nr is None, 'spectral_nr extension is not installed')
class OmlsaNr2Tests(unittest.TestCase):
    def test_output_length_matches_input_for_any_block_size(self):
        signal = test_signal()
        for block_size in (2048, 1000, 333):
            with self.subTest(block_size=block_size):
                output, _ = run_nr2(signal, block_size)
                self.assertEqual(output.shape, signal.shape)

    def test_output_does_not_depend_on_block_size(self):
        signal = test_signal()
        reference, _ = run_nr2(signal, 2048)
        output, _ = run_nr2(signal, 333)
        np.testing.assert_allclose(output, reference, atol=1e-7)

    def test_latency_is_one_32_ms_frame(self):
        processor = spectral_nr.OmlsaNoiseReduction(SAMPLE_RATE)
        self.assertEqual(processor.latency, 1536)

    def test_stationary_noise_is_attenuated(self):
        # The minimum tracking needs about 2.5 s to settle; after that white
        # noise is about 15 dB lower (the residual is OM-LSA musical noise).
        noise = np.random.default_rng(5).normal(0, 0.05, SAMPLE_RATE * 6).astype(np.float32)
        output, _ = run_nr2(noise)
        settled = slice(SAMPLE_RATE * 4, None)
        ratio = np.std(output[settled]) / np.std(noise[settled])
        self.assertLess(ratio, 0.25)

    def test_keyed_tone_snr_improves(self):
        signal, key = keyed_tone_in_noise()
        output, latency = run_nr2(signal)
        aligned = output[latency:]
        key = key[:aligned.size]
        settled = np.arange(aligned.size) > SAMPLE_RATE * 2
        on = np.mean(aligned[key & settled] ** 2)
        off = np.mean(aligned[~key & settled] ** 2)
        in_on = np.mean(signal[:aligned.size][key & settled] ** 2)
        in_off = np.mean(signal[:aligned.size][~key & settled] ** 2)
        gain_db = 10 * np.log10(on / off) - 10 * np.log10(in_on / in_off)
        self.assertGreater(gain_db, 10.0)

    def test_digital_silence_stays_finite(self):
        output, _ = run_nr2(np.zeros(SAMPLE_RATE, dtype=np.float32))
        self.assertTrue(np.all(np.isfinite(output)))
        self.assertEqual(float(np.max(np.abs(output))), 0.0)
