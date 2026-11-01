"""
agy_connector.py
AGY CLI integration layer for Windows and macOS.
Handles CLI discovery, connection diagnostics, and interactive Google authentication terminal.
"""

import os
import sys
import shutil
import subprocess

def find_agy_executable():
    """Locates the agy CLI binary on the current OS."""
    # 1. Search in PATH
    path = shutil.which("agy") or shutil.which("agy.exe")
    if path:
        return path

    # 2. Check well-known install locations
    home = os.path.expanduser("~")
    candidates = [
        # Windows
        os.path.join(home, "AppData", "Local", "agy", "bin", "agy.exe"),
        os.path.join(home, ".gemini", "antigravity-cli", "agy.exe"),
        # macOS / Linux
        os.path.join(home, ".local", "bin", "agy"),
        os.path.join(home, "bin", "agy"),
        "/usr/local/bin/agy",
        "/opt/homebrew/bin/agy"
    ]
    for c in candidates:
        if os.path.exists(c) and os.path.isfile(c):
            return c
    return None

def test_agy_connection():
    """
    Tests connectivity to AGY CLI.
    Returns (success: bool, message: str, version: str)
    """
    agy_path = find_agy_executable()
    if not agy_path:
        return False, "Không tìm thấy AGY CLI trong hệ thống. Vui lòng cài đặt agy.", ""

    try:
        res = subprocess.run(
            [agy_path, "--version"],
            capture_output=True,
            text=True,
            timeout=8
        )
        if res.returncode == 0:
            version_str = res.stdout.strip()
            return True, f"Kết nối thành công! AGY CLI v{version_str}", version_str
        else:
            err = res.stderr.strip() or f"Mã lỗi: {res.returncode}"
            return False, f"Lỗi khởi chạy AGY: {err}", ""
    except subprocess.TimeoutExpired:
        return False, "Hết thời gian chờ phản hồi từ AGY CLI.", ""
    except Exception as e:
        return False, f"Lỗi kết nối: {str(e)}", ""

def launch_login_terminal():
    """
    Opens an interactive terminal window executing AGY to trigger
    Google Account OAuth authentication in the default web browser.
    """
    agy_path = find_agy_executable() or "agy"

    try:
        if sys.platform == "win32":
            # Launch CMD window that runs agy and stays open
            cmd_line = f'start "AGY Authentication & Setup" cmd.exe /k "{agy_path}"'
            subprocess.Popen(cmd_line, shell=True)
            return True, "Đã mở cửa sổ Terminal. Vui lòng làm theo hướng dẫn trên màn hình và đăng nhập tài khoản Google trên trình duyệt."

        elif sys.platform == "darwin":
            # Launch macOS Terminal.app running agy
            apple_script = f'''
            tell application "Terminal"
                activate
                do script "{agy_path}"
            end tell
            '''
            subprocess.run(["osascript", "-e", apple_script], check=True)
            return True, "Đã mở Terminal.app. Vui lòng đăng nhập Google trên trình duyệt theo hướng dẫn."

        else:
            # Linux fallback
            terms = ["gnome-terminal", "x-terminal-emulator", "konsole", "xfce4-terminal", "xterm"]
            for t in terms:
                if shutil.which(t):
                    subprocess.Popen([t, "-e", agy_path])
                    return True, "Đã mở Terminal đăng nhập."
            return False, "Không tìm thấy chương trình Terminal tương thích."
    except Exception as e:
        return False, f"Không thể mở cửa sổ đăng nhập: {str(e)}"
