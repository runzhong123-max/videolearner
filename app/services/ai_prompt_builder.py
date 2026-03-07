from dataclasses import dataclass


@dataclass(frozen=True)
class AIPromptBuildInput:
    system_prompt: str
    user_prompt: str
    context_text: str
    output_options: dict[str, bool]


class PromptBuilder:
    """Builds user-facing prompt text under a stable section contract."""

    REQUIRED_KEYS = ["summary", "expansion", "inspirations", "guidance"]

    @classmethod
    def build(cls, request: AIPromptBuildInput) -> str:
        optional_keys = cls._resolve_optional_keys(request.output_options)
        contract_keys = cls.REQUIRED_KEYS + optional_keys

        contract_desc = ", ".join(contract_keys)
        instruction = (
            "请严格返回 JSON 对象，不要返回 Markdown。"
            f"JSON 键仅允许：{contract_desc}。"
            "其中 summary/expansion 必须是非空字符串；"
            "inspirations/guidance 必须存在，若无内容请返回空字符串。"
        )

        return (
            f"{request.user_prompt.strip()}\n\n"
            f"{instruction}\n\n"
            "[输出契约说明]\n"
            "summary: 学习总结（必填）\n"
            "expansion: 扩展建议（必填）\n"
            "inspirations: 灵感提炼（无灵感时为空字符串）\n"
            "guidance: 指导建议（无内容时为空字符串）\n\n"
            "以下是输入上下文，请基于上下文生成：\n"
            f"{request.context_text}"
        )

    @staticmethod
    def _resolve_optional_keys(output_options: dict[str, bool]) -> list[str]:
        optional_map = {
            "history_link": "history_link",
            "gap_analysis": "gap_analysis",
            "review_questions": "review_questions",
            "homework": "homework",
            "expression_notes": "expression_notes",
            "evaluation": "evaluation",
        }
        keys: list[str] = []
        for option_key, target_key in optional_map.items():
            if output_options.get(option_key, False):
                keys.append(target_key)
        return keys
