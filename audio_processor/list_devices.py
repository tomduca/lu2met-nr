#!/usr/bin/env python3
"""List audio devices available to sounddevice."""
import sounddevice as sd

print("\n" + "="*60)
print("  AVAILABLE AUDIO DEVICES")
print("="*60 + "\n")

try:
    devices = sd.query_devices()
    print(devices)
    print("\n" + "="*60)
    print("  DEVICE SELECTION")
    print("="*60 + "\n")
    print("Select a device with input channels for capture and a device with output channels for playback.")
    print("\n")
except Exception as e:
    print(f"Error querying audio devices: {e}")
    print("\nPossible causes:")
    print("1. macOS may require microphone permission")
    print("   Open System Settings → Privacy & Security → Microphone")
    print("   Allow access for Terminal or your IDE")
    print("\n2. sounddevice may need to be reinstalled")
    print("   Run: pip install --force-reinstall sounddevice")
    print()
