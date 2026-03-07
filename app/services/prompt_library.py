from pathlib import Path

from app.config import BASE_DIR

PROMPTS_DIR = BASE_DIR / "app" / "prompts"

PROMPT_KEY_SYSTEM = "system_prompt"
PROMPT_KEY_NOTE = "note_generation_prompt"
PROMPT_KEY_RECORD_CHAT = "record_chat_prompt"
PROMPT_KEY_IMAGE_CHAT = "image_chat_prompt"

PROMPT_FILENAMES = {
    PROMPT_KEY_SYSTEM: "system_prompt.txt",
    PROMPT_KEY_NOTE: "note_generation.txt",
    PROMPT_KEY_RECORD_CHAT: "record_chat.txt",
    PROMPT_KEY_IMAGE_CHAT: "image_chat.txt",
}

BUILTIN_PROMPTS = {
    PROMPT_KEY_SYSTEM: (
        "你是 VideoLearner 的学习助手。"
        "请基于上下文帮助用户理解知识、提炼结构并给出可执行建议。"
        "不要编造内容，信息不足时请明确说明。"
    ),
    PROMPT_KEY_NOTE: (
        "Use the provided context to generate a structured study note.\n"
        "Return ONLY JSON. Do not include markdown. Do not add explanation.\n"
        "Must include: summary, expansion, inspirations, guidance.\n"
        "Also include configured keys when applicable: {json_keys}.\n\n"
        "User intent:\n{user_prompt}\n\n"
        "Context:\n{context_text}"
    ),
    PROMPT_KEY_RECORD_CHAT: (
        "You are a focused learning assistant for a single text-based learning record.\n"
        "Answer based on context and recent chat. If uncertain, say so briefly and suggest next step.\n\n"
        "User question:\n{user_prompt}\n\n"
        "Context:\n{context_text}"
    ),
    PROMPT_KEY_IMAGE_CHAT: (
        "You are a focused learning assistant for a single image-based learning record.\n"
        "Use OCR and image metadata when available. If OCR is missing, state limitation and suggest OCR first.\n\n"
        "User question:\n{user_prompt}\n\n"
        "Context:\n{context_text}"
    ),
}


def load_prompt_text(key: str, prompt_dir: Path | None = None) -> str:
    directory = prompt_dir or PROMPTS_DIR
    filename = PROMPT_FILENAMES.get(key)
    if filename is None:
        raise KeyError(f"Unsupported prompt key: {key}")

    prompt_path = directory / filename
    if prompt_path.exists():
        content = prompt_path.read_text(encoding="utf-8").strip()
        if content:
            return content

    return BUILTIN_PROMPTS[key]


def choose_chat_prompt_key(context_text: str) -> str:
    text = (context_text or "").lower()
    if "record_type=image" in text:
        return PROMPT_KEY_IMAGE_CHAT
    return PROMPT_KEY_RECORD_CHAT


def safe_render_template(template: str, **mapping: str) -> str:
    try:
        return template.format(**mapping)
    except Exception:
        # Keep robustness when users edit prompt text with unmatched braces.
        blocks = [template]
        if mapping.get("user_prompt"):
            blocks.append(f"\n\nUser prompt:\n{mapping['user_prompt']}")
        if mapping.get("context_text"):
            blocks.append(f"\n\nContext:\n{mapping['context_text']}")
        return "".join(blocks)
