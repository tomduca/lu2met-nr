#!/usr/bin/env python3
"""
LU2MET NR Filter - Native PyQt5 GUI
True standalone desktop application
"""

import sys
import numpy as np
import sounddevice as sd
from scipy import signal
import threading
import time
from pathlib import Path
import logging

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, QPushButton, 
                             QTextEdit, QRadioButton, QButtonGroup, QCheckBox,
                             QGroupBox, QMessageBox, QSlider, QScrollArea, QProgressBar,
                             QFrame)
from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt, QTimer, QSettings
from PyQt5.QtGui import QFont, QPalette, QColor
from audio_pipeline import (
    AsyncMonoRecorder,
    AudioLevelMeter,
    BlockConfig,
    TxGate,
    apply_master_output,
    check_same_host_api,
    choose_stream_channels,
    device_choices,
    find_device_label,
    input_is_clipped,
    input_trim_slider_to_gain,
    recordings_dir,
    to_mono,
    volume_slider_to_gain,
    write_mono,
)
from update_check import app_version, check_for_update, is_development

APP_VERSION = app_version()

# A Windows console may use a legacy code page (e.g. cp1252) that cannot
# encode symbols such as ✓; replace them instead of failing at startup.
for stream in (sys.stdout, sys.stderr):
    if stream is not None and hasattr(stream, 'reconfigure'):
        stream.reconfigure(errors='backslashreplace')

# Setup logging to file for debugging when run from Finder
log_file = Path.home() / 'lu2met_nr_debug.log'
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logging.info(f"LU2MET NR Filter starting... Log file: {log_file}")

try:
    import spectral_nr
    NR_AVAILABLE = True
    logging.info(f"✓ Noise reduction module loaded from: {spectral_nr.__file__}")
    print(f"✓ Noise reduction module loaded from: {spectral_nr.__file__}")
except ImportError as e:
    NR_AVAILABLE = False
    logging.error(f"✗ Noise reduction module not available: {e}")
    print(f"✗ Noise reduction module not available: {e}")
except Exception as e:
    NR_AVAILABLE = False
    logging.error(f"✗ Error loading noise reduction module: {e}", exc_info=True)
    print(f"✗ Error loading noise reduction module: {e}")
    import traceback
    traceback.print_exc()

try:
    from pydub import AudioSegment
    MP3_AVAILABLE = True
except ImportError:
    MP3_AVAILABLE = False

# Audio parameters
SAMPLE_RATE = 48000
BLOCK_SIZE = 2048

# Level meter colors, chosen from peak-hold dBFS
LEVEL_COLOR_OK = '#16a34a'
LEVEL_COLOR_HOT = '#f59e0b'
LEVEL_COLOR_CLIP = '#dc2626'


def level_color(peak_dbfs):
    if peak_dbfs >= -1.0:
        return LEVEL_COLOR_CLIP
    if peak_dbfs >= -6.0:
        return LEVEL_COLOR_HOT
    return LEVEL_COLOR_OK


def level_bar_style(color):
    return (
        'QProgressBar { background: #d1d5db; border: 0; border-radius: 3px; }'
        f'QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}'
    )


def led_style(active, color=LEVEL_COLOR_CLIP):
    if active:
        return (f'background: {color}; color: white; font-weight: bold; '
                'font-size: 10px; border-radius: 3px; padding: 1px;')
    return ('background: #e5e7eb; color: #9ca3af; font-size: 10px; '
            'border-radius: 3px; padding: 1px;')

# Presets
PRESETS_SSB = {
    'moderate': {'gain': 1.0/1024.0, 'alpha': 0.98, 'asnr': 20.0, 'post_gain': 1.5},
    'aggressive': {'gain': 1.0/2048.0, 'alpha': 0.98, 'asnr': 10.0, 'post_gain': 2.5},
    'ultra': {'gain': 1.0/8192.0, 'alpha': 0.99, 'asnr': 2.0, 'post_gain': 10.0},
    'extreme': {'gain': 1.0/16384.0, 'alpha': 0.99, 'asnr': 1.0, 'post_gain': 14.0}
}

PRESETS_CW = {
    'moderate': {'gain': 1.0/2048.0, 'alpha': 0.98, 'asnr': 15.0, 'post_gain': 3.0},
    'aggressive': {'gain': 1.0/4096.0, 'alpha': 0.99, 'asnr': 8.0, 'post_gain': 5.0},
    'ultra': {'gain': 1.0/8192.0, 'alpha': 0.99, 'asnr': 3.0, 'post_gain': 12.0},
    'extreme': {'gain': 1.0/16384.0, 'alpha': 0.995, 'asnr': 1.0, 'post_gain': 18.0}
}

# NR2 alone keeps about the level of the presets, which lower it 3-8 dB,
# so switching filters does not sound like a volume change.
NR2_ONLY_GAIN = 10 ** (-5 / 20)

BANDPASS_CONFIG = {
    'SSB': {'low': 300, 'high': 2700},
    'CW': {'low': 600, 'high': 900}
}


class AudioProcessor(QThread):
    """Audio processing thread"""
    log_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.tx_mute = True
        self.tx_gate = TxGate(SAMPLE_RATE)
        self.recording = False
        self.mode = 'SSB'
        self.preset = 'extreme'
        self.input_device = None
        self.output_device = None
        self.stream = None
        self.nr = None
        self.nr_enabled = True
        self.nr2 = None
        self.nr2_enabled = False
        self.post_gain = 14.0
        self.input_gain = input_trim_slider_to_gain(36)
        self.output_volume = 1.0  # Default output volume (100%)
        self.input_meter = AudioLevelMeter()
        self.output_meter = AudioLevelMeter()
        self.input_clipping_seen = False
        self.limiter_active_seen = False
        self.bandpass_filter = None
        self.zi_bandpass = None
        self.block_config = BlockConfig({
            'tx_mute': True,
            'input_gain': self.input_gain,
            'output_volume': self.output_volume,
            'bandpass_filter': None,
            'zi_bandpass': None,
            'nr': None,
            'nr_enabled': True,
            'nr2': None,
            'post_gain': self.post_gain,
        })
        self.recorder = None
        self.callback_count = 0
        
    def create_bandpass_filter(self, mode):
        config = BANDPASS_CONFIG[mode]
        low_freq = config['low']
        high_freq = config['high']
        
        nyquist = SAMPLE_RATE / 2
        low_normalized = low_freq / nyquist
        high_normalized = high_freq / nyquist
        
        sos = signal.butter(4, [low_normalized, high_normalized], btype='band', output='sos')
        zi = signal.sosfilt_zi(sos)
        
        return sos, zi
    
    def audio_callback(self, indata, outdata, frames, time_info, status):
        self.callback_count += 1
        
        # Log every 100 callbacks to verify it's running
        if self.callback_count % 100 == 0:
            logging.debug(f"Audio callback running: {self.callback_count} calls")
        
        if status:
            logging.warning(f"Audio status: {status}")
            print(f"Audio status: {status}", file=sys.stderr)
        
        config = self.block_config.apply_pending()
        self.input_meter.update(indata, SAMPLE_RATE)
        self.input_clipping_seen = self.input_clipping_seen or input_is_clipped(indata)
        audio_data = to_mono(indata)

        if config['tx_mute']:
            # During TX: mute, and keep the noise estimate from adapting to silence.
            freeze_nr, tx_envelope = self.tx_gate.update(audio_data)
        else:
            if self.tx_gate.reference_db is not None:
                self.tx_gate.reset()
            freeze_nr, tx_envelope = False, None

        if not NR_AVAILABLE or config['nr'] is None:
            # Without the extension, pass the audio through to the master output stage.
            filtered_audio = audio_data
            if self.callback_count == 1:
                logging.info("Audio callback: pass-through (noise reduction unavailable)")
        else:
            # Apply input gain to prevent saturation
            audio_data = audio_data * config['input_gain']

            try:
                if freeze_nr:
                    filtered_audio = np.zeros_like(audio_data)
                elif config['bandpass_filter'] is not None:
                    filtered_audio, config['zi_bandpass'] = signal.sosfilt(
                        config['bandpass_filter'], audio_data, zi=config['zi_bandpass']
                    )
                else:
                    filtered_audio = audio_data

                if not freeze_nr:
                    if config['nr_enabled']:
                        filtered_audio = config['nr'].process(filtered_audio.astype(np.float32))
                        filtered_audio = filtered_audio * config['post_gain']
                    if config['nr2'] is not None:
                        filtered_audio = config['nr2'].process(filtered_audio.astype(np.float32))
                        if not config['nr_enabled']:
                            filtered_audio = filtered_audio * NR2_ONLY_GAIN

                if self.callback_count == 1:
                    logging.info(f"Audio callback: PROCESSING mode (input level: {np.abs(audio_data).max():.4f}, output level: {np.abs(filtered_audio).max():.4f})")
            except Exception as e:
                logging.error(f"✗ Audio processing error: {e}", exc_info=True)
                print(f"✗ Audio processing error: {e}")
                filtered_audio = audio_data

        filtered_audio, limiter_active = apply_master_output(
            filtered_audio, config['output_volume']
        )
        if tx_envelope is not None:
            filtered_audio = filtered_audio * tx_envelope
        self.limiter_active_seen = self.limiter_active_seen or limiter_active
        self.output_meter.update(filtered_audio, SAMPLE_RATE)

        if self.recording and self.recorder is not None:
            self.recorder.submit(filtered_audio)

        write_mono(outdata, filtered_audio)
    
    def start_processing(self, input_dev, output_dev, preset, mode):
        self.input_device = input_dev
        self.output_device = output_dev
        self.preset = preset
        self.mode = mode
        self.reset_meters()
        
        self.bandpass_filter, self.zi_bandpass = self.create_bandpass_filter(mode)
        
        if NR_AVAILABLE:
            try:
                presets = PRESETS_CW if mode == 'CW' else PRESETS_SSB
                preset_config = presets[preset]
                self.nr = spectral_nr.SpectralNoiseReduction(
                    SAMPLE_RATE,
                    preset_config['gain'],
                    preset_config['alpha'],
                    preset_config['asnr']
                )
                self.post_gain = preset_config['post_gain']
                self.block_config.schedule(
                    bandpass_filter=self.bandpass_filter,
                    zi_bandpass=self.zi_bandpass,
                    nr=self.nr,
                    post_gain=self.post_gain,
                )
                logging.info(f"✓ Noise reduction initialized: {preset} mode {mode}")
                print(f"✓ Noise reduction initialized: {preset} mode {mode}")
            except Exception as e:
                logging.error(f"✗ Failed to initialize noise reduction: {e}", exc_info=True)
                print(f"✗ Failed to initialize noise reduction: {e}")
                import traceback
                traceback.print_exc()
                self.log_signal.emit(f"ERROR: Failed to initialize noise reduction: {e}")
        else:
            self.log_signal.emit("WARNING: Noise reduction module not available - passing audio through")
        
        # Query device info to get correct number of channels
        try:
            input_info = sd.query_devices(input_dev)
            output_info = sd.query_devices(output_dev)
            
            input_channels, output_channels = choose_stream_channels(input_info, output_info)
            hostapis = sd.query_hostapis()
            check_same_host_api(input_info, output_info, hostapis)
            extra_settings = None
            if hostapis[input_info['hostapi']]['name'] == 'Windows WASAPI':
                # Shared-mode WASAPI fails unless the device is already at 48 kHz;
                # let Windows convert instead.
                wasapi = sd.WasapiSettings(auto_convert=True)
                extra_settings = (wasapi, wasapi)
            
            logging.info(f"Input device: {input_channels} channels, Output device: {output_channels} channels")
            print(f"Input device: {input_channels} channels, Output device: {output_channels} channels")
            
            self.stream = sd.Stream(
                device=(input_dev, output_dev),
                samplerate=SAMPLE_RATE,
                blocksize=BLOCK_SIZE,
                channels=(input_channels, output_channels),
                callback=self.audio_callback,
                latency='low',
                extra_settings=extra_settings,
            )
        except Exception as e:
            logging.error(f"ERROR: Failed to open audio stream: {e}", exc_info=True)
            self.log_signal.emit(f"ERROR: Failed to open audio stream: {e}")
            raise
        
        try:
            self.nr2 = self.create_nr2() if self.nr2_enabled else None
            self.block_config.schedule(
                input_gain=self.input_gain,
                output_volume=self.output_volume,
                bandpass_filter=self.bandpass_filter,
                zi_bandpass=self.zi_bandpass,
                nr=self.nr,
                nr_enabled=self.nr_enabled,
                nr2=self.nr2,
                post_gain=self.post_gain,
            )
            self.stream.start()
            self.running = True
            logging.info("✓ Audio stream started successfully")
        except Exception as e:
            logging.error(f"ERROR: Failed to start audio stream: {e}", exc_info=True)
            self.log_signal.emit(f"ERROR: Failed to start audio stream: {e}")
            raise
        
        config = BANDPASS_CONFIG[mode]
        self.log_signal.emit(f"✓ Audio processing started")
        self.log_signal.emit(f"  Mode: {mode} ({config['low']}-{config['high']} Hz)")
        self.log_signal.emit(f"  Preset: {preset}")
        self.log_signal.emit(f"  Latency: ~{(BLOCK_SIZE / SAMPLE_RATE) * 1000:.1f}ms")
    
    def stop_processing(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.running = False
        if self.recording:
            self.stop_recording()
        self.log_signal.emit("✓ Audio processing stopped")

    def reset_meters(self):
        self.tx_gate.reset()
        self.input_meter.reset()
        self.output_meter.reset()
        self.input_clipping_seen = False
        self.limiter_active_seen = False
    
    @staticmethod
    def create_nr2():
        if not NR_AVAILABLE or not hasattr(spectral_nr, 'OmlsaNoiseReduction'):
            return None
        return spectral_nr.OmlsaNoiseReduction(SAMPLE_RATE)

    def set_filters(self, nr_enabled, nr2_enabled):
        """Enable the LU2MET filter and NR2 independently; both run in series."""
        self.nr_enabled = nr_enabled
        if nr2_enabled and (self.nr2 is None or not self.nr2_enabled):
            # A fresh NR2 re-learns the noise in about 2.5 s.
            self.nr2 = self.create_nr2() if self.running else None
        elif not nr2_enabled:
            self.nr2 = None
        self.nr2_enabled = nr2_enabled
        self.block_config.schedule(nr_enabled=nr_enabled, nr2=self.nr2)

    def set_mode(self, mode):
        self.mode = mode
        self.bandpass_filter, self.zi_bandpass = self.create_bandpass_filter(mode)
        
        if self.nr and NR_AVAILABLE:
            presets = PRESETS_CW if mode == 'CW' else PRESETS_SSB
            preset_config = presets[self.preset]
            self.nr = spectral_nr.SpectralNoiseReduction(
                SAMPLE_RATE,
                preset_config['gain'],
                preset_config['alpha'],
                preset_config['asnr']
            )
            self.post_gain = preset_config['post_gain']

        self.block_config.schedule(
            bandpass_filter=self.bandpass_filter,
            zi_bandpass=self.zi_bandpass,
            nr=self.nr,
            post_gain=self.post_gain,
        )
            
        config = BANDPASS_CONFIG[mode]
        self.log_signal.emit(f"Mode changed to {mode} (BW: {config['low']}-{config['high']} Hz)")
    
    def set_preset(self, preset):
        self.preset = preset
        
        if self.nr and NR_AVAILABLE:
            presets = PRESETS_CW if self.mode == 'CW' else PRESETS_SSB
            preset_config = presets[preset]
            self.nr = spectral_nr.SpectralNoiseReduction(
                SAMPLE_RATE,
                preset_config['gain'],
                preset_config['alpha'],
                preset_config['asnr']
            )
            self.post_gain = preset_config['post_gain']
            self.block_config.schedule(
                nr=self.nr,
                post_gain=self.post_gain,
            )
            self.log_signal.emit(f"Preset changed to {preset} ({self.mode} mode)")
    
    def start_recording(self):
        folder = recordings_dir()
        self.recorder = AsyncMonoRecorder(folder, SAMPLE_RATE, MP3_AVAILABLE)
        self.recorder.start()
        self.recording = True
        self.log_signal.emit("🔴 Recording started")
    
    def stop_recording(self):
        self.recording = False
        recorder = self.recorder
        self.recorder = None
        if recorder is None:
            self.log_signal.emit("⏹️ Recording stopped - No data recorded")
            return None
        
        try:
            filepath, duration, dropped_chunks, conversion_error = recorder.stop()
            filename = filepath.name
            if not duration:
                self.log_signal.emit("⏹️ Recording stopped - No data recorded")
                return None
            self.log_signal.emit(f"⏹️ Saved: {filepath}")
            self.log_signal.emit(f"   Duration: {duration:.1f}s, Format: {filepath.suffix[1:].upper()}")
            if dropped_chunks:
                self.log_signal.emit(f"WARNING: Recording dropped {dropped_chunks} audio blocks")
            if conversion_error:
                self.log_signal.emit(f"WARNING: MP3 conversion failed; WAV retained: {conversion_error}")
            return filename, duration
            
        except Exception as e:
            self.log_signal.emit(f"ERROR saving recording: {e}")
            import traceback
            traceback.print_exc()
            return None


SETTINGS_ORGANIZATION = 'LU2MET'
SETTINGS_APPLICATION = 'LU2MET_NR_Filter'
# Settings key used by releases before the rename; copied once on first start.
LEGACY_SETTINGS_APPLICATION = 'NovaSDR_NR_Filter'


def app_keys(settings):
    """Keys stored by this app only; on macOS allKeys() otherwise includes system-wide defaults."""
    settings.setFallbacksEnabled(False)
    return settings.allKeys()


def migrate_legacy_settings(settings):
    if app_keys(settings):
        return
    legacy = QSettings(SETTINGS_ORGANIZATION, LEGACY_SETTINGS_APPLICATION)
    keys = app_keys(legacy)
    for key in keys:
        settings.setValue(key, legacy.value(key))
    if keys:
        settings.sync()
        logging.info(f'Migrated {len(keys)} settings from {LEGACY_SETTINGS_APPLICATION}')


class UpdateChecker(QObject):
    """Look up the latest GitHub release without blocking the UI.

    Uses a daemon thread so a slow or offline check never delays closing the app;
    the signal is delivered to the window on the Qt main thread.
    """
    update_available = pyqtSignal(str, str)

    def start(self):
        threading.Thread(target=self._run, name='update-check', daemon=True).start()

    def _run(self):
        release = check_for_update(APP_VERSION)
        if release:
            self.update_available.emit(*release)


class LU2METNRWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
        migrate_legacy_settings(self.settings)
        self.processor = AudioProcessor()
        self.processor.log_signal.connect(self.add_log)
        self.init_ui()
        self.load_devices()
        self.load_settings()
        self.level_timer = QTimer(self)
        self.level_timer.timeout.connect(self.update_audio_levels)
        self.level_timer.start(100)
        self.update_checker = UpdateChecker(self)
        self.update_checker.update_available.connect(self.show_update)
        if not is_development(APP_VERSION):
            QTimer.singleShot(2000, self.update_checker.start)

    def show_update(self, tag, url):
        if self.settings.value('updates/dismissed_version') == tag:
            return
        self.available_update = tag
        self.update_label.setText(
            f'New version {tag} available (you have {APP_VERSION}). '
            f'<a href="{url}" style="color: #1e3a8a;">Download</a>'
        )
        self.update_banner.show()
        self.add_log(f'Update available: {tag} - {url}')

    def dismiss_update(self):
        if self.available_update:
            self.settings.setValue('updates/dismissed_version', self.available_update)
        self.update_banner.hide()

    def init_ui(self):
        self.setWindowTitle(f'LU2MET NR Filter {APP_VERSION}')
        self.setGeometry(100, 100, 600, 700)
        self.setMinimumSize(400, 300)  # Minimum window size
        
        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setCentralWidget(scroll)
        
        # Content widget inside scroll area
        content_widget = QWidget()
        scroll.setWidget(content_widget)
        layout = QVBoxLayout(content_widget)

        # Update banner, shown when a newer release is published
        self.update_banner = QWidget()
        self.update_banner.setStyleSheet('background: #f59e0b; border-radius: 6px;')
        banner_layout = QHBoxLayout(self.update_banner)
        banner_layout.setContentsMargins(10, 6, 6, 6)
        self.update_label = QLabel()
        self.update_label.setTextFormat(Qt.RichText)
        self.update_label.setOpenExternalLinks(True)
        self.update_label.setWordWrap(True)
        self.update_label.setStyleSheet('color: #1f2937; font-weight: bold;')
        banner_layout.addWidget(self.update_label, 1)
        dismiss_btn = QPushButton('✕')
        dismiss_btn.setFixedWidth(28)
        dismiss_btn.setToolTip('Hide until the next version')
        dismiss_btn.setStyleSheet('background: transparent; color: #1f2937; border: 0; font-weight: bold;')
        dismiss_btn.clicked.connect(self.dismiss_update)
        banner_layout.addWidget(dismiss_btn)
        self.update_banner.hide()
        self.available_update = None
        layout.addWidget(self.update_banner)

        # Header
        header = QLabel('📻 LU2MET NR Filter')
        header.setFont(QFont('Arial', 16, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet('background: #667eea; color: white; padding: 15px; border-radius: 8px;')
        layout.addWidget(header)
        
        # Status
        self.status_label = QLabel('● Stopped')
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet('color: #ef4444; font-size: 14px; padding: 5px;')
        layout.addWidget(self.status_label)
        
        # Devices
        devices_group = QGroupBox('🎧 Audio Devices')
        devices_layout = QVBoxLayout()
        
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel('Input:'))
        self.input_combo = QComboBox()
        input_layout.addWidget(self.input_combo)
        devices_layout.addLayout(input_layout)
        
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel('Output:'))
        self.output_combo = QComboBox()
        output_layout.addWidget(self.output_combo)
        devices_layout.addLayout(output_layout)
        
        devices_group.setLayout(devices_layout)
        layout.addWidget(devices_group)
        
        # Mode
        mode_group = QGroupBox('📡 Mode')
        mode_layout = QHBoxLayout()
        self.mode_group = QButtonGroup()
        
        self.ssb_radio = QRadioButton('SSB (300-2700 Hz)')
        self.ssb_radio.setChecked(True)
        self.ssb_radio.toggled.connect(self.on_mode_change)
        self.mode_group.addButton(self.ssb_radio)
        mode_layout.addWidget(self.ssb_radio)
        
        self.cw_radio = QRadioButton('CW (600-900 Hz)')
        self.cw_radio.toggled.connect(self.on_mode_change)
        self.mode_group.addButton(self.cw_radio)
        mode_layout.addWidget(self.cw_radio)
        
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # Presets
        preset_group = QGroupBox('🎛️ Noise Reduction')
        preset_layout = QVBoxLayout()
        
        preset_buttons_layout = QHBoxLayout()
        self.preset_group = QButtonGroup()
        
        for preset_name in ['moderate', 'aggressive', 'ultra', 'extreme']:
            radio = QRadioButton(preset_name.capitalize())
            if preset_name == 'extreme':
                radio.setChecked(True)
                radio.setText('Extreme ⭐')
            radio.toggled.connect(lambda checked, p=preset_name: self.on_preset_change(p) if checked else None)
            self.preset_group.addButton(radio)
            preset_buttons_layout.addWidget(radio)
        
        # With no filter checked, only the band-pass filter is applied.
        self.nr_check = QCheckBox('Spectral MMSE (Schmitt/Romanin)')
        self.nr_check.setToolTip(
            'Spectral noise reduction after Schmitt et al. (2002) and Romanin et al. (2009), '
            'tuned by the presets below'
        )
        self.nr_check.setChecked(True)
        self.nr_check.stateChanged.connect(self.on_filters_change)
        preset_layout.addWidget(self.nr_check)

        # The presets belong to the first filter: indent them under it with a guide line.
        self.preset_frame = QFrame()
        preset_frame_layout = QVBoxLayout(self.preset_frame)
        preset_frame_layout.setContentsMargins(12, 0, 0, 0)
        preset_frame_layout.addLayout(preset_buttons_layout)
        
        self.preset_info = QLabel()
        self.preset_info.setStyleSheet(
            'QLabel { color: #6b7280; font-size: 11px; } QLabel:disabled { color: #c4c7cc; }'
        )
        preset_frame_layout.addWidget(self.preset_info)
        self.update_preset_info()
        guide = QFrame()
        guide.setFixedWidth(2)
        guide.setStyleSheet('background-color: #9ca3af;')
        preset_row = QHBoxLayout()
        preset_row.setContentsMargins(9, 0, 0, 4)
        preset_row.addWidget(guide)
        preset_row.addWidget(self.preset_frame, 1)
        preset_layout.addLayout(preset_row)

        self.nr2_check = QCheckBox('OM-LSA (Cohen)')
        self.nr2_check.setToolTip(
            'OM-LSA with IMCRA noise tracking, after I. Cohen (2001, 2003). No settings. '
            'With both filters checked it runs after the first one. Adds about 32 ms of '
            'delay and needs about 2.5 s to learn the noise.'
        )
        self.nr2_check.stateChanged.connect(self.on_filters_change)
        preset_layout.addWidget(self.nr2_check)
        
        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)
        
        # Control
        control_group = QGroupBox('⚙️ Control')
        control_layout = QVBoxLayout()
        
        # Input Gain Control
        gain_layout = QHBoxLayout()
        gain_label = QLabel('DSP Input Trim:')
        gain_layout.addWidget(gain_label)
        
        self.gain_slider = QSlider(Qt.Horizontal)
        self.gain_slider.setMinimum(1)  # 1% minimum
        self.gain_slider.setMaximum(100)  # 100% maximum
        self.gain_slider.setValue(36)  # Approximately -26 dB, matching the previous 5% default.
        self.gain_slider.setTickPosition(QSlider.TicksBelow)
        self.gain_slider.setTickInterval(10)
        self.gain_slider.valueChanged.connect(self.on_gain_change)
        gain_layout.addWidget(self.gain_slider)
        
        self.gain_value_label = QLabel('-25.9 dB')
        self.gain_value_label.setStyleSheet('font-weight: bold; min-width: 68px;')
        gain_layout.addWidget(self.gain_value_label)
        
        control_layout.addLayout(gain_layout)
        
        gain_info = QLabel('DSP input trim: -40 to 0 dB. It cannot undo clipping before capture.')
        gain_info.setStyleSheet('color: #f59e0b; font-size: 10px; padding: 2px;')
        control_layout.addWidget(gain_info)
        
        # Output Volume Control
        volume_layout = QHBoxLayout()
        volume_label = QLabel('Output Volume:')
        volume_layout.addWidget(volume_label)
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMinimum(10)  # 10% minimum
        self.volume_slider.setMaximum(400)  # 400% maximum (4x boost)
        self.volume_slider.setValue(100)  # 100% default
        self.volume_slider.setTickPosition(QSlider.TicksBelow)
        self.volume_slider.setTickInterval(50)
        self.volume_slider.valueChanged.connect(self.on_volume_change)
        volume_layout.addWidget(self.volume_slider)
        
        self.volume_value_label = QLabel('0.0 dB')
        self.volume_value_label.setStyleSheet('font-weight: bold; min-width: 60px;')
        volume_layout.addWidget(self.volume_value_label)
        
        control_layout.addLayout(volume_layout)
        
        volume_info = QLabel('Master level applies to all audio; output peaks are limited.')
        volume_info.setStyleSheet('color: #3b82f6; font-size: 10px; padding: 2px;')
        control_layout.addWidget(volume_info)
        
        switches_row = QHBoxLayout()
        self.tx_mute_check = QCheckBox('Mute during TX')
        self.tx_mute_check.setToolTip(
            'Mute the output while the receiver audio drops during transmit, '
            'and fade it back in afterwards'
        )
        self.tx_mute_check.setChecked(True)
        self.tx_mute_check.stateChanged.connect(self.on_tx_mute_change)
        switches_row.addWidget(self.tx_mute_check)
        switches_row.addStretch(1)
        self.tx_led = QLabel('TX')
        self.tx_led.setAlignment(Qt.AlignCenter)
        self.tx_led.setFixedWidth(48)
        self.tx_led.setToolTip('Lit while the output is muted for transmit')
        self.tx_led.setStyleSheet(led_style(False))
        switches_row.addWidget(self.tx_led)
        control_layout.addLayout(switches_row)

        for label, bar_name, value_name, led_name, led_text in (
            ('IN', 'input_level_bar', 'input_level_value', 'input_clip_led', 'CLIP'),
            ('OUT', 'output_level_bar', 'output_level_value', 'output_limit_led', 'LIMIT'),
        ):
            level_row = QHBoxLayout()
            name_label = QLabel(label)
            name_label.setFixedWidth(40)
            level_row.addWidget(name_label)
            level_bar = QProgressBar()
            level_bar.setRange(0, 60)
            level_bar.setValue(0)
            level_bar.setTextVisible(False)
            level_bar.setFixedHeight(12)
            level_bar.setStyleSheet(level_bar_style(LEVEL_COLOR_OK))
            setattr(self, bar_name, level_bar)
            level_row.addWidget(level_bar, 1)
            value_label = QLabel('RMS -120.0 | PK -120.0 dBFS')
            value_label.setFont(QFont('Courier New', 10))
            value_label.setFixedWidth(225)
            setattr(self, value_name, value_label)
            level_row.addWidget(value_label)
            led = QLabel(led_text)
            led.setAlignment(Qt.AlignCenter)
            led.setFixedWidth(48)
            led.setStyleSheet(led_style(False))
            setattr(self, led_name, led)
            level_row.addWidget(led)
            control_layout.addLayout(level_row)
        
        buttons_layout = QHBoxLayout()
        self.start_btn = QPushButton('▶ Start')
        self.start_btn.clicked.connect(self.start_processing)
        self.start_btn.setStyleSheet('background: #10b981; color: white; padding: 8px; font-weight: bold;')
        buttons_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton('■ Stop')
        self.stop_btn.clicked.connect(self.stop_processing)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet('background: #ef4444; color: white; padding: 8px; font-weight: bold;')
        buttons_layout.addWidget(self.stop_btn)
        
        control_layout.addLayout(buttons_layout)
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # Recording
        rec_group = QGroupBox('🔴 Recording')
        rec_layout = QVBoxLayout()
        
        rec_info = QLabel('Recordings saved as: recording_YYYYMMDD_HHMMSS.mp3')
        rec_info.setStyleSheet('color: #6b7280; font-size: 11px;')
        rec_layout.addWidget(rec_info)
        
        rec_buttons_layout = QHBoxLayout()
        self.rec_start_btn = QPushButton('🔴 Start Recording')
        self.rec_start_btn.clicked.connect(self.start_recording)
        self.rec_start_btn.setEnabled(False)
        self.rec_start_btn.setStyleSheet('background: #dc2626; color: white; padding: 6px; font-weight: bold;')
        rec_buttons_layout.addWidget(self.rec_start_btn)
        
        self.rec_stop_btn = QPushButton('⏹️ Stop Recording')
        self.rec_stop_btn.clicked.connect(self.stop_recording)
        self.rec_stop_btn.setEnabled(False)
        self.rec_stop_btn.setStyleSheet('background: #6b7280; color: white; padding: 6px; font-weight: bold;')
        rec_buttons_layout.addWidget(self.rec_stop_btn)
        
        rec_layout.addLayout(rec_buttons_layout)
        
        # Open folder button
        self.open_folder_btn = QPushButton('📁 Open Recordings Folder')
        self.open_folder_btn.clicked.connect(self.open_recordings_folder)
        self.open_folder_btn.setStyleSheet('background: #3b82f6; color: white; padding: 6px; margin-top: 3px;')
        rec_layout.addWidget(self.open_folder_btn)
        
        rec_group.setLayout(rec_layout)
        layout.addWidget(rec_group)
        
        # Log
        log_group = QGroupBox('📋 Log')
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet('background: #1f2937; color: #10b981; font-family: Courier; font-size: 11px;')
        self.log_text.setMaximumHeight(120)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # Cafecito donation link
        cafecito = QLabel('If you found this useful, <a href="https://cafecito.app/lu2met" style="color: #f59e0b; text-decoration: none; font-weight: bold;">☕ buy me a coffee</a>')
        cafecito.setOpenExternalLinks(True)
        cafecito.setAlignment(Qt.AlignCenter)
        cafecito.setStyleSheet('color: #6b7280; font-size: 13px; padding: 6px;')
        cafecito.setTextFormat(Qt.RichText)
        cafecito.setToolTip('Si te resultó útil, invitame un cafecito')
        layout.addWidget(cafecito)
        
        # Footer with repository link (smaller)
        footer = QLabel('Project source: '
                   '<a href="https://github.com/tomduca/lu2met-nr" style="color: #3b82f6; text-decoration: none;">LU2MET NR Filter on GitHub</a>')
        footer.setOpenExternalLinks(True)
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet('color: #6b7280; font-size: 9px; padding: 2px;')
        footer.setTextFormat(Qt.RichText)
        layout.addWidget(footer)
        
        # Initial log
        self.add_log(f"Noise reduction module: {'✓ Available' if NR_AVAILABLE else '✗ Not available'}")
        self.add_log(f"MP3 recording: {'✓ Available' if MP3_AVAILABLE else '✗ Not available (will use WAV)'}")
    
    def load_devices(self):
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        
        virtual_input = None
        for idx, label in device_choices(devices, hostapis, 'input'):
            self.input_combo.addItem(label, idx)
            if virtual_input is None and any(
                name in label for name in ('BlackHole', 'Loopback', 'CABLE Output')
            ):
                virtual_input = self.input_combo.count() - 1
        if virtual_input is not None:
            self.input_combo.setCurrentIndex(virtual_input)
        
        for idx, label in device_choices(devices, hostapis, 'output'):
            self.output_combo.addItem(label, idx)
        
        self.add_log(f"Loaded {self.input_combo.count()} input and {self.output_combo.count()} output devices")
    
    def update_preset_info(self):
        mode = 'CW' if self.cw_radio.isChecked() else 'SSB'
        presets = PRESETS_CW if mode == 'CW' else PRESETS_SSB
        
        for button in self.preset_group.buttons():
            if button.isChecked():
                preset_name = button.text().lower().replace(' ⭐', '')
                preset = presets[preset_name]
                gain = int(1 / preset['gain'])
                info = f"Gain: 1/{gain}, Alpha: {preset['alpha']}, ASNR: {preset['asnr']} dB, Post-Gain: {preset['post_gain']}x"
                self.preset_info.setText(info)
                break
    
    def on_mode_change(self):
        mode = 'CW' if self.cw_radio.isChecked() else 'SSB'
        if self.processor.running:
            self.processor.set_mode(mode)
        self.update_preset_info()
    
    def on_filters_change(self, _state=None):
        nr_enabled = self.nr_check.isChecked()
        nr2_enabled = self.nr2_check.isChecked()
        self.preset_frame.setEnabled(nr_enabled)
        self.processor.set_filters(nr_enabled, nr2_enabled)
        names = [name for name, on in (('Spectral MMSE', nr_enabled), ('OM-LSA', nr2_enabled)) if on]
        self.add_log(f"Filters: {' + '.join(names) if names else 'band-pass only'}")

    def on_preset_change(self, preset):
        if self.processor.running:
            self.processor.set_preset(preset)
        self.update_preset_info()
    
    def on_gain_change(self, value):
        gain = input_trim_slider_to_gain(value)
        self.processor.input_gain = gain
        self.processor.block_config.schedule(input_gain=gain)
        self.gain_value_label.setText(f'{20 * np.log10(gain):.1f} dB')
        if self.processor.running:
            self.add_log(f"DSP input trim: {20 * np.log10(gain):.1f} dB")
    
    def on_volume_change(self, value):
        log_volume = volume_slider_to_gain(value)
        self.processor.output_volume = log_volume
        self.processor.block_config.schedule(output_volume=log_volume)
        self.volume_value_label.setText(f'{20 * np.log10(log_volume):+.1f} dB')
        if self.processor.running:
            self.add_log(f'Master output: {20 * np.log10(log_volume):+.1f} dB ({log_volume:.2f}x)')

    def update_audio_levels(self):
        input_rms, _, input_hold = self.processor.input_meter.snapshot
        output_rms, _, output_hold = self.processor.output_meter.snapshot
        self.input_level_bar.setValue(max(0, min(60, round(input_rms + 60))))
        self.output_level_bar.setValue(max(0, min(60, round(output_rms + 60))))
        self.input_level_value.setText(f'RMS {input_rms:6.1f} | PK {input_hold:6.1f} dBFS')
        self.output_level_value.setText(f'RMS {output_rms:6.1f} | PK {output_hold:6.1f} dBFS')
        self.input_level_bar.setStyleSheet(level_bar_style(level_color(input_hold)))
        self.output_level_bar.setStyleSheet(level_bar_style(level_color(output_hold)))
        self.input_clip_led.setStyleSheet(led_style(self.processor.input_clipping_seen))
        self.output_limit_led.setStyleSheet(led_style(self.processor.limiter_active_seen))
        tx_active = self.processor.running and self.processor.tx_mute and self.processor.tx_gate.muted
        self.tx_led.setStyleSheet(led_style(tx_active, LEVEL_COLOR_HOT))
    
    def on_tx_mute_change(self, state):
        self.processor.tx_mute = (state == Qt.Checked)
        self.processor.block_config.schedule(tx_mute=self.processor.tx_mute)
        self.add_log(f"Mute during TX: {'on' if self.processor.tx_mute else 'off'}")

    def start_processing(self):
        input_idx = self.input_combo.currentData()
        output_idx = self.output_combo.currentData()
        
        mode = 'CW' if self.cw_radio.isChecked() else 'SSB'
        
        for button in self.preset_group.buttons():
            if button.isChecked():
                preset = button.text().lower().replace(' ⭐', '')
                break
        
        try:
            self.processor.start_processing(input_idx, output_idx, preset, mode)
            
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.rec_start_btn.setEnabled(True)
            self.status_label.setText('● Running')
            self.status_label.setStyleSheet('color: #10b981; font-size: 14px; padding: 5px;')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to start: {str(e)}')
            self.add_log(f"ERROR: {str(e)}")
    
    def stop_processing(self):
        self.processor.stop_processing()
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.rec_start_btn.setEnabled(False)
        self.rec_stop_btn.setEnabled(False)
        self.status_label.setText('● Stopped')
        self.status_label.setStyleSheet('color: #ef4444; font-size: 14px; padding: 5px;')
    
    def start_recording(self):
        self.processor.start_recording()
        self.rec_start_btn.setEnabled(False)
        self.rec_stop_btn.setEnabled(True)
        self.rec_stop_btn.setStyleSheet('background: #dc2626; color: white; padding: 6px; font-weight: bold;')  # Red when active
    
    def stop_recording(self):
        self.processor.stop_recording()
        self.rec_start_btn.setEnabled(True)
        self.rec_stop_btn.setEnabled(False)
        self.rec_stop_btn.setStyleSheet('background: #6b7280; color: white; padding: 6px; font-weight: bold;')  # Gray when disabled
    
    def open_recordings_folder(self):
        """Open the recordings folder in file explorer"""
        import subprocess
        import platform
        
        folder = recordings_dir()
        folder.mkdir(parents=True, exist_ok=True)
        
        try:
            system = platform.system()
            if system == 'Windows':
                subprocess.run(['explorer', str(folder)])
            elif system == 'Darwin':  # macOS
                subprocess.run(['open', str(folder)])
            else:  # Linux
                subprocess.run(['xdg-open', str(folder)])
            self.add_log(f"📁 Opened: {folder}")
        except Exception as e:
            self.add_log(f"❌ Error opening folder: {e}")
    
    def add_log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
    
    def load_settings(self):
        """Load saved settings from QSettings"""
        try:
            # Load mode (SSB/CW)
            mode = self.settings.value('mode', 'SSB')
            if mode == 'CW':
                self.cw_radio.setChecked(True)
            else:
                self.ssb_radio.setChecked(True)
            
            # Load preset
            preset = self.settings.value('preset', 'extreme')
            for button in self.preset_group.buttons():
                button_text = button.text().lower().replace(' ⭐', '')
                if button_text == preset:
                    button.setChecked(True)
                    break
            
            # Load input gain
            if self.settings.contains('audio/input_trim_slider'):
                input_trim = int(self.settings.value('audio/input_trim_slider', 36))
            else:
                legacy_percent = int(self.settings.value('audio/input_gain', 5))
                legacy_gain = min(1.0, max(0.01, legacy_percent / 100.0))
                legacy_db = 20.0 * np.log10(legacy_gain)
                input_trim = round(1.0 + ((legacy_db + 40.0) / 40.0) * 99.0)
            self.gain_slider.setValue(input_trim)
            
            # Load output volume
            output_volume = int(self.settings.value('audio/output_volume', 100))
            self.volume_slider.setValue(output_volume)
            
            if self.settings.contains('audio/bypass'):
                # Bypass was removed; no filter checked is the closest to it.
                if self.settings.value('audio/bypass', False, type=bool):
                    self.settings.setValue('audio/nr_enabled', False)
                    self.settings.setValue('audio/nr2_enabled', False)
                self.settings.remove('audio/bypass')
            self.tx_mute_check.setChecked(self.settings.value('audio/tx_mute', True, type=bool))
            self.nr_check.setChecked(self.settings.value('audio/nr_enabled', True, type=bool))
            self.nr2_check.setChecked(self.settings.value('audio/nr2_enabled', False, type=bool))
            
            # Load input/output devices (by name)
            input_device = self.settings.value('audio/input_device', '')
            output_device = self.settings.value('audio/output_device', '')
            
            for combo, saved in ((self.input_combo, input_device), (self.output_combo, output_device)):
                if saved:
                    labels = [combo.itemText(i) for i in range(combo.count())]
                    index = find_device_label(labels, saved)
                    if index >= 0:
                        combo.setCurrentIndex(index)
            
            self.add_log('✓ Settings loaded')
        except Exception as e:
            self.add_log(f'⚠️ Could not load settings: {e}')
    
    def save_settings(self):
        """Save current settings to QSettings"""
        try:
            # Save input/output devices
            self.settings.setValue('audio/input_device', self.input_combo.currentText())
            self.settings.setValue('audio/output_device', self.output_combo.currentText())
            
            # Save mode
            mode = 'CW' if self.cw_radio.isChecked() else 'SSB'
            self.settings.setValue('mode', mode)
            
            # Save preset
            for button in self.preset_group.buttons():
                if button.isChecked():
                    preset = button.text().lower().replace(' ⭐', '')
                    self.settings.setValue('preset', preset)
                    break
            
            # Save input gain
            self.settings.setValue('audio/input_trim_slider', self.gain_slider.value())
            
            # Save output volume
            self.settings.setValue('audio/output_volume', self.volume_slider.value())
            
            self.settings.setValue('audio/tx_mute', self.tx_mute_check.isChecked())
            self.settings.setValue('audio/nr_enabled', self.nr_check.isChecked())
            self.settings.setValue('audio/nr2_enabled', self.nr2_check.isChecked())
            
            # Sync to disk
            self.settings.sync()
            
            self.add_log('✓ Settings saved')
        except Exception as e:
            self.add_log(f'⚠️ Could not save settings: {e}')
    
    def closeEvent(self, event):
        """Override close event to save settings before exit"""
        self.save_settings()
        if self.processor.running:
            self.processor.stop_processing()
        event.accept()


def self_test():
    """Check that a packaged build contains a working DSP chain.

    Used by the build scripts on the frozen executable; returns an exit code.
    """
    try:
        if not NR_AVAILABLE:
            raise RuntimeError('spectral_nr extension is not available')
        logging.info('Self-test: DSP chain')
        rng = np.random.default_rng(7)
        block = rng.normal(0, 0.1, BLOCK_SIZE * 4).astype(np.float32)
        band = BANDPASS_CONFIG['SSB']
        sos = signal.butter(
            4, [band['low'] / (SAMPLE_RATE / 2), band['high'] / (SAMPLE_RATE / 2)],
            btype='band', output='sos',
        )
        filtered = signal.sosfilt(sos, block)
        preset = PRESETS_SSB['extreme']
        nr = spectral_nr.SpectralNoiseReduction(
            SAMPLE_RATE, preset['gain'], preset['alpha'], preset['asnr']
        )
        output = nr.process(filtered.astype(np.float32))
        peak = float(np.max(np.abs(output)))
        # The extreme preset scales by 1/16384; unfiltered samples would be ~0.1+.
        if output.shape != block.shape or not 0.0 < peak < 0.01:
            raise RuntimeError(f'Unexpected NR output: shape={output.shape} peak={peak}')
        logging.info('Self-test: NR2')
        nr2 = spectral_nr.OmlsaNoiseReduction(SAMPLE_RATE)
        output2 = nr2.process(filtered.astype(np.float32))
        if output2.shape != block.shape or not np.all(np.isfinite(output2)):
            raise RuntimeError(f'Unexpected NR2 output: shape={output2.shape}')
        logging.info(f'Self-test: version {APP_VERSION}, TLS certificates')
        if getattr(sys, 'frozen', False):
            if APP_VERSION == 'dev':
                raise RuntimeError('app_version.txt is missing from the package')
            import certifi
            import ssl
            ssl.create_default_context(cafile=certifi.where())
        logging.info('Self-test: audio devices')
        sd.query_devices()
        logging.info('Self-test: Qt')
        app = QApplication.instance() or QApplication(['self-test'])
        app.processEvents()
    except Exception as e:
        logging.error(f'Self-test failed: {e}', exc_info=True)
        print(f'Self-test failed: {e}')
        return 1
    logging.info(f'Self-test OK (NR peak {peak:.6f})')
    print(f'Self-test OK (NR peak {peak:.6f})')
    return 0


def main():
    if '--self-test' in sys.argv:
        sys.exit(self_test())

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Dark palette
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)
    
    gui = LU2METNRWindow()
    gui.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
