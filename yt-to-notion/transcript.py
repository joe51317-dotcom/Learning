"""擷取 YouTube 影片的英文逐字稿。"""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from youtube_transcript_api import YouTubeTranscriptApi

from transcript_ytdlp import fetch_transcript_ytdlp

# YouTube 被限流時，底層請求可能不會乾脆地報錯，而是卡住不回應，
# 沒有這個上限會讓整批處理卡死在同一支影片上。
FETCH_TIMEOUT_SECONDS = 60


def _fetch_via_transcript_api(video_id: str) -> str | None:
    ytt = YouTubeTranscriptApi()

    try:
        transcript = ytt.fetch(
            video_id,
            languages=["en", "en-US", "en-GB"],
        )
        full_text = " ".join(snippet.text for snippet in transcript.snippets)
        return full_text
    except Exception:
        pass

    # Fallback：嘗試任何可用的字幕（可能是自動產生的）
    try:
        transcript_list = ytt.list(video_id)
        for t in transcript_list:
            if t.language_code.startswith("en"):
                transcript = ytt.fetch(video_id, languages=[t.language_code])
                full_text = " ".join(snippet.text for snippet in transcript.snippets)
                return full_text
    except Exception:
        pass

    return None


def _with_timeout(fn, video_id: str) -> str | None:
    # 不用 context manager：卡住的請求執行緒無法強制中止，
    # shutdown(wait=True) 會讓逾時失去意義（照樣等到它結束才返回）。
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(fn, video_id)
    try:
        return future.result(timeout=FETCH_TIMEOUT_SECONDS)
    except FutureTimeoutError:
        print(f"    逐字稿請求超過 {FETCH_TIMEOUT_SECONDS} 秒無回應，視為失敗")
        return None
    finally:
        pool.shutdown(wait=False)


def fetch_transcript(video_id: str) -> str | None:
    """取得英文逐字稿，回傳完整文字。無字幕時回傳 None。

    youtube-transcript-api 在批次連續請求時容易被 YouTube 暫時擋下，
    失敗時改用 yt-dlp 重試一次（走不同的請求路徑）。兩者都包一層逾時，
    避免被限流卡住的請求（不報錯、單純不回應）讓整批處理卡死。
    """
    text = _with_timeout(_fetch_via_transcript_api, video_id)
    if text:
        return text
    return _with_timeout(fetch_transcript_ytdlp, video_id)
