import unittest

import numpy as np

try:
    import novasdr_nr
except ImportError:
    novasdr_nr = None


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
    processor = novasdr_nr.SpectralNoiseReduction(SAMPLE_RATE, gain, alpha, asnr)
    blocks = np.split(signal, BLOCKS)
    return np.concatenate([processor.process(block) for block in blocks])


@unittest.skipIf(novasdr_nr is None, 'novasdr_nr extension is not installed')
class NovaSdrNrTests(unittest.TestCase):
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
