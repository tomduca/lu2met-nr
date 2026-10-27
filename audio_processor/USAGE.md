# Usage Guide

## Start

From `audio_processor/`, run the native desktop interface:

```bash
./run_qt_gui.sh
```

To use the browser interface:

```bash
./run_web.sh
```

The browser interface is served locally at `http://localhost:5001`.

## Audio Routing

1. Select the radio or virtual capture device as the input.
2. Select headphones or speakers as the output.
3. The processor opens one or two input channels, downmixes them to mono, and copies the mono signal to every output channel.
4. Start the stream and confirm that input and output meters respond.

On macOS, a virtual device such as BlackHole may be used to route receiver audio into the processor. Configure system audio routing in Audio MIDI Setup as required by the receiver and capture setup.

## Controls

- **Mode:** SSB uses the 300-2700 Hz band-pass; CW uses 600-900 Hz.
- **Preset:** Selects the spectral noise-reduction parameters for the chosen mode.
- **DSP Input Trim:** Adjusts the level sent into the filter. It only affects the filtered path and cannot undo clipping that already occurred at the audio device or ADC.
- **Master Output:** Adjusts listening level in both bypass and filtered modes. A soft limiter controls output peaks.
- **Bypass:** Skips band-pass and spectral noise reduction while retaining the master output stage.
- **Mute during TX:** Mutes the output while you transmit and fades it back in afterwards (enabled by default; saved with your settings). The **TX** indicator lights while the output is muted or fading in.

## Transmit Muting

While the radio transmits, its receive audio line goes almost silent. Without muting, the noise-reduction filter adapts to that silence: when reception resumes it treats all band noise as signal, and for about one second the audio comes out unfiltered and roughly 10 dB louder.

With **Mute during TX** enabled, the application follows the normal receive level and treats a sudden drop of more than 25 dB as transmit. During transmit it mutes the output and stops feeding the filter, so the filter keeps the noise profile it had before transmitting. When the receive level returns, the output stays muted for 150 ms (relay click and receiver AGC recovery) and then fades in over 400 ms.

Detection is relative to the receive level, so it does not depend on the radio volume. Gradual fading (QSB) does not trigger it. If the level stays low for more than three minutes, the application assumes the receiver volume was turned down, accepts the new level, and unmutes. The browser interface applies the same muting and shows **TX MUTE** while active.

The meters show recent RMS and a peak value that holds briefly and then decays. The bar turns amber when the peak passes -6 dBFS and red above -1 dBFS. The **CLIP** indicator next to IN turns red when input clipping is detected; lower the radio/interface output before capture. The **LIMIT** indicator next to OUT turns red when the output soft limiter has engaged. Both indicators stay latched until the stream is stopped and started again.

## Input Level Calibration

Many USB audio interfaces, including common Realtek USB adapters, have a high-gain microphone-level input. A receiver's headphone or speaker output is much hotter, so the interface clips at its ADC long before the receiver volume reaches its maximum. Some of these interfaces then apply their macOS input volume digitally, after the ADC. In that case clipped peaks appear below 0 dBFS: with the input volume at -7.5 dB in Audio MIDI Setup, a clipped signal tops out at about -7.5 dBFS in the application.

The CLIP indicator detects both full-scale samples and flat-topped runs at the channel peak, so it also catches clipping that the interface has scaled down. Another sign of upstream clipping or heavy compression is a small gap between the peak and RMS readings: clean SSB speech typically shows 12-18 dB, HF band noise about 10-12 dB, and a gap near 5 dB means the peaks are being flattened before capture.

To set the level:

1. Enable **Bypass** and set **Master Output** to 0 dB.
2. Raise the receiver volume until CLIP turns red, then lower it until the audio sounds clean.
3. Press **Stop** and **Start** to clear the indicator and confirm it stays grey. Aim for roughly -20 dBFS RMS with peaks between -12 and -6 dBFS.
4. Recover the listening level with **Master Output**, which applies to both bypass and filtered audio.

A clean setting may require a very low receiver volume; this is expected with a microphone-level input. A fixed-level line, ACC, or DATA output on the receiver, or an attenuator before the interface, allows a higher receiver setting. Audio isolation transformers on the input and output lines prevent ground-loop hum but do not by themselves reduce the level enough for a microphone input.

## Updates

When a newer version is published, a banner at the top of the window shows its number and a **Download** link. Select **✕** to hide it until the next version.

## Recording

Start audio processing before recording. Recordings are written as mono WAV and converted to MP3 when the optional MP3 encoder dependencies are available. Recording writes happen on a background thread with a bounded queue; if the queue fills, dropped blocks are reported.

## Troubleshooting

- **No input signal:** Run `python list_devices.py`, check input permissions, and verify the radio's routing to the selected capture device.
- **No output:** Check the selected output device and the system output level.
- **Clipped input or distorted bypass audio:** Reduce the level before the computer's audio input; see [Input Level Calibration](#input-level-calibration). The DSP trim is downstream and cannot repair ADC clipping.
- **Uneven level between bypass and filtering:** Adjust Master Output to a comfortable listening level; the filter path may have a different average level from bypass.

For attribution and dependency notices, see [THIRD_PARTY.md](../THIRD_PARTY.md).
