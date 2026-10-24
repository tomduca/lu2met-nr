# Installation Guide

## Prerequisites

- **macOS** (tested on macOS 13+)
- **Python 3.12** (3.9-3.13 also work; 3.14 is not supported by the PyO3 version in use)
- **Rust** (latest stable)
- **Virtual audio device** (BlackHole, Loopback, or similar)

## Step 1: Install System Dependencies

### Install Rust

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
```

### Install BlackHole (Virtual Audio Device)

```bash
brew install blackhole-2ch
```

Or download from: https://existential.audio/blackhole/

## Step 2: Set Up the Python Environment

```bash
cd /Users/tomasduca/CascadeProjects/nr_filter/audio_processor

python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt PyQt5 pydub maturin
```

## Step 3: Build the Rust Module

With the virtual environment still active:

```bash
cd /Users/tomasduca/CascadeProjects/nr_filter/spectral_nr
maturin develop --release
```

This compiles the `spectral_nr` noise-reduction module and installs it into the virtual environment. Verify it:

```bash
python3 -c "import sounddevice, spectral_nr; print('✓ All dependencies installed')"
```

## Step 4: Configure Audio Devices

### Create Multi-Output Device

1. Open **Audio MIDI Setup** (`/Applications/Utilities/Audio MIDI Setup.app`)
2. Click **"+"** → **"Create Multi-Output Device"**
3. Check **ONLY** your virtual audio device (e.g., BlackHole 2ch)
4. **DO NOT** check your output device (headphones/speakers) - this prevents echo

### Set System Output

1. Open **System Settings** → **Sound** → **Output**
2. Select **"Multi-Output Device"**

### Check Devices

```bash
cd /Users/tomasduca/CascadeProjects/nr_filter/audio_processor
source venv/bin/activate
python3 list_devices.py
```

Confirm that your capture device (for example, BlackHole 2ch or the USB audio interface connected to the radio) and your headphones or speakers are listed. Devices are selected in the application window.

## Step 5: Test

```bash
cd /Users/tomasduca/CascadeProjects/nr_filter
./audio_processor/run_qt_gui.sh
```

The terminal should show:
```
✓ Noise reduction module loaded from: ...
```

Select the input and output devices, press **Start**, and confirm that the IN and OUT meters respond.

## Troubleshooting

### "ModuleNotFoundError: No module named 'spectral_nr'"

The Rust module wasn't built. Run:
```bash
cd spectral_nr
maturin develop --release
```

### "No module named 'sounddevice'"

Virtual environment not activated or dependencies not installed:
```bash
cd audio_processor
source venv/bin/activate
pip install sounddevice numpy scipy
```

### "Invalid number of channels"

The selected device does not provide input or output channels. Run `python3 list_devices.py` and select a device with input channels for capture and one with output channels for playback.

### No audio output

1. Verify browser is outputting to Multi-Output Device
2. Verify Multi-Output Device includes virtual audio device
3. Verify the selected devices in the application window
4. Check volume is not muted

## Quick Setup (All Commands)

```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Install BlackHole
brew install blackhole-2ch

# Python environment
cd /Users/tomasduca/CascadeProjects/nr_filter/audio_processor
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt PyQt5 pydub maturin

# Rust module
cd ../spectral_nr
maturin develop --release

# Run
cd ..
./audio_processor/run_qt_gui.sh
```

## Next Steps

- See **`USAGE.md`** for usage instructions
- See **`README.md`** for project overview
- See **`SOLUTION_SUMMARY.md`** for technical details

---

**73 de LU2MET** 📻
