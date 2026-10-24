# LU2MET NR Filter - GUI Options

This document describes the two available GUI options for the LU2MET NR Filter and how to use and distribute them.

## 📱 Option 1: Native Desktop Application (PyQt5) - **RECOMMENDED**

### Description
True native desktop application using PyQt5. No browser required, runs as a standalone macOS/Windows application.

### Advantages
- ✅ **Native experience** - Real desktop application
- ✅ **Clean shutdown** - Closes properly when window is closed
- ✅ **No browser dependency** - Runs independently
- ✅ **Professional appearance** - Native OS controls and theme
- ✅ **Faster** - No HTTP/Flask overhead
- ✅ **Easier to distribute** - Single .app or .exe file

### Disadvantages
- ⚠️ Requires PyQt5 installation (included in build)
- ⚠️ Larger file size (~150-200 MB when compiled)

### Running in Development

```bash
cd audio_processor
./run_qt_gui.sh
```

### Building Standalone Application

#### macOS (.app bundle)

```bash
cd audio_processor
./build_macos.sh
```

**Output:** `dist/LU2MET NR Filter.app`

**To run:**
```bash
open "dist/LU2MET NR Filter.app"
```

**To distribute:**
1. Compress: `zip -r LU2MET_NR-macOS.zip "dist/LU2MET NR Filter.app"`
2. Share the .zip file
3. Users extract and drag to Applications folder

#### Windows (.exe)

**Note:** Must be built on Windows machine

```batch
cd audio_processor
build_windows.bat
```

**Output:** `dist\LU2MET NR Filter.exe`

**To distribute:**
- Share the .exe file directly
- Users can run without Python installation

### Installation for End Users

**macOS:**
1. Download and extract `LU2MET_NR-macOS.zip`
2. Drag `LU2MET NR Filter.app` to Applications folder
3. Right-click → Open (first time only, to bypass Gatekeeper)
4. Install BlackHole 2ch virtual audio device
5. Configure Multi-Output Device in Audio MIDI Setup
6. Run the application

**Windows:**
1. Download `LU2MET NR Filter.exe`
2. Run the executable
3. If Windows Defender warns, click "More info" → "Run anyway"
4. Install VB-Cable or similar virtual audio device
5. Configure audio routing
6. Use the application

### Features
- Device selection (input/output)
- Mode selector (SSB/CW)
- Preset selection (Moderate, Aggressive, Ultra, Extreme)
- Bypass toggle
- Audio recording (MP3/WAV)
- Real-time log display
- Parameter information
- Dark theme

---

## 🌐 Option 2: Web Interface (Flask)

### Description
Browser-based interface using Flask web server. Opens in Chrome app mode for a native-like experience.

### Advantages
- ✅ **Modern UI** - HTML/CSS based, easy to customize
- ✅ **Cross-platform** - Same code for all platforms
- ✅ **Easy updates** - Just edit HTML/CSS
- ✅ **Familiar** - Web technologies

### Disadvantages
- ⚠️ Requires browser (Chrome recommended)
- ⚠️ Flask server runs in background
- ⚠️ More complex shutdown handling
- ⚠️ Slightly higher resource usage

### Running in Development

```bash
cd audio_processor
./run_web.sh
# Open browser at http://localhost:5001
```

Or use the app wrapper (opens browser automatically):

```bash
cd audio_processor
./run_app.sh
```

### Building Standalone Application

The web version can also be packaged as a standalone app that starts Flask and opens the browser automatically.

#### macOS

```bash
cd audio_processor
# Edit build_macos.sh to use web_launcher.py instead of lu2met_nr_gui.py
./build_macos.sh
```

**Output:** `dist/LU2MET NR Filter.app`

The app will:
1. Start Flask server on localhost:5001
2. Open Chrome in app mode (no address bar)
3. Display the web interface

#### Windows

```batch
cd audio_processor
REM Edit build_windows.bat to use web_launcher.py
build_windows.bat
```

### Features
- All features of native app
- Additional: Better visual design with gradients and modern styling
- Responsive layout

### Stopping the Application

**Issue:** Closing the browser window may leave Flask running in background.

**Solutions:**
1. Press Ctrl+C in the terminal where it's running
2. Use Activity Monitor (macOS) or Task Manager (Windows) to kill the process
3. The standalone .app version attempts to detect window closure (experimental)

---

## 🔄 Comparison Table

| Feature | Native App (PyQt5) | Web Interface (Flask) |
|---------|-------------------|----------------------|
| **Browser Required** | ❌ No | ✅ Yes (Chrome recommended) |
| **Clean Shutdown** | ✅ Perfect | ⚠️ Manual/Experimental |
| **File Size** | ~150-200 MB | ~100-150 MB |
| **Startup Speed** | ⚡ Fast | 🐌 Slower (Flask startup) |
| **UI Customization** | 🔧 PyQt code | 🎨 HTML/CSS (easier) |
| **Resource Usage** | 💚 Lower | 💛 Higher (Flask + Browser) |
| **Distribution** | ✅ Single file | ✅ Single file |
| **User Experience** | ⭐⭐⭐⭐⭐ Native | ⭐⭐⭐⭐ Web-like |

---

## 📋 Build Requirements

### Common Requirements
- Python 3.10+
- Virtual environment with dependencies installed
- `spectral_nr` Rust module compiled (`maturin develop --release`)

### Native App Additional Requirements
- PyQt5: `pip install PyQt5`

### Web App Additional Requirements
- Flask: `pip install flask`
- pydub: `pip install pydub` (for MP3 recording)
- ffmpeg: `brew install ffmpeg` (macOS) or download for Windows

### Build Tool
- PyInstaller: `pip install pyinstaller` (installed automatically by build scripts)

---

## 🚀 Recommended Workflow

### For Development
Use **Native App** (`./run_qt_gui.sh`) for:
- Faster iteration
- Better debugging
- Clean shutdown

Use **Web Interface** (`./run_web.sh`) for:
- UI design work
- Testing responsive layouts
- Quick CSS changes

### For Distribution
**Recommended:** Native App (PyQt5)
- Better user experience
- Cleaner shutdown
- More professional

**Alternative:** Web Interface
- If you prefer web technologies
- If UI customization is priority
- If you're comfortable with Flask

---

## 📦 Distribution Checklist

### Before Building

- [ ] Test all features thoroughly
- [ ] Verify Noise reduction module works
- [ ] Test on clean system (no Python)
- [ ] Check recording functionality
- [ ] Test mode switching (SSB/CW)
- [ ] Verify all presets work

### macOS Distribution

- [ ] Build .app bundle
- [ ] Test on different macOS version (10.14+)
- [ ] (Optional) Code sign with Apple Developer certificate
- [ ] (Optional) Notarize for Gatekeeper
- [ ] Create .zip archive
- [ ] Write installation instructions
- [ ] Test installation on clean Mac

### Windows Distribution

- [ ] Build .exe on Windows machine
- [ ] Test on Windows 10/11
- [ ] (Optional) Code sign with certificate
- [ ] Test antivirus compatibility
- [ ] Create installer (optional, using Inno Setup)
- [ ] Write installation instructions
- [ ] Test installation on clean Windows

---

## 🐛 Troubleshooting

### Native App

**"Module not found" errors:**
- Ensure PyQt5 is installed: `pip install PyQt5`
- Check virtual environment is activated

**App won't start:**
- Check terminal output for errors
- Verify audio devices are available
- Try running with `python3 lu2met_nr_gui.py` directly

**Audio not working:**
- Verify virtual audio device is installed
- Check device selection in app
- Ensure correct input/output devices

### Web Interface

**Browser doesn't open:**
- Manually open http://localhost:5001
- Check if port 5001 is already in use
- Try different browser

**Flask stays running after closing browser:**
- Press Ctrl+C in terminal
- Use Activity Monitor/Task Manager to kill process
- Restart terminal if needed

**Can't record in MP3:**
- Install ffmpeg: `brew install ffmpeg` (macOS)
- Will fallback to WAV if ffmpeg not available

---

## 📚 Files Reference

### Native App (PyQt5)
- **Source:** `audio_processor/lu2met_nr_gui.py`
- **Run script:** `audio_processor/run_qt_gui.sh`
- **Build script:** `audio_processor/build_macos.sh` (set to use lu2met_nr_gui.py)

### Web Interface
- **Source:** `audio_processor/audio_processor_web.py`
- **Run script:** `audio_processor/run_web.sh`
- **App wrapper:** `audio_processor/web_launcher.py`
- **App run script:** `audio_processor/run_app.sh`
- **Build script:** `audio_processor/build_macos.sh` (set to use web_launcher.py)

### Common
- **Recordings:** `audio_processor/recordings/`
- **Dependencies:** `audio_processor/venv/`
- **Rust module:** `spectral_nr/`

---

## 🎯 Quick Start Commands

### Native App
```bash
# Development
./run_qt_gui.sh

# Build for distribution
./build_macos.sh  # Creates dist/LU2MET NR Filter.app
```

### Web Interface
```bash
# Development
./run_web.sh      # Manual browser open
./run_app.sh      # Auto-opens browser

# Build for distribution
# Edit build_macos.sh to use web_launcher.py, then:
./build_macos.sh
```

---

## 📖 Additional Documentation

- **Installation:** See `INSTALL.md`
- **Usage Guide:** See `audio_processor/USAGE.md`
- **Standalone Apps:** See `BUILD.md`
- **Technical Details:** See `SOLUTION_SUMMARY.md`

---

**73 de LU2MET!** 📻
