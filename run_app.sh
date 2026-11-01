#!/usr/bin/env bash
# AGY Short-Drama Studio launcher for macOS / Linux.
# First run: creates .venv and installs Python packages. Later runs start at once.
set -e
cd "$(dirname "$0")"

echo "AGY Short-Drama Studio"

# 1. Find Python 3
PY=""
for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
        PY="$c"; break
    fi
done
if [ -z "$PY" ]; then
    echo "LỖI: Không tìm thấy Python 3.9 trở lên."
    echo "Cài Python từ https://www.python.org/downloads/ rồi chạy lại."
    exit 1
fi

# 2. Tkinter (GUI) must be present
if ! "$PY" -c 'import tkinter' 2>/dev/null; then
    echo "LỖI: Python này thiếu Tkinter (thư viện giao diện)."
    if command -v brew >/dev/null 2>&1; then
        VER=$("$PY" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
        echo "Chạy lệnh sau rồi mở lại app:  brew install python-tk@$VER"
    else
        echo "Cài Python từ https://www.python.org/downloads/ (bản này có sẵn Tkinter)."
    fi
    exit 1
fi

# 3. Private environment + packages
if [ ! -x ".venv/bin/python" ]; then
    echo "Lần chạy đầu: đang tạo môi trường .venv ..."
    "$PY" -m venv .venv
fi
VPY=".venv/bin/python"

STAMP=".venv/.requirements.stamp"
if [ ! -f "$STAMP" ] || ! cmp -s requirements.txt "$STAMP"; then
    echo "Đang cài thư viện (opencv, numpy, Pillow). Lần đầu mất vài phút..."
    "$VPY" -m pip install --upgrade pip >/dev/null
    "$VPY" -m pip install -r requirements.txt
    echo "Đang cài faster-whisper để tạo sub (không bắt buộc)..."
    if ! "$VPY" -m pip install faster-whisper; then
        echo "CẢNH BÁO: Không cài được faster-whisper. App vẫn chạy, nhưng có thể không tạo được sub."
    fi
    cp requirements.txt "$STAMP"
fi

# 4. ffmpeg is needed to cut and render video
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "CẢNH BÁO: Chưa có ffmpeg. App mở được nhưng sẽ không xuất được video."
    if command -v brew >/dev/null 2>&1; then
        echo "Cài bằng lệnh:  brew install ffmpeg"
    else
        echo "Cài Homebrew (https://brew.sh) rồi chạy:  brew install ffmpeg"
    fi
fi

exec "$VPY" app.py "$@"
