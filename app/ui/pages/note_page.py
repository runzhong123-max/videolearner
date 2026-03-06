from app.ui.pages.base_page import BasePage


class NotePage(BasePage):
    def __init__(self, parent=None):
        super().__init__(
            title="Note Page",
            description="学习笔记页面（当前阶段为页面壳子）。",
            parent=parent,
        )
