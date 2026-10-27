#!/bin/bash
# LU2MET NR Filter - Web Interface
# Simple web-based interface accessible from browser

cd "$(dirname "$0")"
source venv/bin/activate

# Install dependencies if not present
pip install flask pydub > /dev/null 2>&1

echo "Starting LU2MET NR Filter Web Interface..."
echo ""
echo "Open your browser at: http://localhost:5001"
echo ""

python3 audio_processor_web.py
