import datetime
import importlib
import os
import streamlit as st
import streamlit.components.v1 as components
import mutagen.mp3
import tts_engine

# Luôn reload tts_engine để cập nhật thay đổi mã nguồn ngay lập tức trong Streamlit
importlib.reload(tts_engine)

# Thiết lập cấu hình trang Streamlit
st.set_page_config(
    page_title="AI Voice & IELTS Listening Studio",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Cấu hình giới hạn lưu trữ & phân trang
MAX_STORED_FILES = 20  # Tối đa 20 file MP3 lưu trên server
PAGE_SIZE = 5          # 5 dòng lịch sử mỗi trang
MAX_PAGES = 4          # Tối đa 4 trang (4 x 5 = 20 dòng)


def trigger_scroll_to_top():
    """Tự động cuộn trang lên đầu mượt mà ngay khi bắt đầu xử lý tạo âm thanh."""
    # 1. Kích hoạt scroll qua components.html (chạy trực tiếp script trong cùng origin)
    components.html("""
        <script>
            (function() {
                function scrollNow() {
                    try {
                        const doc = window.parent.document;
                        const title = doc.querySelector('.main-title') || doc.querySelector('[data-testid="stAppViewContainer"] h1') || doc.body;
                        if (title && typeof title.scrollIntoView === 'function') {
                            title.scrollIntoView({ behavior: 'smooth', block: 'start' });
                        }
                        const scrollable = doc.querySelector('[data-testid="stAppViewContainer"]') || 
                                           doc.querySelector('.main') || 
                                           doc.querySelector('section.main') || 
                                           doc.documentElement;
                        if (scrollable && typeof scrollable.scrollTo === 'function') {
                            scrollable.scrollTo({ top: 0, behavior: 'smooth' });
                        }
                        window.parent.scrollTo({ top: 0, behavior: 'smooth' });
                    } catch(err) {
                        console.error("Scroll error:", err);
                    }
                }
                scrollNow();
                setTimeout(scrollNow, 60);
                setTimeout(scrollNow, 200);
            })();
        </script>
    """, height=0, width=0)

    # 2. Bổ trợ thêm bằng onload event trên inline element
    st.markdown("""
        <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E" 
             onload="(function(){
                 try {
                     const target = window.parent.document.querySelector('.main-title') || 
                                  window.parent.document.querySelector('[data-testid=\\'stAppViewContainer\\']') || 
                                  window.parent.document.documentElement;
                     if (target && typeof target.scrollIntoView === 'function') {
                         target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                     } else if (target && typeof target.scrollTo === 'function') {
                         target.scrollTo({ top: 0, behavior: 'smooth' });
                     }
                 } catch(e){}
             })(); this.remove();" 
             style="display:none;" />
    """, unsafe_allow_html=True)


def prune_server_storage(output_dir: str, max_files: int = MAX_STORED_FILES) -> set:
    """
    Dọn dẹp các file MP3 cũ nhất trên server để tổng số file không vượt quá max_files.
    Trả về tập hợp các tên file đã bị xóa.
    """
    if not os.path.exists(output_dir):
        return set()

    mp3_files = []
    for f in os.listdir(output_dir):
        if f.lower().endswith(".mp3"):
            fpath = os.path.join(output_dir, f)
            if os.path.isfile(fpath):
                try:
                    mp3_files.append((fpath, f, os.path.getmtime(fpath)))
                except OSError:
                    pass

    # Sắp xếp mới nhất trước
    mp3_files.sort(key=lambda x: x[2], reverse=True)

    removed_set = set()
    if len(mp3_files) > max_files:
        for fpath, fname, _ in mp3_files[max_files:]:
            try:
                os.remove(fpath)
                removed_set.add(fname)
            except OSError:
                pass
    return removed_set


def sync_and_cleanup_history(output_dir: str):
    """
    Dọn dẹp file thừa trên server và đồng bộ lại session_state lịch sử:
    - Loại bỏ file bị xóa trên ổ đĩa
    - Đảm bảo mỗi danh sách lịch sử không vượt quá MAX_STORED_FILES (20)
    """
    removed_files = prune_server_storage(output_dir, MAX_STORED_FILES)

    if "history_general" in st.session_state:
        st.session_state.history_general = [
            item for item in st.session_state.history_general
            if item.get("file_name") not in removed_files
            and os.path.exists(os.path.join(output_dir, item.get("file_name", "")))
        ][:MAX_STORED_FILES]

    if "history_ielts" in st.session_state:
        st.session_state.history_ielts = [
            item for item in st.session_state.history_ielts
            if item.get("file_name") not in removed_files
            and os.path.exists(os.path.join(output_dir, item.get("file_name", "")))
        ][:MAX_STORED_FILES]


def load_existing_files_to_history(output_dir: str):
    """
    Nạp các file MP3 sẵn có từ outputs/ vào lịch sử nếu session state chưa có dữ liệu.
    """
    if not os.path.exists(output_dir):
        return

    mp3_files = []
    for f in os.listdir(output_dir):
        if f.lower().endswith(".mp3"):
            fpath = os.path.join(output_dir, f)
            if os.path.isfile(fpath):
                try:
                    mp3_files.append((fpath, f, os.path.getmtime(fpath)))
                except OSError:
                    pass

    mp3_files.sort(key=lambda x: x[2], reverse=True)

    general_items = []
    ielts_items = []

    for fpath, fname, mtime in mp3_files[:MAX_STORED_FILES]:
        time_str = datetime.datetime.fromtimestamp(mtime).strftime("%H:%M:%S")
        try:
            with open(fpath, "rb") as af:
                audio_bytes = af.read()
        except Exception:
            continue

        if "ielts" in fname.lower():
            audio_len = "N/A"
            try:
                info = mutagen.mp3.MP3(fpath).info
                mins = int(info.length // 60)
                secs = int(info.length % 60)
                audio_len = f"{mins:02d}:{secs:02d} ({round(info.length, 1)}s)"
            except Exception:
                pass

            ielts_items.append({
                "title": fname.replace(".mp3", "").replace("_", " "),
                "time": time_str,
                "length": audio_len,
                "audio_bytes": audio_bytes,
                "file_name": fname
            })
        else:
            general_items.append({
                "text": fname.replace(".mp3", "").replace("_", " "),
                "voice": "Edge Neural TTS",
                "time": time_str,
                "audio_bytes": audio_bytes,
                "file_name": fname
            })

    if not st.session_state.get("history_general") and general_items:
        st.session_state.history_general = general_items[:MAX_STORED_FILES]
    if not st.session_state.get("history_ielts") and ielts_items:
        st.session_state.history_ielts = ielts_items[:MAX_STORED_FILES]


def render_paginated_history(history_type: str, page_key: str, output_dir: str):
    """
    Hiển thị giao diện lịch sử với phân trang tối đa 4 trang, mỗi trang 5 dòng.
    """
    history_list = st.session_state.get(f"history_{history_type}", [])
    if not history_list:
        return

    # Giới hạn tối đa MAX_STORED_FILES (20)
    if len(history_list) > MAX_STORED_FILES:
        history_list = history_list[:MAX_STORED_FILES]
        st.session_state[f"history_{history_type}"] = history_list

    total_items = len(history_list)
    total_pages = min(MAX_PAGES, max(1, (total_items + PAGE_SIZE - 1) // PAGE_SIZE))

    qp_param = "page_g" if history_type == "general" else "page_i"
    # Đồng bộ số trang từ URL query param để khi F5 không bị nhảy về trang 1
    if qp_param in st.query_params:
        try:
            val_p = int(st.query_params[qp_param])
            if 1 <= val_p <= total_pages:
                st.session_state[page_key] = val_p
        except ValueError:
            pass

    if page_key not in st.session_state:
        st.session_state[page_key] = 1

    current_page = st.session_state[page_key]
    if current_page > total_pages:
        current_page = total_pages
        st.session_state[page_key] = current_page
    if current_page < 1:
        current_page = 1
        st.session_state[page_key] = current_page

    start_idx = (current_page - 1) * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, total_items)
    page_items = history_list[start_idx:end_idx]

    # Tiêu đề và badge thông tin trang
    st.markdown("---")
    header_col1, header_col2 = st.columns([1.4, 1])
    with header_col1:
        title_text = ":material/history: Lịch sử chuyển đổi văn bản" if history_type == "general" else ":material/history: Lịch sử bài nghe IELTS đã tạo"
        st.subheader(title_text)
    with header_col2:
        st.markdown(
            f"""<div style="text-align: right; padding-top: 6px;">
                <span style="font-size: 0.82rem; background: #F1F5F9; color: #334155; padding: 4px 12px; border-radius: 9999px; font-weight: 600; border: 1px solid #E2E8F0;">
                    Trang {current_page}/{total_pages} &nbsp;•&nbsp; {total_items}/{MAX_STORED_FILES} file
                </span>
            </div>""",
            unsafe_allow_html=True
        )

    st.caption(f":material/storage: *Server lưu trữ tối đa 20 file gần nhất (tự động luân chuyển). Đang hiển thị dòng {start_idx + 1} - {end_idx} trên tổng {total_items} mục.*")

    # Render 5 dòng lịch sử cho trang hiện tại
    for local_idx, item in enumerate(page_items):
        global_idx = start_idx + local_idx + 1
        fname = item.get("file_name", "audio.mp3")
        fpath = os.path.join(output_dir, fname)

        audio_data = item.get("audio_bytes")
        if not audio_data and os.path.exists(fpath):
            try:
                with open(fpath, "rb") as f:
                    audio_data = f.read()
                    item["audio_bytes"] = audio_data
            except Exception:
                pass

        if history_type == "general":
            exp_title = f"#{global_idx} | [{item.get('time', '')}] {item.get('text', fname)}"
            extra_info = f"Giọng đọc: `{item.get('voice', 'Edge Neural TTS')}` | File: `{fname}`"
        else:
            title_disp = item.get("title", fname)
            len_disp = item.get("length", "")
            exp_title = f"#{global_idx} | [{item.get('time', '')}] {title_disp}" + (f" ({len_disp})" if len_disp else "")
            extra_info = f"File: `{fname}`" + (f" | Thời lượng: **{len_disp}**" if len_disp else "")

        with st.expander(exp_title, icon=":material/audio_file:", expanded=(local_idx == 0 and current_page == 1)):
            st.markdown(extra_info)
            if audio_data:
                st.audio(audio_data, format="audio/mp3")

            c_dl, c_del = st.columns([3, 1])
            with c_dl:
                if audio_data:
                    st.download_button(
                        label=f"Tải MP3 ({fname})",
                        icon=":material/download:",
                        data=audio_data,
                        file_name=fname,
                        mime="audio/mp3",
                        use_container_width=True,
                        key=f"dl_{history_type}_{global_idx}_{fname}"
                    )
            with c_del:
                if st.button("Xóa file", icon=":material/delete:", key=f"del_{history_type}_{global_idx}_{fname}", use_container_width=True, help="Xóa file này khỏi server"):
                    if os.path.exists(fpath):
                        try:
                            os.remove(fpath)
                        except OSError:
                            pass
                    st.session_state[f"history_{history_type}"] = [
                        x for x in history_list if x.get("file_name") != fname
                    ]
                    remaining = len(st.session_state[f"history_{history_type}"])
                    new_max = max(1, (remaining + PAGE_SIZE - 1) // PAGE_SIZE)
                    if st.session_state[page_key] > new_max:
                        st.session_state[page_key] = new_max
                    st.query_params[qp_param] = str(st.session_state[page_key])
                    st.rerun()

    # Thanh điều hướng phân trang (nếu có từ 2 trang trở lên)
    if total_pages > 1:
        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
        col_widths = [1.2] + [1] * total_pages + [1.2]
        nav_cols = st.columns(col_widths)

        def set_page(new_p):
            st.session_state[page_key] = new_p
            st.query_params[qp_param] = str(new_p)
            st.rerun()

        # Nút Trước
        if nav_cols[0].button("Trước", icon=":material/chevron_left:", disabled=(current_page == 1), key=f"prev_{page_key}", use_container_width=True):
            set_page(max(1, current_page - 1))

        # Nút số trang: 1, 2, 3, 4
        for p in range(1, total_pages + 1):
            is_active = (p == current_page)
            btn_lbl = f"Trang {p}" if is_active else str(p)
            btn_t = "primary" if is_active else "secondary"
            if nav_cols[p].button(btn_lbl, key=f"btn_p_{p}_{page_key}", type=btn_t, disabled=is_active, use_container_width=True):
                set_page(p)

        # Nút Sau
        if nav_cols[-1].button("Sau", icon=":material/chevron_right:", disabled=(current_page == total_pages), key=f"next_{page_key}", use_container_width=True):
            set_page(min(total_pages, current_page + 1))


# Khởi tạo session state
if "history_general" not in st.session_state:
    st.session_state.history_general = []

if "history_ielts" not in st.session_state:
    st.session_state.history_ielts = []

if "page_general" not in st.session_state:
    st.session_state.page_general = 1

if "page_ielts" not in st.session_state:
    st.session_state.page_ielts = 1

if "storage_initialized" not in st.session_state:
    sync_and_cleanup_history(OUTPUT_DIR)
    load_existing_files_to_history(OUTPUT_DIR)
    st.session_state.storage_initialized = True

if "text_input" not in st.session_state:
    st.session_state.text_input = "Xin chào! Chào mừng bạn đến với ứng dụng chuyển đổi văn bản thành giọng nói tiếng Việt bằng AI. Giọng đọc rất tự nhiên và truyền cảm!"

if "ielts_script" not in st.session_state:
    st.session_state.ielts_script = ""

if "ielts_intro" not in st.session_state:
    st.session_state.ielts_intro = "You will hear a conversation. First, you have some time to look at questions one to five."

# CSS tùy biến giao diện
st.markdown("""
<style>
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    .header-box {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-top: -1.2rem;
        margin-bottom: 1.2rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid rgba(226, 232, 240, 0.8);
    }
    .brand-icon-box {
        background: linear-gradient(135deg, #4F46E5 0%, #06B6D4 100%);
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 14px rgba(79, 70, 229, 0.25);
        flex-shrink: 0;
    }
    .main-title {
        font-size: 1.85rem;
        font-weight: 700;
        color: #0F172A;
        letter-spacing: -0.02em;
        line-height: 1.25;
        margin: 0;
    }
    .sub-title {
        color: #64748B;
        font-size: 0.95rem;
        line-height: 1.4;
        margin: 0;
        margin-top: 4px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 1rem;
        font-weight: 600;
        padding: 10px 18px;
        border-radius: 8px 8px 0px 0px;
    }
    .badge-accent {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 600;
        background-color: #F1F5F9;
        color: #334155;
        border: 1px solid #E2E8F0;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="header-box">
    <div class="brand-icon-box">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
            <line x1="12" y1="19" x2="12" y2="22"></line>
        </svg>
    </div>
    <div>
        <div class="main-title">AI Voice & IELTS Listening Studio</div>
        <div class="sub-title">Chuyển văn bản thành giọng nói AI Neural & Thiết kế bài thi nghe IELTS chuẩn Cambridge phân cấp độ khó</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Định nghĩa tên 2 Tabs chính
TAB_GENERAL_TITLE = ":material/graphic_eq: Văn bản thông thường (TTS)"
TAB_IELTS_TITLE = ":material/headphones: IELTS Listening Studio"

# Đọc query param từ URL để F5 không bị nhảy tab
query_tab = st.query_params.get("tab", "general")
default_tab = TAB_IELTS_TITLE if query_tab == "ielts" else TAB_GENERAL_TITLE

def on_main_tab_change():
    active = st.session_state.get("active_main_tab")
    if active == TAB_IELTS_TITLE:
        st.query_params["tab"] = "ielts"
    else:
        st.query_params["tab"] = "general"

# Tạo 2 Tabs chính kèm đồng bộ URL
tab_general, tab_ielts = st.tabs(
    [TAB_GENERAL_TITLE, TAB_IELTS_TITLE],
    default=default_tab,
    key="active_main_tab",
    on_change=on_main_tab_change
)

# =========================================================================
# TAB 1: CHUYỂN ĐỔI VĂN BẢN THÔNG THƯỜNG
# =========================================================================
with tab_general:
    col_g1, col_g2 = st.columns([1, 1], gap="large")
    
    with col_g1:
        st.subheader(":material/edit_note: Nhập nội dung văn bản")
        
        # Chọn giọng đọc thông thường
        mode_voice = st.radio(
            "Danh mục giọng đọc:",
            ["Giọng phổ biến (Khuyên dùng)", "Toàn bộ danh sách thế giới"],
            horizontal=True,
            key="g_mode_voice"
        )
        
        if mode_voice == "Giọng phổ biến (Khuyên dùng)":
            voice_options = {item["label"]: item["name"] for item in tts_engine.POPULAR_VOICES}
            selected_voice_label = st.selectbox("Chọn giọng nói:", list(voice_options.keys()), index=0, key="g_sel_voice")
            selected_voice = voice_options[selected_voice_label]
        else:
            @st.cache_data(show_spinner=False)
            def get_cached_all_voices():
                return tts_engine.get_all_voices_sync()
            with st.spinner("Đang tải danh sách giọng..."):
                all_v = get_cached_all_voices()
                all_v_map = {item["label"]: item["name"] for item in all_v}
                selected_voice_label = st.selectbox("Tìm & chọn giọng:", list(all_v_map.keys()), index=0, key="g_sel_all_voice")
                selected_voice = all_v_map[selected_voice_label]

        # Nhập văn bản
        inp_tab1, inp_tab2 = st.tabs([":material/edit: Gõ văn bản", ":material/upload_file: Tải file .txt"])
        with inp_tab1:
            s_c1, s_c2, s_c3 = st.columns(3)
            if s_c1.button("Chào hỏi", icon=":material/waving_hand:", key="s_btn1", use_container_width=True):
                st.session_state.text_input = "Xin chào quý vị và các bạn! Chúc các bạn một ngày làm việc thật hiệu quả và tràn đầy năng lượng tích cực."
            if s_c2.button("Bản tin", icon=":material/newspaper:", key="s_btn2", use_container_width=True):
                st.session_state.text_input = "Bản tin công nghệ: Trí tuệ nhân tạo đang thay đổi cách chúng ta tiếp cận thông tin và sáng tạo nội dung số một cách mạnh mẽ."
            if s_c3.button("Kể chuyện", icon=":material/auto_stories:", key="s_btn3", use_container_width=True):
                st.session_state.text_input = "Đêm ấy, trăng sáng vằng vặc chiếu rọi qua khung cửa sổ. Tiếng gió khẽ lay động cành tre đầu ngõ tạo nên một khúc ca êm dịu."
                
            user_text = st.text_area(
                "Nội dung cần chuyển thành giọng nói:",
                value=st.session_state.text_input,
                height=220,
                key="g_text_area"
            )
        with inp_tab2:
            up_file = st.file_uploader("Tải lên file văn bản (.txt)", type=["txt"], key="g_file_up")
            if up_file is not None:
                try:
                    user_text = up_file.read().decode("utf-8")
                    st.success(f"Đã nạp file '{up_file.name}' ({len(user_text)} ký tự)")
                except Exception as e:
                    st.error(f"Lỗi: {e}")

        # Tinh chỉnh thông số
        st.markdown(":material/tune: **Tinh chỉnh âm thanh:**")
        adj_c1, adj_c2, adj_c3 = st.columns(3)
        with adj_c1:
            rate_g = st.slider("Tốc độ (Rate %):", -50, 50, 0, 5, key="g_rate")
        with adj_c2:
            pitch_g = st.slider("Cao độ (Pitch Hz):", -50, 50, 0, 5, key="g_pitch")
        with adj_c3:
            volume_g = st.slider("Âm lượng (Volume %):", -50, 50, 0, 5, key="g_volume")

        char_cnt = len(user_text.strip()) if user_text else 0
        word_cnt = len(user_text.strip().split()) if user_text else 0
        st.caption(f":material/analytics: Thống kê: **{char_cnt}** ký tự &nbsp;•&nbsp; **{word_cnt}** từ")
        
        btn_gen_g = st.button("Chuyển đổi thành giọng nói ngay", icon=":material/bolt:", type="primary", use_container_width=True, key="btn_gen_general")

    with col_g2:
        st.subheader(":material/volume_up: Kết quả âm thanh")
        if btn_gen_g:
            if not user_text or not user_text.strip():
                st.warning("Vui lòng nhập văn bản trước khi bấm chuyển đổi!", icon=":material/warning:")
            else:
                trigger_scroll_to_top()
                progress_container_g = st.empty()
                with progress_container_g.container():
                    st.markdown("""
                        <style>
                            /* Khóa toàn bộ cột nhập liệu và thiết lập bên trái */
                            [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child {
                                pointer-events: none !important;
                                opacity: 0.52 !important;
                                filter: grayscale(0.2) !important;
                                user-select: none !important;
                                cursor: not-allowed !important;
                                transition: opacity 0.25s ease;
                            }
                            /* Khóa chuyển tab chính để tránh bị ngắt quá trình */
                            .stTabs [data-baseweb="tab-list"] {
                                pointer-events: none !important;
                                opacity: 0.55 !important;
                                cursor: not-allowed !important;
                            }
                            /* Khóa các nút tương tác ở phần lịch sử phía dưới */
                            [data-testid="stExpander"] button, [data-testid="stExpander"] a {
                                pointer-events: none !important;
                                opacity: 0.55 !important;
                            }
                            /* Đảm bảo nút Hủy ở góc trên vẫn luôn bấm được */
                            #cancel-g-btn {
                                pointer-events: auto !important;
                                cursor: pointer !important;
                                opacity: 1 !important;
                            }
                        </style>
                        <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E" 
                             onload="(function(){
                                 try {
                                     const doc = window.parent.document || document;
                                     if (doc.activeElement && typeof doc.activeElement.blur === 'function') {
                                         doc.activeElement.blur();
                                     }
                                     function blockInputs(e) {
                                         const hasCancel = doc.querySelector('#cancel-g-btn') || doc.querySelector('#cancel-ielts-btn');
                                         if (hasCancel && (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT')) {
                                             e.preventDefault();
                                             e.stopPropagation();
                                         }
                                     }
                                     doc.addEventListener('keydown', blockInputs, true);
                                     doc.addEventListener('paste', blockInputs, true);
                                 } catch(e){}
                             })(); this.remove();" 
                             style="display:none;" />
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <div>
                                <span style="font-weight: 600; color: #1E293B; display: inline-flex; align-items: center; gap: 8px;">
                                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="animation: spin 1.5s linear infinite;"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
                                    Đang xử lý giọng nói AI...
                                </span>
                                <div style="font-size: 0.76rem; color: #64748B; margin-top: 3px; display: flex; align-items: center; gap: 4px;">
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                                    Đã tạm thời khóa các ô nhập & điều khiển bên trái để bảo toàn quá trình tạo
                                </div>
                            </div>
                            <button id="cancel-g-btn" onclick="(function(){
                                const stopBtn = window.parent.document.querySelector('[data-testid=\\'stStatusWidget\\'] button, button[aria-label=\\'Stop\\']');
                                if (stopBtn) { stopBtn.click(); } else { window.parent.location.reload(); }
                            })()" style="background-color: #EF4444; color: white; border: none; padding: 6px 14px; border-radius: 8px; font-weight: 600; font-size: 0.85rem; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 1px 3px rgba(239, 68, 68, 0.25);">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"></rect></svg>
                                Hủy quá trình
                            </button>
                        </div>
                    """, unsafe_allow_html=True)
                    g_prog = st.progress(0.0, text="Khởi động bộ chuyển đổi âm thanh...")

                def on_g_progress(pct: float, msg: str):
                    g_prog.progress(min(1.0, max(0.0, pct)), text=msg)

                fname = ""
                fpath = ""
                try:
                    start_time = datetime.datetime.now()
                    fname = f"tts_{start_time.strftime('%Y%m%d_%H%M%S')}.mp3"
                    fpath = os.path.join(OUTPUT_DIR, fname)
                    
                    audio_data, _ = tts_engine.run_tts_sync(
                        text=user_text.strip(),
                        voice=selected_voice,
                        rate_percent=rate_g,
                        pitch_hz=pitch_g,
                        volume_percent=volume_g,
                        output_filepath=fpath,
                        progress_callback=on_g_progress
                    )
                    progress_container_g.empty()
                    duration = (datetime.datetime.now() - start_time).total_seconds()
                    st.success(f"Hoàn tất trong {duration:.2f} giây!", icon=":material/check_circle:")
                    st.audio(audio_data, format="audio/mp3")
                    st.download_button(
                        label="Tải file MP3 về máy",
                        icon=":material/download:",
                        data=audio_data,
                        file_name=fname,
                        mime="audio/mp3",
                        use_container_width=True,
                        key="dl_btn_g"
                    )
                    st.session_state.history_general.insert(0, {
                        "text": user_text[:80] + ("..." if len(user_text) > 80 else ""),
                        "voice": selected_voice,
                        "time": start_time.strftime("%H:%M:%S"),
                        "audio_bytes": audio_data,
                        "file_name": fname
                    })
                    st.session_state.page_general = 1
                    st.query_params["page_g"] = "1"
                    sync_and_cleanup_history(OUTPUT_DIR)
                except Exception as ex:
                    progress_container_g.empty()
                    if fpath and os.path.exists(fpath):
                        try:
                            os.remove(fpath)
                        except OSError:
                            pass
                    st.warning(f"Quá trình đã bị hủy hoặc gặp lỗi: {str(ex)}", icon=":material/warning:")

        render_paginated_history("general", "page_general", OUTPUT_DIR)


# =========================================================================
# TAB 2: IELTS LISTENING STUDIO
# =========================================================================
with tab_ielts:
    col_i1, col_i2 = st.columns([1, 1], gap="large")

    with col_i1:
        st.subheader(":material/school: Thiết lập bài nghe IELTS")

        # Lời mở đầu chuẩn Cambridge IELTS
        with st.expander("Lời giới thiệu đầu bài thi (Cambridge Intro Prompt)", icon=":material/campaign:", expanded=False):
            enable_intro = st.checkbox("Phát lời giới thiệu đầu bài thi ('You will hear...')", value=True, key="ielts_chk_intro")
            intro_text_input = st.text_area(
                "Nội dung lời giới thiệu:",
                value=st.session_state.ielts_intro,
                height=80,
                help="Lời giới thiệu được đọc bằng giọng Anh - Anh chuẩn Cambridge, sau đó tự động ngưng 2 giây để thí sinh đọc đề.",
                key="ielts_intro_area"
            )

        # Khung nhập kịch bản
        st.markdown(":material/description: **Kịch bản bài nghe (Script):**")
        st.caption(":material/lightbulb: *Mẹo: Hỗ trợ không giới hạn số người. Đặt tên nhân vật kèm dấu `:` ở đầu câu (Ví dụ: `Officer: ...` / `Customer: ...`). Nếu là bài đọc 1 người, không cần đặt tên nhân vật.*")
        
        script_input = st.text_area(
            "Nội dung kịch bản:",
            value=st.session_state.ielts_script,
            height=260,
            placeholder="Dán hoặc gõ kịch bản bài nghe tại đây...\n\nVí dụ Hội thoại:\nOfficer: Good morning. How can I help you today?\nCustomer: Hello, I'd like to ask about membership plans.\n\nHoặc Độc thoại:\nWelcome everyone to today's campus orientation tour...",
            key="ielts_script_area"
        )

        # Danh sách toàn bộ các giọng IELTS kèm phân loại độ khó
        all_ielts_voices = tts_engine.get_all_ielts_voices_flat()

        def make_voice_label(v):
            diff = v.get("difficulty", "easy")
            diff_tag = "[Khó • Hard]" if diff == "hard" else ("[TB • Medium]" if diff == "medium" else "[Dễ • Standard]")
            return f"{diff_tag} {v['accent']} • {v['label']}"

        opts_map = {make_voice_label(v): v["name"] for v in all_ielts_voices}
        opts_keys = list(opts_map.keys())

        # Vòng xoay giọng gợi ý mặc định đa dạng Accent khi có 3, 4+ nhân vật
        DEFAULT_VOICE_ROTATION = [
            "en-GB-RyanNeural",             # 1. Nam Anh (BBC RP)
            "en-AU-NatashaNeural",          # 2. Nữ Úc (Section 1 & 2 IELTS)
            "en-US-JennyNeural",            # 3. Nữ Mỹ (Bắc Mỹ rõ ràng)
            "en-IN-PrabhatNeural",          # 4. Nam Ấn Độ (Thử thách nhịp Syllable-timed)
            "en-GB-ThomasNeural",           # 5. Nam Anh (Giảng viên đại học)
            "en-NZ-MollyNeural",            # 6. Nữ New Zealand (Kiwi)
            "en-CA-LiamNeural",             # 7. Nam Canada
            "en-SG-LunaNeural",             # 8. Nữ Singapore
        ]

        # Phân tích kịch bản và tự động nhận diện hình thức bài thi (Hội thoại vs Độc thoại)
        parsed_turns = tts_engine.parse_dialogue(script_input)
        unique_speakers = list(dict.fromkeys([speaker for speaker, _ in parsed_turns]))
        
        # Nếu có từ 2 nhân vật trở lên -> Tự động là Hội thoại (Dialogue)
        # Nếu chỉ có 1 nhân vật hoặc văn bản thuần -> Tự động là Độc thoại (Monologue)
        is_dialogue = len(unique_speakers) >= 2

        # Cấu hình giọng đọc cho từng nhân vật / Accent
        speaker_voice_map = {}
        single_voice = "en-GB-RyanNeural"
        
        if is_dialogue:
            st.markdown("---")
            st.markdown(":material/diversity_3: **Phân vai nhân vật & Lựa chọn Accent** *(Chuẩn Cambridge)*")
            spk_badges = "  •  ".join([f"**{s}**" for s in unique_speakers])
            st.success(f"Tự động nhận diện bài thi: **Hội thoại phân vai ({len(unique_speakers)} nhân vật)**  |  {spk_badges}", icon=":material/groups:")

            # Gán giọng cho từng nhân vật
            for idx, speaker in enumerate(unique_speakers):
                # Vòng xoay giọng đa dạng Accent cho từng nhân vật
                default_vname = DEFAULT_VOICE_ROTATION[idx % len(DEFAULT_VOICE_ROTATION)]

                def_voice_obj = next((v for v in all_ielts_voices if v["name"] == default_vname), all_ielts_voices[0])
                def_lbl = make_voice_label(def_voice_obj)
                def_idx = opts_keys.index(def_lbl) if def_lbl in opts_keys else 0

                sel_label = st.selectbox(
                    f"Giọng đọc cho nhân vật **'{speaker}'**:",
                    opts_keys,
                    index=def_idx,
                    key=f"ielts_spk_{speaker}_{idx}"
                )
                speaker_voice_map[speaker] = opts_map[sel_label]

            # Xem trước phân vai và lượt nói trực quan
            with st.expander(f"Xem trước lượt đọc của từng nhân vật ({len(parsed_turns)} câu thoại)", icon=":material/visibility:", expanded=False):
                color_palette = ["#2563EB", "#059669", "#D97706", "#7C3AED", "#DB2777"]
                speaker_colors = {spk: color_palette[i % len(color_palette)] for i, spk in enumerate(unique_speakers)}
                for idx, (spk, line) in enumerate(parsed_turns):
                    v_name = speaker_voice_map.get(spk, "")
                    v_obj = next((v for v in all_ielts_voices if v["name"] == v_name), {})
                    v_accent = v_obj.get("accent", "Native")
                    v_diff = v_obj.get("difficulty", "easy")
                    
                    if v_diff == "hard":
                        diff_badge = "Khó • Extreme"
                        diff_bg = "#FEF2F2"
                        diff_color = "#DC2626"
                        diff_border = "#FECACA"
                    elif v_diff == "medium":
                        diff_badge = "Trung bình • Medium"
                        diff_bg = "#FFFBEB"
                        diff_color = "#D97706"
                        diff_border = "#FDE68A"
                    else:
                        diff_badge = "Dễ • Standard"
                        diff_bg = "#F0FDF4"
                        diff_color = "#16A34A"
                        diff_border = "#BBF7D0"

                    color = speaker_colors.get(spk, "#1E293B")
                    st.markdown(
                        f"""<div style="margin-bottom: 6px; padding: 8px 12px; border-left: 4px solid {color}; background-color: #F8FAFC; border-radius: 0 6px 6px 0;">
                            <span style="font-weight: 700; color: {color};">#{idx+1} {spk}</span> 
                            <span style="font-size: 0.75rem; background: #F1F5F9; color: #475569; border: 1px solid #E2E8F0; padding: 2px 8px; border-radius: 9999px; margin-left: 6px; font-weight: 600;">{v_accent}</span>
                            <span style="font-size: 0.75rem; background: {diff_bg}; color: {diff_color}; border: 1px solid {diff_border}; padding: 2px 8px; border-radius: 9999px; margin-left: 4px; font-weight: 600;">{diff_badge}</span>
                            <div style="color: #334155; margin-top: 4px; font-size: 0.92rem;">{line}</div>
                        </div>""",
                        unsafe_allow_html=True
                    )
        else:
            st.markdown("---")
            st.markdown(":material/record_voice_over: **Lựa chọn Accent cho bài giảng / độc thoại:**")
            st.info("Tự động nhận diện bài thi: **Độc thoại / Thuyết trình học thuật** (Section 2 / Section 4 - 1 người đọc)", icon=":material/mic:")
            default_vname = "en-GB-ThomasNeural"
            
            def_voice_obj = next((v for v in all_ielts_voices if v["name"] == default_vname), all_ielts_voices[0])
            def_lbl = make_voice_label(def_voice_obj)
            def_idx = opts_keys.index(def_lbl) if def_lbl in opts_keys else 0

            sel_label = st.selectbox(
                "Chọn giọng đọc chính (Lecturer / Tour Guide):",
                opts_keys,
                index=def_idx,
                key="ielts_single_voice_sel"
            )
            single_voice = opts_map[sel_label]

        # Tinh chỉnh đề thi IELTS
        st.markdown("---")
        st.markdown(":material/tune: **Tinh chỉnh bài thi IELTS:**")
        if is_dialogue:
            i_c1, i_c2, i_c3 = st.columns(3)
            with i_c1:
                rate_i = st.slider(
                    "Tốc độ nói (Rate %):",
                    -30, 30, 0, 5,
                    help="-15% để luyện nghe chép chính tả (Dictation); +10% đến +15% để luyện ép tốc độ thi thật.",
                    key="ielts_rate_slider"
                )
            with i_c2:
                pause_sec = st.slider(
                    "Khoảng nghỉ giữa các câu (Giây):",
                    0.2, 3.0, 0.8, 0.1,
                    help="Độ trễ nghỉ giữa các lượt nhân vật trả lời nhau để tạo độ tự nhiên.",
                    key="ielts_pause_slider"
                )
            with i_c3:
                volume_i = st.slider("Âm lượng (Volume %):", -50, 50, 0, 5, key="ielts_vol_slider")
        else:
            i_c1, i_c2 = st.columns(2)
            with i_c1:
                rate_i = st.slider(
                    "Tốc độ nói (Rate %):",
                    -30, 30, 0, 5,
                    help="-15% để luyện nghe chép chính tả (Dictation); +10% đến +15% để luyện ép tốc độ thi thật.",
                    key="ielts_rate_slider"
                )
            with i_c2:
                volume_i = st.slider("Âm lượng (Volume %):", -50, 50, 0, 5, key="ielts_vol_slider")
            pause_sec = 0.0

        btn_gen_ielts = st.button("Tạo bài nghe IELTS ngay", icon=":material/headphones:", type="primary", use_container_width=True, key="btn_gen_ielts")

    with col_i2:
        st.subheader(":material/volume_up: Audio bài thi IELTS hoàn chỉnh")
        
        if btn_gen_ielts:
            if not script_input or not script_input.strip():
                st.warning("Vui lòng nhập nội dung kịch bản bài nghe!", icon=":material/warning:")
            else:
                trigger_scroll_to_top()
                progress_container_i = st.empty()
                with progress_container_i.container():
                    st.markdown("""
                        <style>
                            /* Khóa toàn bộ cột thiết lập bài thi IELTS bên trái */
                            [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child {
                                pointer-events: none !important;
                                opacity: 0.52 !important;
                                filter: grayscale(0.2) !important;
                                user-select: none !important;
                                cursor: not-allowed !important;
                                transition: opacity 0.25s ease;
                            }
                            /* Khóa chuyển tab chính để tránh bị ngắt quá trình */
                            .stTabs [data-baseweb="tab-list"] {
                                pointer-events: none !important;
                                opacity: 0.55 !important;
                                cursor: not-allowed !important;
                            }
                            /* Khóa các nút tương tác ở phần lịch sử phía dưới */
                            [data-testid="stExpander"] button, [data-testid="stExpander"] a {
                                pointer-events: none !important;
                                opacity: 0.55 !important;
                            }
                            /* Đảm bảo nút Hủy ở góc trên vẫn luôn bấm được */
                            #cancel-ielts-btn {
                                pointer-events: auto !important;
                                cursor: pointer !important;
                                opacity: 1 !important;
                            }
                        </style>
                        <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E" 
                             onload="(function(){
                                 try {
                                     const doc = window.parent.document || document;
                                     if (doc.activeElement && typeof doc.activeElement.blur === 'function') {
                                         doc.activeElement.blur();
                                     }
                                     function blockInputs(e) {
                                         const hasCancel = doc.querySelector('#cancel-g-btn') || doc.querySelector('#cancel-ielts-btn');
                                         if (hasCancel && (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT')) {
                                             e.preventDefault();
                                             e.stopPropagation();
                                         }
                                     }
                                     doc.addEventListener('keydown', blockInputs, true);
                                     doc.addEventListener('paste', blockInputs, true);
                                 } catch(e){}
                             })(); this.remove();" 
                             style="display:none;" />
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <div>
                                <span style="font-weight: 600; color: #1E293B; display: inline-flex; align-items: center; gap: 8px;">
                                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="animation: spin 1.5s linear infinite;"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
                                    Đang tổng hợp bài nghe IELTS đa giọng đọc...
                                </span>
                                <div style="font-size: 0.76rem; color: #64748B; margin-top: 3px; display: flex; align-items: center; gap: 4px;">
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                                    Đã tạm thời khóa các ô nhập & điều khiển bên trái để bảo toàn quá trình tạo
                                </div>
                            </div>
                            <button id="cancel-ielts-btn" onclick="(function(){
                                const stopBtn = window.parent.document.querySelector('[data-testid=\\'stStatusWidget\\'] button, button[aria-label=\\'Stop\\']');
                                if (stopBtn) { stopBtn.click(); } else { window.parent.location.reload(); }
                            })()" style="background-color: #EF4444; color: white; border: none; padding: 6px 14px; border-radius: 8px; font-weight: 600; font-size: 0.85rem; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 1px 3px rgba(239, 68, 68, 0.25);">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"></rect></svg>
                                Hủy quá trình
                            </button>
                        </div>
                    """, unsafe_allow_html=True)
                    ielts_prog = st.progress(0.0, text="Khởi động thiết lập bài thi Cambridge...")

                def on_ielts_progress(pct: float, msg: str):
                    ielts_prog.progress(min(1.0, max(0.0, pct)), text=msg)

                fname = ""
                fpath = ""
                try:
                    start_time = datetime.datetime.now()
                    fname = f"IELTS_Listening_{start_time.strftime('%Y%m%d_%H%M%S')}.mp3"
                    fpath = os.path.join(OUTPUT_DIR, fname)
                    
                    audio_data, _ = tts_engine.generate_ielts_audio_sync(
                        script_text=script_input.strip(),
                        is_dialogue=is_dialogue,
                        speaker_voice_map=speaker_voice_map,
                        single_voice=single_voice,
                        rate_percent=rate_i,
                        pitch_hz=0,
                        volume_percent=volume_i,
                        pause_between_turns=pause_sec,
                        include_intro=enable_intro,
                        intro_text=intro_text_input if enable_intro else "",
                        output_filepath=fpath,
                        progress_callback=on_ielts_progress
                    )
                    progress_container_i.empty()

                    # Đọc thời lượng bài nghe
                    audio_len_str = "N/A"
                    try:
                        mp3_info = mutagen.mp3.MP3(fpath).info
                        minutes = int(mp3_info.length // 60)
                        seconds = int(mp3_info.length % 60)
                        audio_len_str = f"{minutes:02d}:{seconds:02d} ({round(mp3_info.length, 1)}s)"
                    except Exception:
                        pass

                    word_count = len(script_input.split())
                    st.success(f"Đã tạo thành công bài nghe IELTS! Thời lượng: **{audio_len_str}** &nbsp;•&nbsp; Số từ: **{word_count}** từ", icon=":material/check_circle:")
                    
                    # Trình phát
                    st.audio(audio_data, format="audio/mp3")

                    # Nút tải file
                    st.download_button(
                        label="Tải Audio bài thi IELTS (.MP3)",
                        icon=":material/download:",
                        data=audio_data,
                        file_name=fname,
                        mime="audio/mp3",
                        use_container_width=True,
                        key="dl_btn_ielts"
                    )

                    first_line = script_input.strip().split("\n")[0]
                    title_text = (first_line[:50] + "...") if len(first_line) > 50 else first_line
                    st.session_state.history_ielts.insert(0, {
                        "title": title_text,
                        "time": start_time.strftime("%H:%M:%S"),
                        "length": audio_len_str,
                        "audio_bytes": audio_data,
                        "file_name": fname
                    })
                    st.session_state.page_ielts = 1
                    st.query_params["page_i"] = "1"
                    sync_and_cleanup_history(OUTPUT_DIR)
                except Exception as ex:
                    progress_container_i.empty()
                    if fpath and os.path.exists(fpath):
                        try:
                            os.remove(fpath)
                        except OSError:
                            pass
                    st.warning(f"Quá trình tạo bài nghe đã bị hủy hoặc gặp lỗi: {str(ex)}", icon=":material/warning:")

        render_paginated_history("ielts", "page_ielts", OUTPUT_DIR)

        if not st.session_state.get("history_ielts") and not btn_gen_ielts:
            st.info("""
            **Hướng dẫn sử dụng:**
            1. Dán hoặc nhập kịch bản bài nghe vào ô bên trái (đặt `Tên nhân vật:` nếu là hội thoại nhiều người).
            2. Hệ thống sẽ tự động phát hiện số nhân vật và hiển thị các ô chọn Accent bản xứ.
            3. Chọn Accent theo độ khó phù hợp ([Dễ] Standard / [TB] Medium / [Khó] Extreme: Ấn Độ, Singapore...).
            4. Bấm **'Tạo bài nghe IELTS ngay'** để nghe trực tiếp hoặc tải file MP3 về máy!
            """, icon=":material/info:")
