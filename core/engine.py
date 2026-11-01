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
            if sys.platform == 'darwin' and 'h264_videotoolbox' in res.stdout:
                return 'h264_videotoolbox', ['-b:v', '12M']
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
    # Audio analysis & Dialogue Transcription via Whisper
    # -------------------------------------------------------------
    def extract_audio_16k(self, video_path):
        """Returns the full soundtrack as mono float32 at 16 kHz (empty array if no audio)."""
        temp_wav = os.path.join(self.cache_dir, f"_temp_16k_{int(time.time() * 1000)}.wav")
        subprocess.run(['ffmpeg', '-y', '-i', video_path, '-vn', '-ac', '1', '-ar', '16000', temp_wav],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            with wave.open(temp_wav, 'rb') as wf:
                return np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        except Exception:
            return np.zeros(0, dtype=np.float32)
        finally:
            try: os.remove(temp_wav)
            except Exception: pass

    @staticmethod
    def loudness_per_second(audio, sr=16000):
        """Loudness per second, normalised to 0..1 (robust to quiet/loud masters)."""
        n = len(audio) // sr
        if n <= 0:
            return np.zeros(0, dtype=np.float32)
        blocks = audio[:n * sr].reshape(n, sr)
        rms = np.sqrt(np.mean(blocks ** 2, axis=1) + 1e-10)
        db = 20.0 * np.log10(rms + 1e-10)
        lo, hi = np.percentile(db, 10), np.percentile(db, 98)
        if hi - lo < 1e-3:
            return np.full(n, 0.5, dtype=np.float32)
        return np.clip((db - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)

    def transcribe_audio(self, audio):
        if len(audio) == 0:
            return []
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel("base", device="cpu", compute_type="int8")
            segments, info = model.transcribe(audio, word_timestamps=True)
            subs = []
            for s in segments:
                if self.is_cancelled():
                    break
                text = s.text.strip()
                if len(text) > 0:
                    subs.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": text})
            return subs
        except Exception as e:
            self.log(f"[Cảnh báo] Không thể dùng faster-whisper ({e}), bỏ qua auto-transcribe.")
            return []

    def transcribe(self, video_path, temp_wav=None):
        """Kept for compatibility: transcribe a whole file."""
        return self.transcribe_audio(self.extract_audio_16k(video_path))

    # -------------------------------------------------------------
    # Climax (hook) selection
    # -------------------------------------------------------------
    def pick_hook_window(self, cut_secs, dur, loud, subs, ideal=30.0, lo=24.0, hi=36.0):
        """
        Scores every cut-aligned window of 24-36 s and returns the best (in_sec, out_sec, info).
        Score favours: loud passages, a strong peak, a build-up toward the end,
        fast cutting, and dense dialogue. Ties no longer fall back to the first window.
        """
        import bisect

        n_sec = len(loud)
        talk = np.zeros(max(n_sec, int(np.ceil(dur)) + 1), dtype=np.float32)
        for s in subs:
            a, b = int(max(0, s["start"])), int(min(len(talk) - 1, np.ceil(s["end"])))
            talk[a:b + 1] = 1.0

        candidates = []
        for i, a in enumerate(cut_secs):
            j0 = bisect.bisect_left(cut_secs, a + lo)
            j1 = bisect.bisect_right(cut_secs, a + hi)
            for j in range(j0, j1):
                candidates.append((a, cut_secs[j]))
        if not candidates:
            # Too few scene cuts: slide a 30 s window second by second
            step = 1.0
            t = 0.0
            while t + ideal <= dur:
                candidates.append((t, t + ideal))
                t += step
        if not candidates:
            return 0.0, dur, "video ngắn hơn cửa sổ hook"

        cut_arr = np.array(cut_secs)
        rows = []
        for a, b in candidates:
            ia, ib = int(a), max(int(a) + 1, int(np.ceil(b)))
            seg = loud[ia:ib] if n_sec else np.zeros(1)
            if len(seg) == 0:
                seg = np.zeros(1)
            mean_e = float(seg.mean())
            peak = float(np.sort(seg)[-3:].mean())
            third = max(1, len(seg) // 3)
            build = float(np.clip(seg[-third:].mean() - seg[:third].mean(), 0, 1))
            n_cuts = int(((cut_arr > a + 0.2) & (cut_arr < b - 0.2)).sum())
            rate = n_cuts / (b - a)
            dialog = float(talk[ia:ib].mean()) if subs else 0.0
            closeness = abs((b - a) - ideal) / (hi - lo)
            rows.append((a, b, mean_e, peak, build, rate, dialog, closeness))

        max_rate = max(r[5] for r in rows) or 1.0
        best, best_score = None, -1e9
        for a, b, mean_e, peak, build, rate, dialog, closeness in rows:
            score = (0.32 * mean_e + 0.28 * peak + 0.12 * build +
                     0.18 * (rate / max_rate) + 0.10 * dialog - 0.05 * closeness)
            if score > best_score:
                best_score, best = score, (a, b, mean_e, peak, rate)
        a, b, mean_e, peak, rate = best
        info = (f"điểm {best_score:.2f} · độ lớn TB {mean_e:.2f} · đỉnh {peak:.2f} · "
                f"{rate * 10:.1f} cảnh/10s · xét {len(rows)} đoạn")
        return a, b, info

    # -------------------------------------------------------------
    # Montage (cut & join) for sparse videos
    # -------------------------------------------------------------
    @staticmethod
    def intensity_per_second(cut_secs, dur, loud, subs):
        """0..1-ish 'how much is happening' per second: loudness (peaks emphasised),
        dialogue and scene-cut density, lightly smoothed."""
        n = max(len(loud), int(np.ceil(dur)), 1)
        L = np.zeros(n, dtype=np.float32)
        L[:len(loud)] = loud
        talk = np.zeros(n, dtype=np.float32)
        for s in subs:
            a, b = int(max(0, s["start"])), int(min(n - 1, np.ceil(s["end"])))
            if b >= a:
                talk[a:b + 1] = 1.0
        cuts = np.zeros(n, dtype=np.float32)
        for c in cut_secs[1:-1]:
            k = int(c)
            if 0 <= k < n:
                cuts[k] += 1.0
        k3 = np.ones(3, dtype=np.float32) / 3.0
        cut_d = np.convolve(cuts, k3, mode='same')
        if cut_d.max() > 0:
            cut_d /= cut_d.max()
        raw = 0.6 * L ** 1.4 + 0.2 * talk + 0.2 * cut_d
        return np.convolve(raw, k3, mode='same').astype(np.float32)

    @staticmethod
    def hot_fraction(inten, hot_thr, segments):
        idx = []
        for a, b in segments:
            idx.extend(range(int(a), min(len(inten), int(np.ceil(b)))))
        if not idx:
            return 0.0
        return float((inten[idx] >= hot_thr).mean())

    def pick_montage(self, cut_secs, dur, inten, subs, target=30.0):
        """
        Picks the strongest moments anywhere in the video and returns them as
        chronological pieces [(a, b), ...] totalling about `target` seconds.
        Piece edges snap to sentence edges (no cut mid-line) or to scene cuts.
        """
        cut_arr = np.array(cut_secs[1:-1]) if len(cut_secs) > 2 else np.zeros(0)

        def inside_sub(t):
            for s in subs:
                if s["start"] + 0.15 < t < s["end"] - 0.15:
                    return s
            return None

        def near_cut(t, lim=1.0):
            if len(cut_arr) == 0:
                return None
            k = int(np.argmin(np.abs(cut_arr - t)))
            return float(cut_arr[k]) if abs(cut_arr[k] - t) <= lim else None

        def snap_start(t):
            s = inside_sub(t)
            if s is not None and t - s["start"] <= 2.5:
                return max(0.0, s["start"] - 0.1)
            c = near_cut(t)
            return max(0.0, c if c is not None else t)

        def snap_end(t):
            s = inside_sub(t)
            if s is not None and s["end"] - t <= 3.0:
                return min(dur, s["end"] + 0.15)
            c = near_cut(t)
            return min(dur, c if c is not None else t)

        pieces = []
        top = float(inten.max()) if len(inten) else 0.0
        for p in np.argsort(-inten):
            if sum(b - a for a, b in pieces) >= target - 1.5:
                break
            if top <= 0 or inten[p] < 0.25 * top:
                break
            if any(a - 1.5 <= p + 0.5 <= b + 1.5 for a, b in pieces):
                continue
            a = snap_start(p - 2.0)
            b = snap_end(p + 3.5)  # lean forward: the hit, then the reaction
            if b - a > 8.0:
                b = snap_end(a + 6.0) if snap_end(a + 6.0) - a <= 8.0 else a + 8.0
            if b - a < 2.0:
                b = min(dur, a + 2.0)
            # Merge with neighbours that are almost touching
            merged = True
            while merged:
                merged = False
                for q in pieces:
                    if a <= q[1] + 1.5 and b >= q[0] - 1.5:
                        pieces.remove(q)
                        a, b = min(a, q[0]), max(b, q[1])
                        merged = True
                        break
            total = sum(x1 - x0 for x0, x1 in pieces)
            if total + (b - a) > target + 3.0:
                b = a + max(2.0, target - total)
            pieces.append((a, b))
        pieces.sort()
        # Too short? Give each moment more build-up before the hit (and a bit of reaction after)
        total = sum(b - a for a, b in pieces)
        if pieces and target - total > 2.0:
            per = (target - total) / len(pieces)
            grown = []
            for k, (a, b) in enumerate(pieces):
                prev_end = grown[-1][1] if grown else 0.0
                next_start = pieces[k + 1][0] if k + 1 < len(pieces) else dur
                na = max(prev_end + 0.5, min(a, snap_start(a - min(per * 0.65, 4.0))))
                nb = min(next_start - 0.5, max(b, snap_end(b + min(per * 0.35, 2.5))))
                grown.append((min(a, na), max(b, nb)))
            pieces = grown
        total = sum(b - a for a, b in pieces)
        info =f"{len(pieces)} đoạn, tổng {total:.1f}s: " + ", ".join(f"{a:.1f}-{b:.1f}s" for a, b in pieces)
        return pieces, info

    # -------------------------------------------------------------
    # Frame fitting (no stretching)
    # -------------------------------------------------------------
    @staticmethod
    def make_fitter(src_w, src_h, target_w, target_h):
        """Returns frame -> 1080x1920 function. Near-vertical sources are cover-cropped;
        horizontal/square sources sit centred over a blurred fill of themselves."""
        if src_w <= 0 or src_h <= 0:
            return lambda f: cv2.resize(f, (target_w, target_h))
        src_ar, dst_ar = src_w / src_h, target_w / target_h
        cover = max(target_w / src_w, target_h / src_h)
        cw, ch = int(round(src_w * cover)), int(round(src_h * cover))
        cx0, cy0 = (cw - target_w) // 2, (ch - target_h) // 2

        def cover_crop(f):
            r = cv2.resize(f, (cw, ch), interpolation=cv2.INTER_LANCZOS4 if cover > 1 else cv2.INTER_AREA)
            return r[cy0:cy0 + target_h, cx0:cx0 + target_w]

        if abs(src_ar - dst_ar) / dst_ar < 0.12:
            if (src_w, src_h) == (target_w, target_h):
                return lambda f: f
            return cover_crop

        fit = min(target_w / src_w, target_h / src_h)
        fw, fh = int(round(src_w * fit)), int(round(src_h * fit))
        fx0, fy0 = (target_w - fw) // 2, (target_h - fh) // 2

        def blur_fill(f):
            bg = cv2.resize(f, (cw // 12 or 1, ch // 12 or 1), interpolation=cv2.INTER_AREA)
            bg = cv2.GaussianBlur(bg, (0, 0), 3)
            bg = cv2.resize(bg, (cw, ch), interpolation=cv2.INTER_LINEAR)[cy0:cy0 + target_h, cx0:cx0 + target_w]
            bg = cv2.convertScaleAbs(bg, alpha=0.55, beta=0)
            bg[fy0:fy0 + fh, fx0:fx0 + fw] = cv2.resize(f, (fw, fh), interpolation=cv2.INTER_AREA)
            return bg
        return blur_fill

    @staticmethod
    def load_sub_font(size):
        candidates = [
            r'C:\Windows\Fonts\arialbd.ttf',
            r'C:\Windows\Fonts\segoeuib.ttf',
            '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
            '/Library/Fonts/Arial Bold.ttf',
            '/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf',
            '/System/Library/Fonts/Helvetica.ttc',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
        try:
            return ImageFont.load_default(size=size)  # Pillow >= 10.1 scalable fallback
        except Exception:
            return ImageFont.load_default()

    # -------------------------------------------------------------
    # Master Processing Execution
    # -------------------------------------------------------------
    def process_video(self, input_path, output_path, mode="hook-and-polish",
                      sub_mode="en", enable_sfx=True, enable_pacing=True, hook_style="auto"):
        """hook_style: 'auto' (cut & join only when the climax moments are scattered),
        'window' (always one continuous piece) or 'montage' (always cut & join)."""
        self._stop_event.clear()
        start_time = time.time()
        self.log(f"=== BẮT ĐẦU XỬ LÝ: {os.path.basename(input_path)} ===")
        self.update_progress(5, "Đang nạp video & kiểm tra phần cứng...")

        # "Chỉ cắt hook" = cut only: original sound, no added effects
        if mode == "hook-only":
            enable_sfx = False
            enable_pacing = False

        specs = self.get_video_specs(input_path)
        self.log(f"Thông số gốc: {specs['width']}x{specs['height']} @ {specs['fps']:.1f}fps, {specs['duration']:.2f}s")
        if specs['width'] <= 0 or specs['duration'] <= 0:
            return False, "Không đọc được video này (định dạng lỗi hoặc file hỏng)."

        encoder, enc_args = self.check_encoder()
        self.log(f"Trình mã hóa video: {encoder}")

        target_w, target_h = 1080, 1920
        fps = specs['fps'] if specs['fps'] > 0 else 30.0
        dur = specs['duration']
        want_hook = mode in ["hook-and-polish", "hook-only"] and dur > 35.0

        # Step 1: Scene cuts (for hook choice and punch-zoom rhythm)
        cut_secs = [0.0, dur]
        if want_hook or enable_pacing:
            self.update_progress(10, "Đang quét chuyển cảnh...")
            cuts, c_fps, total_f = self.detect_cuts(input_path)
            cut_secs = sorted(set(c / fps for c in cuts))
            self.log(f"Đã phát hiện {max(0, len(cut_secs) - 2)} điểm chuyển cảnh.")
        if self.is_cancelled(): return False, "Đã hủy bởi người dùng."

        # Step 2: Audio loudness + dialogue (whole video, used for choosing the climax)
        self.update_progress(18, "Đang phân tích âm thanh & nhận diện thoại...")
        audio16 = self.extract_audio_16k(input_path)
        loud = self.loudness_per_second(audio16)
        subs_full = self.transcribe_audio(audio16) if sub_mode != "none" else []
        if self.is_cancelled(): return False, "Đã hủy bởi người dùng."

        # Step 3: Source pieces to keep. One continuous window, or (sparse video)
        # several strong moments cut & joined together.
        segments = [(0.0, dur)]
        if want_hook:
            self.update_progress(30, "Đang chấm điểm các đoạn để tìm cao trào...")
            w_in, w_out, info = self.pick_hook_window(cut_secs, dur, loud, subs_full)
            segments = [(w_in, w_out)]
            style = hook_style if hook_style in ("auto", "window", "montage") else "auto"
            if style != "window" and dur >= (40.0 if style == "montage" else 60.0):
                inten = self.intensity_per_second(cut_secs, dur, loud, subs_full)
                hot_thr = float(np.percentile(inten, 75))
                pieces, m_info = self.pick_montage(cut_secs, dur, inten, subs_full)
                wh = self.hot_fraction(inten, hot_thr, segments)
                mh = self.hot_fraction(inten, hot_thr, pieces) if pieces else 0.0
                self.log(f"Mật độ cao trào: đoạn liền {wh:.0%} · cắt ghép {mh:.0%}")
                use_montage = len(pieces) >= 2 and (
                    style == "montage" or (wh < 0.55 and mh - wh >= 0.20))
                if use_montage:
                    segments = pieces
                    self.log(f"Video thưa cao trào -> CẮT GHÉP {m_info}")
            if len(segments) == 1:
                self.log(f"Khóa Hook cao trào: {w_in:.2f}s -> {w_out:.2f}s ({w_out - w_in:.2f}s) | {info}")
        else:
            self.log(f"Chế độ {mode}: Giữ trọn vẹn mạch video ({dur:.2f}s).")

        # Output timeline: frame counts per piece keep sound and picture in sync
        seg_frames = [max(1, int(round((b - a) * fps))) for a, b in segments]
        seg_offs = [0.0]
        for nf in seg_frames[:-1]:
            seg_offs.append(seg_offs[-1] + nf / fps)
        clip_frames = sum(seg_frames)
        clip_dur = clip_frames / fps
        joins = seg_offs[1:]
        is_montage = len(segments) > 1

        def map_t(t):
            for (a, _), off, nf in zip(segments, seg_offs, seg_frames):
                if a <= t <= a + nf / fps:
                    return off + (t - a)
            return None

        subs = []
        for s in subs_full:
            for (a, _), off, nf in zip(segments, seg_offs, seg_frames):
                b = a + nf / fps
                s0, s1 = max(s["start"], a), min(s["end"], b)
                if s1 - s0 >= 0.4:
                    subs.append({"start": off + s0 - a, "end": off + s1 - a, "text": s["text"]})
        subs.sort(key=lambda x: x["start"])
        if sub_mode != "none":
            self.log(f"Đã tạo {len(subs)} câu phụ đề tiếng Anh tự động.")

        # Rhythm points inside the clip (scene cuts + every join of the montage)
        rel_cuts = []
        for c in cut_secs:
            t = map_t(c)
            if t is not None and 0.3 < t < clip_dur - 0.3 and (not rel_cuts or t - rel_cuts[-1] >= 0.8):
                rel_cuts.append(t)
        for j in joins:
            if all(abs(j - c) > 0.3 for c in rel_cuts):
                rel_cuts.append(j)
        rel_cuts.sort()
        # Loudness for each second of the OUTPUT timeline
        clip_loud = np.zeros(0)
        if len(loud):
            vals = []
            for s_out in range(int(clip_dur)):
                k = int(np.searchsorted(seg_offs, s_out + 0.5, side='right')) - 1
                src = segments[k][0] + (s_out + 0.5 - seg_offs[k])
                vals.append(loud[min(len(loud) - 1, int(src))])
            clip_loud = np.array(vals, dtype=np.float32)
        climax_t = None
        if len(clip_loud) > 4 and clip_dur > 8.0:
            # loudest second, ignoring the first 2 s; snap to a nearby cut if there is one
            tail = clip_loud[2:len(clip_loud) - 2]  # skip first/last 2 s: the boom needs room
            # near-ties go to the later moment, so the hook builds toward its hit
            k = int(np.argmax(tail + 0.05 * np.linspace(0.0, 1.0, len(tail)))) + 2
            climax_t = float(k)
            near = [c for c in rel_cuts if abs(c - climax_t) <= 1.0 and c <= clip_dur - 1.5]
            if near:
                climax_t = min(near, key=lambda c: abs(c - climax_t))
        if enable_pacing:
            self.log(f"Nhịp dựng: {len(rel_cuts)} punch zoom theo chuyển cảnh"
                     + (f", điểm nhấn cao trào tại {climax_t:.1f}s." if climax_t is not None else "."))

        # Step 4: Audio Mastering & SFX
        self.update_progress(45, "Đang phối âm thanh & hiệu ứng chuyển cảnh...")
        temp_audio_orig = os.path.join(self.cache_dir, f"_temp_orig_{int(time.time())}.wav")
        temp_master_audio = os.path.join(self.cache_dir, f"_temp_master_{int(time.time())}.wav")
        sr = 44100
        pieces_audio = []
        has_audio = False
        fade_n = int(0.012 * sr)  # tiny fade at joins, avoids clicks
        for (a, _), nf in zip(segments, seg_frames):
            need = int(round(nf / fps * sr))
            subprocess.run([
                'ffmpeg', '-y', '-ss', f"{a:.4f}", '-t', f"{nf / fps:.4f}",
                '-i', input_path, '-vn', '-ac', '2', '-ar', str(sr), temp_audio_orig
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                with wave.open(temp_audio_orig, 'rb') as wf:
                    pa = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
                    pa = pa.reshape(-1, 2) if wf.getnchannels() == 2 else np.column_stack([pa, pa])
                has_audio = True
            except Exception:
                pa = np.zeros((0, 2), dtype=np.float32)
            if len(pa) < need:
                pa = np.vstack([pa, np.zeros((need - len(pa), 2), dtype=np.float32)])
            pa = pa[:need].copy()
            if is_montage and len(pa) > 2 * fade_n:
                ramp = np.linspace(0.0, 1.0, fade_n, dtype=np.float32)[:, None]
                pa[:fade_n] *= ramp
                pa[-fade_n:] *= ramp[::-1]
            pieces_audio.append(pa)
        orig_audio = np.vstack(pieces_audio) if pieces_audio else np.zeros((int(clip_dur * sr), 2), dtype=np.float32)
        if not has_audio:
            self.log("Video không có âm thanh, dùng nền im lặng.")

        total_audio_samples = len(orig_audio)
        sfx_layer = np.zeros_like(orig_audio)

        def _mix(data, at_sec, gain):
            s0 = int(at_sec * sr)
            if s0 < 0 or s0 >= total_audio_samples:
                return
            e0 = min(s0 + len(data), total_audio_samples)
            sfx_layer[s0:e0] += data[:e0 - s0] * gain

        if enable_sfx:
            boom_file, whoosh_file = self.get_or_generate_sfx()
            with wave.open(whoosh_file, 'rb') as wf:
                whoosh_data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
                whoosh_data = np.column_stack([whoosh_data, whoosh_data])
            with wave.open(boom_file, 'rb') as wf:
                boom_data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
                boom_data = np.column_stack([boom_data, boom_data])

            whoosh_lead = 0.12  # whoosh starts slightly before the cut
            last = -99.0
            placed = 0
            for c in rel_cuts:
                if climax_t is not None and abs(c - climax_t) < 1.5:
                    continue
                is_join = any(abs(c - j) < 0.05 for j in joins)
                if c - last >= 4.0 or (is_join and c - last >= 1.2):
                    _mix(whoosh_data, c - whoosh_lead, 0.28)
                    last = c
                    placed += 1
            if placed == 0:
                _mix(whoosh_data, 0.7, 0.35)
            _mix(boom_data, climax_t if climax_t is not None else clip_dur * 0.5, 0.65)

        mixed_audio = orig_audio * 1.05 + sfx_layer
        peak = np.max(np.abs(mixed_audio)) if len(mixed_audio) else 0
        if peak > 0.95:
            mixed_audio = np.tanh(mixed_audio / 0.95) * 0.95

        out_i16 = (np.clip(mixed_audio, -1, 1) * 32767).astype(np.int16)
        with wave.open(temp_master_audio, 'wb') as wf:
            wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(sr)
            wf.writeframes(out_i16.tobytes())

        if self.is_cancelled(): return False, "Đã hủy bởi người dùng."

        # Step 5: Prepare subtitle images (bold outlined "pop" text, no background box)
        self.update_progress(55, "Đang dựng phụ đề chữ nổi...")
        from PIL import ImageFilter
        font_size = int(target_h * 0.034)  # ~65px on 1920
        font = self.load_sub_font(font_size)
        stroke = max(4, font_size // 11)
        max_line_w = int(target_w * 0.84)
        shadow_dy, shadow_blur = max(4, font_size // 12), max(4, font_size // 9)

        dummy = Image.new('RGBA', (1, 1))
        d_dummy = ImageDraw.Draw(dummy)
        cards = []

        def _wrap(text):
            # Greedy wrap by measured width, at most 2 lines (rebalanced)
            words, lines, cur = text.split(), [], ""
            for wd in words:
                trial = (cur + " " + wd).strip()
                if d_dummy.textlength(trial, font=font) + 2 * stroke <= max_line_w or not cur:
                    cur = trial
                else:
                    lines.append(cur); cur = wd
            if cur:
                lines.append(cur)
            if len(lines) > 2:
                mid = len(words) // 2
                lines = [" ".join(words[:mid]), " ".join(words[mid:])]
            return "\n".join(lines)

        for s in subs:
            text = _wrap(s["text"].strip())
            b = d_dummy.multiline_textbbox((0, 0), text, font=font, align='center',
                                           stroke_width=stroke, spacing=8)
            tw, th = b[2] - b[0], b[3] - b[1]
            pad = shadow_blur * 2 + shadow_dy
            bw, bh = int(tw + pad * 2), int(th + pad * 2)

            cx = target_w // 2
            cy = int(target_h * 0.797)  # Y = 1530 safe zone (clear of TikTok/Reels UI)
            x0 = max(0, cx - bw // 2)
            y0 = max(0, cy - bh // 2)
            x1 = min(target_w, x0 + bw)
            y1 = min(target_h, y0 + bh)
            bw, bh = x1 - x0, y1 - y0

            # Soft drop shadow
            shadow = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
            ImageDraw.Draw(shadow).multiline_text(
                (bw // 2, pad - b[1] + shadow_dy), text, font=font, fill=(0, 0, 0, 170),
                stroke_width=stroke, stroke_fill=(0, 0, 0, 170), align='center', anchor='ma', spacing=8)
            shadow = shadow.filter(ImageFilter.GaussianBlur(shadow_blur))

            # White text with a thick black outline
            txt = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
            ImageDraw.Draw(txt).multiline_text(
                (bw // 2, pad - b[1]), text, font=font, fill=(255, 255, 255, 255),
                stroke_width=stroke, stroke_fill=(0, 0, 0, 255), align='center', anchor='ma', spacing=8)
            img = Image.alpha_composite(shadow, txt)

            rgba = np.array(img, dtype=np.float32)
            cards.append({
                "start": s["start"], "end": s["end"],
                "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                "alpha": (rgba[:, :, 3] / 255.0)[:, :, None],
                "bgr": rgba[:, :, [2, 1, 0]]
            })

        # Per-frame zoom curve: slow push-in + punch on every cut + bigger hit at the climax
        zoom_curve = np.ones(max(clip_frames, 1), dtype=np.float32)
        if enable_pacing and clip_frames > 0:
            t_arr = np.arange(clip_frames, dtype=np.float32) / fps
            if clip_dur > 12.0:
                half = clip_dur * 0.5
                zoom_curve += np.where(t_arr >= half, 0.06 * (t_arr - half) / half, 0.0)
            punches = [(c, 0.08, 0.35) for c in rel_cuts]
            if climax_t is not None:
                punches.append((climax_t, 0.15, 0.55))
            for tc, amp, length in punches:
                p = (t_arr - tc) / length
                mask = (p >= 0) & (p < 1)
                zoom_curve[mask] += amp * (1.0 - p[mask]) ** 3  # ease-out decay

        # Step 6: Render
        self.update_progress(60, f"Đang render video ({encoder})...")
        cap = cv2.VideoCapture(input_path)
        fit =self.make_fitter(specs['width'], specs['height'], target_w, target_h)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'error',
            '-f', 'rawvideo', '-vcodec', 'rawvideo',
            '-s', f'{target_w}x{target_h}', '-pix_fmt', 'bgr24', '-r', str(fps),
            '-i', '-',
            '-i', temp_master_audio,
            '-c:v', encoder, *enc_args, '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '256k',
            '-shortest', output_path
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

        # Frame i of the output -> (piece start in source, first output frame of that piece)
        seg_first = np.cumsum([0] + seg_frames[:-1])
        seg_idx = 0
        last_raw = None
        cap.set(cv2.CAP_PROP_POS_MSEC, segments[0][0] * 1000.0)
        for i in range(clip_frames):
            if self.is_cancelled():
                proc.stdin.close()
                proc.terminate()
                cap.release()
                return False, "Đã hủy bởi người dùng."

            if seg_idx + 1 < len(segments) and i >= seg_first[seg_idx + 1]:
                seg_idx += 1
                cap.set(cv2.CAP_PROP_POS_MSEC, segments[seg_idx][0] * 1000.0)
            ret, frame = cap.read()
            if not ret:
                if last_raw is None:
                    break
                frame = last_raw.copy()  # hold the last frame so audio stays in sync
            else:
                last_raw = frame
            t = i / fps

            # 1. Fit to 1080x1920 without stretching
            frame = fit(frame)

            # 2. Color pop
            if enable_pacing:
                frame = cv2.convertScaleAbs(frame, alpha=1.06, beta=2)

            # 3. Zoom (push-in + punches)
            zoom = float(zoom_curve[i])
            if zoom > 1.001:
                cw, ch = int(target_w / zoom), int(target_h / zoom)
                y0c, x0c = (target_h - ch) // 2, (target_w - cw) // 2
                frame = cv2.resize(frame[y0c:y0c + ch, x0c:x0c + cw], (target_w, target_h),
                                   interpolation=cv2.INTER_LINEAR)
            elif not frame.flags['C_CONTIGUOUS']:
                frame = np.ascontiguousarray(frame)

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
                    frame[y0:y1, x0:x1] = (roi * (1.0 - a) + c["bgr"] * a).astype(np.uint8)
                    break

            proc.stdin.write(frame.tobytes())

            if i % 15 == 0:
                pct = 60 + int((i / clip_frames) * 35)
                self.update_progress(pct, f"Render khung hình {i}/{clip_frames} ({pct}%)...")

        cap.release()
        proc.stdin.close()
        proc.wait()

        try: os.remove(temp_audio_orig)
        except Exception: pass
        try: os.remove(temp_master_audio)
        except Exception: pass

        if proc.returncode != 0 or not os.path.exists(output_path):
            return False, f"ffmpeg không xuất được video (mã lỗi {proc.returncode})."

        elapsed = time.time() - start_time
        self.update_progress(100, "Hoàn tất biên tập video!")
        self.log(f"=== XUẤT FILE THÀNH CÔNG trong {elapsed:.1f}s ===")
        self.log(f"Đường dẫn lưu: {output_path}")

        return True, f"Video đã được biên tập và lưu thành công tại:\n{output_path}"
