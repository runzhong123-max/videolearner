from app.ui.pages.base_page import BasePage


class PromptPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(
            title="Prompt Page",
            description="Prompt 模板管理页面（当前阶段为页面壳子）。",
            parent=parent,
        )
