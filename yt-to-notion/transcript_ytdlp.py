"""用 yt-dlp 抓英文逐字稿（youtube-transcript-api 失敗時的備援）。

走不同於 youtube-transcript-api 的請求路徑，兩者其中一個被 YouTube 暫時限流時
另一個通常還能用。
"""

import json
import tempfile
from pathlib import Path

import yt_dlp


def _base_opts(tmpdir: str) -> dict:
    return {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en.*", "en"],
        "subtitlesformat": "json3",
        "outtmpl": str(Path(tmpdir) / "%(id)s.%(ext)s"),
    }


def _parse_json3(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    parts = []
    for ev in data.get("events", []):
        for s in ev.get("segs") or []:
            t = s.get("utf8")
            if t:
                parts.append(t)
    return "".join(parts).replace("\n", " ").strip()


def fetch_transcript_ytdlp(video_id: str) -> str | None:
    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmp:
        opts = _base_opts(tmp)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except Exception as e:
            print(f"    yt-dlp 下載字幕失敗: {e}")
            return None

        for f in Path(tmp).glob(f"{video_id}.*.json3"):
            try:
                text = _parse_json3(f)
                if text:
                    return text
            except Exception as e:
                print(f"    json3 解析失敗: {e}")

    return None


if __name__ == "__main__":
    import sys
    vid = sys.argv[1] if len(sys.argv) > 1 else "00Y-p62sk0s"
    t = fetch_transcript_ytdlp(vid)
    print("len:", len(t) if t else 0)
    if t:
        print("preview:", t[:300])
