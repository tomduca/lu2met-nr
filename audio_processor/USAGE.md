# Usage Guide

## Start

Open the app downloaded from [Releases](https://github.com/tomduca/lu2met-nr/releases) (see [BUILD.md](../BUILD.md#first-launch) for the first launch), or run it from source in `audio_processor/`:

```bash
./run_qt_gui.sh
```

## Audio Routing

1. Select the radio or virtual capture device as the input.
2. Select headphones or speakers as the output.
3. The processor opens one or two input channels, downmixes them to mono, and copies the mono signal to every output channel.
4. Start the stream and confirm that input and output meters respond.

On macOS, a virtual device such as BlackHole may be used to route receiver audio into the processor. Configure system audio routing in Audio MIDI Setup as required by the receiver and capture setup.

## Windows Setup

### When a virtual cable is needed

- **Radio through a USB audio interface:** no virtual cable. Input is the interface (for example `Microphone (USB Audio CODEC)`), output is your headphones or speakers.
- **Receiver running on the PC** (WebSDR in a browser, SDR software): install [VB-CABLE](https://vb-audio.com/Cable/) so the receiver's audio can reach the processor.
- **Sending the filtered audio to another program** (decoder, recorder): use VB-CABLE on the output side instead. A single cable can carry only one of these paths; a second path needs a second virtual cable.

### VB-CABLE names

VB-CABLE creates two endpoints, and the names are counterintuitive:

| Endpoint | Windows tab | Role |
| --- | --- | --- |
| **CABLE Input** | Playback | Programs *send* audio here |
| **CABLE Output** | Recording | Programs *read* that same audio here |

### Receiver on the PC → processor → speakers

1. Install VB-CABLE (run `VBCABLE_Setup_x64.exe` as administrator) and restart Windows.
2. Installing may make **CABLE Input** the default playback device, which silences the PC speakers. In **Settings → System → Sound**, set the output back to your speakers.
3. Route only the receiver to the cable: **Settings → System → Sound → Volume mixer** (Windows 11) or **App volume and device preferences** (Windows 10), and set the browser or SDR program output to **CABLE Input**. Alternatively, select CABLE Input in the SDR program's own audio settings. The receiver must be playing for the device to appear in the mixer.
4. Set both cable endpoints to 48 kHz. Open the classic **Sound** control panel (`mmsys.cpl`):
   - **Playback** tab → **CABLE Input** → Properties → Advanced → `2 channel, 16 bit, 48000 Hz`;
   - **Recording** tab → **CABLE Output** → Properties → Advanced → `2 channel, 16 bit, 48000 Hz`.

   Do the same for the headphones or speakers if possible.
5. Also in the Recording tab, CABLE Output → Properties → **Listen**: leave **Listen to this device** unchecked, otherwise the unfiltered audio plays under the filtered audio.
6. Allow microphone access for desktop apps: **Settings → Privacy & security → Microphone** → enable **Microphone access** and **Let desktop apps access your microphone**. Without this, every input, including the cable, delivers silence.
7. In the processor: Input **CABLE Output [WASAPI]**, Output **your headphones or speakers [WASAPI]**. Press Start and check that the IN meter moves.

### Device tags: [WASAPI] and [MME]

Windows exposes each device once per audio system. The device lists show two of them, tagged after the name, with WASAPI first:

- **[WASAPI]**: full device names and lower latency. The application lets Windows convert the sample rate, so it also works with devices that are not set to 48 kHz. Use these entries by default.
- **[MME]**: the older system. Names are cut to 31 characters, for example `CABLE Output (VB-Audio Virtual`. Use it if a WASAPI entry fails to start.

Choose the input and output with the **same tag**. If the tags differ, Start shows an error instead of opening the stream. A device saved by an earlier version, which showed numbered entries without tags, is selected again automatically.

### Windows troubleshooting

- **IN meter does not move:** check microphone privacy (step 6), that the receiver is actually routed to CABLE Input (step 3), and that its volume is not muted.
- **No sound from the PC after installing VB-CABLE:** the default output was changed to CABLE Input (step 2).
- **Echo or unfiltered audio mixed in:** "Listen to this device" is enabled on CABLE Output, or the receiver is also playing to the speakers.
- **Crackles or dropouts:** set the devices to 48000 Hz (step 4), try the [MME] entries, and close other audio programs that hold the device in exclusive mode.

## Controls

- **Mode:** SSB uses the 300-2700 Hz band-pass; CW uses 600-900 Hz.
- **LU2MET NR / NR2 (OM-LSA):** the two noise-reduction filters. Either, both, or neither can be enabled; see [Noise Reduction Filters](#noise-reduction-filters).
- **Preset:** Selects the parameters of LU2MET NR for the chosen mode. Disabled while LU2MET NR is off.
- **DSP Input Trim:** Adjusts the level sent into the filter. It only affects the filtered path and cannot undo clipping that already occurred at the audio device or ADC.
- **Master Output:** Adjusts listening level in both bypass and filtered modes. A soft limiter controls output peaks.
- **Bypass:** Skips band-pass and spectral noise reduction while retaining the master output stage.
- **Mute during TX:** Mutes the output while you transmit and fades it back in afterwards (enabled by default; saved with your settings). The **TX** indicator lights while the output is muted or fading in.

## Noise Reduction Filters

- **LU2MET NR** (default): spectral noise reduction with four presets per mode.
- **NR2 (OM-LSA)** (experimental): optimally modified log-spectral amplitude estimator with IMCRA noise tracking, written from the published papers by I. Cohen. It has no settings. It follows changing noise (QRN, local noise) more closely, adds about 32 ms of delay, and needs about 2.5 s to learn the noise after it is enabled or the stream starts.
- **Both:** NR2 runs after LU2MET NR. Two filters of the same family in series usually remove more speech along with the noise, so compare it against each filter alone.
- **Neither:** only the band-pass filter is applied.

NR2 alone is lowered 5 dB so that switching filters does not change the listening level much.

## Transmit Muting

While the radio transmits, its receive audio line goes almost silent. Without muting, the noise-reduction filter adapts to that silence: when reception resumes it treats all band noise as signal, and for about one second the audio comes out unfiltered and roughly 10 dB louder.

With **Mute during TX** enabled, the application follows the normal receive level and treats a sudden drop of more than 25 dB as transmit. During transmit it mutes the output and stops feeding the filter, so the filter keeps the noise profile it had before transmitting. When the receive level returns, the output stays muted for 150 ms (relay click and receiver AGC recovery) and then fades in over 400 ms.

Detection is relative to the receive level, so it does not depend on the radio volume. Gradual fading (QSB) does not trigger it. If the level stays low for more than three minutes, the application assumes the receiver volume was turned down, accepts the new level, and unmutes.

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
