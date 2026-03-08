import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.prompt_library import PROMPT_KEY_RECORD_CHAT, load_prompt_text
from app.utils import runtime_paths


class RuntimePathsPackagingTest(unittest.TestCase):
    def test_source_mode_paths_resolve(self) -> None:
        self.assertFalse(runtime_paths.is_frozen())
        self.assertTrue((runtime_paths.source_root() / "app" / "main.py").exists())

    def test_prompts_dir_and_prompt_loading_available(self) -> None:
        prompts_dir = runtime_paths.prompts_dir()
        self.assertTrue(prompts_dir.exists())
        self.assertTrue((prompts_dir / "record_chat.txt").exists())

        prompt_text = load_prompt_text(PROMPT_KEY_RECORD_CHAT)
        self.assertIn("VideoLearner", prompt_text)

    def test_icon_path_is_stable(self) -> None:
        icon = runtime_paths.icon_path()
        self.assertIn("assets", str(icon))
        self.assertIn("videolearner.ico", str(icon).lower())

    def test_writable_root_respects_environment_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("VIDEOLEARNER_HOME")
            os.environ["VIDEOLEARNER_HOME"] = tmp
            try:
                self.assertEqual(runtime_paths.writable_root(), Path(tmp).resolve())
            finally:
                if old is None:
                    del os.environ["VIDEOLEARNER_HOME"]
                else:
                    os.environ["VIDEOLEARNER_HOME"] = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
