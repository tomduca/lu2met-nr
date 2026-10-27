# Third-Party Sources and Notices

This document identifies the external source code and direct dependencies used by the LU2MET NR Filter. License texts and notices are included in the repository where indicated. Check the license attached to each upstream component before redistributing a modified or packaged build.

## Adapted DSP Source

- **Spectral noise reduction algorithm:** adapted in [`spectral_nr/src/spectralnoisereduction.rs`](spectral_nr/src/spectralnoisereduction.rs) from [Steven9101/novasdr-wasm `src/spectralnoisereduction.rs`](https://github.com/Steven9101/novasdr-wasm/blob/main/src/spectralnoisereduction.rs).
- The upstream repository includes GPL-3.0, Apache-2.0, and MIT license texts. Copies of those texts and the upstream `NOTICE` are kept in [`third_party/novasdr-wasm/`](third_party/novasdr-wasm/) and are included in packaged builds under `licenses/`. The upstream `NOTICE` states that the repository as a whole is distributed under GPL-3.0-only. This project is distributed under GPL-3.0-only; see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

## Direct Runtime Dependencies

### Python

- **sounddevice** — audio device enumeration and PortAudio streams (`audio_processor/requirements.txt`).
- **NumPy** — audio buffers and numerical operations (`audio_processor/requirements.txt`).
- **SciPy** — Butterworth band-pass filter design and streaming filtering (`audio_processor/requirements.txt`).
- **PyQt5** — native desktop interface, used under the GNU GPL v3; bundled in packaged builds.
- **pydub** — optional MP3 export; WAV recording remains available without it.
- **spectral_nr** — this repository's Rust extension, imported by both audio frontends when available.

### Rust Extension

The Rust binding and spectral filter are in `spectral_nr/`:

- **PyO3** — Python extension bindings.
- **rust-numpy** — NumPy array interoperability.
- **rustfft** — FFT/IFFT operations used by spectral noise reduction.

Versions are declared in [`spectral_nr/Cargo.toml`](spectral_nr/Cargo.toml). The complete transitive dependency/license inventory has not been generated; review it when preparing release builds.

## Project Source

- [LU2MET NR Filter repository](https://github.com/tomduca/lu2met-nr)
