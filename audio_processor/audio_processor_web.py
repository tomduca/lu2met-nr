#!/usr/bin/env python3
"""
LU2MET NR Filter - Web Interface
Simple web-based interface for device selection, preset control, and bypass toggle
"""

from flask import Flask, render_template_string, jsonify, request
import threading
import sys
import numpy as np
import sounddevice as sd
from scipy import signal
import time
import os
from pathlib import Path

# A Windows console may use a legacy code page that cannot encode ✓ or ✗.
for stream in (sys.stdout, sys.stderr):
    if stream is not None and hasattr(stream, 'reconfigure'):
        stream.reconfigure(errors='backslashreplace')

from audio_pipeline import (
    AsyncMonoRecorder,
    AudioLevelMeter,
    BlockConfig,
    apply_master_output,
    choose_stream_channels,
    input_is_clipped,
    input_trim_slider_to_gain,
    recordings_dir,
    to_mono,
    volume_slider_to_gain,
    write_mono,
)
try:
    from pydub import AudioSegment
    MP3_AVAILABLE = True
except ImportError:
    MP3_AVAILABLE = False

try:
    import spectral_nr
    NR_AVAILABLE = True
except ImportError:
    NR_AVAILABLE = False

app = Flask(__name__)

# Global state
processor_state = {
    'running': False,
    'bypass': False,
    'preset': 'extreme',
    'mode': 'SSB',  # SSB or CW
    'input_device': None,
    'output_device': None,
    'stream': None,
    'nr': None,
    'post_gain': 14.0,
    'input_gain': input_trim_slider_to_gain(36),
    'output_volume': volume_slider_to_gain(100),
    'logs': [],
    'recording': False,
    'recorder': None,
    'bandpass_filter': None,
    'zi_bandpass': None,
    'block_config': None,
    'meters': {
        'input': AudioLevelMeter(),
        'output': AudioLevelMeter(),
        'input_clipping': False,
        'limiter_active': False,
    },
}

# Audio parameters
SAMPLE_RATE = 48000
BLOCK_SIZE = 2048

# Presets for SSB mode
PRESETS_SSB = {
    'moderate': {'gain': 1.0/1024.0, 'alpha': 0.98, 'asnr': 20.0, 'post_gain': 1.5},
    'aggressive': {'gain': 1.0/2048.0, 'alpha': 0.98, 'asnr': 10.0, 'post_gain': 2.5},
    'ultra': {'gain': 1.0/8192.0, 'alpha': 0.99, 'asnr': 2.0, 'post_gain': 10.0},
    'extreme': {'gain': 1.0/16384.0, 'alpha': 0.99, 'asnr': 1.0, 'post_gain': 14.0}
}

# Presets for CW mode (more aggressive, optimized for narrow bandwidth)
PRESETS_CW = {
    'moderate': {'gain': 1.0/2048.0, 'alpha': 0.98, 'asnr': 15.0, 'post_gain': 3.0},
    'aggressive': {'gain': 1.0/4096.0, 'alpha': 0.99, 'asnr': 8.0, 'post_gain': 5.0},
    'ultra': {'gain': 1.0/8192.0, 'alpha': 0.99, 'asnr': 3.0, 'post_gain': 12.0},
    'extreme': {'gain': 1.0/16384.0, 'alpha': 0.995, 'asnr': 1.0, 'post_gain': 18.0}
}

# Bandpass filter configurations
BANDPASS_CONFIG = {
    'SSB': {'low': 300, 'high': 2700},   # Standard SSB bandwidth
    'CW': {'low': 600, 'high': 900}      # Narrow CW filter (300 Hz centered at 750 Hz)
}

processor_state['block_config'] = BlockConfig({
    'bypass': processor_state['bypass'],
    'input_gain': processor_state['input_gain'],
    'output_volume': processor_state['output_volume'],
    'nr': processor_state['nr'],
    'post_gain': processor_state['post_gain'],
    'bandpass_filter': processor_state['bandpass_filter'],
    'zi_bandpass': processor_state['zi_bandpass'],
})

def log(message):
    """Add log message with timestamp"""
    timestamp = time.strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    processor_state['logs'].append(log_entry)
    print(log_entry)

def create_bandpass_filter(mode):
    """Create bandpass filter based on mode (SSB or CW)"""
    config = BANDPASS_CONFIG[mode]
    low_freq = config['low']
    high_freq = config['high']
    
    # Design Butterworth bandpass filter
    nyquist = SAMPLE_RATE / 2
    low_normalized = low_freq / nyquist
    high_normalized = high_freq / nyquist
    
    sos = signal.butter(4, [low_normalized, high_normalized], btype='band', output='sos')
    zi = signal.sosfilt_zi(sos)
    
    return sos, zi

def audio_callback(indata, outdata, frames, time_info, status):
    """Real-time audio processing callback"""
    if status:
        log(f"Audio status: {status}")

    config = processor_state['block_config'].apply_pending()
    meters = processor_state['meters']
    meters['input'].update(indata, SAMPLE_RATE)
    meters['input_clipping'] = meters['input_clipping'] or input_is_clipped(indata)
    audio_data = to_mono(indata)

    if config['bypass'] or not NR_AVAILABLE or config['nr'] is None:
        filtered_audio = audio_data
    else:
        audio_data = audio_data * config['input_gain']
        try:
            if config['bandpass_filter'] is not None:
                filtered_audio, config['zi_bandpass'] = signal.sosfilt(
                    config['bandpass_filter'],
                    audio_data,
                    zi=config['zi_bandpass'],
                )
            else:
                filtered_audio = audio_data
            filtered_audio = config['nr'].process(filtered_audio.astype(np.float32))
            filtered_audio = filtered_audio * config['post_gain']
        except Exception as error:
            log(f"Audio processing error: {error}")
            filtered_audio = audio_data

    filtered_audio, limiter_active = apply_master_output(
        filtered_audio, config['output_volume']
    )
    meters['limiter_active'] = meters['limiter_active'] or limiter_active
    meters['output'].update(filtered_audio, SAMPLE_RATE)

    recorder = processor_state['recorder']
    if processor_state['recording'] and recorder is not None:
        recorder.submit(filtered_audio)

    write_mono(outdata, filtered_audio)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>LU2MET NR Filter</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="mobile-web-app-capable" content="yes">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 { font-size: 28px; margin-bottom: 10px; }
        .status {
            display: inline-block;
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: bold;
            margin-top: 10px;
        }
        .status.running { background: #10b981; }
        .status.stopped { background: #ef4444; }
        .content { padding: 30px; }
        .section {
            background: #f9fafb;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .section h2 {
            font-size: 18px;
            margin-bottom: 15px;
            color: #374151;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: 500;
            color: #4b5563;
        }
        select, input[type="checkbox"] {
            width: 100%;
            padding: 10px;
            border: 2px solid #e5e7eb;
            border-radius: 6px;
            font-size: 14px;
        }
        select:focus {
            outline: none;
            border-color: #667eea;
        }
        .presets {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }
        .preset-btn {
            padding: 12px;
            border: 2px solid #e5e7eb;
            border-radius: 6px;
            background: white;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.2s;
        }
        .preset-btn:hover { border-color: #667eea; }
        .preset-btn.active {
            background: #667eea;
            color: white;
            border-color: #667eea;
        }
        .preset-info {
            margin-top: 10px;
            padding: 10px;
            background: white;
            border-radius: 6px;
            font-size: 12px;
            color: #6b7280;
        }
        .mode-btn {
            flex: 1;
            padding: 12px;
            border: 2px solid #e5e7eb;
            background: white;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
        }
        .mode-btn:hover {
            border-color: #10b981;
            background: #f9fafb;
        }
        .mode-btn.active {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            border-color: #10b981;
            transform: scale(1.05);
        }
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .checkbox-group input[type="checkbox"] {
            width: auto;
        }
        .gain-control {
            display: grid;
            grid-template-columns: minmax(120px, 1fr) minmax(120px, 3fr) 72px;
            align-items: center;
            gap: 12px;
            margin: 12px 0;
        }
        .gain-control input[type="range"] { width: 100%; }
        .gain-value, .level-meter {
            font-family: 'Courier New', monospace;
            font-variant-numeric: tabular-nums;
        }
        .gain-value { text-align: right; font-weight: 600; }
        .level-meter {
            display: grid;
            gap: 9px;
            margin-top: 14px;
        }
        .level-row {
            display: grid;
            grid-template-columns: 28px minmax(80px, 1fr) 235px;
            align-items: center;
            gap: 10px;
            font-size: 12px;
        }
        .level-track {
            position: relative;
            height: 12px;
            overflow: visible;
            background: #d1d5db;
            border-radius: 3px;
        }
        .level-fill {
            height: 100%;
            width: 0;
            background: #16a34a;
            border-radius: 3px;
            transition: width 100ms linear;
        }
        .level-peak-marker {
            position: absolute;
            top: -2px;
            left: 0;
            width: 2px;
            height: 16px;
            background: #111827;
            transform: translateX(-1px);
            transition: left 100ms linear;
        }
        .level-value {
            width: 235px;
            color: #374151;
            font-family: 'Courier New', monospace;
            font-variant-numeric: tabular-nums;
            text-align: right;
        }
        .level-warning { color: #b91c1c; font-weight: 700; }
        @media (max-width: 480px) {
            .gain-control {
                grid-template-columns: minmax(0, 1fr) auto;
                gap: 6px 10px;
            }
            .gain-control input[type="range"] { grid-column: 1 / -1; }
            .level-row {
                grid-template-columns: 28px minmax(0, 1fr);
                gap: 6px 8px;
            }
            .level-value {
                grid-column: 2;
                width: auto;
                text-align: left;
                font-size: 11px;
            }
        }
        .buttons {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }
        button {
            flex: 1;
            padding: 15px;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-start {
            background: #10b981;
            color: white;
        }
        .btn-start:hover { background: #059669; }
        .btn-start:disabled {
            background: #d1d5db;
            cursor: not-allowed;
        }
        .btn-stop {
            background: #ef4444;
            color: white;
        }
        .btn-stop:hover { background: #dc2626; }
        .btn-stop:disabled {
            background: #d1d5db;
            cursor: not-allowed;
        }
        .btn-rec {
            padding: 12px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.2s;
            color: white;
        }
        .btn-rec:hover:not(:disabled) { opacity: 0.9; }
        .btn-rec:disabled {
            background: #d1d5db !important;
            cursor: not-allowed;
        }
        input[type="text"] {
            width: 100%;
        }
        input[type="text"]:focus {
            outline: none;
            border-color: #667eea;
        }
        .log {
            background: #1f2937;
            color: #10b981;
            padding: 15px;
            border-radius: 6px;
            height: 300px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            line-height: 1.6;
        }
        .log::-webkit-scrollbar { width: 8px; }
        .log::-webkit-scrollbar-track { background: #374151; }
        .log::-webkit-scrollbar-thumb {
            background: #667eea;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📻 LU2MET NR Filter</h1>
            <div class="status" id="status">● Stopped</div>
        </div>
        
        <div class="content">
            <div class="section">
                <h2>🎧 Audio Devices</h2>
                <div class="form-group">
                    <label>Input Device</label>
                    <select id="input-device"></select>
                </div>
                <div class="form-group">
                    <label>Output Device</label>
                    <select id="output-device"></select>
                </div>
            </div>
            
            <div class="section">
                <h2>📡 Mode</h2>
                <div class="presets">
                    <button class="mode-btn active" data-mode="SSB">SSB (300-2700 Hz)</button>
                    <button class="mode-btn" data-mode="CW">CW (600-900 Hz)</button>
                </div>
            </div>
            
            <div class="section">
                <h2>🎛️ Noise Reduction Preset</h2>
                <div class="presets">
                    <button class="preset-btn" data-preset="moderate">Moderate</button>
                    <button class="preset-btn" data-preset="aggressive">Aggressive</button>
                    <button class="preset-btn" data-preset="ultra">Ultra</button>
                    <button class="preset-btn active" data-preset="extreme">Extreme ⭐</button>
                </div>
                <div class="preset-info" id="preset-info"></div>
            </div>
            
            <div class="section">
                <h2>⚙️ Processing Control</h2>
                <div class="gain-control">
                    <label for="input-trim">DSP input trim</label>
                    <input id="input-trim" type="range" min="1" max="100" value="36">
                    <output class="gain-value" id="input-trim-value">-25.9 dB</output>
                </div>
                <div class="gain-control">
                    <label for="output-volume">Master output</label>
                    <input id="output-volume" type="range" min="10" max="400" value="100">
                    <output class="gain-value" id="output-volume-value">0.0 dB</output>
                </div>
                <div class="level-meter">
                    <div class="level-row">
                        <strong>IN</strong>
                        <div class="level-track">
                            <div class="level-fill" id="input-level-fill"></div>
                            <span class="level-peak-marker" id="input-peak-marker"></span>
                        </div>
                        <output class="level-value" id="input-level-value">RMS -120.0 | PK -120.0 dBFS</output>
                    </div>
                    <div class="level-row">
                        <strong>OUT</strong>
                        <div class="level-track">
                            <div class="level-fill" id="output-level-fill"></div>
                            <span class="level-peak-marker" id="output-peak-marker"></span>
                        </div>
                        <output class="level-value" id="output-level-value">RMS -120.0 | PK -120.0 dBFS</output>
                    </div>
                    <div id="level-warning" class="level-value"></div>
                </div>
                <div class="checkbox-group">
                    <input type="checkbox" id="bypass">
                    <label for="bypass" style="margin: 0;">Bypass (Pass-through audio without processing)</label>
                </div>
            </div>
            
            <div class="buttons">
                <button class="btn-start" id="start-btn">▶ Start</button>
                <button class="btn-stop" id="stop-btn" disabled>■ Stop</button>
            </div>
            
            <div class="section">
                <h2>🔴 Recording</h2>
                <p style="color: #6b7280; font-size: 14px; margin-bottom: 15px;">
                    Recordings will be saved as: recording_YYYYMMDD_HHMMSS.mp3 (128kbps)
                </p>
                <div class="buttons">
                    <button class="btn-rec" id="rec-start-btn" disabled style="background: #dc2626; flex: 1;">🔴 Start Recording</button>
                    <button class="btn-rec" id="rec-stop-btn" disabled style="background: #6b7280; flex: 1;">⏹️ Stop Recording</button>
                </div>
                <p id="rec-status" style="display: none; margin-top: 12px;"></p>
            </div>
            <div class="section">
                <h2>📋 Log</h2>
                <div class="log" id="log"></div>
            </div>
            
            <div style="text-align: center; padding: 20px; color: white; font-size: 12px; opacity: 0.8;">
                <p>LU2MET NR Filter</p>
                <p style="margin-top: 10px;">
                    <a href="https://github.com/tomduca/novasdr-audio-processor" target="_blank" style="color: #86efac; text-decoration: none;">
                        📻 Project source on GitHub
                    </a>
                </p>
            </div>
        </div>
    </div>
    
    <script>
        const presetsSSB = {{ presets_ssb|tojson }};
        const presetsCW = {{ presets_cw|tojson }};
        let currentPreset = 'extreme';
        let currentMode = 'SSB';
        
        // Load devices
        fetch('/api/devices')
            .then(r => r.json())
            .then(data => {
                const inputSelect = document.getElementById('input-device');
                const outputSelect = document.getElementById('output-device');
                
                data.input.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d.index;
                    opt.textContent = d.name;
                    inputSelect.appendChild(opt);
                    
                    // Auto-select BlackHole or Loopback
                    if (d.name.includes('BlackHole') || d.name.includes('Loopback')) {
                        inputSelect.value = d.index;
                    }
                });
                
                data.output.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d.index;
                    opt.textContent = d.name;
                    outputSelect.appendChild(opt);
                });
            });
        
        // Update preset info
        function updatePresetInfo() {
            const presets = currentMode === 'CW' ? presetsCW : presetsSSB;
            const preset = presets[currentPreset];
            const gain = Math.round(1 / preset.gain);
            document.getElementById('preset-info').textContent = 
                `Gain: 1/${gain}, Alpha: ${preset.alpha}, ASNR: ${preset.asnr} dB, Post-Gain: ${preset.post_gain}x`;
        }
        updatePresetInfo();
        
        // Mode buttons
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentMode = btn.dataset.mode;
                updatePresetInfo();
                
                fetch('/api/mode', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({mode: currentMode})
                });
            });
        });
        
        // Preset buttons
        document.querySelectorAll('.preset-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentPreset = btn.dataset.preset;
                updatePresetInfo();
                
                fetch('/api/preset', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({preset: currentPreset})
                });
            });
        });
        
        // Bypass toggle
        document.getElementById('bypass').addEventListener('change', (e) => {
            fetch('/api/bypass', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({bypass: e.target.checked})
            });
        });

        const inputTrim = document.getElementById('input-trim');
        const outputVolume = document.getElementById('output-volume');

        inputTrim.addEventListener('input', () => {
            const value = Number(inputTrim.value);
            const gainDb = -40 + ((value - 1) / 99) * 40;
            document.getElementById('input-trim-value').textContent = `${gainDb.toFixed(1)} dB`;
            fetch('/api/input-trim', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({value})
            });
        });

        outputVolume.addEventListener('input', () => {
            const value = Number(outputVolume.value);
            const gain = value <= 100
                ? 10 ** ((value - 100) / 90)
                : 10 ** (((value - 100) / 300) * Math.log10(4));
            document.getElementById('output-volume-value').textContent =
                `${(20 * Math.log10(gain)).toFixed(1)} dB`;
            fetch('/api/output-volume', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({value})
            });
        });

        function meterPosition(dbfs) {
            return Math.max(0, Math.min(100, ((dbfs + 60) / 60) * 100));
        }

        setInterval(() => {
            fetch('/api/levels')
                .then(r => r.json())
                .then(levels => {
                    document.getElementById('input-level-fill').style.width = `${meterPosition(levels.input_rms_dbfs)}%`;
                    document.getElementById('input-peak-marker').style.left = `${meterPosition(levels.input_peak_hold_dbfs)}%`;
                    document.getElementById('output-level-fill').style.width = `${meterPosition(levels.output_rms_dbfs)}%`;
                    document.getElementById('output-peak-marker').style.left = `${meterPosition(levels.output_peak_hold_dbfs)}%`;
                    document.getElementById('input-level-value').textContent =
                        `RMS ${levels.input_rms_dbfs.toFixed(1).padStart(6)} | PK ${levels.input_peak_hold_dbfs.toFixed(1).padStart(6)} dBFS`;
                    document.getElementById('output-level-value').textContent =
                        `RMS ${levels.output_rms_dbfs.toFixed(1).padStart(6)} | PK ${levels.output_peak_hold_dbfs.toFixed(1).padStart(6)} dBFS`;
                    const warnings = [];
                    if (levels.input_clipping) warnings.push('INPUT CLIP');
                    if (levels.limiter_active) warnings.push('SOFT LIMIT');
                    const warningElement = document.getElementById('level-warning');
                    warningElement.textContent = warnings.join('  ·  ');
                    warningElement.className = warnings.length ? 'level-value level-warning' : 'level-value';
                });
        }, 150);
        
        // Start button
        document.getElementById('start-btn').addEventListener('click', () => {
            const input = document.getElementById('input-device').value;
            const output = document.getElementById('output-device').value;
            
            fetch('/api/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    input: parseInt(input),
                    output: parseInt(output),
                    preset: currentPreset
                })
            }).then(r => r.json()).then(data => {
                if (data.success) {
                    document.getElementById('start-btn').disabled = true;
                    document.getElementById('stop-btn').disabled = false;
                    document.getElementById('status').textContent = '● Running';
                    document.getElementById('status').className = 'status running';
                }
            });
        });
        
        // Stop button
        document.getElementById('stop-btn').addEventListener('click', () => {
            fetch('/api/stop', {method: 'POST'})
                .then(r => r.json())
                .then(data => {
                    document.getElementById('start-btn').disabled = false;
                    document.getElementById('stop-btn').disabled = true;
                    document.getElementById('rec-start-btn').disabled = true;
                    document.getElementById('rec-stop-btn').disabled = true;
                    document.getElementById('status').textContent = '● Stopped';
                    document.getElementById('status').className = 'status stopped';
                    document.getElementById('rec-status').style.display = 'none';
                });
        });
        
        // Recording start button
        document.getElementById('rec-start-btn').addEventListener('click', () => {
            fetch('/api/recording/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({})
            }).then(r => r.json()).then(data => {
                if (data.success) {
                    document.getElementById('rec-start-btn').disabled = true;
                    document.getElementById('rec-stop-btn').disabled = false;
                    document.getElementById('rec-status').style.display = 'block';
                    document.getElementById('rec-status').innerHTML = '🔴 <strong>Recording...</strong>';
                }
            });
        });
        
        // Recording stop button
        document.getElementById('rec-stop-btn').addEventListener('click', () => {
            fetch('/api/recording/stop', {method: 'POST'})
                .then(r => r.json())
                .then(data => {
                    document.getElementById('rec-start-btn').disabled = false;
                    document.getElementById('rec-stop-btn').disabled = true;
                    if (data.success) {
                        document.getElementById('rec-status').innerHTML = 
                            '✅ <strong>Saved:</strong> ' + data.filename + ' (' + data.duration.toFixed(1) + 's)';
                    }
                });
        });
        
        // Enable recording button when processing starts
        const originalStartHandler = document.getElementById('start-btn').onclick;
        document.getElementById('start-btn').addEventListener('click', () => {
            setTimeout(() => {
                document.getElementById('rec-start-btn').disabled = false;
            }, 500);
        });
        
        // Update logs
        setInterval(() => {
            fetch('/api/logs')
                .then(r => r.json())
                .then(data => {
                    const logDiv = document.getElementById('log');
                    logDiv.textContent = data.logs.join('\\n');
                    logDiv.scrollTop = logDiv.scrollHeight;
                });
        }, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, presets_ssb=PRESETS_SSB, presets_cw=PRESETS_CW)

@app.route('/api/devices')
def get_devices():
    devices = sd.query_devices()
    input_devices = []
    output_devices = []
    
    for idx, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            input_devices.append({'index': idx, 'name': f"{idx}: {device['name']}"})
        if device['max_output_channels'] > 0:
            output_devices.append({'index': idx, 'name': f"{idx}: {device['name']}"})
    
    log(f"Loaded {len(input_devices)} input and {len(output_devices)} output devices")
    return jsonify({'input': input_devices, 'output': output_devices})

@app.route('/api/preset', methods=['POST'])
def set_preset():
    data = request.json
    preset_name = data['preset']
    
    # Get presets based on current mode
    presets = PRESETS_CW if processor_state['mode'] == 'CW' else PRESETS_SSB
    
    if preset_name not in presets:
        return jsonify({'success': False, 'error': 'Invalid preset'})
    
    processor_state['preset'] = preset_name
    
    if processor_state['nr'] and NR_AVAILABLE:
        preset = presets[preset_name]
        processor_state['nr'] = spectral_nr.SpectralNoiseReduction(
            SAMPLE_RATE,
            preset['gain'],
            preset['alpha'],
            preset['asnr']
        )
        processor_state['post_gain'] = preset['post_gain']
        processor_state['block_config'].schedule(
            nr=processor_state['nr'],
            post_gain=processor_state['post_gain'],
        )
        log(f"Preset changed to {preset_name} ({processor_state['mode']} mode)")
    
    return jsonify({'success': True})

@app.route('/api/bypass', methods=['POST'])
def set_bypass():
    data = request.json
    processor_state['bypass'] = data['bypass']
    processor_state['block_config'].schedule(bypass=processor_state['bypass'])
    status = "BYPASSED" if data['bypass'] else "ACTIVE"
    log(f"Processing {status}")
    return jsonify({'success': True})

@app.route('/api/input-trim', methods=['POST'])
def set_input_trim():
    value = int(request.json['value'])
    if not 1 <= value <= 100:
        return jsonify({'success': False, 'error': 'Input trim must be between 1 and 100'})
    processor_state['input_gain'] = input_trim_slider_to_gain(value)
    processor_state['block_config'].schedule(input_gain=processor_state['input_gain'])
    return jsonify({'success': True})

@app.route('/api/output-volume', methods=['POST'])
def set_output_volume():
    value = int(request.json['value'])
    if not 10 <= value <= 400:
        return jsonify({'success': False, 'error': 'Output volume must be between 10 and 400'})
    processor_state['output_volume'] = volume_slider_to_gain(value)
    processor_state['block_config'].schedule(output_volume=processor_state['output_volume'])
    return jsonify({'success': True})

@app.route('/api/mode', methods=['POST'])
def set_mode():
    data = request.json
    mode = data['mode']
    
    if mode not in ['SSB', 'CW']:
        return jsonify({'success': False, 'error': 'Invalid mode'})
    
    processor_state['mode'] = mode
    
    # Update bandpass filter
    processor_state['bandpass_filter'], processor_state['zi_bandpass'] = create_bandpass_filter(mode)
    
    # Update noise reduction parameters based on mode and current preset
    presets = PRESETS_CW if mode == 'CW' else PRESETS_SSB
    preset = presets[processor_state['preset']]
    
    if processor_state['nr'] and NR_AVAILABLE:
        processor_state['nr'] = spectral_nr.SpectralNoiseReduction(
            SAMPLE_RATE,
            preset['gain'],
            preset['alpha'],
            preset['asnr']
        )
        processor_state['post_gain'] = preset['post_gain']
    processor_state['block_config'].schedule(
        bandpass_filter=processor_state['bandpass_filter'],
        zi_bandpass=processor_state['zi_bandpass'],
        nr=processor_state['nr'],
        post_gain=processor_state['post_gain'],
    )
    
    config = BANDPASS_CONFIG[mode]
    log(f"Mode changed to {mode} (BW: {config['low']}-{config['high']} Hz)")
    return jsonify({'success': True})

@app.route('/api/start', methods=['POST'])
def start_processing():
    data = request.json
    
    try:
        processor_state['input_device'] = data['input']
        processor_state['output_device'] = data['output']
        input_info = sd.query_devices(data['input'])
        output_info = sd.query_devices(data['output'])
        input_channels, output_channels = choose_stream_channels(input_info, output_info)
        processor_state['preset'] = data['preset']
        
        # Initialize bandpass filter based on current mode
        processor_state['bandpass_filter'], processor_state['zi_bandpass'] = create_bandpass_filter(processor_state['mode'])
        
        # Initialize noise reduction with mode-specific presets
        if NR_AVAILABLE:
            presets = PRESETS_CW if processor_state['mode'] == 'CW' else PRESETS_SSB
            preset = presets[data['preset']]
            processor_state['nr'] = spectral_nr.SpectralNoiseReduction(
                SAMPLE_RATE,
                preset['gain'],
                preset['alpha'],
                preset['asnr']
            )
            processor_state['post_gain'] = preset['post_gain']
            log(f"✓ Noise reduction initialized: {data['preset']} preset")

        processor_state['block_config'].schedule(
            bypass=processor_state['bypass'],
            input_gain=processor_state['input_gain'],
            output_volume=processor_state['output_volume'],
            bandpass_filter=processor_state['bandpass_filter'],
            zi_bandpass=processor_state['zi_bandpass'],
            nr=processor_state['nr'],
            post_gain=processor_state['post_gain'],
        )
        processor_state['meters'] = {
            'input': AudioLevelMeter(),
            'output': AudioLevelMeter(),
            'input_clipping': False,
            'limiter_active': False,
        }
        
        processor_state['stream'] = sd.Stream(
            device=(data['input'], data['output']),
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            channels=(input_channels, output_channels),
            callback=audio_callback,
            latency='low'
        )
        
        processor_state['stream'].start()
        processor_state['running'] = True
        processor_state['input_device'] = data['input']
        processor_state['output_device'] = data['output']
        
        log(f"✓ Audio processing started")
        log(f"  Preset: {data['preset']}")
        log(f"  Latency: ~{(BLOCK_SIZE / SAMPLE_RATE) * 1000:.1f}ms")
        
        return jsonify({'success': True})
    except Exception as e:
        log(f"ERROR: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/stop', methods=['POST'])
def stop_processing():
    if processor_state['stream']:
        processor_state['stream'].stop()
        processor_state['stream'].close()
        processor_state['stream'] = None
    
    processor_state['running'] = False
    if processor_state['recording']:
        stop_recording()
    log("✓ Audio processing stopped")
    
    return jsonify({'success': True})

@app.route('/api/logs')
def get_logs():
    return jsonify({'logs': processor_state['logs']})

@app.route('/api/levels')
def get_levels():
    meters = processor_state['meters']
    input_rms, _, input_peak_hold = meters['input'].snapshot
    output_rms, _, output_peak_hold = meters['output'].snapshot
    return jsonify({
        'input_rms_dbfs': input_rms,
        'input_peak_hold_dbfs': input_peak_hold,
        'output_rms_dbfs': output_rms,
        'output_peak_hold_dbfs': output_peak_hold,
        'input_clipping': meters['input_clipping'],
        'limiter_active': meters['limiter_active'],
    })

@app.route('/api/recording/start', methods=['POST'])
def start_recording():
    if not processor_state['running']:
        return jsonify({'success': False, 'error': 'Audio processing not running'})
    
    if processor_state['recording']:
        return jsonify({'success': False, 'error': 'Already recording'})
    
    folder = recordings_dir()
    recorder = AsyncMonoRecorder(folder, SAMPLE_RATE, MP3_AVAILABLE)
    recorder.start()
    processor_state['recorder'] = recorder
    processor_state['recording'] = True
    
    log(f"🔴 Recording started")
    return jsonify({'success': True})

@app.route('/api/recording/stop', methods=['POST'])
def stop_recording():
    if not processor_state['recording']:
        return jsonify({'success': False, 'error': 'Not recording'})
    
    processor_state['recording'] = False
    recorder = processor_state['recorder']
    processor_state['recorder'] = None
    if recorder is None:
        log("⏹️ Recording stopped - No data recorded")
        return jsonify({'success': False, 'error': 'No data recorded'})
    try:
        filepath, duration, dropped_chunks, conversion_error = recorder.stop()
    except Exception as error:
        log(f"ERROR saving recording: {error}")
        return jsonify({'success': False, 'error': str(error)})
    if not duration:
        log("⏹️ Recording stopped - No data recorded")
        return jsonify({'success': False, 'error': 'No data recorded'})

    filename = filepath.name
    log(f"⏹️ Recording stopped - Saved: {filename} ({duration:.1f}s)")
    if dropped_chunks:
        log(f"WARNING: Recording dropped {dropped_chunks} audio blocks")
    if conversion_error:
        log(f"WARNING: MP3 conversion failed; WAV retained: {conversion_error}")
    return jsonify({'success': True, 'filename': filename, 'duration': duration})

@app.route('/api/recording/status')
def recording_status():
    return jsonify({
        'recording': processor_state['recording']
    })

if __name__ == '__main__':
    log("LU2MET NR Filter Web Interface")
    log(f"Noise reduction module: {'✓ Available' if NR_AVAILABLE else '✗ Not available'}")
    print("\n" + "="*50)
    print("Open your browser at: http://localhost:5001")
    print("="*50 + "\n")
    app.run(debug=False, host='0.0.0.0', port=5001)
