"""回補指定頻道最新 N 支影片（不依賴 processed 狀態，直接抓 RSS 前 N 筆）。"""

import sys
import io
import time
import argparse
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

import config
from monitor import fetch_rss_videos, load_processed, save_processed, VideoInfo
from transcript import fetch_transcript
from transcript_ytdlp import fetch_transcript_ytdlp
from article import generate_article
from notion_writer import write_to_notion


def fetch_transcript_robust(video_id: str) -> str | None:
    """先試 youtube-transcript-api，失敗再用 yt-dlp。"""
    t = fetch_transcript(video_id)
    if t:
        return t
    return fetch_transcript_ytdlp(video_id)


TARGETS = [
    {"id": "UC_x36zCEGilGpB1m-V4gmjg", "name": "IndyDevDan", "tags": ["AI", "Vibe Coding"]},
    {"id": "UCMwVTLZIRRUyyVrkjDpn4pA", "name": "Cole Medin", "tags": ["AI", "Vibe Coding"]},
    {"id": "UCrXSVX9a1mj8l0CMLwKgMVw", "name": "AI Jason", "tags": ["AI", "Vibe Coding"]},
]
LIMIT = 3


def process_video(video: VideoInfo, dry_run: bool) -> bool:
    print(f"\n  📹 {video.title}", flush=True)
    print(f"     {video.url}", flush=True)

    print("  → 擷取逐字稿...", end=" ", flush=True)
    transcript = fetch_transcript_robust(video.video_id)
    if not transcript:
        print("✗ 無英文字幕，跳過", flush=True)
        return False
    print(f"✓ ({len(transcript)} 字元)", flush=True)

    if dry_run:
        print("  → [dry-run] 跳過文章生成與 Notion 寫入", flush=True)
        return True

    print("  → Gemini 生成文章...", end=" ", flush=True)
    article = generate_article(transcript, video.title, video.channel_name)
    if not article:
        print("✗ 生成失敗", flush=True)
        return False
    print(f"✓ 《{article['title']}》", flush=True)

    print("  → 寫入 Notion...", end=" ", flush=True)
    page_id = write_to_notion(
        article=article,
        video_url=video.url,
        channel_name=video.channel_name,
        published=video.published,
        tags=video.tags,
    )
    if not page_id:
        print("✗ 寫入失敗", flush=True)
        return False
    print(f"✓ (page: {page_id[:8]}...)", flush=True)

    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 50, flush=True)
    print(f"回補模式：每個頻道最新 {LIMIT} 支", flush=True)
    print(f"時間: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", flush=True)
    print("=" * 50, flush=True)

    processed = load_processed()

    total = 0
    total_success = 0

    for ch in TARGETS:
        print(f"\n🔍 {ch['name']} ({ch['id'][:10]}...)", flush=True)
        rss = fetch_rss_videos(ch["id"])[:LIMIT]
        print(f"  RSS 抓到 {len(rss)} 支", flush=True)

        queue = []
        for v in rss:
            if v["video_id"] in processed:
                continue
            queue.append(VideoInfo(
                video_id=v["video_id"],
                title=v["title"],
                channel_name=ch["name"],
                channel_id=ch["id"],
                published=v["published"],
                url=f"https://www.youtube.com/watch?v={v['video_id']}",
                tags=ch["tags"],
            ))

        if not queue:
            print(f"  前 {LIMIT} 支都已處理過", flush=True)
            continue

        print(f"  待處理 {len(queue)} 支", flush=True)
        total += len(queue)

        for video in queue:
            try:
                success = process_video(video, args.dry_run)
                if success and not args.dry_run:
                    total_success += 1
                    processed[video.video_id] = {
                        "title": video.title,
                        "channel": video.channel_name,
                        "processed_at": datetime.now(timezone.utc).isoformat(),
                    }
                    save_processed(processed)
                time.sleep(20)
            except Exception as e:
                print(f"  ✗ 處理失敗: {e}", flush=True)
                continue

    print("\n" + "=" * 50, flush=True)
    print(f"完成！待處理: {total} / 成功: {total_success}", flush=True)
    print("=" * 50, flush=True)


if __name__ == "__main__":
    main()
