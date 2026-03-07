import os
import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QImage

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.ai_prompt_builder import AIPromptBuildInput, PromptBuilder
from app.services.prompt_library import (
    PROMPT_KEY_IMAGE_CHAT,
    PROMPT_KEY_NOTE,
    PROMPT_KEY_RECORD_CHAT,
    PROMPT_KEY_SYSTEM,
    load_prompt_text,
)
from app.ui.widgets.image_preview_label import ImagePreviewLabel
from app.ui.widgets.image_viewer_dialog import ImageViewerDialog


class PromptBuilderPhaseP1Test(unittest.TestCase):
    def test_prompt_file_loading_uses_file_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prompt_dir = Path(tmp)
            note_file = prompt_dir / "note_generation.txt"
            custom = "Return ONLY JSON. User={user_prompt}; Context={context_text}; Keys={json_keys}"
            note_file.write_text(custom, encoding="utf-8")

            loaded = load_prompt_text(PROMPT_KEY_NOTE, prompt_dir=prompt_dir)
            self.assertEqual(loaded, custom)

    def test_prompt_file_missing_falls_back_to_builtin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prompt_dir = Path(tmp)
            loaded = load_prompt_text(PROMPT_KEY_SYSTEM, prompt_dir=prompt_dir)
            self.assertIn("VideoLearner", loaded)

    def test_prompt_builder_output_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prompt_dir = Path(tmp)
            (prompt_dir / "note_generation.txt").write_text(
                "Return ONLY JSON. User={user_prompt}\nContext={context_text}\nKeys={json_keys}",
                encoding="utf-8",
            )

            builder = PromptBuilder(prompt_dir=prompt_dir)
            prompt = builder.build(
                AIPromptBuildInput(
                    system_prompt="sys",
                    user_prompt="u",
                    context_text="ctx",
                    output_options={"summary": True, "extension": True, "insight": False},
                )
            )

            self.assertIn("Return ONLY JSON", prompt)
            self.assertIn("User=u", prompt)
            self.assertIn("Context=ctx", prompt)
            self.assertIn("summary", prompt)
            self.assertIn("expansion", prompt)
            self.assertIn("inspirations", prompt)
            self.assertIn("guidance", prompt)

    def test_record_chat_prompt_prioritizes_direct_answer(self) -> None:
        prompt = load_prompt_text(PROMPT_KEY_RECORD_CHAT)
        self.assertIn("先回答用户当前问题", prompt)
        self.assertIn("不要先复述上下文", prompt)
        self.assertIn("定义或直接结论", prompt)

    def test_image_chat_prompt_avoids_default_image_description(self) -> None:
        prompt = load_prompt_text(PROMPT_KEY_IMAGE_CHAT)
        self.assertIn("默认先回答用户问题本身", prompt)
        self.assertIn("不要先长篇描述截图", prompt)
        self.assertIn("仅当用户明确询问", prompt)
        self.assertIn("定义或直接结论", prompt)


class ImageUXPhaseP1Test(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        self.app = QApplication.instance() or QApplication([])
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def _create_png(self, name: str = "sample.png") -> Path:
        path = self.tmp_root / name
        image = QImage(64, 48, QImage.Format.Format_ARGB32)
        image.fill(0xFF77AA33)
        saved = image.save(str(path), "PNG")
        self.assertTrue(saved)
        return path

    def test_image_viewer_dialog_loads_image(self) -> None:
        image_path = self._create_png()
        dialog = ImageViewerDialog(image_path)
        self.assertTrue(dialog.has_image())
        dialog.close()

    def test_drag_mime_contains_file_url_and_path(self) -> None:
        image_path = self._create_png("drag.png")
        mime_data = ImagePreviewLabel.build_mime_data_for_path(image_path)

        urls = mime_data.urls()
        self.assertEqual(len(urls), 1)
        self.assertEqual(Path(urls[0].toLocalFile()), image_path)
        self.assertEqual(mime_data.text(), str(image_path))


if __name__ == "__main__":
    unittest.main(verbosity=2)
