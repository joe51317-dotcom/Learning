"""擷取 YouTube 影片的英文逐字稿。"""

from youtube_transcript_api import YouTubeTranscriptApi


def fetch_transcript(video_id: str) -> str | None:
    """取得英文逐字稿，回傳完整文字。無字幕時回傳 None。"""
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
