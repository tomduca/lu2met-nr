# Audio Processor

The LU2MET NR Filter processes live HF receiver audio through a Python audio-I/O pipeline and a Rust spectral noise-reduction extension.

## Run

From this directory:

```bash
./run_qt_gui.sh
```

## Signal Path

- Input is captured at 48 kHz and converted to mono. A multichannel device is downmixed before processing.
- The DSP input trim is applied only to the filtered path.
- SSB or CW band-pass filtering (SciPy) is followed by spectral noise reduction in the Rust extension.
- The master output level and soft limiter are shared by bypass and filtered audio.
- Mono output is copied to every selected output channel.
- The meters show recent RMS and a decaying peak hold. Input-clipping and soft-limiter warnings remain latched until the stream is restarted.
- Recording data is sent to a bounded queue and written by a background thread.

## Files

- `lu2met_nr_gui.py` — PyQt5 interface and audio callback.
- `audio_pipeline.py` — channel, gain, meter, transmit-muting, and recording helpers.
- `update_check.py` — app version and new-release check.

## DSP Source and Dependencies

The Rust spectral noise-reduction implementation is adapted from the novasdr-wasm project. See the repository's [third-party source and license inventory](../THIRD_PARTY.md) for the upstream file, direct dependencies, and included license notices.
