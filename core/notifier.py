"""
notifier.py
Cross-platform desktop notifications, audio chimes, and file explorer integration
Compatible with Windows, macOS, and Linux without any external pip packages.
"""

import os
import sys
import subprocess

def send_notification(title, message, is_success=True):
    """Sends native desktop notification and plays audio alert."""
    try:
        if sys.platform == "win32":
            # 1. Play sound
            try:
                import winsound
                sound_type = winsound.MB_ICONASTERISK if is_success else winsound.MB_ICONHAND
                winsound.MessageBeep(sound_type)
            except Exception:
                pass

            # 2. PowerShell Balloon / Toast
            escaped_title = title.replace("'", "''").replace('"', '`"')
            escaped_msg = message.replace("'", "''").replace('"', '`"')
            ps_script = f"""
            Add-Type -AssemblyName System.Windows.Forms
            $global:balloon = New-Object System.Windows.Forms.NotifyIcon
            $icon_type = if ('{1 if is_success else 0}' -eq '1') {{ [System.Windows.Forms.ToolTipIcon]::Info }} else {{ [System.Windows.Forms.ToolTipIcon]::Error }}
            $balloon.Icon = [System.Drawing.SystemIcons]::Application
            $balloon.BalloonTipIcon = $icon_type
            $balloon.BalloonTipTitle = '{escaped_title}'
            $balloon.BalloonTipText = '{escaped_msg}'
            $balloon.Visible = $True
            $balloon.ShowBalloonTip(5000)
            """
            subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        elif sys.platform == "darwin":
            # macOS native notification via AppleScript
            sound_name = "Glass" if is_success else "Basso"
            escaped_title = title.replace('"', '\\"')
            escaped_msg = message.replace('"', '\\"')
            cmd = f'display notification "{escaped_msg}" with title "{escaped_title}" sound name "{sound_name}"'
            subprocess.run(["osascript", "-e", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        else:
            # Linux notify-send
            subprocess.run(["notify-send", title, message], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Notification error: {e}")

def reveal_in_file_manager(file_path):
    """Opens File Explorer / Finder with the file selected."""
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        return False
    try:
        if sys.platform == "win32":
            subprocess.run(["explorer.exe", f"/select,{abs_path}"], check=False)
        elif sys.platform == "darwin":
            subprocess.run(["open", "-R", abs_path], check=False)
        else:
            folder = os.path.dirname(abs_path)
            subprocess.run(["xdg-open", folder], check=False)
        return True
    except Exception as e:
        print(f"Error revealing file: {e}")
        return False

def open_media_file(file_path):
    """Launches the default system media player for the video."""
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        return False
    try:
        if sys.platform == "win32":
            os.startfile(abs_path)
        elif sys.platform == "darwin":
            subprocess.run(["open", abs_path], check=False)
        else:
            subprocess.run(["xdg-open", abs_path], check=False)
        return True
    except Exception as e:
        print(f"Error opening media: {e}")
        return False
