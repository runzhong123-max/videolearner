import json
import re
from typing import Any

from app.services.ai_errors import AIContractError
from app.services.ai_providers.ai_result import AIGenerationResult


class AIResponseNormalizer:
    """Normalizes AI provider content to stable section contract."""

    def normalize(
        self,
        result: AIGenerationResult,
        output_options: dict[str, bool],
    ) -> dict[str, str]:
        data = self._parse_content_to_dict(result.content)

        summary = self._pick_text(data, "summary")
        expansion = self._pick_text(data, "expansion", "extension")
        inspirations = self._pick_text(data, "inspirations", "insight")
        guidance = self._pick_text(data, "guidance")

        if not summary:
            raise AIContractError("AI 输出缺少必填字段 summary。")
        if not expansion:
            raise AIContractError("AI 输出缺少必填字段 expansion。")

        if output_options.get("insight", False) and not inspirations:
            raise AIContractError("当前 Session 需要 inspirations，但 AI 输出为空。")

        normalized: dict[str, str] = {
            "summary": summary,
            "expansion": expansion,
            "inspirations": inspirations,
            "guidance": guidance,
            # Backward-compatible aliases for existing business code.
            "extension": expansion,
            "insight": inspirations,
        }

        for key in [
            "history_link",
            "gap_analysis",
            "review_questions",
            "homework",
            "expression_notes",
            "evaluation",
        ]:
            normalized[key] = self._pick_text(data, key)

        return normalized

    def _parse_content_to_dict(self, content: str) -> dict[str, Any]:
        text = (content or "").strip()
        if not text:
            raise AIContractError("AI 输出为空，无法解析。")

        try:
            loaded = json.loads(text)
            if isinstance(loaded, dict):
                return loaded
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{[\s\S]*\}", text)
        if match is None:
            raise AIContractError("AI 输出不是可解析 JSON，无法抽取 sections。")

        try:
            loaded = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise AIContractError("AI 输出 JSON 解析失败。") from exc

        if not isinstance(loaded, dict):
            raise AIContractError("AI 输出结构非法，根节点必须为对象。")
        return loaded

    @staticmethod
    def _pick_text(data: dict[str, Any], *keys: str) -> str:
        for key in keys:
            if key in data:
                value = data[key]
                if value is None:
                    return ""
                if isinstance(value, str):
                    return value.strip()
                return str(value).strip()
        return ""
