from dataclasses import dataclass
from pathlib import Path

from app.services.prompt_library import PROMPT_KEY_NOTE, load_prompt_text, safe_render_template


@dataclass(frozen=True)
class AIPromptBuildInput:
    system_prompt: str
    user_prompt: str
    context_text: str
    output_options: dict[str, bool]


class PromptBuilder:
    """Builds user-facing prompt text under a stable section contract."""

    REQUIRED_KEYS = ["summary", "expansion", "inspirations", "guidance"]
    LIGHT_REVIEW_KEYS = ["review_questions", "key_points", "follow_up_tasks"]

    def __init__(self, prompt_dir: Path | None = None):
        self.prompt_dir = prompt_dir

    def build(self, request: AIPromptBuildInput) -> str:
        optional_keys = self._resolve_optional_keys(request.output_options)
        contract_keys = self.REQUIRED_KEYS + optional_keys
        contract_desc = ", ".join(contract_keys)

        template = load_prompt_text(PROMPT_KEY_NOTE, prompt_dir=self.prompt_dir)
        prompt = safe_render_template(
            template,
            system_prompt=request.system_prompt.strip(),
            user_prompt=request.user_prompt.strip(),
            context_text=request.context_text,
            json_keys=contract_desc,
        )

        if "return only json" not in prompt.lower():
            prompt += (
                "\n\nReturn ONLY JSON. Do not include markdown. Do not add explanation."
                f"\nRequired JSON keys: {contract_desc}."
            )
        return prompt

    def _resolve_optional_keys(self, output_options: dict[str, bool]) -> list[str]:
        optional_map = {
            "history_link": "history_link",
            "gap_analysis": "gap_analysis",
            "review_questions": "review_questions",
            "homework": "homework",
            "expression_notes": "expression_notes",
            "evaluation": "evaluation",
        }
        keys: list[str] = []
        for key in self.LIGHT_REVIEW_KEYS:
            keys.append(key)

        for option_key, target_key in optional_map.items():
            if output_options.get(option_key, False) and target_key not in keys:
                keys.append(target_key)
        return keys
