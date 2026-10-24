from pathlib import Path
from datetime import datetime
import math
import queue
import threading
import time
import wave

import numpy as np


def input_trim_slider_to_gain(value):
    value = min(100.0, max(1.0, float(value)))
    gain_db = -40.0 + ((value - 1.0) / 99.0) * 40.0
    return 10.0 ** (gain_db / 20.0)


def volume_slider_to_gain(value):
    value = min(400.0, max(10.0, float(value)))
    if value <= 100.0:
        return 10.0 ** ((value - 100.0) / 90.0)
    return 10.0 ** (((value - 100.0) / 300.0) * math.log10(4.0))


def peak_dbfs(audio):
    samples = np.asarray(audio)
    if samples.size == 0:
        return -120.0
    peak = float(np.max(np.abs(samples)))
    return 20.0 * math.log10(peak) if peak > 0.0 else -120.0


def input_is_clipped(audio, min_run=4, min_level=0.05):
    """Detect full-scale or flat-topped clipping in any input channel.

    Some interfaces clip at the ADC and then apply their input volume
    digitally, so clipped peaks sit below 0 dBFS. Clipped samples still
    form runs of identical magnitude at the channel peak, which natural
    audio at 48 kHz does not.
    """
    samples = np.asarray(audio, dtype=np.float32)
    if samples.ndim == 1:
        samples = samples[:, np.newaxis]
    for channel in np.abs(samples).T:
        if channel.size == 0:
            continue
        peak = float(channel.max())
        if peak >= 0.999:
            return True
        if peak < min_level:
            continue
        at_peak = np.concatenate(([0], (channel >= peak * (1.0 - 1e-6)).astype(np.int8), [0]))
        edges = np.flatnonzero(np.diff(at_peak))
        if np.any(edges[1::2] - edges[::2] >= min_run):
            return True
    return False


class AudioLevelMeter:
    def __init__(self, smoothing_seconds=0.2, hold_seconds=1.0, decay_db_per_second=18.0):
        self.smoothing_seconds = smoothing_seconds
        self.hold_seconds = hold_seconds
        self.decay_db_per_second = decay_db_per_second
        self._rms_power = None
        self._peak_hold_dbfs = -120.0
        self._hold_until = 0.0
        self._last_update = None
        self._snapshot = (-120.0, -120.0, -120.0)

    @property
    def snapshot(self):
        return self._snapshot

    def reset(self):
        self._rms_power = None
        self._peak_hold_dbfs = -120.0
        self._hold_until = 0.0
        self._last_update = None
        self._snapshot = (-120.0, -120.0, -120.0)

    def update(self, audio, sample_rate, now=None):
        if sample_rate <= 0:
            raise ValueError('Sample rate must be positive')
        samples = np.asarray(audio, dtype=np.float32)
        if samples.size == 0:
            return self._snapshot

        now = time.monotonic() if now is None else now
        duration = samples.shape[0] / sample_rate
        block_power = float(np.vdot(samples, samples).real) / samples.size
        if self._rms_power is None:
            self._rms_power = block_power
        else:
            smoothing = max(self.smoothing_seconds, 1e-6)
            alpha = math.exp(-duration / smoothing)
            self._rms_power = alpha * self._rms_power + (1.0 - alpha) * block_power

        recent_rms_dbfs = (
            10.0 * math.log10(self._rms_power)
            if self._rms_power > 0.0
            else -120.0
        )
        recent_peak_dbfs = peak_dbfs(samples)

        if recent_peak_dbfs >= self._peak_hold_dbfs:
            self._peak_hold_dbfs = recent_peak_dbfs
            self._hold_until = now + self.hold_seconds
        elif now > self._hold_until and self._last_update is not None:
            decay_start = max(self._last_update, self._hold_until)
            elapsed = max(0.0, now - decay_start)
            self._peak_hold_dbfs = max(
                recent_peak_dbfs,
                self._peak_hold_dbfs - self.decay_db_per_second * elapsed,
            )

        self._last_update = now
        self._snapshot = (
            recent_rms_dbfs,
            recent_peak_dbfs,
            self._peak_hold_dbfs,
        )
        return self._snapshot


def soft_limit(audio, threshold=0.85, ceiling=0.98):
    if not 0.0 < threshold < ceiling <= 1.0:
        raise ValueError('Limiter requires 0 < threshold < ceiling <= 1')
    samples = np.asarray(audio, dtype=np.float32)
    limited = samples.copy()
    magnitude = np.abs(limited)
    over_threshold = magnitude > threshold
    if np.any(over_threshold):
        excess = magnitude[over_threshold] - threshold
        compressed = threshold + (ceiling - threshold) * (
            1.0 - np.exp(-excess / (ceiling - threshold))
        )
        limited[over_threshold] = np.copysign(compressed, limited[over_threshold])
    return limited


def apply_master_output(audio, gain):
    pre_limiter = np.asarray(audio, dtype=np.float32) * float(gain)
    limiter_active = bool(
        pre_limiter.size > 0 and float(np.max(np.abs(pre_limiter))) > 0.85
    )
    return soft_limit(pre_limiter), limiter_active


def choose_stream_channels(input_info, output_info):
    input_channels = min(int(input_info['max_input_channels']), 2)
    output_channels = min(int(output_info['max_output_channels']), 2)
    if input_channels < 1 or output_channels < 1:
        raise ValueError('Selected audio devices must support input and output channels')
    return input_channels, output_channels


def to_mono(indata):
    audio = np.asarray(indata, dtype=np.float32)
    if audio.ndim == 1:
        return audio
    if audio.ndim < 2:
        raise ValueError('Audio input must have at least one sample dimension')
    if audio.shape[-1] == 0:
        return np.zeros(audio.shape[0], dtype=np.float32)
    if audio.shape[-1] == 1:
        return audio[..., 0]
    return np.mean(audio, axis=-1, dtype=np.float32)


def write_mono(outdata, audio):
    if outdata.ndim == 1:
        outdata[:] = audio
    elif outdata.ndim == 2:
        outdata[:] = audio[:, np.newaxis]
    else:
        raise ValueError('Audio output must have one or two dimensions')


class BlockConfig:
    def __init__(self, initial):
        self.active = dict(initial)
        self._pending = queue.SimpleQueue()

    def schedule(self, **updates):
        self._pending.put(updates)

    def apply_pending(self):
        while True:
            try:
                self.active.update(self._pending.get_nowait())
            except queue.Empty:
                return self.active


class AsyncMonoRecorder:
    def __init__(self, output_dir, sample_rate, mp3_enabled=False, queue_size=64):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.sample_rate = sample_rate
        self.mp3_enabled = mp3_enabled
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.wav_path = self.output_dir / f'recording_{self.timestamp}.wav'
        self._queue = queue.Queue(maxsize=queue_size)
        self._lock = threading.Lock()
        self._accepting = True
        self._started = False
        self._error = None
        self._conversion_error = None
        self._sample_count = 0
        self._output_path = self.wav_path
        self.dropped_chunks = 0
        self._thread = threading.Thread(target=self._write_loop, daemon=True)

    def start(self):
        self._thread.start()
        self._started = True

    def submit(self, audio):
        with self._lock:
            if not self._accepting:
                return
            chunk = np.array(audio, dtype=np.float32, copy=True)
            try:
                self._queue.put_nowait(chunk)
            except queue.Full:
                self.dropped_chunks += 1

    def stop(self):
        with self._lock:
            self._accepting = False
        if self._started:
            self._queue.put(None)
            self._thread.join()
        if self._error is not None:
            raise RuntimeError(f'Failed to write recording: {self._error}') from self._error

        duration = self._sample_count / self.sample_rate
        return self._output_path, duration, self.dropped_chunks, self._conversion_error

    def _write_loop(self):
        try:
            with wave.open(str(self.wav_path), 'wb') as audio_file:
                audio_file.setnchannels(1)
                audio_file.setsampwidth(2)
                audio_file.setframerate(self.sample_rate)
                while True:
                    chunk = self._queue.get()
                    if chunk is None:
                        break
                    pcm = (np.clip(chunk, -1.0, 1.0) * 32767).astype(np.int16)
                    audio_file.writeframesraw(pcm.tobytes())
                    self._sample_count += len(chunk)
            if self.mp3_enabled and self._sample_count:
                mp3_path = self.wav_path.with_suffix('.mp3')
                try:
                    from pydub import AudioSegment

                    AudioSegment.from_wav(str(self.wav_path)).export(
                        str(mp3_path), format='mp3', bitrate='128k'
                    )
                    self.wav_path.unlink()
                    self._output_path = mp3_path
                except Exception as error:
                    self._conversion_error = str(error)
        except Exception as error:
            self._error = error
            while self._queue.get() is not None:
                pass