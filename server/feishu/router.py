import re


def detect_intent(content: str) -> tuple[str, str | None]:
    text = content.strip()

    if text in ("/new_plan", "/开始学习", "开始学习"):
        return ("new_plan", None)
    if text in ("/status", "/状态", "学习进度"):
        return ("status", None)
    if text in ("/help", "/帮助", "帮助"):
        return ("help", None)

    feedback_map = {
        "太难": "too_hard", "太简单": "too_easy", "没时间": "no_time",
        "已完成": "completed", "感兴趣": "interested",
        "不感兴趣": "not_interested", "已掌握": "mastered",
    }
    for kw, sig in feedback_map.items():
        if kw in text:
            return ("feedback", sig)

    url_pattern = re.compile(
        r"https?://(?:www\.)?"
        r"(?:youtube\.com/watch\?v=|youtu\.be/|"
        r"bilibili\.com/video/|"
        r"xiaohongshu\.com/|"
        r"(?:v\.)?douyin\.com/)"
        r"[^\s]+"
    )
    if url_pattern.search(text):
        return ("paste_link", text)

    return ("unknown", None)
