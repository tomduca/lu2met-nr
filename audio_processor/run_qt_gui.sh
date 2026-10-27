#!/bin/bash
# Run LU2MET NR Filter - PyQt5 Native GUI

cd "$(dirname "$0")"
source venv/bin/activate

echo "Starting LU2MET NR Filter (Native GUI)..."
echo ""

python3 lu2met_nr_gui.py
