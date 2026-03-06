from app.ui.pages.base_page import BasePage


class HomeworkPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(
            title="Homework Page",
            description="扩展练习与行动项页面（当前阶段为页面壳子）。",
            parent=parent,
        )
