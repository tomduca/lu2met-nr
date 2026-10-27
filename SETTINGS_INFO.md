# Persistent Settings

The **LU2MET NR Filter** automatically saves your preferences.

## Saved Settings

The following settings are saved when the application closes:

- **Audio devices** (selected input and output)
- **Mode** (SSB or CW)
- **Preset** (Moderate, Aggressive, Ultra, Extreme)
- **DSP input trim** (1-100% slider range)
- **Master output** (10-400% slider range)
- **Bypass** (enabled/disabled)

## Storage Locations

### Windows
Settings are stored in the **Windows Registry**:
```
HKEY_CURRENT_USER\Software\LU2MET\LU2MET_NR_Filter
```

You can view or edit them with `regedit` if needed.

### macOS
Settings are stored in:
```
~/Library/Preferences/com.lu2met.LU2MET_NR_Filter.plist
```

### Linux
Settings are stored in:
```
~/.config/LU2MET/LU2MET_NR_Filter.conf
```

## Behavior

1. **On launch:** The last saved settings are loaded automatically.
2. **On close:** The current settings are saved automatically.
3. **Earlier versions:** Releases before the rename stored settings under `NovaSDR_NR_Filter` instead of `LU2MET_NR_Filter`. On the first launch of a newer version, those settings are copied to the new location automatically; the old entry is left in place and can be deleted.
4. **First launch:** Default values are used (Extreme preset, approximately -26 dB DSP input trim, 0 dB master output).

## Reset Settings

To restore the defaults, remove the settings for your platform:

### Windows
```powershell
reg delete "HKEY_CURRENT_USER\Software\LU2MET\LU2MET_NR_Filter" /f
```

### macOS
```bash
rm ~/Library/Preferences/com.lu2met.LU2MET_NR_Filter.plist
```

### Linux
```bash
rm ~/.config/LU2MET/LU2MET_NR_Filter.conf
```

## Notes

- Settings are **per user**; each Windows or macOS account has its own values.
- Settings **persist** across application reinstalls.
- The application attempts to reuse the previously selected devices if they are available.
- If a saved device is unavailable, select another device in the application.

## Default Values

When no settings have been saved, or after resetting:

```
Mode: SSB
Preset: Extreme
DSP Input Trim: approximately -26 dB
Master Output: 0 dB
Bypass: Off
Input Device: System default
Output Device: System default
```

---

Settings are managed with the cross-platform `QSettings` API from PyQt5.
