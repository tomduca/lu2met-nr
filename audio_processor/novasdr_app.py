#!/usr/bin/env python3
"""
NovaSDR Audio Processor - Standalone Application Wrapper
Starts Flask server and opens browser automatically
Auto-shuts down when browser window is closed
"""

import sys
import webbrowser
import threading
import time
import os
import signal
import psutil
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import the web application
from audio_processor_web import app, log, NOVASDR_AVAILABLE, MP3_AVAILABLE

# Global flag for shutdown
shutdown_flag = threading.Event()
chrome_pid = None

def monitor_browser():
    """Monitor browser window and shutdown when closed"""
    global chrome_pid

    # Wait for Chrome to start
    time.sleep(3)

    # Find Chrome process with our URL
    url_marker = 'localhost:5001'

    while not shutdown_flag.is_set():
        found = False
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'Chrome' in proc.info['name']:
                        cmdline = proc.info.get('cmdline', [])
                        if cmdline and any(url_marker in str(arg) for arg in cmdline):
                            found = True
                            chrome_pid = proc.info['pid']
                            break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if not found and chrome_pid:
                # Chrome window was closed
                print("\n\nBrowser window closed. Shutting down...")
                shutdown_flag.set()
                os.kill(os.getpid(), signal.SIGINT)
                break

        except Exception as e:
            pass

        time.sleep(2)

def open_browser():
    """Open browser in new window (app mode) after short delay"""
    time.sleep(1.5)

    # Try to open in app mode (new window, no tabs/address bar)
    import platform
    import subprocess

    url = 'http://localhost:5001'
    system = platform.system()

    try:
        if system == 'Darwin':  # macOS
            # Open in Chrome app mode (looks like native app)
            subprocess.Popen([
                'open', '-na', 'Google Chrome', '--args',
                '--app=' + url,
                '--window-size=800,900',
                '--window-position=100,100'
            ])

            # Start monitoring thread
            monitor_thread = threading.Thread(target=monitor_browser, daemon=True)
            monitor_thread.start()

        elif system == 'Windows':
            # Try Chrome app mode on Windows
            chrome_path = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
            proc = subprocess.Popen([
                chrome_path,
                '--app=' + url,
                '--window-size=800,900'
            ])

            # Start monitoring thread
            monitor_thread = threading.Thread(target=monitor_browser, daemon=True)
            monitor_thread.start()
        else:
            # Fallback to default browser
            webbrowser.open_new(url)
    except:
        # If Chrome not available, open in new window with default browser
        webbrowser.open_new(url)

def main():
    """Main entry point for standalone app"""
    print("=" * 60)
    print("NovaSDR Audio Processor - Standalone Application")
    print("=" * 60)
    print()
    log("NovaSDR Audio Processor Starting...")
    log(f"NovaSDR module: {'✓ Available' if NOVASDR_AVAILABLE else '✗ Not available'}")
    log(f"MP3 recording: {'✓ Available' if MP3_AVAILABLE else '✗ Not available (will use WAV)'}")
    print()
    print("Opening browser at: http://localhost:5001")
    print()
    print("To stop: Close the browser window or press Ctrl+C")
    print("=" * 60)
    print()

    # Open browser in background thread
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    # Start Flask app
    try:
        app.run(debug=False, host='0.0.0.0', port=5001, use_reloader=False, threaded=True)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        print("\n\nShutting down NovaSDR Audio Processor...")
        print("73!")
        shutdown_flag.set()

if __name__ == '__main__':
    main()
