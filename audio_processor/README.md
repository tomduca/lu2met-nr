# Audio Processor

The LU2MET NR Filter processes live HF receiver audio through a Python audio-I/O pipeline and a Rust spectral noise-reduction extension.

## Run

From this directory:

```bash
./run_qt_gui.sh
```

To use the browser interface instead:

```bash
./run_web.sh
```

The web interface is served locally on port `5001`.

## Signal Path

- Input is captured at 48 kHz and converted to mono. A multichannel device is downmixed before processing.
- The DSP input trim is applied only to the filtered path.
- SSB or CW band-pass filtering and spectral noise reduction run in the Rust extension.
- The master output level and soft limiter are shared by bypass and filtered audio.
- Mono output is copied to every selected output channel.
- The meters show recent RMS and a decaying peak hold. Input-clipping and soft-limiter warnings remain latched until the stream is restarted.
- Recording data is sent to a bounded queue and written by a background thread.

## Interfaces

- `novasdr_gui_qt.py` provides the native PyQt5 interface.
- `audio_processor_web.py` provides the Flask browser interface.
- `audio_pipeline.py` contains shared channel, gain, meter, and recording helpers.

## DSP Source and Dependencies

The Rust spectral noise-reduction implementation is adapted from NovaSDR. See the repository's [third-party source and license inventory](../THIRD_PARTY.md) for the upstream file, direct dependencies, and included license notices.
