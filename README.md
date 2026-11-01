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
   * 🌟 **Trọn Gói Tự Động (Hook 30s + Nhịp + Sub Tiếng Anh)**: Quét chuyển cảnh và độ lớn âm thanh của cả video, chấm điểm mọi đoạn 24-36s (độ lớn, đỉnh âm, độ dồn lên cuối, nhịp cắt, mật độ thoại) để chọn đoạn cao trào. Thêm punch zoom ở mỗi điểm chuyển cảnh, nhấn mạnh tại điểm cao trào (zoom + boom), whoosh theo nhịp cắt và sub tiếng Anh chữ nổi.
   * ✂️ **Tạo Nhịp & Sub Cho Video Cắt Sẵn**: Giữ nguyên toàn bộ thời lượng video đã cắt sẵn, bổ sung nhịp giật visual, hiệu ứng âm thanh và sub.
   * 🎯 **Chỉ Cắt Hook 30s**: Chọn đoạn cao trào như trên, giữ nguyên âm thanh gốc, không thêm hiệu ứng.
4. **Phụ Đề Tiếng Anh Chữ Nổi**:
   * Chữ trắng đậm, viền đen dày, bóng đổ mềm, không có nền; tự xuống tối đa 2 dòng.
   * Đặt ở Safe Zone `Y: 1530` (không bị giao diện TikTok/Reels che khuất).
   * Lưu ý: chữ nổi không che phụ đề cứng có sẵn trong video gốc.
   * Video ngang hoặc vuông được đặt giữa khung 9:16 trên nền mờ, không bị kéo méo.
5. **Tiến Trình Thời Gian Thực & Chẩn Đoán %**:
   * Thanh tiến trình mượt mà từ 0% đến 100%.
   * Ô Console Log hiển thị chi tiết nhật ký từng khung hình đang chạy.
   * Nút **`⏹ HỦY TIẾN TRÌNH`** an toàn nếu muốn dừng giữa chừng.
6. **Thông Báo & Phát Video Khi Hoàn Tất**:
   * Tự động phát âm thanh chuông báo và hiển thị thông báo Desktop (Windows Toast / macOS Notification Center).
   * Nút **`📂 Mở Thư Mục Chứa Video`** (mở trực tiếp File Explorer / Finder).
   * Nút **`▶️ Phát Video Ngay`** (mở xem ngay trên trình phát video mặc định).
