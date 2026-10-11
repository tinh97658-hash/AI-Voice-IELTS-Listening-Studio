# 🎙️ AI Voice & IELTS Listening Studio

Dự án chuyển đổi văn bản (Text) thành giọng nói (Speech) tự nhiên chất lượng cao sử dụng công nghệ **Microsoft Edge Neural TTS**, tích hợp phân hệ chuyên biệt **IELTS Listening Studio** tạo bài thi nghe chuẩn Cambridge đa Accent bản xứ, đi kèm giao diện Web tương tác đẹp mắt (**Streamlit**) và công cụ dòng lệnh (**CLI**).

---

## ✨ Điểm nổi bật

### 1. 🎓 IELTS Listening Studio (Tạo bài thi nghe chuẩn Cambridge & Phân loại Độ Khó)
- 🎯 **Phân loại Accent theo 3 cấp độ thử thách (Difficulty Levels):**
  - 🟢 **Dễ (Standard / Quen thuộc):**
    - **British (Anh - Anh)**: Ryan (Nam BBC), Sonia (Nữ Cambridge), Thomas (Nam Giảng viên), Libby (Nữ Sinh viên).
    - **American (Anh - Mỹ)**: Jenny, Guy, Aria, Christopher.
    - **Canadian (Anh - Canada)**: Clara, Liam.
  - 🟡 **Trung bình (Challenging / Đề thi thật):**
    - **Australian (Anh - Úc)**: Natasha (Nữ), William (Nam) - đặc trưng trong IELTS Section 1 & Section 2.
    - **New Zealand (Kiwi)**: Molly, Mitchell - biến âm nguyên âm ngắn đặc thù.
    - **Irish (Ireland)**: Emily, Connor - ngữ điệu du dương, lướt nhanh.
  - 🔴 **Khó (Extreme / Thách thức cao - Đi làm & Giao tiếp quốc tế):**
    - **Indian (Anh - Ấn)**: Neerja Expressive (Nữ), Prabhat (Nam), Neerja Standard - uốn lưỡi vòm họng (*retroflex /t/, /d/*), nhịp điệu *Syllable-timed* chuẩn xác.
    - **Singaporean (Singlish)**: Luna, Wayne - ngữ điệu nhanh, đảo câu.
    - **South African (Nam Phi)**: Leah, Luke - pha âm Afrikaans đặc trưng.
    - **Nigerian (Tây Phi)**: Ezinne, Abeo - giọng vang, nhấn âm đều.
- 👥 **Hội thoại phân vai (Dialogue):** Tự động nhận diện các nhân vật trong kịch bản (ví dụ: `Officer: ...` / `Customer: ...`) và gán riêng giọng đọc / Accent / Độ khó cho từng nhân vật.
- 🎙️ **Độc thoại / Thuyết trình học thuật (Monologue):** Dành cho Section 2 (Hướng dẫn tham quan) và Section 4 (Bài giảng học thuật đại học).
- ⏱️ **Căn chỉnh nhịp điệu bài thi:** Tùy chỉnh khoảng nghỉ giữa các lượt thoại (0.2s - 3.0s), tăng giảm tốc độ (-30% để luyện chép chính tả Dictation, +15% để ép phản xạ thi thật).
- 🔔 **Câu lệnh mở đầu chuẩn Cambridge:** Tự động phát lời dẫn *"You will hear... First, you have some time to look at questions..."* kèm 2 giây dừng đọc đề.
- 📋 **Có sẵn 5 Preset bài thi mẫu:** Bao gồm Section 1 đến Section 4 và **Preset Thử thách Độ Khó Cao (Họp dự án IT: Nữ Ấn Độ & Nam Anh)**.

### 2. 🇻🇳 Đọc văn bản tiếng Việt & Đa ngôn ngữ thông thường
- Giọng tiếng Việt cực kỳ tự nhiên: **Hoài My (Nữ)** truyền cảm, **Nam Minh (Nam)** trầm ấm rõ chữ.
- Hỗ trợ đa ngôn ngữ thế giới (Nhật, Hàn, Pháp, Trung, Đức,...).
- Hoàn toàn miễn phí, không cần API Key, không giới hạn ký tự.

### 3. 💾 Tối ưu Server Free & Phân trang Lịch sử Thông minh
- **Giới hạn lưu trữ tối đa 20 file MP3 trên server:** Tự động dọn dẹp các file cũ nhất (FIFO) khi vượt quá 20 file, giúp tiết kiệm dung lượng ổ cứng và bộ nhớ RAM, vận hành ổn định trên mọi server free (Streamlit Cloud, Render, Hugging Face...).
- **Phân trang lịch sử (Pagination):** Tối đa **4 trang**, mỗi trang **5 dòng lịch sử** ($4 \times 5 = 20$). Hỗ trợ nghe thử trực tiếp, tải về máy và xóa file chủ động.

### 4. 🧭 Điều hướng Routing, Tiến trình thời gian thực & Nút Hủy
- **Đồng bộ Route URL (`?tab=ielts`, `?page_i=2`):** Tab đang chọn và trang lịch sử hiện tại được lưu trực tiếp trên URL query parameters, giúp khi bấm **F5 (Refresh)** hoặc chia sẻ link không bị nhảy về Tab 1 hay Trang 1.
- **Tự động cuộn trang (Auto Scroll-to-Top):** Khi bấm nút tạo âm thanh/bài nghe, trang web sẽ tự động cuộn mượt mà lên đầu để người dùng theo dõi ngay tiến trình mà không cần cuộn tay.
- **Thanh tiến trình thời gian thực (Real-time Progress Bar):** Hiển thị rõ tỷ lệ % hoàn thành và tên nhân vật / câu thoại / đoạn văn bản đang được tổng hợp.
- **Nút Hủy quá trình (🛑 Cancel / Stop):** Cho phép người dùng dừng ngay lập tức quá trình tổng hợp nếu bài quá dài hoặc muốn đổi kịch bản khác.

---

## 📁 Cấu trúc thư mục

```text
AI voice/
├── venv/                 # Môi trường ảo Python
├── outputs/              # Thư mục chứa các file âm thanh MP3 đã xuất
├── tts_engine.py         # Module xử lý cốt lõi chuyển đổi TTS & IELTS Audio
├── app.py                # Giao diện Web Streamlit (2 Tabs: Văn bản & IELTS)
├── cli.py                # Công cụ dòng lệnh CLI
├── run_app.bat           # File click đúp chạy nhanh ứng dụng Web trên Windows
├── requirements.txt      # Danh sách thư viện phụ thuộc
└── README.md             # Hướng dẫn sử dụng
```

---

## 🚀 Hướng dẫn cài đặt & Khởi chạy

### 1. Khởi chạy nhanh bằng 1 cú click (Windows)
Chỉ cần nhấp đúp chuột vào file:
```text
run_app.bat
```
Trình duyệt sẽ tự động mở trang web điều khiển tại `http://localhost:8501`.

---

### 2. Khởi chạy thủ công qua Terminal

#### Kích hoạt môi trường ảo & Khởi động Web:
```powershell
.\venv\Scripts\activate
streamlit run app.py
```

---

### 3. Sử dụng công cụ dòng lệnh (CLI)

#### Xem danh sách giọng theo độ khó:
```powershell
# Xem tất cả giọng IELTS
python cli.py --list-ielts-voices

# Lọc riêng các giọng Độ Khó Cao (Accent Ấn Độ, Singapore, Nam Phi...)
python cli.py --list-ielts-voices --difficulty hard
```

#### Tạo nhanh bài nghe IELTS từ Preset có sẵn:
```powershell
# Tạo bài nghe Thử thách ĐỘ KHÓ CAO (Họp dự án IT: Nữ Ấn - Ấn & Nam Anh - Anh)
python cli.py --ielts-preset hard -o outputs/ielts_hard_it.mp3

# Tạo bài nghe Section 1 (Đăng ký CLB thể thao - Nữ Anh & Nam Úc)
python cli.py --ielts-preset section1 -o outputs/ielts_sec1.mp3

# Tạo bài nghe Section 4 (Bài giảng học thuật) với tốc độ tăng 10%
python cli.py --ielts-preset section4 --rate 10 -o outputs/ielts_sec4_fast.mp3
```

#### Đọc văn bản tiếng Việt thông thường:
```powershell
python cli.py -t "Xin chào bạn, chúc bạn một ngày tốt lành!" -o chao.mp3
```

---

### 4. Tích hợp vào code Python của bạn

#### Tạo bài nghe IELTS đa nhân vật trong Python:
```python
import tts_engine

script = """Receptionist: Good morning, South City Leisure Centre. How can I help you?
Customer: Hello, I would like to join the pool today.
Receptionist: Certainly! We offer several monthly plans."""

speaker_map = {
    "Receptionist": "en-GB-SoniaNeural",          # Nữ Anh - Anh
    "Customer": "en-AU-WilliamMultilingualNeural"  # Nam Anh - Úc
}

audio_bytes, path = tts_engine.generate_ielts_audio_sync(
    script_text=script,
    is_dialogue=True,
    speaker_voice_map=speaker_map,
    rate_percent=0,             # Tốc độ đọc
    pause_between_turns=0.8,    # Nghỉ 0.8s giữa các câu
    include_intro=True,         # Chèn lời dẫn Cambridge
    intro_text="You will hear a telephone conversation. First you have some time to look at questions one to five.",
    output_filepath="outputs/my_ielts_test.mp3"
)

print(f"Đã tạo file tại: {path}")
```
