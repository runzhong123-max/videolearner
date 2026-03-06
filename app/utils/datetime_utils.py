from datetime import UTC, datetime
from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def to_beijing(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC).astimezone(SHANGHAI_TZ)
    return dt.astimezone(SHANGHAI_TZ)


def format_cn_datetime(dt: datetime) -> str:
    bj = to_beijing(dt)
    return f"{bj.year}年{bj.month}月{bj.day}日 {bj.strftime('%H:%M')}"


def format_cn_time(dt: datetime) -> str:
    bj = to_beijing(dt)
    return bj.strftime("%H:%M:%S")
