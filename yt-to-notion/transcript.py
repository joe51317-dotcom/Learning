"""擷取 YouTube 影片的英文逐字稿。"""

from youtube_transcript_api import YouTubeTranscriptApi

from transcript_ytdlp import fetch_transcript_ytdlp


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


def fetch_transcript(video_id: str) -> str | None:
    """取得英文逐字稿，回傳完整文字。無字幕時回傳 None。

    youtube-transcript-api 在批次連續請求時容易被 YouTube 暫時擋下，
    失敗時改用 yt-dlp 重試一次（走不同的請求路徑）。
    """
    text = _fetch_via_transcript_api(video_id)
    if text:
        return text
    return fetch_transcript_ytdlp(video_id)
