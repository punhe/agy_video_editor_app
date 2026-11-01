# 🎬 AGY Short-Drama Studio (Desktop App)

Ứng dụng Desktop (GUI) chuyên nghiệp dùng để biên tập video phim ngắn / short-drama triệu view, chạy tương thích hoàn hảo trên **Windows** và **macOS**.

---

## 🚀 1. Cách Khởi Chạy Ứng Dụng

### Cần cài trước
* **Python 3.9 trở lên**, tải tại https://www.python.org/downloads/ (bản này có sẵn Tkinter).
* **ffmpeg** để cắt và xuất video:
  * macOS: `brew install ffmpeg`
  * Windows: `winget install Gyan.FFmpeg`

Thư viện Python (`opencv-python`, `numpy`, `Pillow`, `faster-whisper`) được file chạy **tự cài** vào thư mục `.venv` ở lần mở đầu tiên. Lần đầu mất vài phút. Các lần sau app mở ngay.

### Trên macOS:
* Cách 1: **Click đúp vào file `run_app.command`**.
* Cách 2: Mở Terminal trong thư mục app và gõ:
  ```bash
  bash run_app.sh
  ```
* Nếu báo thiếu Tkinter khi dùng Python của Homebrew: chạy `brew install python-tk@3.13` (thay `3.13` bằng phiên bản Python của bạn).

### Trên Windows:
* Cách 1: **Click đúp vào file `run_app.bat`**.
* Cách 2: Mở terminal trong thư mục app và gõ `run_app.bat`.

### Cài thủ công (nếu không dùng file chạy)
```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt faster-whisper
python app.py
```

---

## 🌟 2. Các Tính Năng Nổi Bật

1. **Kết Nối & Đăng Nhập AGY CLI**:
   * **Nút `⚡ Test Kết Nối AGY`**: Kiểm tra trạng thái AGY CLI trên hệ thống (`agy --version`).
   * **Nút `🔑 Đăng Nhập Google`**: Tự động mở cửa sổ Terminal kích hoạt quy trình đăng nhập tài khoản Google trên trình duyệt web cho AGY CLI.
2. **Chọn Video & Nơi Lưu Linh Hoạt**:
   * Hỗ trợ dán trực tiếp đường dẫn file (`Ctrl+V` / `Cmd+V`) hoặc bấm **`📁 Chọn Video...`** (hỗ trợ `.mp4`, `.mov`, `.mkv`, `.avi`, `.webm`).
   * Tự động nhận diện thông số video (độ phân giải, fps, thời lượng).
   * Cho phép chọn thư mục lưu thành phẩm bất kỳ qua nút **`📂 Chọn Nơi Lưu...`**.
3. **Các Chế Độ Biên Tập (Workflows)**:
   * 🌟 **Trọn Gói Tự Động (Hook 30s + Nhịp + Sub Tiếng Anh)**: Tự động phát hiện chuyển cảnh, khóa đoạn cao trào 30s đắt giá nhất, tạo nhịp giật punch zoom và chèn sub tiếng Anh viên thuốc kính mờ.
   * ✂️ **Tạo Nhịp & Sub Cho Video Cắt Sẵn**: Giữ nguyên toàn bộ thời lượng video đã cắt sẵn, bổ sung nhịp giật visual, hiệu ứng âm thanh và sub.
   * 🎯 **Chỉ Cắt Hook 30s**: Trích xuất cao trào nhanh mà không can thiệp âm thanh.
4. **Phụ Đề Tiếng Anh Viên Thuốc Kính Mờ (English Frosted Glass Capsule)**:
   * Thiết kế chuẩn Safe Zone `Y: 1530` (không bị giao diện TikTok/Reels che khuất).
   * Tự động xóa sạch/che phủ phụ đề thô cũ nếu có.
5. **Tiến Trình Thời Gian Thực & Chẩn Đoán %**:
   * Thanh tiến trình mượt mà từ 0% đến 100%.
   * Ô Console Log hiển thị chi tiết nhật ký từng khung hình đang chạy.
   * Nút **`⏹ HỦY TIẾN TRÌNH`** an toàn nếu muốn dừng giữa chừng.
6. **Thông Báo & Phát Video Khi Hoàn Tất**:
   * Tự động phát âm thanh chuông báo và hiển thị thông báo Desktop (Windows Toast / macOS Notification Center).
   * Nút **`📂 Mở Thư Mục Chứa Video`** (mở trực tiếp File Explorer / Finder).
   * Nút **`▶️ Phát Video Ngay`** (mở xem ngay trên trình phát video mặc định).
