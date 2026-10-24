# Third-Party Sources and Notices

This document identifies the external source code and direct dependencies used by the LU2MET NR Filter. License texts and notices are included in the repository where indicated. Check the license attached to each upstream component before redistributing a modified or packaged build.

## Adapted DSP Source

- **Spectral noise reduction algorithm:** adapted in [`novasdr_nr_py/src/spectralnoisereduction.rs`](novasdr_nr_py/src/spectralnoisereduction.rs) from [Steven9101/novasdr-wasm `src/spectralnoisereduction.rs`](https://github.com/Steven9101/novasdr-wasm/blob/main/src/spectralnoisereduction.rs).
- The upstream repository includes GPL-3.0, Apache-2.0, and MIT license texts. Copies are present under [`novasdr-wasm/LICENSE`](novasdr-wasm/LICENSE), [`novasdr-wasm/LICENSE-APACHE`](novasdr-wasm/LICENSE-APACHE), and [`novasdr-wasm/LICENSE-MIT`](novasdr-wasm/LICENSE-MIT). The project license and applicable upstream terms are described in [`LICENSE`](LICENSE).

The checked-in [`novasdr-wasm/THIRD_PARTY.md`](novasdr-wasm/THIRD_PARTY.md) documents the separate PhantomSDR decoder-derived code in that subtree; it is not the source attribution for the Python audio processor's spectral filter.

## Direct Runtime Dependencies

### Python

- **sounddevice** — audio device enumeration and PortAudio streams (`audio_processor/requirements.txt`).
- **NumPy** — audio buffers and numerical operations (`audio_processor/requirements.txt`).
- **SciPy** — Butterworth band-pass filter design and streaming filtering (`audio_processor/requirements.txt`).
- **PyQt5** — native desktop interface; installed by the setup/build instructions.
- **Flask** — local browser interface; installed by `audio_processor/run_web.sh`.
- **pydub** — optional MP3 export; WAV recording remains available without it.
- **novasdr_nr** — this repository's Rust extension, imported by both audio frontends when available.

### Rust Extension

The Rust binding and spectral filter are in `novasdr_nr_py/`:

- **PyO3** — Python extension bindings.
- **rust-numpy** — NumPy array interoperability.
- **rustfft** — FFT/IFFT operations used by spectral noise reduction.

Versions are declared in [`novasdr_nr_py/Cargo.toml`](novasdr_nr_py/Cargo.toml). The complete transitive dependency/license inventory has not been generated; review it when preparing release builds.

## Project Source

- [LU2MET NR Filter repository](https://github.com/tomduca/novasdr-audio-processor)
