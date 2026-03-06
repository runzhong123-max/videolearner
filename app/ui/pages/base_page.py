from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class BasePage(QWidget):
    def __init__(self, title: str, description: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 20px; font-weight: 600;")
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        layout.addStretch(1)
