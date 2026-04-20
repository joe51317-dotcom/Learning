"""YouTube 頻道監控 → 逐字稿 → 繁體中文文章 → Notion。"""

import sys
import io
import argparse
import time
from datetime import datetime, timezone

# Windows UTF-8 輸出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import config
from monitor import get_channels_from_notion, check_new_videos, load_processed, save_processed
from transcript import fetch_transcript
from article import generate_article
from notion_writer import write_to_notion


def process_video(video, args) -> bool:
    """處理單一影片：逐字稿 → 文章 → Notion。回傳是否成功。"""
    print(f"\n  📹 {video.title}")
    print(f"     {video.url}")

    # Step 1: 擷取逐字稿
    print("  → 擷取逐字稿...", end=" ")
    transcript = fetch_transcript(video.video_id)
    if not transcript:
        print("✗ 無英文字幕，跳過")
        return False
    print(f"✓ ({len(transcript)} 字元)")

    if args.dry_run:
        print("  → [dry-run] 跳過文章生成與 Notion 寫入")
        return True

    # Step 2: 生成文章
    print("  → Gemini 生成文章...", end=" ")
    article = generate_article(transcript, video.title, video.channel_name)
    if not article:
        print("✗ 生成失敗")
        return False
    print(f"✓ 《{article['title']}》")

    # Step 3: 寫入 Notion
    print("  → 寫入 Notion...", end=" ")
    page_id = write_to_notion(
        article=article,
        video_url=video.url,
        channel_name=video.channel_name,
        published=video.published,
        tags=video.tags,
    )
    if not page_id:
        print("✗ 寫入失敗")
        return False
    print(f"✓ (page: {page_id[:8]}...)")

    return True


def main():
    parser = argparse.ArgumentParser(description="YouTube → Notion 文章系統")
    parser.add_argument("--dry-run", action="store_true", help="只偵測不寫入")
    parser.add_argument("--verbose", "-v", action="store_true", help="顯示詳細資訊")
    args = parser.parse_args()

    # 檢查必要設定
    missing = []
    if not config.NOTION_API_KEY:
        missing.append("NOTION_API_KEY")
    if not config.NOTION_CHANNELS_DB:
        missing.append("NOTION_CHANNELS_DB")
    if not config.NOTION_ARTICLES_DB:
        missing.append("NOTION_ARTICLES_DB")
    if not config.GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")

    if missing:
        print(f"✗ 缺少環境變數: {', '.join(missing)}")
        print("  請在 .env 檔案中設定")
        sys.exit(1)

    print(f"{'='*50}")
    print(f"YouTube → Notion 文章系統")
    print(f"時間: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    if args.dry_run:
        print("模式: DRY RUN（不寫入）")
    print(f"{'='*50}")

    # 從 Notion 讀取頻道
    print("\n📡 讀取追蹤頻道...")
    try:
        channels = get_channels_from_notion()
    except Exception as e:
        print(f"✗ 無法讀取 Notion 頻道清單: {e}")
        sys.exit(1)

    if not channels:
        print("  沒有啟用的追蹤頻道")
        return

    print(f"  找到 {len(channels)} 個頻道")

    # 載入已處理紀錄
    processed = load_processed()

    total_new = 0
    total_success = 0

    for ch in channels:
        print(f"\n🔍 {ch['name']} ({ch['id'][:10]}...)")

        new_videos = check_new_videos(ch, processed)
        if not new_videos:
            print("  沒有新影片")
            continue

        print(f"  發現 {len(new_videos)} 支新影片")
        total_new += len(new_videos)

        for video in new_videos:
            try:
                success = process_video(video, args)
                if success:
                    total_success += 1
                    processed[video.video_id] = {
                        "title": video.title,
                        "channel": video.channel_name,
                        "processed_at": datetime.now(timezone.utc).isoformat(),
                    }
                    save_processed(processed)

                # 間隔避免觸發 YouTube IP 封鎖和 Gemini 速率限制
                time.sleep(20)

            except Exception as e:
                print(f"  ✗ 處理失敗: {e}")
                continue

    # 總結
    print(f"\n{'='*50}")
    print(f"完成！新影片: {total_new} / 成功處理: {total_success}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
