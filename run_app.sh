#!/usr/bin/env bash
# AGY Short-Drama Studio launcher for macOS / Linux.
# First run: creates .venv and installs Python packages. Later runs start at once.
set -e
cd "$(dirname "$0")"

echo "AGY Short-Drama Studio"

export TK_SILENCE_DEPRECATION=1

# 1. Find a Python 3.9+ whose Tkinter uses Tk 8.6 or newer.
#    Apple's built-in /usr/bin/python3 ships Tk 8.5, which shows a blank or
#    invisible window on recent macOS, so it is skipped.
GOOD_TK='import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 9) and tkinter.TkVersion >= 8.6 else 1)'
CANDIDATES=""
for v in 3.13 3.12 3.11 3.10 3.14 3.9; do
    CANDIDATES="$CANDIDATES /Library/Frameworks/Python.framework/Versions/$v/bin/python3"
    CANDIDATES="$CANDIDATES /opt/homebrew/bin/python$v /usr/local/bin/python$v"
done
CANDIDATES="$CANDIDATES /opt/homebrew/bin/python3 /usr/local/bin/python3"
for c in python3.13 python3.12 python3.11 python3.10 python3 python; do
    p=$(command -v "$c" 2>/dev/null || true)
    [ -n "$p" ] && CANDIDATES="$CANDIDATES $p"
done

PY=""
OLD_TK=""
NO_TK=""
for c in $CANDIDATES; do
    [ -x "$c" ] || continue
    if "$c" -c "$GOOD_TK" >/dev/null 2>&1; then
        PY="$c"; break
    elif "$c" -c 'import tkinter' >/dev/null 2>&1; then
        OLD_TK="$c"
    else
        NO_TK="$c"
    fi
done

if [ -z "$PY" ]; then
    echo
    echo "LỖI: Không tìm thấy Python có giao diện Tk 8.6 trở lên."
    if [ -n "$OLD_TK" ]; then
        echo "Máy chỉ có Python của Apple ($OLD_TK) với Tk 8.5 cũ: app sẽ không hiện cửa sổ."
    fi
    echo "Cách sửa (chọn 1):"
    echo "  A. Cài Python từ https://www.python.org/downloads/macos/ (bản có sẵn Tk mới), rồi chạy lại."
    if command -v brew >/dev/null 2>&1; then
        echo "  B. brew install python@3.12 python-tk@3.12   rồi chạy lại."
    fi
    if [ -n "$NO_TK" ]; then
        echo "  (Python $NO_TK thiếu Tkinter. Với Homebrew: brew install python-tk@<phiên bản>)"
    fi
    exit 1
fi
echo "Dùng Python: $PY ($("$PY" -c 'import sys, tkinter; print(f"Python {sys.version.split()[0]}, Tk {tkinter.TkVersion}")'))"

# 2. Private environment + packages. Rebuild it if it was made with another Python.
VPY=".venv/bin/python"
if [ -x "$VPY" ]; then
    if [ "$(cat .venv/.base_python 2>/dev/null)" != "$PY" ] || ! "$VPY" -c "$GOOD_TK" >/dev/null 2>&1; then
        echo "Môi trường .venv cũ dùng Python khác, đang tạo lại..."
        rm -rf .venv
    fi
fi
if [ ! -x "$VPY" ]; then
    echo "Đang tạo môi trường .venv ..."
    "$PY" -m venv .venv
    echo "$PY" > .venv/.base_python
fi

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
