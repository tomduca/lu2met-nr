# Current Architecture Summary

LU2MET NR Filter provides live HF audio processing through a Python audio-I/O layer and a Rust spectral noise-reduction extension.

## Processing Path

1. `sounddevice` captures audio at 48 kHz.
2. Input with one or two channels is converted to mono.
3. In filtered mode, the selected SSB/CW band-pass runs before the Rust spectral noise-reduction filter.
4. Master output gain and a soft limiter apply in both bypass and filtered modes.
5. Mono audio is copied to every selected output channel.

The configured callback block is 2048 frames, about 42.7 ms at 48 kHz. End-to-end latency depends on device and host buffers.

## Main Components

- `audio_processor/lu2met_nr_gui.py` — desktop interface and audio callback.
- `audio_processor/audio_pipeline.py` — shared mono conversion, gain mapping, meters, and asynchronous recording.
- `spectral_nr/` — PyO3 extension wrapping the Rust spectral filter.

Launch commands and controls are documented in [audio_processor/USAGE.md](audio_processor/USAGE.md).

## DSP Attribution

The spectral noise-reduction implementation is adapted from NovaSDR's [`src/spectralnoisereduction.rs`](https://github.com/Steven9101/novasdr-wasm/blob/main/src/spectralnoisereduction.rs). See [THIRD_PARTY.md](THIRD_PARTY.md) for direct dependencies and license notices.
