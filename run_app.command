#!/bin/bash
cd "$(dirname "$0")"
echo "Starting AGY Short-Drama Studio on macOS..."
if command -v python3 &>/dev/null; then
    python3 app.py
else
    python app.py
fi
