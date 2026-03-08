import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.note import Note
from app.models.record import Record
from app.models.session import Session
from app.services.record_service import RECORD_TYPE_IMAGE
from app.utils.datetime_utils import format_cn_datetime, format_cn_time, format_offset_hms

_STATUS_LABELS = {
    "in_progress": "进行中",
    "paused": "已暂停",
    "finished": "已完成",
    "not_started": "未开始",
}

_NOTE_SECTION_TITLES = {
    "summary": "Summary",
    "inspirations": "Inspirations",
    "expansion": "Expansion",
    "guidance": "Guidance",
    "review_questions": "Review Questions",
    "key_points": "Key Points",
    "follow_up_tasks": "Follow-up Tasks",
    "history_link": "History Link",
    "gap_analysis": "Gap Analysis",
    "homework": "Homework",
    "expression_notes": "Expression Notes",
    "evaluation": "Evaluation",
}

_HEADING_ALIASES = {
    "summary": "summary",
    "extension": "expansion",
    "expansion": "expansion",
    "insight": "inspirations",
    "inspirations": "inspirations",
    "guidance": "guidance",
    "review_questions": "review_questions",
    "review questions": "review_questions",
    "key_points": "key_points",
    "key points": "key_points",
    "follow_up_tasks": "follow_up_tasks",
    "follow-up tasks": "follow_up_tasks",
    "follow up tasks": "follow_up_tasks",
    "history_link": "history_link",
    "history link": "history_link",
    "gap_analysis": "gap_analysis",
    "gap analysis": "gap_analysis",
    "homework": "homework",
    "expression_notes": "expression_notes",
    "expression notes": "expression_notes",
    "evaluation": "evaluation",
}


def session_status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, status)


def sort_sessions_for_display(sessions: list[Session]) -> list[Session]:
    def sort_key(session: Session) -> tuple[datetime, datetime, int]:
        primary_time = session.started_at or session.created_at or datetime.max
        fallback_time = session.created_at or session.started_at or datetime.max
        session_id = session.id if session.id is not None else 0
        return (primary_time, fallback_time, session_id)

    return sorted(sessions, key=sort_key)


def build_session_display_numbers(sessions: list[Session]) -> dict[int, int]:
    return {
        session.id: idx
        for idx, session in enumerate(sort_sessions_for_display(sessions), start=1)
        if session.id is not None
    }


def session_display_label(session: Session | None, display_numbers: dict[int, int] | None = None) -> str:
    if session is None:
        return "本节"
    if display_numbers is not None and session.id is not None:
        display_number = display_numbers.get(session.id)
        if display_number is not None:
            return f"第{display_number}节"
    return "本节"


def build_note_session_display(
    project_name: str | None,
    session: Session | None,
    display_numbers: dict[int, int] | None = None,
) -> tuple[str, str]:
    session_label = session_display_label(session, display_numbers)
    if project_name:
        title_text = f"{project_name} · {session_label}学习笔记"
        source_text = f"来源：{project_name} · {session_label}"
    else:
        title_text = f"{session_label}学习笔记"
        source_text = f"来源：{session_label}"
    return title_text, source_text


def build_session_item_text(
    session: Session,
    record_count: int,
    has_note: bool,
) -> str:
    note_text = "有笔记" if has_note else "无笔记"
    status = session_status_label(session.status)
    started = format_cn_datetime(session.started_at)
    title = session.title.strip() or f"Session #{session.id}"
    return (
        f"{title}\n"
        f"#{session.id} | {status} | 开始 {started}\n"
        f"Record {record_count} 条 | {note_text}"
    )


def parse_record_metadata(record: Record) -> dict[str, Any]:
    raw = (record.metadata_json or "").strip()
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def record_display_type(record: Record) -> str:
    if record.record_type == "text" and record.is_inspiration:
        return "insight"
    if record.record_type == "image" and record.is_inspiration:
        return "insight_image"
    return record.record_type


def record_display_name(record: Record) -> str:
    metadata = parse_record_metadata(record)
    for key in ["name", "image_name", "title"]:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    if record.record_type == RECORD_TYPE_IMAGE and record.file_path:
        return Path(record.file_path).name

    return f"Record #{record.id}"


def record_preview_text(record: Record, max_len: int = 70) -> str:
    if record.record_type == RECORD_TYPE_IMAGE:
        text = record_display_name(record)
    else:
        text = record.content

    one_line = " ".join((text or "").splitlines()).strip()
    if not one_line:
        return "-"
    if len(one_line) <= max_len:
        return one_line
    return f"{one_line[:max_len]}..."


def build_record_item_text(record: Record) -> str:
    display_type = record_display_type(record)
    created = format_cn_time(record.created_at)
    offset = format_offset_hms(record.timestamp_offset)
    name = record_display_name(record)
    preview = record_preview_text(record)

    if record.record_type == RECORD_TYPE_IMAGE:
        return f"#{record.id} [{created}] ({offset}) image | {name}"

    return f"#{record.id} [{created}] ({offset}) {display_type}: {preview}"


def parse_note_sections(note: Note) -> dict[str, str]:
    parsed_from_content = _parse_markdown_sections(note.content)

    summary = parsed_from_content.get("summary") or note.summary
    expansion = parsed_from_content.get("expansion") or note.suggestions
    inspirations = parsed_from_content.get("inspirations") or note.inspiration_refinement
    guidance = parsed_from_content.get("guidance") or note.guidance
    review_questions = parsed_from_content.get("review_questions") or note.review_questions
    key_points = parsed_from_content.get("key_points") or note.key_points
    follow_up_tasks = parsed_from_content.get("follow_up_tasks") or note.follow_up_tasks

    sections = {
        "summary": (summary or "").strip(),
        "inspirations": (inspirations or "").strip(),
        "expansion": (expansion or "").strip(),
        "guidance": (guidance or "").strip(),
        "review_questions": (review_questions or "").strip(),
        "key_points": (key_points or "").strip(),
        "follow_up_tasks": (follow_up_tasks or "").strip(),
    }

    for key, value in parsed_from_content.items():
        if key in sections:
            continue
        sections[key] = value

    return sections


def iter_note_sections(note: Note) -> list[tuple[str, str, str]]:
    sections = parse_note_sections(note)
    ordered_keys = [
        "summary",
        "inspirations",
        "expansion",
        "guidance",
        "review_questions",
        "key_points",
        "follow_up_tasks",
        "history_link",
        "gap_analysis",
        "homework",
        "expression_notes",
        "evaluation",
    ]
    result: list[tuple[str, str, str]] = []
    for key in ordered_keys:
        if key not in sections:
            continue
        value = sections[key].strip()
        if key in {
            "summary",
            "inspirations",
            "expansion",
            "guidance",
            "review_questions",
            "key_points",
            "follow_up_tasks",
        }:
            result.append((key, _NOTE_SECTION_TITLES[key], value or "（空）"))
            continue
        if value:
            result.append((key, _NOTE_SECTION_TITLES.get(key, key), value))
    return result


def build_note_preview_text(note: Note, max_section_len: int = 220) -> str:
    lines: list[str] = []
    for _key, title, value in iter_note_sections(note):
        trimmed = value if len(value) <= max_section_len else f"{value[:max_section_len]}..."
        lines.append(f"[{title}]\n{trimmed}")
    return "\n\n".join(lines) if lines else "暂无可预览内容。"


def _parse_markdown_sections(content: str) -> dict[str, str]:
    text = (content or "").strip()
    if not text:
        return {}

    matches = list(re.finditer(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE))
    if not matches:
        return {}

    sections: dict[str, str] = {}
    for idx, match in enumerate(matches):
        heading = match.group(1).strip().lower()
        key = _HEADING_ALIASES.get(heading, heading.replace(" ", "_"))
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections[key] = body

    return sections
