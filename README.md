# LU2MET NR Filter

A local, live HF audio processor with a native PyQt5 desktop interface, distributed as packaged apps for macOS and Windows. Audio capture and playback use `sounddevice`; spectral noise reduction is provided by a Rust extension.

## Run

Download the app for your platform from [Releases](https://github.com/tomduca/lu2met-nr/releases), or run it from source at the repository root:

```bash
./audio_processor/run_qt_gui.sh
```

See [INSTALL.md](INSTALL.md) for development setup, [BUILD.md](BUILD.md) for platform packaging instructions, and [audio_processor/USAGE.md](audio_processor/USAGE.md) for using the application.

## Audio Path

- Audio is captured at 48 kHz and normalized to mono before bypass or processing. Mono is copied to every selected output channel.
- The DSP input trim affects only the filtered path. Master Output applies to both bypass and filtered audio.
- The filtered path applies an SSB or CW band-pass filter, followed by spectral noise reduction.
- A shared soft limiter controls output peaks. It cannot repair clipping that occurred before the application received the signal.
- Live meters show recent RMS and a decaying peak hold. Input clipping detection also catches flat-topped peaks below 0 dBFS, which occur when an interface clips at its ADC and then scales the signal down. Input clipping and limiter warnings remain latched until the stream is restarted. See [Input Level Calibration](audio_processor/USAGE.md#input-level-calibration) for setting the receiver level.
- Transmit muting detects the near-silent receive line during TX, mutes the output, freezes the noise-reduction estimate, and fades back in afterwards. See [Transmit Muting](audio_processor/USAGE.md#transmit-muting).
- Recording uses a bounded queue and a background writer so file I/O and encoding stay out of the audio callback.

The configured block size is 2048 frames at 48 kHz (about 42.7 ms per block). Actual end-to-end latency depends on the selected devices and their host buffers; verify it on the target setup.

## Repository Layout

- `audio_processor/lu2met_nr_gui.py` — PyQt5 interface and audio callback.
- `audio_processor/audio_pipeline.py` — shared channel, gain, meter, and recording helpers.
- `spectral_nr/` — PyO3 Rust extension with the spectral noise-reduction implementation.

## Source Attribution

The spectral noise-reduction implementation in [`spectral_nr/src/spectralnoisereduction.rs`](spectral_nr/src/spectralnoisereduction.rs) is adapted from [NovaSDR's upstream `src/spectralnoisereduction.rs`](https://github.com/Steven9101/novasdr-wasm/blob/main/src/spectralnoisereduction.rs). See [THIRD_PARTY.md](THIRD_PARTY.md) for direct dependencies, related source trees, and bundled license notices.

## License

Copyright (c) 2024-2026 Tomás Duca (LU2MET).

Licensed under the GNU General Public License v3.0 only (GPL-3.0-only); see [`LICENSE`](LICENSE) for the full text and [`NOTICE`](NOTICE) for copyright and attribution. GPL-3.0 applies because the spectral filter is adapted from GPL-3.0-only code and the application bundles PyQt5 under the GPL.
