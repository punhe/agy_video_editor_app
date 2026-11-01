"""
engine.py
Modular Video Editing Engine for Short-Drama & Reels.
Features real-time progress callbacks, stage diagnostics, cancellation support,
and GPU NVENC hardware acceleration.
"""

import os
import sys
import subprocess
import threading
import time
import cv2
import numpy as np
import wave
from PIL import Image, ImageDraw, ImageFont

class VideoEditorEngine:
    def __init__(self, log_callback=None, progress_callback=None):
        self.log_callback = log_callback or (lambda text: print(text))
        self.progress_callback = progress_callback or (lambda pct, msg: None)
        self._stop_event = threading.Event()
        self.app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cache_dir = os.path.join(self.app_dir, ".cache_sfx")
        os.makedirs(self.cache_dir, exist_ok=True)

    def cancel(self):
        """Signals the processing pipeline to abort cleanly."""
        self._stop_event.set()

    def is_cancelled(self):
        return self._stop_event.is_set()

    def log(self, text):
        self.log_callback(text)

    def update_progress(self, pct, msg):
        self.progress_callback(min(100, max(0, int(pct))), msg)

    # -------------------------------------------------------------
    # Hardware & Specs Diagnostics
    # -------------------------------------------------------------
    def check_encoder(self):
        """Detects whether NVIDIA NVENC hardware acceleration is available."""
        try:
            res = subprocess.run(
                ['ffmpeg', '-encoders'],
                capture_output=True, text=True, timeout=5
            )
            if 'h264_nvenc' in res.stdout:
                return 'h264_nvenc', ['-preset', 'p5', '-cq', '18']
        except Exception:
            pass
        return 'libx264', ['-preset', 'veryfast', '-crf', '20']

    def get_video_specs(self, video_path):
        """Reads width, height, fps, total frames, and duration."""
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        dur = total_frames / fps if fps > 0 else 0
        return {"width": w, "height": h, "fps": fps, "frames": total_frames, "duration": dur}

    # -------------------------------------------------------------
    # Audio Synthesis: Whoosh & Sub-bass 808 Boom Hit
    # -------------------------------------------------------------
    def get_or_generate_sfx(self):
        sr = 44100
        boom_path = os.path.join(self.cache_dir, "boom_808.wav")
        whoosh_path = os.path.join(self.cache_dir, "whoosh_clean.wav")

        if not os.path.exists(boom_path):
            t = np.linspace(0, 2.0, int(sr * 2.0), endpoint=False)
            freq = 38.0 + (130.0 - 38.0) * np.exp(-3.5 * t)
            phase = 2 * np.pi * np.cumsum(freq) / sr
            sine = np.sin(phase) + 0.3 * np.sin(2 * phase)
            punch = np.random.normal(0, 0.4, len(t)) * np.exp(-40 * t)
            punch = np.convolve(punch, np.ones(20)/20, mode='same')
            env = (1 - np.exp(-t / 0.008)) * np.exp(-1.8 * t)
            boom = (sine * 0.8 + punch * 0.4) * env
            boom = (boom / np.max(np.abs(boom)) * 0.85 * 32767).astype(np.int16)
            with wave.open(boom_path, 'wb') as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
                wf.writeframes(boom.tobytes())

        if not os.path.exists(whoosh_path):
            t = np.linspace(0, 0.8, int(sr * 0.8), endpoint=False)
            noise = np.random.normal(0, 0.5, len(t))
            env = np.exp(-((t - 0.4) ** 2) / (2 * (0.12 ** 2)))
            whoosh = np.convolve(noise * env, np.ones(30)/30, mode='same')
            whoosh = (whoosh / np.max(np.abs(whoosh)) * 0.75 * 32767).astype(np.int16)
            with wave.open(whoosh_path, 'wb') as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
                wf.writeframes(whoosh.tobytes())

        return boom_path, whoosh_path

    # -------------------------------------------------------------
    # Scene Cut Detection
    # -------------------------------------------------------------
    def detect_cuts(self, video_path):
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        cuts = [0]
        prev_hist = None
        frame_idx = 0

        while cap.isOpened() and not self.is_cancelled():
            ret, frame = cap.read()
            if not ret: break
            if frame_idx % 2 == 0:
                small = cv2.resize(frame, (180, 320))
                hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
                hist = cv2.calcHist([hsv], [0, 1], None, [30, 32], [0, 180, 0, 256])
                cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
                if prev_hist is not None:
                    diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA)
                    if diff > 0.40:
                        cuts.append(frame_idx)
                prev_hist = hist
            frame_idx += 1
        cap.release()
        if cuts[-1] != total_frames:
            cuts.append(total_frames)
        return cuts, fps, total_frames

    # -------------------------------------------------------------
    # Dialogue Transcription via Whisper
    # -------------------------------------------------------------
    def transcribe(self, video_path, temp_wav):
        subprocess.run(['ffmpeg', '-y', '-i', video_path, '-vn', '-ac', '1', '-ar', '16000', temp_wav],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with wave.open(temp_wav, 'rb') as wf:
            audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0

        try:
            from faster_whisper import WhisperModel
            model = WhisperModel("base", device="cpu", compute_type="int8")
            segments, info = model.transcribe(audio, word_timestamps=True)
            subs = []
            for s in segments:
                text = s.text.strip()
                if len(text) > 0:
                    subs.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": text})
            return subs
        except Exception as e:
            self.log(f"[Cảnh báo] Không thể dùng faster-whisper ({e}), bỏ qua auto-transcribe.")
            return []

    # -------------------------------------------------------------
    # Master Processing Execution
    # -------------------------------------------------------------
    def process_video(self, input_path, output_path, mode="hook-and-polish",
                      sub_mode="en", enable_sfx=True, enable_pacing=True):
        self._stop_event.clear()
        start_time = time.time()
        self.log(f"=== BẮT ĐẦU XỬ LÝ: {os.path.basename(input_path)} ===")
        self.update_progress(5, "Đang nạp video & kiểm tra phần cứng...")

        specs = self.get_video_specs(input_path)
        self.log(f"Thông số gốc: {specs['width']}x{specs['height']} @ {specs['fps']:.1f}fps, {specs['duration']:.2f}s")

        encoder, enc_args = self.check_encoder()
        self.log(f"Trình mã hóa video: {encoder} ({'NVIDIA RTX GPU' if 'nvenc' in encoder else 'CPU x264'})")

        target_w, target_h = 1080, 1920
        fps = specs['fps'] if specs['fps'] > 0 else 30.0
        dur = specs['duration']

        # Determine In-point and Out-point
        in_sec = 0.0
        out_sec = dur

        if mode in ["hook-and-polish", "hook-only"] and dur > 35.0:
            self.update_progress(15, "Đang quét chuyển cảnh để tìm Hook 30s cao trào...")
            cuts, c_fps, total_f = self.detect_cuts(input_path)
            self.log(f"Đã phát hiện {len(cuts)} điểm chuyển cảnh trong tệp.")

            # Find best 25-35s window
            ideal_dur = 30.0
            best_in, best_out = 0, total_f
            min_f, max_f = int(24.0 * fps), int(36.0 * fps)
            ideal_f = int(ideal_dur * fps)
            best_diff = 999999

            for i in range(len(cuts)):
                for j in range(i + 1, len(cuts)):
                    span = cuts[j] - cuts[i]
                    if min_f <= span <= max_f:
                        diff = abs(span - ideal_f)
                        if diff < best_diff:
                            best_diff = diff
                            best_in = cuts[i]
                            best_out = cuts[j]

            in_sec = best_in / fps
            out_sec = best_out / fps
            self.log(f"Khóa Hook vàng: {in_sec:.2f}s -> {out_sec:.2f}s ({out_sec - in_sec:.2f}s)")
        else:
            self.log(f"Chế độ {mode}: Giữ trọn vẹn mạch video ({dur:.2f}s).")

        clip_dur = out_sec - in_sec
        clip_frames = int(clip_dur * fps)

        if self.is_cancelled(): return False, "Đã hủy bởi người dùng."

        # Step 2: Audio Extraction & Subtitle Transcription
        self.update_progress(25, "Đang nhận diện giọng thoại & xây dựng phụ đề...")
        temp_audio_orig = os.path.join(self.cache_dir, f"_temp_orig_{int(time.time())}.wav")
        temp_master_audio = os.path.join(self.cache_dir, f"_temp_master_{int(time.time())}.wav")

        # Extract audio chunk
        subprocess.run([
            'ffmpeg', '-y', '-ss', f"{in_sec:.4f}", '-to', f"{out_sec:.4f}",
            '-i', input_path, '-vn', '-ac', '2', '-ar', '44100', temp_audio_orig
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Transcribe
        subs = []
        if sub_mode != "none":
            temp_16k = os.path.join(self.cache_dir, f"_temp_16k_{int(time.time())}.wav")
            subs = self.transcribe(input_path, temp_16k)
            try: os.remove(temp_16k)
            except Exception: pass

            # Re-offset subtitles to clip relative time
            rel_subs = []
            for s in subs:
                if s["end"] > in_sec and s["start"] < out_sec:
                    rel_subs.append({
                        "start": max(0.0, s["start"] - in_sec),
                        "end": min(clip_dur, s["end"] - in_sec),
                        "text": s["text"]
                    })
            subs = rel_subs
            self.log(f"Đã tạo {len(subs)} câu phụ đề tiếng Anh tự động.")

        if self.is_cancelled(): return False, "Đã hủy bởi người dùng."

        # Step 3: Audio Mastering & SFX
        self.update_progress(45, "Đang phối âm thanh & hiệu ứng chuyển cảnh...")
        with wave.open(temp_audio_orig, 'rb') as wf:
            sr = wf.getframerate()
            orig_audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
            if wf.getnchannels() == 2:
                orig_audio = orig_audio.reshape(-1, 2)
            else:
                orig_audio = np.column_stack([orig_audio, orig_audio])

        total_audio_samples = len(orig_audio)
        sfx_layer = np.zeros_like(orig_audio)

        if enable_sfx:
            boom_file, whoosh_file = self.get_or_generate_sfx()
            with wave.open(whoosh_file, 'rb') as wf:
                whoosh_data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
                whoosh_data = np.column_stack([whoosh_data, whoosh_data])
            with wave.open(boom_file, 'rb') as wf:
                boom_data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
                boom_data = np.column_stack([boom_data, boom_data])

            # Add whoosh near start
            s0 = int(0.7 * sr)
            e0 = min(s0 + len(whoosh_data), total_audio_samples)
            if s0 < total_audio_samples:
                sfx_layer[s0:e0] += whoosh_data[:e0 - s0] * 0.35

            # Add boom hit midway or at climax (e.g. 15s)
            mid_t = clip_dur * 0.5
            s1 = int(mid_t * sr)
            e1 = min(s1 + len(boom_data), total_audio_samples)
            if s1 < total_audio_samples:
                sfx_layer[s1:e1] += boom_data[:e1 - s1] * 0.65

        # Final mix with soft limiter
        mixed_audio = orig_audio * 1.05 + sfx_layer
        peak = np.max(np.abs(mixed_audio))
        if peak > 0.95:
            mixed_audio = np.tanh(mixed_audio / 0.95) * 0.95

        out_i16 = (mixed_audio * 32767).astype(np.int16)
        with wave.open(temp_master_audio, 'wb') as wf:
            wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(sr)
            wf.writeframes(out_i16.tobytes())

        if self.is_cancelled(): return False, "Đã hủy bởi người dùng."

        # Step 4: Prepare Subtitle Cards (English Frosted Glass Capsule)
        self.update_progress(55, "Đang dựng khung phụ đề viên thuốc kính mờ...")
        font_size = int(target_h * 0.020) # 38px on 1920
        font_path = r'C:\Windows\Fonts\arialbd.ttf' if sys.platform == 'win32' else '/Library/Fonts/Arial Bold.ttf'
        try:
            font = ImageFont.truetype(font_path, font_size)
        except Exception:
            font = ImageFont.load_default()

        dummy = Image.new('RGBA', (1, 1))
        d_dummy = ImageDraw.Draw(dummy)
        cards = []

        for s in subs:
            text = s["text"].strip()
            # Wrap long text
            if len(text) > 40 and "\n" not in text:
                wds = text.split()
                mid = len(wds) // 2
                text = " ".join(wds[:mid]) + "\n" + " ".join(wds[mid:])

            b = d_dummy.multiline_textbbox((0, 0), text, font=font, align='center')
            tw, th = b[2] - b[0], b[3] - b[1]
            pad_x, pad_y = 42, 20
            bw, bh = int(tw + pad_x * 2), int(th + pad_y * 2)

            cx = target_w // 2
            cy = int(target_h * 0.797) # Y = 1530 Safe Zone

            x0 = max(0, cx - bw // 2)
            y0 = max(0, cy - bh // 2)
            x1 = min(target_w, x0 + bw)
            y1 = min(target_h, y0 + bh)
            bw, bh = x1 - x0, y1 - y0

            box_img = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
            draw = ImageDraw.Draw(box_img)

            # Frosted glass capsule
            draw.rounded_rectangle([3, 5, bw - 3, bh - 3], radius=24, fill=(0, 0, 0, 130))
            draw.rounded_rectangle([1, 1, bw - 3, bh - 5], radius=24, fill=(14, 14, 20, 252),
                                   outline=(255, 255, 255, 75), width=2)
            draw.multiline_text((bw // 2, pad_y), text, font=font, fill=(250, 250, 255, 255),
                               stroke_width=2, stroke_fill=(0, 0, 0, 255), align='center', anchor='ma')

            rgba = np.array(box_img, dtype=np.float32)
            cards.append({
                "start": s["start"], "end": s["end"],
                "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                "alpha": (rgba[:, :, 3] / 255.0)[:, :, None],
                "bgr": rgba[:, :, [2, 1, 0]]
            })

        # Step 5: Render Video with Visual Pacing & GPU Acceleration
        self.update_progress(60, "Đang render video với GPU NVENC...")
        cap = cv2.VideoCapture(input_path)
        start_frame = int(in_sec * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        cmd = [
            'ffmpeg', '-y',
            '-f', 'rawvideo', '-vcodec', 'rawvideo',
            '-s', f'{target_w}x{target_h}', '-pix_fmt', 'bgr24', '-r', str(fps),
            '-i', '-',
            '-i', temp_master_audio,
            '-c:v', encoder, *enc_args, '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '256k',
            '-shortest', output_path
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

        for i in range(clip_frames):
            if self.is_cancelled():
                proc.stdin.close()
                proc.terminate()
                cap.release()
                return False, "Đã hủy bởi người dùng."

            ret, frame = cap.read()
            if not ret: break
            t = i / fps

            # 1. Resize to 1080x1920 if needed
            if frame.shape[0] != target_h or frame.shape[1] != target_w:
                frame = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)

            # 2. Color pop
            frame = cv2.convertScaleAbs(frame, alpha=1.04, beta=2)

            # 3. Dynamic visual pacing
            if enable_pacing:
                zoom = 1.00
                if clip_dur > 20.0 and t >= clip_dur * 0.5:
                    zoom = 1.00 + 0.045 * ((t - clip_dur * 0.5) / (clip_dur * 0.5))

                if zoom > 1.001:
                    cw, ch = int(target_w / zoom), int(target_h / zoom)
                    crop = frame[(target_h - ch)//2:(target_h - ch)//2 + ch, (target_w - cw)//2:(target_w - cw)//2 + cw]
                    frame = cv2.resize(crop, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

            # 4. Overlay subtitles
            for c in cards:
                if c["start"] <= t <= c["end"]:
                    fade = 1.0
                    dt_in = t - c["start"]
                    dt_out = c["end"] - t
                    if dt_in < 0.10: fade = dt_in / 0.10
                    elif dt_out < 0.12: fade = dt_out / 0.12

                    x0, y0, x1, y1 = c["x0"], c["y0"], c["x1"], c["y1"]
                    roi = frame[y0:y1, x0:x1]
                    a = c["alpha"] * fade
                    bgr = c["bgr"]
                    frame[y0:y1, x0:x1] = (roi * (1.0 - a) + bgr * a).astype(np.uint8)
                    break

            proc.stdin.write(frame.tobytes())

            # Progress update every 15 frames
            if i % 15 == 0:
                pct = 60 + int((i / clip_frames) * 35)
                self.update_progress(pct, f"Render khung hình {i}/{clip_frames} ({pct}%)...")

        cap.release()
        proc.stdin.close()
        proc.wait()

        # Clean temp audio
        try: os.remove(temp_audio_orig)
        except Exception: pass
        try: os.remove(temp_master_audio)
        except Exception: pass

        elapsed = time.time() - start_time
        self.update_progress(100, "Hoàn tất biên tập video!")
        self.log(f"=== XUẤT FILE THÀNH CÔNG trong {elapsed:.1f}s ===")
        self.log(f"Đường dẫn lưu: {output_path}")

        return True, f"Video đã được biên tập và lưu thành công tại:\n{output_path}"
