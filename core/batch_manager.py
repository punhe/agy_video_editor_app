"""
batch_manager.py
Smart Queue & Concurrency Resource Manager for Batch Video Processing.
Dynamically calculates safe worker threads based on available physical RAM and GPU limits.
"""

import os
import sys
import time
import gc
import threading
from concurrent.futures import ThreadPoolExecutor

def get_system_ram_info():
    """Returns (total_gb, avail_gb, percent_used)."""
    try:
        if sys.platform == 'win32':
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ('dwLength', ctypes.c_ulong),
                    ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong),
                    ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong),
                    ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            total_gb = stat.ullTotalPhys / (1024**3)
            avail_gb = stat.ullAvailPhys / (1024**3)
            return total_gb, avail_gb, stat.dwMemoryLoad
        elif sys.platform == 'darwin':
            import subprocess
            res = subprocess.run(['sysctl', '-n', 'hw.memsize'], capture_output=True, text=True)
            total = int(res.stdout.strip()) / (1024**3)
            return total, total * 0.6, 40
        else:
            total = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / (1024**3)
            return total, total * 0.5, 50
    except Exception:
        return 8.0, 4.0, 50

def calculate_smart_workers():
    """
    Computes optimal concurrent workers to prevent OOM (Out Of Memory)
    and avoid exhausting GPU NVENC encoding sessions.
    """
    total, avail, load = get_system_ram_info()

    # Base rule:
    # Reserve at least 2.5 GB for OS/background processes.
    # Each NVENC + OpenCV + Whisper pipeline uses ~1.2 GB - 1.5 GB.
    usable_ram = max(0.5, avail - 2.5)
    workers_by_ram = int(usable_ram // 1.4)

    # NVENC sessions limit on consumer GPUs is 3-5, keep max 2 to ensure stability
    safe_workers = max(1, min(workers_by_ram, 2))
    return safe_workers, total, avail, load

class BatchJob:
    def __init__(self, job_id, input_path, output_dir, mode="hook-and-polish", sub_mode="en"):
        self.job_id = job_id
        self.input_path = input_path
        self.output_dir = output_dir
        self.mode = mode
        self.sub_mode = sub_mode
        self.status = "Chờ xử lý"
        self.progress = 0
        self.stage = "Đang trong hàng đợi"
        self.output_path = ""
        self.captions_path = ""
        self.error_msg = ""
        self.dialogue_lines = []
        self.caption_variants = []

class BatchManager:
    def __init__(self, on_job_update=None, on_batch_complete=None, log_callback=None):
        self.on_job_update = on_job_update or (lambda job: None)
        self.on_batch_complete = on_batch_complete or (lambda: None)
        self.log_callback = log_callback or (lambda text: print(text))

        self.jobs = []
        self._is_running = False
        self._cancel_event = threading.Event()
        self.executor = None
        self.lock = threading.Lock()
        self.active_engines = {}

    def log(self, text):
        self.log_callback(text)

    def add_job(self, input_path, output_dir, mode="hook-and-polish", sub_mode="en"):
        with self.lock:
            job_id = len(self.jobs) + 1
            job = BatchJob(job_id, input_path, output_dir, mode, sub_mode)
            self.jobs.append(job)
            return job

    def clear_jobs(self):
        with self.lock:
            if not self._is_running:
                self.jobs.clear()
                return True
        return False

    def remove_job(self, job_id):
        with self.lock:
            if not self._is_running:
                self.jobs = [j for j in self.jobs if j.job_id != job_id]
                return True
        return False

    def cancel_all(self):
        self._cancel_event.set()
        with self.lock:
            for job_id, engine in list(self.active_engines.items()):
                try: engine.cancel()
                except Exception: pass
        self.log("[Batch Manager] Đã gửi tín hiệu hủy toàn bộ hàng đợi...")

    def is_running(self):
        return self._is_running

    def start_batch(self, user_workers=None, auto_caption=True):
        if self._is_running or not self.jobs:
            return False

        self._is_running = True
        self._cancel_event.clear()

        # Calculate concurrency
        safe_workers, total_ram, avail_ram, load = calculate_smart_workers()
        num_workers = user_workers if (user_workers and user_workers > 0) else safe_workers

        self.log(f"=======================================================")
        self.log(f"🚀 BẮT ĐẦU BATCH PROCESSING: {len(self.jobs)} VIDEO")
        self.log(f"🧠 Phân bổ RAM thông minh: Tổng {total_ram:.1f}GB, Khả dụng {avail_ram:.1f}GB (Tải {load}%)")
        self.log(f"⚡ Số luồng xử lý đồng thời tối ưu: {num_workers} worker(s)")
        self.log(f"=======================================================")

        threading.Thread(target=self._batch_worker_loop, args=(num_workers, auto_caption), daemon=True).start()
        return True

    def _batch_worker_loop(self, num_workers, auto_caption):
        from core.engine import VideoEditorEngine
        from core.caption_generator import generate_captions_with_agy, save_captions_to_file

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            self.executor = executor
            futures = []
            for job in self.jobs:
                if self._cancel_event.is_set():
                    job.status = "Đã hủy"
                    self.on_job_update(job)
                    continue

                f = executor.submit(self._process_single_job, job, auto_caption)
                futures.append(f)

            # Wait for all to finish
            for f in futures:
                try: f.result()
                except Exception as e:
                    self.log(f"[Lỗi tác vụ] {e}")

        self._is_running = False
        gc.collect() # Immediate RAM cleanup
        self.log("🏁 ĐÃ HOÀN TẤT TOÀN BỘ TIẾN TRÌNH HÀNG ĐỢI (BATCH COMPLETED)!")
        self.on_batch_complete()

    def _process_single_job(self, job, auto_caption):
        from core.engine import VideoEditorEngine
        from core.caption_generator import generate_captions_with_agy, save_captions_to_file

        if self._cancel_event.is_set():
            job.status = "Đã hủy"
            self.on_job_update(job)
            return

        job.status = "Đang xử lý"
        job.progress = 0
        job.stage = "Đang khởi tạo..."
        self.on_job_update(job)

        base_name = os.path.splitext(os.path.basename(job.input_path))[0]
        out_file = os.path.join(job.output_dir, f"{base_name}_edited.mp4")
        job.output_path = out_file

        def _log_cb(msg):
            self.log(f"[{base_name[:14]}] {msg}")

        def _prog_cb(pct, stage_msg):
            job.progress = pct
            job.stage = stage_msg
            self.on_job_update(job)

        engine = VideoEditorEngine(log_callback=_log_cb, progress_callback=_prog_cb)
        with self.lock:
            self.active_engines[job.job_id] = engine

        try:
            success, msg = engine.process_video(
                input_path=job.input_path,
                output_path=out_file,
                mode=job.mode,
                sub_mode=job.sub_mode,
                enable_sfx=True,
                enable_pacing=True
            )

            if success:
                job.status = "Hoàn thành"
                job.progress = 100
                job.stage = "Đã xuất video thành công"

                # Step: Auto generate X/Twitter Caption if enabled
                if auto_caption and not self._cancel_event.is_set():
                    try:
                        self.log(f"[{base_name[:14]}] ✍️ Đang tạo Caption X/Twitter (Shadowban-Safe)...")
                        variants = generate_captions_with_agy(out_file, job.dialogue_lines)
                        txt_path = save_captions_to_file(out_file, variants, job.dialogue_lines)
                        job.captions_path = txt_path
                        job.caption_variants = variants
                        self.log(f"[{base_name[:14]}] ✅ Đã lưu Caption tại: {os.path.basename(txt_path)}")
                    except Exception as ce:
                        self.log(f"[{base_name[:14]}] Lỗi tạo caption: {ce}")

            else:
                job.status = "Thất bại" if not self._cancel_event.is_set() else "Đã hủy"
                job.error_msg = msg
                job.stage = msg

        except Exception as e:
            job.status = "Lỗi"
            job.error_msg = str(e)
            job.stage = f"Lỗi ngoại lệ: {str(e)}"

        finally:
            with self.lock:
                self.active_engines.pop(job.job_id, None)
            self.on_job_update(job)
            # Explicit garbage collection to release video frames and buffers from RAM
            gc.collect()
