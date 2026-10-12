import asyncio
import concurrent.futures
import io
import os
from typing import List, Dict, Optional, Tuple, Callable
import edge_tts

# Danh sách một số giọng phổ biến được cấu hình sẵn để người dùng dễ chọn nhanh
POPULAR_VOICES = [
    {
        "name": "vi-VN-HoaiMyNeural",
        "label": "Tiếng Việt • Hoài My (Nữ, Truyền cảm)",
        "locale": "vi-VN",
        "gender": "Female"
    },
    {
        "name": "vi-VN-NamMinhNeural",
        "label": "Tiếng Việt • Nam Minh (Nam, Trầm ấm)",
        "locale": "vi-VN",
        "gender": "Male"
    },
    {
        "name": "en-US-JennyNeural",
        "label": "English (US) • Jenny (Nữ, Tự nhiên)",
        "locale": "en-US",
        "gender": "Female"
    },
    {
        "name": "en-US-GuyNeural",
        "label": "English (US) • Guy (Nam, Thân thiện)",
        "locale": "en-US",
        "gender": "Male"
    },
    {
        "name": "en-US-AriaNeural",
        "label": "English (US) • Aria (Nữ, Chuyên nghiệp)",
        "locale": "en-US",
        "gender": "Female"
    },
    {
        "name": "en-GB-SoniaNeural",
        "label": "English (UK) • Sonia (Nữ, Chuẩn Cambridge)",
        "locale": "en-GB",
        "gender": "Female"
    },
    {
        "name": "ja-JP-NanamiNeural",
        "label": "Japanese • Nanami (Nữ, Chuẩn Tokyo)",
        "locale": "ja-JP",
        "gender": "Female"
    },
    {
        "name": "ko-KR-SunHiNeural",
        "label": "Korean • SunHi (Nữ)",
        "locale": "ko-KR",
        "gender": "Female"
    },
    {
        "name": "zh-CN-XiaoxiaoNeural",
        "label": "Chinese • Xiaoxiao (Nữ, Phổ thông)",
        "locale": "zh-CN",
        "gender": "Female"
    },
    {
        "name": "fr-FR-DeniseNeural",
        "label": "French • Denise (Nữ)",
        "locale": "fr-FR",
        "gender": "Female"
    }
]


def format_rate(rate_percent: int) -> str:
    """Định dạng tốc độ giọng đọc, ví dụ: +10% hoặc -15%"""
    return f"{'+' if rate_percent >= 0 else ''}{rate_percent}%"


def format_pitch(pitch_hz: int) -> str:
    """Định dạng cao độ giọng đọc, ví dụ: +5Hz hoặc -10Hz"""
    return f"{'+' if pitch_hz >= 0 else ''}{pitch_hz}Hz"


def format_volume(volume_percent: int) -> str:
    """Định dạng âm lượng, ví dụ: +0% hoặc -20%"""
    return f"{'+' if volume_percent >= 0 else ''}{volume_percent}%"


async def fetch_all_voices() -> List[Dict[str, str]]:
    """Lấy danh sách tất cả các giọng nói hỗ trợ từ Edge TTS."""
    try:
        voices = await edge_tts.list_voices()
        formatted = []
        for v in voices:
            formatted.append({
                "name": v["ShortName"],
                "gender": v["Gender"],
                "locale": v["Locale"],
                "label": f"{v['Locale']} - {v['ShortName']} ({v['Gender']})"
            })
        return formatted
    except Exception as e:
        print(f"Lỗi khi tải danh sách giọng nói: {e}")
        return POPULAR_VOICES


def split_text_into_chunks(text: str, max_chars: int = 1500) -> List[str]:
    """Chia văn bản dài thành các đoạn nhỏ hơn để tránh timeout và tối ưu xử lý."""
    if len(text) <= max_chars:
        return [text]
    
    paragraphs = text.split("\n")
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current_chunk) + len(para) + 1 <= max_chars:
            current_chunk = f"{current_chunk}\n{para}" if current_chunk else para
        else:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            
            # Nếu bản thân đoạn văn quá dài, chia theo câu
            if len(para) > max_chars:
                sentences = para.replace(". ", ".\n").replace("? ", "?\n").replace("! ", "!\n").split("\n")
                sub_chunk = ""
                for sent in sentences:
                    sent = sent.strip()
                    if not sent:
                        continue
                    if len(sub_chunk) + len(sent) + 1 <= max_chars:
                        sub_chunk = f"{sub_chunk} {sent}" if sub_chunk else sent
                    else:
                        if sub_chunk:
                            chunks.append(sub_chunk)
                        sub_chunk = sent
                if sub_chunk:
                    chunks.append(sub_chunk)
            else:
                current_chunk = para
                
    if current_chunk:
        chunks.append(current_chunk)
        
    return chunks if chunks else [text]


FALLBACK_VOICES = {
    "en-IE-EmilyNeural": "en-IE-ConnorNeural",
}


def get_configured_proxy() -> Optional[str]:
    """Lấy địa chỉ proxy nếu được cấu hình qua biến môi trường EDGE_TTS_PROXY hoặc HTTP(S)_PROXY."""
    p = os.environ.get("EDGE_TTS_PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    return p.strip() if (p and p.strip()) else None


async def _synthesize_chunk_with_retry(
    text: str,
    voice: str,
    rate: str,
    pitch: str,
    volume: str,
    max_retries: int = 4,
    proxy: Optional[str] = None
) -> bytes:
    """
    Tạo audio cho một đoạn văn bản kèm cơ chế tự động thử lại thông minh khi gặp
    sự cố mạng, lỗi 403 rate limit từ máy chủ Microsoft hoặc giọng bị lỗi âm thanh.
    Hỗ trợ kết nối qua Proxy để vượt qua IP bị chặn.
    """
    last_err = None
    curr_voice = voice
    proxy_url = proxy or get_configured_proxy()
    for attempt in range(max_retries):
        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=curr_voice,
                rate=rate,
                pitch=pitch,
                volume=volume,
                proxy=proxy_url
            )
            audio_buffer = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])
            data = audio_buffer.getvalue()
            if len(data) > 0:
                return data
        except edge_tts.exceptions.NoAudioReceived as e:
            last_err = e
            # Nếu giọng bị sự cố từ máy chủ (trả về 0 byte âm thanh), tự động fallback
            if curr_voice in FALLBACK_VOICES:
                curr_voice = FALLBACK_VOICES[curr_voice]
                await asyncio.sleep(0.5)
                continue
            elif curr_voice.startswith("en-"):
                curr_voice = "en-GB-RyanNeural"
                await asyncio.sleep(0.5)
                continue
            await asyncio.sleep(1.0 * (attempt + 1))
        except Exception as e:
            last_err = e
            err_msg = str(e)
            # Nếu gặp lỗi 403 (Microsoft rate-limit hoặc lệch token Sec-MS-GEC)
            if "403" in err_msg or "Invalid response status" in err_msg:
                try:
                    # Reset lại lệch đồng hồ DRM trong trường hợp bị tính lệch múi giờ
                    edge_tts.drm.DRM.clock_skew_seconds = 0.0
                except Exception:
                    pass
                # Giãn cách lũy tiến để máy chủ Microsoft giải phóng rate-limit: 2s, 4s, 7s, 10s
                sleep_sec = 2.0 * (attempt + 1)
                await asyncio.sleep(sleep_sec)
            else:
                await asyncio.sleep(1.0 * (attempt + 1))
            
    if last_err:
        raise last_err
    raise RuntimeError("Không nhận được dữ liệu âm thanh từ dịch vụ TTS.")


async def text_to_speech_bytes(
    text: str,
    voice: str = "vi-VN-HoaiMyNeural",
    rate: str = "+0%",
    pitch: str = "+0Hz",
    volume: str = "+0%",
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> bytes:
    """
    Chuyển đổi text thành dữ liệu bytes audio MP3 (hỗ trợ văn bản dài, retry và progress callback).
    """
    chunks = split_text_into_chunks(text)
    combined = io.BytesIO()
    total_chunks = len(chunks)
    for idx, chunk in enumerate(chunks):
        if idx > 0:
            await asyncio.sleep(0.6)
        if progress_callback:
            progress_callback(
                min(0.95, idx / max(1, total_chunks)),
                f"Đang tạo giọng đoạn {idx+1}/{total_chunks}..."
            )
        chunk_data = await _synthesize_chunk_with_retry(
            text=chunk,
            voice=voice,
            rate=rate,
            pitch=pitch,
            volume=volume
        )
        combined.write(chunk_data)
        if progress_callback:
            progress_callback(
                min(1.0, (idx + 1) / max(1, total_chunks)),
                f"Đã xử lý xong đoạn {idx+1}/{total_chunks}"
            )
        
    return combined.getvalue()


async def text_to_speech_file(
    text: str,
    output_filepath: str,
    voice: str = "vi-VN-HoaiMyNeural",
    rate: str = "+0%",
    pitch: str = "+0Hz",
    volume: str = "+0%",
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> str:
    """
    Chuyển đổi text và lưu trực tiếp ra file MP3.
    """
    audio_bytes = await text_to_speech_bytes(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch,
        volume=volume,
        progress_callback=progress_callback
    )
    with open(output_filepath, "wb") as f:
        f.write(audio_bytes)
    return output_filepath


def _run_sync(coro_fn, *args, **kwargs):
    """
    Chạy coroutine an toàn từ môi trường đồng bộ (sync),
    hoạt động hoàn hảo trong CLI, script thông thường và luồng ứng dụng của Streamlit.
    """
    def _worker():
        return asyncio.run(coro_fn(*args, **kwargs))

    try:
        asyncio.get_running_loop()
        # Nếu đã có event loop đang chạy (ví dụ trong Streamlit)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(_worker).result()
    except RuntimeError:
        # Nếu chưa có loop đang chạy
        return asyncio.run(coro_fn(*args, **kwargs))


def run_tts_sync(
    text: str,
    voice: str = "vi-VN-HoaiMyNeural",
    rate_percent: int = 0,
    pitch_hz: int = 0,
    volume_percent: int = 0,
    output_filepath: Optional[str] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    **kwargs
) -> Tuple[bytes, Optional[str]]:
    """
    Wrapper đồng bộ (sync) tiện lợi để gọi từ các môi trường như Streamlit hoặc CLI script.
    Trả về: (audio_bytes, output_filepath)
    """
    rate = format_rate(rate_percent)
    pitch = format_pitch(pitch_hz)
    volume = format_volume(volume_percent)

    audio_bytes = _run_sync(
        text_to_speech_bytes,
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch,
        volume=volume,
        progress_callback=progress_callback
    )

    if output_filepath:
        dirname = os.path.dirname(output_filepath)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(output_filepath, "wb") as f:
            f.write(audio_bytes)
            
    return audio_bytes, output_filepath


def get_all_voices_sync() -> List[Dict[str, str]]:
    """Lấy danh sách tất cả giọng nói đồng bộ."""
    return _run_sync(fetch_all_voices)


# ==========================================================
# CẤU HÌNH PHÂN LOẠI ĐỘ KHÓ & ACCENT CHO BÀI THI IELTS
# ==========================================================

DIFFICULTY_LEVELS = {
    "all": "Tất cả độ khó (All Levels)",
    "easy": "Dễ • Standard (Anh-Mỹ, Anh-Anh RP, Canada)",
    "medium": "Trung bình • Challenging (Anh-Úc, New Zealand, Ireland)",
    "hard": "Khó • Extreme (Anh-Ấn Độ, Singapore, Nam Phi, Nigeria)"
}

DIFFICULTY_DETAILS = {
    "easy": {
        "badge": "Dễ (Standard)",
        "color": "#16A34A",
        "desc": "Phát âm chuẩn mực, tròn vành rõ chữ, quen thuộc với đại đa số người học qua phim ảnh & tài liệu luyện thi cơ bản.",
        "phonetics": "Ngữ điệu rõ ràng, nhả âm cuối (ending sounds) đầy đủ, phân biệt nguyên âm/phụ âm chuẩn quốc tế."
    },
    "medium": {
        "badge": "Trung bình (IELTS Exam)",
        "color": "#D97706",
        "desc": "Rất phổ biến trong Section 1 & Section 2 của các đề thi Cambridge IELTS thật.",
        "phonetics": "Biến đổi nguyên âm đặc trưng (ví dụ Úc & Kiwi: /ei/ thành /ai/, 'pen' nghe tựa như 'pin'), ngữ điệu lướt nhanh hoặc lên giọng cuối câu (uptalk)."
    },
    "hard": {
        "badge": "Khó (Extreme Accent)",
        "color": "#DC2626",
        "desc": "Các Accent có đặc trưng phương ngữ hoặc nhịp điệu phi bản xứ nặng (tiêu biểu là Accent Ấn Độ), đòi hỏi độ tập trung và phản xạ nghe cực cao.",
        "phonetics": "Âm uốn lưỡi vòm họng (retroflex /t/, /d/), nhịp điệu Syllable-timed (đều từng âm tiết thay vì nhấn trọng âm từ), biến âm /v/ và /w/, /p/ và /b/."
    }
}

IELTS_VOICES = {
    "British (UK) • Chuẩn BBC/RP [Dễ]": [
        {"name": "en-GB-RyanNeural", "label": "Ryan (Nam • Chuẩn BBC/RP, Điềm đạm)", "gender": "Male", "accent": "British", "difficulty": "easy"},
        {"name": "en-GB-SoniaNeural", "label": "Sonia (Nữ • Chuẩn Cambridge, Rõ chữ)", "gender": "Female", "accent": "British", "difficulty": "easy"},
        {"name": "en-GB-ThomasNeural", "label": "Thomas (Nam • Giảng viên, Học thuật)", "gender": "Male", "accent": "British", "difficulty": "easy"},
        {"name": "en-GB-LibbyNeural", "label": "Libby (Nữ • Trẻ trung, Sinh viên)", "gender": "Female", "accent": "British", "difficulty": "easy"},
        {"name": "en-GB-MaisieNeural", "label": "Maisie (Nữ • Đời thường, Tự nhiên)", "gender": "Female", "accent": "British", "difficulty": "easy"}
    ],
    "American (US) • Chuẩn Bắc Mỹ [Dễ]": [
        {"name": "en-US-JennyNeural", "label": "Jenny (Nữ • Trong trẻo, Tự nhiên)", "gender": "Female", "accent": "American", "difficulty": "easy"},
        {"name": "en-US-GuyNeural", "label": "Guy (Nam • Tự nhiên, Thân thiện)", "gender": "Male", "accent": "American", "difficulty": "easy"},
        {"name": "en-US-AriaNeural", "label": "Aria (Nữ • Học thuật, Chuyên nghiệp)", "gender": "Female", "accent": "American", "difficulty": "easy"},
        {"name": "en-US-ChristopherNeural", "label": "Christopher (Nam • Phát âm chuẩn xác)", "gender": "Male", "accent": "American", "difficulty": "easy"}
    ],
    "Canadian (CA) • Chuẩn Canada [Dễ]": [
        {"name": "en-CA-ClaraNeural", "label": "Clara (Nữ • Giọng Canada chuẩn)", "gender": "Female", "accent": "Canadian", "difficulty": "easy"},
        {"name": "en-CA-LiamNeural", "label": "Liam (Nam • Giọng Canada tự nhiên)", "gender": "Male", "accent": "Canadian", "difficulty": "easy"}
    ],
    "Australian (AU) • Anh - Úc [Trung bình]": [
        {"name": "en-AU-NatashaNeural", "label": "Natasha (Nữ • Giọng Úc đề thi IELTS)", "gender": "Female", "accent": "Australian", "difficulty": "medium"},
        {"name": "en-AU-WilliamMultilingualNeural", "label": "William (Nam • Giọng Úc tự nhiên, Trầm ấm)", "gender": "Male", "accent": "Australian", "difficulty": "medium"}
    ],
    "New Zealand (NZ) • Kiwi Accent [Trung bình]": [
        {"name": "en-NZ-MollyNeural", "label": "Molly (Nữ • Biến âm nguyên âm ngắn Kiwi)", "gender": "Female", "accent": "New Zealand", "difficulty": "medium"},
        {"name": "en-NZ-MitchellNeural", "label": "Mitchell (Nam • Giọng Kiwi bản xứ)", "gender": "Male", "accent": "New Zealand", "difficulty": "medium"}
    ],
    "Irish (IE) • Ireland [Trung bình]": [
        {"name": "en-IE-ConnorNeural", "label": "Connor (Nam • Giọng Ireland tự nhiên)", "gender": "Male", "accent": "Irish", "difficulty": "medium"}
    ],
    "Indian (IN) • Anh - Ấn [Khó]": [
        {"name": "en-IN-NeerjaExpressiveNeural", "label": "Neerja (Nữ • Giọng Ấn tự nhiên, Đặc trưng)", "gender": "Female", "accent": "Indian", "difficulty": "hard"},
        {"name": "en-IN-PrabhatNeural", "label": "Prabhat (Nam • Giọng Ấn chuẩn, Nhịp Syllable-timed)", "gender": "Male", "accent": "Indian", "difficulty": "hard"},
        {"name": "en-IN-NeerjaNeural", "label": "Neerja Standard (Nữ • Giọng Ấn công sở, Rõ âm)", "gender": "Female", "accent": "Indian", "difficulty": "hard"}
    ],
    "Singaporean (SG) • Singlish [Khó]": [
        {"name": "en-SG-LunaNeural", "label": "Luna (Nữ • Giọng Singapore ngữ điệu nhanh)", "gender": "Female", "accent": "Singaporean", "difficulty": "hard"},
        {"name": "en-SG-WayneNeural", "label": "Wayne (Nam • Giọng Singapore tự nhiên)", "gender": "Male", "accent": "Singaporean", "difficulty": "hard"}
    ],
    "South African (ZA) • Nam Phi [Khó]": [
        {"name": "en-ZA-LeahNeural", "label": "Leah (Nữ • Giọng Nam Phi nguyên âm dẹt)", "gender": "Female", "accent": "South African", "difficulty": "hard"},
        {"name": "en-ZA-LukeNeural", "label": "Luke (Nam • Giọng Nam Phi trầm, Âm đóng)", "gender": "Male", "accent": "South African", "difficulty": "hard"}
    ],
    "Nigerian (NG) • Tây Phi [Khó]": [
        {"name": "en-NG-EzinneNeural", "label": "Ezinne (Nữ • Giọng Tây Phi vang, Nhấn âm đều)", "gender": "Female", "accent": "Nigerian", "difficulty": "hard"},
        {"name": "en-NG-AbeoNeural", "label": "Abeo (Nam • Giọng Tây Phi trầm ấm)", "gender": "Male", "accent": "Nigerian", "difficulty": "hard"}
    ]
}


def get_all_ielts_voices_flat(difficulty: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Trả về danh sách phẳng các giọng IELTS.
    Nếu có tham số difficulty ('easy', 'medium', 'hard'), chỉ trả về giọng thuộc độ khó đó.
    """
    flat_list = []
    for category, voices in IELTS_VOICES.items():
        for v in voices:
            if not difficulty or difficulty == "all" or v.get("difficulty") == difficulty:
                flat_list.append(v)
    return flat_list


IELTS_PRESETS = {
    "Section 1: Đăng ký CLB thể thao (Hội thoại: Nữ Anh - Anh & Nam Anh - Úc)": {
        "type": "dialogue",
        "intro": "You will hear a telephone conversation between a leisure centre receptionist and a customer inquiring about membership. First, you have some time to look at questions one to five.",
        "speaker_defaults": {
            "Receptionist": "en-GB-SoniaNeural",
            "Customer": "en-AU-WilliamMultilingualNeural"
        },
        "script": """Receptionist: Good morning, South City Leisure Centre. How can I help you today?
Customer: Hello. I've recently moved to the area and I'd like some information about joining the sports center.
Receptionist: Certainly! We have a number of different membership schemes. Are you interested in using the gym, the swimming pool, or both?
Customer: Well, mainly the pool, but I'd like to use the gym occasionally on weekends.
Receptionist: In that case, our Silver Package would be ideal. It includes unlimited pool access and weekend gym sessions for forty-five pounds a month.
Customer: That sounds reasonable. Do I need to book an induction session for the gym?
Receptionist: Yes, all new members must attend a thirty-minute induction with a personal trainer before using the equipment.
Customer: Perfect. Can I arrange that for this Saturday morning, say around ten o'clock?
Receptionist: Let me check the schedule... Yes, ten o'clock on Saturday is available. Could I take your full name and contact number, please?"""
    },
    "Section 2: Hướng dẫn tham quan khu bảo tồn (Độc thoại: Nữ Anh - Úc)": {
        "type": "monologue",
        "intro": "You will hear a tour guide introducing visitors to the Green Valley Nature Reserve. First, you have some time to look at questions eleven to sixteen.",
        "default_voice": "en-AU-NatashaNeural",
        "script": """Welcome everyone to the Green Valley Nature Reserve. My name is Sarah, and I'll be your guide for this morning's walking tour. Before we set off, I'd like to give you a brief overview of the reserve and some important safety advice.
The reserve covers approximately two hundred hectares of native woodland and wetland. It was established thirty years ago to protect several endangered bird species, including the rare crested crane.
If you look at the map on your brochures, you'll see three main walking trails. We will be taking the Blue Trail, which is about three kilometers long and takes roughly one hour at a gentle pace.
Please make sure you stay on the marked paths at all times, as the surrounding vegetation is fragile. Also, remember that feeding the wildlife is strictly prohibited. Now, if everyone is ready, let's begin our tour by heading toward the observation hide."""
    },
    "Section 3: Thảo luận bài tập nhóm (Hội thoại 2 người: Nam Anh - Anh & Nữ Anh - Mỹ)": {
        "type": "dialogue",
        "intro": "You will hear two university students, Jack and Emma, discussing their marketing assignment. First, you have some time to look at questions twenty-one to twenty-five.",
        "speaker_defaults": {
            "Jack": "en-GB-RyanNeural",
            "Emma": "en-US-JennyNeural"
        },
        "script": """Jack: Hi Emma, thanks for meeting up. Have you had time to look over our assignment guidelines for the marketing project?
Emma: Hi Jack. Yes, I read through the brief yesterday. It seems we need to select a small local business and analyze their digital advertising strategy.
Jack: Right. And Professor Davis mentioned that our primary focus should be on how social media impacts customer engagement.
Emma: Exactly. I was thinking we could look at the independent bookshop on High Street. They started an online delivery service last year.
Jack: That's a great idea! They have an active Instagram account, so we'll have plenty of data to evaluate.
Emma: What about the survey? The rubric says we need responses from at least fifty customers.
Jack: We can design a short questionnaire on Google Forms and ask the store manager if they can share the link on their Facebook page.
Emma: Sounds good. Let's draft the questions this evening and meet again on Thursday to finalize everything."""
    },
    "Section 3: Thảo luận nhóm 3 người (Giảng viên Nam Anh, Nữ sinh Úc & Nam sinh Ấn)": {
        "type": "dialogue",
        "intro": "You will hear a university tutor, Dr. Evans, discussing a research presentation with two postgraduate students, Chloe and Aryan. First, you have some time to look at questions twenty-one to twenty-six.",
        "speaker_defaults": {
            "Dr. Evans": "en-GB-ThomasNeural",
            "Chloe": "en-AU-NatashaNeural",
            "Aryan": "en-IN-PrabhatNeural"
        },
        "script": """Dr. Evans: Good afternoon, Chloe and Aryan. Come on in. How is the preparation for your renewable energy presentation coming along?
Chloe: Good afternoon, Dr. Evans. We've structured the slides into three main areas: solar, offshore wind, and battery storage.
Aryan: Yes, and I've compiled the comparative data on investment returns across different regions. However, we're still debating how much time to allocate to emerging green hydrogen technologies.
Dr. Evans: That's a thoughtful question, Aryan. Remember that your presentation is limited to twenty minutes. I suggest keeping hydrogen as a concluding point rather than a core chapter.
Chloe: That makes complete sense. We wouldn't want to rush through the primary wind and solar case studies.
Aryan: Exactly. I will rebalance the statistical charts this evening to reflect that emphasis.
Dr. Evans: Excellent. Send me your revised slide deck by Wednesday, and we can do a quick dry run before Friday's seminar."""
    },
    "Section 4: Bài giảng học thuật về rạn san hô (Độc thoại: Giảng viên Nam Anh - Anh)": {
        "type": "monologue",
        "intro": "You will hear an academic lecture on marine biology and the conservation of coral reefs. First, you have some time to look at questions thirty-one to forty.",
        "default_voice": "en-GB-ThomasNeural",
        "script": """Good morning, everyone. In today's lecture, we are going to examine the ecological significance of coral reef ecosystems and the contemporary challenges they face due to climate change.
Coral reefs are often described as the rainforests of the ocean. Despite occupying less than zero point one percent of the marine environment, they provide a habitat for more than twenty-five percent of all marine species.
The foundation of any reef is the coral polyp, a tiny invertebrate that secretes calcium carbonate to form a hard, protective skeleton. However, the survival of coral relies fundamentally on a symbiotic relationship with microscopic algae known as zooxanthellae.
When sea surface temperatures rise even by one or two degrees Celsius above the seasonal maximum, corals become stressed and expel these algae. This phenomenon is known as coral bleaching. Without the algae, the coral loses its primary source of nutrition and will eventually die if elevated temperatures persist for an extended period.
Recent satellite observations suggest that mass bleaching events are occurring with increasing frequency, leaving ecosystems less time to recover between thermal anomalies."""
    },
    "Thử thách KHÓ (Hard): Họp dự án Công nghệ (Hội thoại: Nữ Ấn - Ấn & Nam Anh - Anh)": {
        "type": "dialogue",
        "difficulty": "hard",
        "intro": "You will hear a project coordination meeting between an IT lead from Bangalore, Priya, and a software architect from London, David, discussing system migration. First, you have some time to look at questions twenty-one to twenty-six.",
        "speaker_defaults": {
            "Priya": "en-IN-NeerjaExpressiveNeural",
            "David": "en-GB-RyanNeural"
        },
        "script": """Priya: Good morning David. Thank you for joining our project sync today. Have you reviewed the migration schedule for our database cluster?
David: Good morning Priya. Yes, I went through the timeline. Moving the production database during peak hours on Thursday might cause latency issues.
Priya: That is a very valid concern, David. However, our Bangalore DevOps team will provide round-the-clock monitoring to maintain data consistency.
David: That's reassuring. What about the contingency rollback plan if the API gateway fails to respond?
Priya: I have already instructed the infrastructure leads to prepare automated backup snapshots prior to deployment. We will test this procedure in the staging environment this afternoon.
David: Brilliant. I will run the benchmark tests and share the performance metrics with you by five PM.
Priya: Excellent. Let us ensure all configuration dependencies are strictly documented before we proceed."""
    }
}


def generate_silence_mp3(seconds: float) -> bytes:
    """Tạo khoảng lặng MP3 chuẩn xác (24kHz 48kbps mono, 24ms mỗi frame)."""
    if seconds <= 0:
        return b""
    silent_frame = bytes.fromhex("fff364c4") + b"\x00" * 140
    frame_duration = 0.024
    num_frames = max(1, int(round(seconds / frame_duration)))
    return silent_frame * num_frames


def is_valid_speaker_name(candidate: str) -> bool:
    """Kiểm tra một chuỗi có phải là tên nhân vật hợp lệ hay không."""
    candidate = candidate.strip().strip("[](){}「」:：-")
    if not candidate or len(candidate) > 25:
        return False
    # Tên nhân vật không chứa dấu phẩy, chấm than, hỏi, ngoặc kép, nháy đơn
    if any(ch in candidate for ch in [',', '!', '?', ';', '"', '“', '”', "'", '’']):
        return False
    words = candidate.split()
    if len(words) > 4:
        return False
    # Không phải là các từ mệnh đề hoặc từ thông dụng đứng trước dấu hai chấm
    invalid_words = {'guess', 'think', 'know', 'remember', 'see', 'note', 'time', 'date', 'warning', 'tip', 'say', 'said'}
    if any(w.lower() in invalid_words for w in words):
        return False
    return True


def parse_dialogue(script_text: str) -> List[Tuple[str, str]]:
    """
    Phân tích kịch bản thành danh sách [(speaker_name, dialogue_line)].
    Hỗ trợ linh hoạt:
    - Tên nhân vật cùng dòng: 'CLERK: Good morning.'
    - Tên nhân vật đứng riêng ở 1 dòng:
        CLERK:
        Good morning.
    - Dạng ngoặc: '[CLERK] Good morning' hoặc '(CLERK) Good morning'
    - Tự động tránh nhận diện nhầm các dấu hai chấm ở giữa câu văn thông thường.
    """
    lines = script_text.strip().split("\n")
    turns = []
    current_speaker = None
    current_lines = []
    
    def flush():
        nonlocal current_speaker, current_lines
        if current_speaker and current_lines:
            text = " ".join(current_lines).strip()
            if text:
                turns.append((current_speaker, text))
            current_lines = []
    
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
            
        # 1. Tên nhân vật đứng riêng trên 1 dòng kết thúc bằng dấu ':' (Ví dụ 'CLERK:' hoặc 'WOMAN:')
        matched_header = False
        for delim in [':', '：']:
            if line.endswith(delim):
                candidate = line[:-1].strip()
                if is_valid_speaker_name(candidate):
                    flush()
                    current_speaker = candidate.strip("[](){}「」")
                    matched_header = True
                    break
        if matched_header:
            continue
            
        # 2. Dòng chỉ chứa '[CLERK]' hoặc '(CLERK)'
        if (line.startswith('[') and line.endswith(']')) or (line.startswith('(') and line.endswith(')')):
            candidate = line[1:-1].strip()
            if is_valid_speaker_name(candidate):
                flush()
                current_speaker = candidate
                continue
                
        # 3. Tên nhân vật cùng dòng 'CLERK: Lời thoại...' hoặc 'CLERK - Lời thoại...'
        matched_inline = False
        for delim in [':', '：', ' - ']:
            if delim in line:
                parts = line.split(delim, 1)
                candidate = parts[0].strip()
                content = parts[1].strip()
                if is_valid_speaker_name(candidate) and content:
                    flush()
                    current_speaker = candidate.strip("[](){}「」")
                    current_lines.append(content)
                    matched_inline = True
                    break
        if matched_inline:
            continue
            
        # 4. Dòng văn bản bình thường (nối tiếp vào lượt nói của speaker hiện tại)
        if current_speaker is None:
            current_speaker = "Speaker 1"
        current_lines.append(line)
        
    flush()
    return turns


async def _generate_ielts_audio_async(
    script_text: str,
    is_dialogue: bool,
    speaker_voice_map: Dict[str, str],
    single_voice: str,
    rate_percent: int = 0,
    pitch_hz: int = 0,
    volume_percent: int = 0,
    pause_between_turns: float = 0.8,
    include_intro: bool = False,
    intro_text: str = "",
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> bytes:
    rate = format_rate(rate_percent)
    pitch = format_pitch(pitch_hz)
    volume = format_volume(volume_percent)
    
    combined = io.BytesIO()
    
    turns = parse_dialogue(script_text) if is_dialogue else []
    total_steps = (1 if (include_intro and intro_text.strip()) else 0) + (len(turns) if is_dialogue else 1)
    step_count = 0

    if progress_callback:
        progress_callback(0.02, "Khởi tạo bài nghe IELTS...")

    # 1. Nếu có phần giới thiệu chuẩn IELTS ("You will hear...")
    if include_intro and intro_text.strip():
        step_count += 1
        if progress_callback:
            progress_callback(
                min(0.95, step_count / total_steps),
                "Đang tạo lời giới thiệu chuẩn Cambridge (Intro)..."
            )
        intro_voice = "en-GB-RyanNeural"
        intro_data = await _synthesize_chunk_with_retry(
            text=intro_text.strip(),
            voice=intro_voice,
            rate="+0%",
            pitch="+0Hz",
            volume="+0%"
        )
        combined.write(intro_data)
        # Chèn khoảng dừng 2.0s để thí sinh đọc đề
        combined.write(generate_silence_mp3(2.0))
        await asyncio.sleep(0.8)

    # 2. Xử lý phần nội dung chính
    if is_dialogue:
        silence_between_turns = generate_silence_mp3(pause_between_turns)
        
        for idx, (speaker, line) in enumerate(turns):
            step_count += 1
            if progress_callback:
                progress_callback(
                    min(0.95, step_count / total_steps),
                    f"Đang tạo lượt thoại {idx+1}/{len(turns)}: {speaker}..."
                )
            if idx > 0:
                await asyncio.sleep(0.8)
            voice = speaker_voice_map.get(speaker, single_voice or "en-GB-RyanNeural")
            line_audio = await text_to_speech_bytes(
                text=line,
                voice=voice,
                rate=rate,
                pitch=pitch,
                volume=volume
            )
            combined.write(line_audio)
            # Thêm khoảng lặng giữa các lượt nói
            if idx < len(turns) - 1 and pause_between_turns > 0:
                combined.write(silence_between_turns)
    else:
        step_count += 1
        if progress_callback:
            progress_callback(0.4, "Đang tạo giọng đọc bài giảng độc thoại...")
        mono_audio = await text_to_speech_bytes(
            text=script_text.strip(),
            voice=single_voice or "en-GB-RyanNeural",
            rate=rate,
            pitch=pitch,
            volume=volume
        )
        combined.write(mono_audio)

    if progress_callback:
        progress_callback(1.0, "Đang hoàn tất bài nghe IELTS...")

    return combined.getvalue()


def generate_ielts_audio_sync(
    script_text: str,
    is_dialogue: bool,
    speaker_voice_map: Dict[str, str],
    single_voice: str = "en-GB-RyanNeural",
    rate_percent: int = 0,
    pitch_hz: int = 0,
    volume_percent: int = 0,
    pause_between_turns: float = 0.8,
    include_intro: bool = False,
    intro_text: str = "",
    output_filepath: Optional[str] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    **kwargs
) -> Tuple[bytes, Optional[str]]:
    """Tạo audio bài nghe IELTS hoàn chỉnh đồng bộ kèm theo dõi tiến trình."""
    audio_bytes = _run_sync(
        _generate_ielts_audio_async,
        script_text=script_text,
        is_dialogue=is_dialogue,
        speaker_voice_map=speaker_voice_map,
        single_voice=single_voice,
        rate_percent=rate_percent,
        pitch_hz=pitch_hz,
        volume_percent=volume_percent,
        pause_between_turns=pause_between_turns,
        include_intro=include_intro,
        intro_text=intro_text,
        progress_callback=progress_callback
    )

    if output_filepath:
        dirname = os.path.dirname(output_filepath)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(output_filepath, "wb") as f:
            f.write(audio_bytes)

    return audio_bytes, output_filepath
