import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from audio_pipeline import (
    AsyncMonoRecorder,
    AudioLevelMeter,
    BlockConfig,
    apply_master_output,
    choose_stream_channels,
    input_is_clipped,
    input_trim_slider_to_gain,
    peak_dbfs,
    soft_limit,
    to_mono,
    volume_slider_to_gain,
    write_mono,
)


class AudioPipelineTests(unittest.TestCase):
    def test_clip_detection_finds_flat_tops_below_full_scale(self):
        t = np.arange(2048) / 48000.0
        clean = np.sin(2 * np.pi * 300 * t).astype(np.float32)
        # ADC clips at full scale, then the device scales by -7.5 dB.
        device_gain = 10 ** (-7.5 / 20)
        clipped = np.clip(clean * 3.0, -1.0, 1.0) * device_gain
        noise = np.random.default_rng(1).normal(0, 0.1, 2048).astype(np.float32)

        self.assertFalse(input_is_clipped(clean * 0.9))
        self.assertFalse(input_is_clipped(noise))
        self.assertFalse(input_is_clipped(np.zeros((2048, 2), dtype=np.float32)))
        self.assertTrue(input_is_clipped(clipped))
        self.assertTrue(input_is_clipped(np.column_stack((clean * 0.5, clipped))))
        self.assertTrue(input_is_clipped(np.full(16, 1.0, dtype=np.float32)))
    def test_block_config_applies_pending_updates_together_at_block_start(self):
        config = BlockConfig({'mode': 'SSB', 'gain': 1.0})
        config.schedule(mode='CW')
        config.schedule(gain=0.5)

        self.assertEqual(config.active, {'mode': 'SSB', 'gain': 1.0})
        active = config.apply_pending()
        self.assertEqual(active, {'mode': 'CW', 'gain': 0.5})

    def test_to_mono_accepts_mono_and_downmixes_multichannel(self):
        mono = np.array([0.25, -0.5], dtype=np.float32)
        dual_mono = np.column_stack((mono, mono))
        stereo = np.array([[1.0, -1.0], [0.5, 0.25]], dtype=np.float32)

        np.testing.assert_array_equal(to_mono(mono), mono)
        np.testing.assert_array_equal(to_mono(dual_mono), mono)
        np.testing.assert_allclose(to_mono(stereo), [0.0, 0.375])

    def test_write_mono_duplicates_to_all_output_channels(self):
        audio = np.array([0.25, -0.5], dtype=np.float32)
        mono_output = np.zeros((2, 1), dtype=np.float32)
        dual_output = np.zeros((2, 2), dtype=np.float32)

        write_mono(mono_output, audio)
        write_mono(dual_output, audio)

        np.testing.assert_array_equal(mono_output[:, 0], audio)
        np.testing.assert_array_equal(dual_output[:, 0], audio)
        np.testing.assert_array_equal(dual_output[:, 1], audio)

    def test_channel_selection_supports_one_or_two_channels(self):
        self.assertEqual(
            choose_stream_channels(
                {'max_input_channels': 1}, {'max_output_channels': 1}
            ),
            (1, 1),
        )

    def test_output_volume_slider_maps_to_documented_gain_range(self):
        self.assertAlmostEqual(volume_slider_to_gain(10), 0.1)
        self.assertAlmostEqual(volume_slider_to_gain(100), 1.0)
        self.assertAlmostEqual(volume_slider_to_gain(400), 4.0)
        self.assertAlmostEqual(volume_slider_to_gain(55), np.sqrt(0.1), delta=0.001)
        self.assertAlmostEqual(volume_slider_to_gain(250), 2.0, delta=0.001)

    def test_input_trim_slider_is_logarithmic_and_attenuation_only(self):
        self.assertAlmostEqual(input_trim_slider_to_gain(1), 0.01)
        self.assertAlmostEqual(input_trim_slider_to_gain(100), 1.0)
        self.assertAlmostEqual(input_trim_slider_to_gain(36), 0.05, delta=0.001)
        self.assertLessEqual(input_trim_slider_to_gain(100), 1.0)

    def test_soft_limiter_preserves_safe_audio_and_controls_peaks(self):
        audio = np.array([-2.0, -0.85, -0.4, 0.4, 0.85, 2.0], dtype=np.float32)
        limited = soft_limit(audio)

        np.testing.assert_array_equal(limited[1:5], audio[1:5])
        self.assertLess(np.max(np.abs(limited)), 0.98)
        self.assertGreater(limited[0], -0.98)
        self.assertLess(limited[-1], 0.98)
        self.assertAlmostEqual(peak_dbfs(np.array([1.0], dtype=np.float32)), 0.0)
        self.assertEqual(peak_dbfs(np.zeros(4, dtype=np.float32)), -120.0)

    def test_master_output_applies_gain_and_reports_soft_limiting(self):
        quiet, quiet_limited = apply_master_output(np.array([0.2]), 0.5)
        loud, loud_limited = apply_master_output(np.array([0.5]), 2.0)

        np.testing.assert_allclose(quiet, [0.1])
        self.assertFalse(quiet_limited)
        self.assertTrue(loud_limited)
        self.assertLess(float(np.max(np.abs(loud))), 0.98)

    def test_meter_reports_recent_rms_and_peak_hold_decay(self):
        meter = AudioLevelMeter(
            smoothing_seconds=0.01,
            hold_seconds=1.0,
            decay_db_per_second=18.0,
        )
        signal = np.full(480, 0.5, dtype=np.float32)
        silence = np.zeros(480, dtype=np.float32)

        first = meter.update(signal, 48000, now=0.0)
        held = meter.update(silence, 48000, now=0.5)
        decayed = meter.update(silence, 48000, now=2.0)

        self.assertAlmostEqual(first[0], 20.0 * np.log10(0.5), delta=0.01)
        self.assertAlmostEqual(first[1], 20.0 * np.log10(0.5), delta=0.01)
        self.assertAlmostEqual(held[2], first[2], delta=0.01)
        self.assertLess(decayed[2], held[2])
        self.assertAlmostEqual(decayed[2], held[2] - 18.0, delta=0.01)
        self.assertEqual(
            choose_stream_channels(
                {'max_input_channels': 8}, {'max_output_channels': 6}
            ),
            (2, 2),
        )

    def test_recorder_writes_bounded_mono_wav_data(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = AsyncMonoRecorder(directory, 48000, queue_size=4)
            recorder.start()
            recorder.submit(np.array([0.25, -0.5], dtype=np.float32))
            recorder.submit(np.array([0.0, 1.0], dtype=np.float32))
            path, duration, dropped_chunks, conversion_error = recorder.stop()

            self.assertEqual(path.suffix, '.wav')
            self.assertEqual(duration, 4 / 48000)
            self.assertEqual(dropped_chunks, 0)
            self.assertIsNone(conversion_error)
            with wave.open(str(path), 'rb') as audio_file:
                self.assertEqual(audio_file.getnchannels(), 1)
                self.assertEqual(audio_file.getnframes(), 4)
            self.assertEqual(Path(path).parent, Path(directory))

    def test_recorder_drops_chunks_when_bounded_queue_is_full(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = AsyncMonoRecorder(directory, 48000, queue_size=1)
            recorder.submit(np.array([0.25, -0.5], dtype=np.float32))
            recorder.submit(np.array([0.0, 1.0], dtype=np.float32))
            recorder.start()
            path, duration, dropped_chunks, conversion_error = recorder.stop()

            self.assertEqual(duration, 2 / 48000)
            self.assertEqual(dropped_chunks, 1)
            self.assertIsNone(conversion_error)
            with wave.open(str(path), 'rb') as audio_file:
                self.assertEqual(audio_file.getnframes(), 2)


if __name__ == '__main__':
    unittest.main()