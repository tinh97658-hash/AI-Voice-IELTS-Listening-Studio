import argparse
import sys
import os

# Đảm bảo in tiếng Việt không bị lỗi Unicode trên Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import tts_engine


def main():
    parser = argparse.ArgumentParser(
        description="Chương trình dòng lệnh chuyển đổi Text sang Speech & Tạo bài thi IELTS Listening bằng Edge Neural TTS"
    )
    
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "-t", "--text",
        type=str,
        help="Đoạn văn bản cần đọc"
    )
    input_group.add_argument(
        "-f", "--file",
        type=str,
        help="Đường dẫn file văn bản (.txt) cần đọc"
    )
    input_group.add_argument(
        "--ielts-preset",
        type=str,
        choices=["section1", "section2", "section3", "section4", "hard"],
        help="Tạo nhanh bài nghe mẫu IELTS: section1 (CLB thể thao), section2 (Khu bảo tồn), section3 (Bài tập nhóm), section4 (Bài giảng), hard (Thử thách Accent Ấn Độ)"
    )
    input_group.add_argument(
        "--list-voices",
        action="store_true",
        help="Liệt kê danh sách các giọng nói phổ biến"
    )
    input_group.add_argument(
        "--list-ielts-voices",
        action="store_true",
        help="Liệt kê toàn bộ các giọng đọc và Accent phân loại theo Độ Khó (Dễ: Anh/Mỹ, TB: Úc/Kiwi, Khó: Ấn Độ/Singapore/Nam Phi)"
    )

    parser.add_argument(
        "--difficulty",
        type=str,
        choices=["all", "easy", "medium", "hard"],
        default="all",
        help="Lọc danh sách giọng IELTS theo độ khó: all (tất cả), easy (dễ), medium (trung bình), hard (khó - ví dụ Accent Ấn)"
    )
    parser.add_argument(
        "-v", "--voice",
        type=str,
        default="vi-VN-HoaiMyNeural",
        help="Tên giọng đọc (mặc định: vi-VN-HoaiMyNeural)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="output.mp3",
        help="Đường dẫn file MP3 đầu ra (mặc định: output.mp3)"
    )
    parser.add_argument(
        "--rate",
        type=int,
        default=0,
        help="Tốc độ nói (-50% đến +50%, mặc định 0)"
    )
    parser.add_argument(
        "--pitch",
        type=int,
        default=0,
        help="Cao độ nói (-50Hz đến +50Hz, mặc định 0)"
    )
    parser.add_argument(
        "--volume",
        type=int,
        default=0,
        help="Âm lượng (-50% đến +50%, mặc định 0)"
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=0.8,
        help="Khoảng nghỉ giữa các lượt thoại trong bài nghe IELTS (giây, mặc định 0.8s)"
    )
    parser.add_argument(
        "--no-intro",
        action="store_true",
        help="Không chèn câu lệnh giới thiệu IELTS ở đầu bài"
    )

    args = parser.parse_args()

    if args.list_voices:
        print("\n=== CÁC GIỌNG NÓI PHỔ BIẾN ===")
        for v in tts_engine.POPULAR_VOICES:
            print(f"- {v['name']}: {v['label']}")
        return

    if args.list_ielts_voices:
        print("\n=== DANH SÁCH GIỌNG ĐỌC & ACCENT PHÂN THEO ĐỘ KHÓ ===")
        diff_filter = args.difficulty
        for group_name, vlist in tts_engine.IELTS_VOICES.items():
            matching_voices = [v for v in vlist if diff_filter == "all" or v.get("difficulty") == diff_filter]
            if matching_voices:
                print(f"\n[{group_name}]")
                for v in matching_voices:
                    diff_badge = "[🔴 Khó]" if v.get("difficulty") == "hard" else ("[🟡 TB]" if v.get("difficulty") == "medium" else "[🟢 Dễ]")
                    print(f"  * {v['name']}: {diff_badge} {v['label']}")
        return

    # Chế độ tạo bài nghe mẫu IELTS
    if args.ielts_preset:
        preset_key_map = {
            "section1": "Section 1: Đăng ký CLB thể thao (Hội thoại: Nữ Anh - Anh & Nam Anh - Úc)",
            "section2": "Section 2: Hướng dẫn tham quan khu bảo tồn (Độc thoại: Nữ Anh - Úc)",
            "section3": "Section 3: Thảo luận bài tập nhóm (Hội thoại: Nam Anh - Anh & Nữ Anh - Mỹ)",
            "section4": "Section 4: Bài giảng học thuật về rạn san hô (Độc thoại: Giảng viên Nam Anh - Anh)",
            "hard": "Thử thách KHÓ (Hard): Họp dự án Công nghệ (Hội thoại: Nữ Ấn - Ấn & Nam Anh - Anh)"
        }
        full_key = preset_key_map[args.ielts_preset]
        preset_data = tts_engine.IELTS_PRESETS[full_key]
        
        print(f"[*] Đang tạo bài nghe IELTS: {full_key}...")
        print(f"[*] Tốc độ: {args.rate}% | Âm lượng: {args.volume}%")
        
        is_diag = (preset_data["type"] == "dialogue")
        speaker_map = preset_data.get("speaker_defaults", {})
        single_v = preset_data.get("default_voice", "en-GB-RyanNeural")

        tts_engine.generate_ielts_audio_sync(
            script_text=preset_data["script"],
            is_dialogue=is_diag,
            speaker_voice_map=speaker_map,
            single_voice=single_v,
            rate_percent=args.rate,
            pitch_hz=args.pitch,
            volume_percent=args.volume,
            pause_between_turns=args.pause,
            include_intro=(not args.no_intro),
            intro_text=preset_data.get("intro", ""),
            output_filepath=args.output
        )
        print(f"[+] Thành công! File bài thi IELTS đã lưu tại: {os.path.abspath(args.output)}")
        return

    # Chế độ đọc văn bản bình thường
    content = ""
    if args.text:
        content = args.text
    elif args.file:
        if not os.path.isfile(args.file):
            print(f"Lỗi: Không tìm thấy file '{args.file}'!", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        print("Vui lòng cung cấp văn bản qua --text hoặc --file hoặc --ielts-preset. Gõ --help để xem hướng dẫn.")
        sys.exit(1)

    if not content.strip():
        print("Văn bản rỗng! Vui lòng nhập nội dung hợp lệ.")
        sys.exit(1)

    print(f"[*] Đang chuyển đổi văn bản sang giọng nói...")
    print(f"[*] Giọng đọc: {args.voice}")
    print(f"[*] Tốc độ: {args.rate}% | Cao độ: {args.pitch}Hz | Âm lượng: {args.volume}%")
    print(f"[*] Đang lưu file vào: {args.output}")

    try:
        tts_engine.run_tts_sync(
            text=content.strip(),
            voice=args.voice,
            rate_percent=args.rate,
            pitch_hz=args.pitch,
            volume_percent=args.volume,
            output_filepath=args.output
        )
        print(f"[+] Thành công! File đã được lưu tại: {os.path.abspath(args.output)}")
    except Exception as e:
        print(f"[-] Có lỗi xảy ra: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
