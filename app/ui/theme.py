from pathlib import Path

from PySide6.QtWidgets import QApplication

SESSION_SELECTOR_ARROW = (Path(__file__).resolve().parent / "assets" / "chevron-down.svg").as_posix()

APP_STYLESHEET = """
QWidget {
    background: #0f1115;
    color: #e8edf5;
    font-family: "Microsoft YaHei UI";
    font-size: 14px;
}

QMainWindow, QDialog {
    background: #0f1115;
}

QStatusBar {
    background: #12161d;
    color: #8f9aae;
    border-top: 1px solid #1f2632;
}

QLabel {
    background: transparent;
}

QLabel[role="muted"] {
    color: #8f9aae;
}

QLabel[role="pageTitle"] {
    color: #f4f7fb;
    font-size: 24px;
    font-weight: 700;
}

QLabel[role="pageSubtitle"] {
    color: #909aad;
    font-size: 12px;
}

QLabel[role="sectionTitle"] {
    color: #f0f4fa;
    font-size: 16px;
    font-weight: 600;
}

QLabel[role="sectionHint"] {
    color: #778298;
    font-size: 12px;
}

QLabel[role="cardTitle"] {
    color: #eef3fa;
    font-size: 16px;
    font-weight: 600;
}

QLabel[role="cardMeta"] {
    color: #8994a8;
    font-size: 12px;
}

QLabel[role="cardBody"] {
    color: #c8d1e0;
    font-size: 14px;
}

QLabel[role="badge"] {
    color: #a9c7ff;
    background: #16243a;
    border: 1px solid #27456f;
    border-radius: 10px;
    padding: 3px 8px;
}

QLabel[role="emptyTitle"] {
    color: #edf2fa;
    font-size: 18px;
    font-weight: 600;
}

QLabel[role="emptyBody"] {
    color: #8994a8;
    font-size: 14px;
}

QWidget#AppShell {
    background: #0b0d12;
}

QWidget#ContentShell {
    background: #0f1115;
}

QWidget#PanelCard,
QFrame#PanelCard,
QWidget#InsetCard,
QGroupBox {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
}

QWidget#InsetCard {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
}

QWidget#PreviewPanel {
    background: transparent;
    border: none;
}

QLabel#PreviewSurface {
    background: rgba(255,255,255,0.02);
    border: none;
    border-radius: 10px;
}

QScrollArea#OcrScrollArea {
    background: transparent;
    border: none;
}

QScrollArea#OcrScrollArea > QWidget > QWidget {
    background: transparent;
}

QListWidget#TimelineList {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    outline: 0;
}

QListWidget#TimelineList::item {
    min-height: 56px;
    border-radius: 10px;
    padding: 8px 12px;
    margin: 4px;
}

QListWidget#TimelineList::item:selected {
    background: rgba(80,140,255,0.15);
    color: #ffffff;
}

QListWidget#TimelineList::item:hover {
    background: rgba(255,255,255,0.05);
}

QPushButton[variant="panelToggle"] {
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    padding: 0;
}
QListWidget#SideNav {
    background: #0b0d12;
    border: none;
    border-right: 1px solid #161b24;
    padding: 16px 10px;
    outline: 0;
}

QListWidget#SideNav::item {
    color: #8792a8;
    border-radius: 12px;
    padding: 14px 16px;
    margin: 4px 0;
}

QListWidget#SideNav::item:selected,
QListWidget#SideNav::item:hover {
    background: #1a2230;
    color: #f4f7fb;
}

QListWidget#CardList {
    background: transparent;
    border: none;
    outline: 0;
}

QListWidget#CardList::item {
    border: none;
    margin: 0 0 14px 0;
    padding: 0;
}

QListWidget#EmbeddedList {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    outline: 0;
}

QListWidget#EmbeddedList::item {
    border-radius: 10px;
    padding: 12px;
    margin: 4px;
}

QListWidget#EmbeddedList::item:selected {
    background: #22314a;
    color: #ffffff;
}

QListWidget#EmbeddedList::item:hover {
    background: #182131;
}


QWidget#SettingRow {
    background: #14181f;
    border: 1px solid #181d26;
    border-radius: 16px;
}

QWidget#SettingRow QLabel[role="cardTitle"] {
    font-size: 14px;
}

QListWidget#CardList::item:selected {
    background: #1b2230;
    border-radius: 16px;
}

QListWidget#CardList::item:hover {
    background: #141922;
    border-radius: 16px;
}

QPushButton {
    background: #181d27;
    border: 1px solid #222a36;
    border-radius: 12px;
    color: #ecf1f8;
    padding: 8px 14px;
}

QPushButton:hover {
    background: #202836;
    border-color: #2a3342;
}

QPushButton:pressed {
    background: #16202f;
}

QPushButton:disabled {
    background: #121720;
    color: #667085;
    border-color: #1d2430;
}

QPushButton[variant="primary"] {
    background: #3d78d8;
    border-color: #3d78d8;
    color: #ffffff;
    font-weight: 600;
}

QPushButton[variant="primary"]:hover {
    background: #4985e6;
    border-color: #4985e6;
}

QPushButton[variant="ghost"] {
    background: transparent;
    border-color: transparent;
    color: #9aa6bb;
}

QPushButton[variant="ghost"]:hover {
    background: #1a2230;
    border-color: #1a2230;
    color: #eef3fb;
}

QLineEdit,
QTextEdit,
QPlainTextEdit,
QComboBox,
QSpinBox {
    background: #10141b;
    border: 1px solid #1b222d;
    border-radius: 12px;
    padding: 8px 10px;
    selection-background-color: #35507a;
}

QLineEdit:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QComboBox:focus,
QSpinBox:focus {
    border-color: #3f6fb8;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox#SessionSelector {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 12px;
    padding: 8px 40px 8px 12px;
    color: #eef3fb;
}

QComboBox#SessionSelector:hover {
    background: rgba(255,255,255,0.045);
    border-color: rgba(255,255,255,0.18);
}

QComboBox#SessionSelector:focus,
QComboBox#SessionSelector:on {
    background: rgba(255,255,255,0.05);
    border-color: #4b7fd8;
}

QComboBox#SessionSelector:disabled {
    background: rgba(255,255,255,0.018);
    border-color: rgba(255,255,255,0.08);
    color: #a6b0c1;
}

QComboBox#SessionSelector::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 34px;
    border: none;
    background: transparent;
    border-left: 1px solid rgba(255,255,255,0.06);
}

QComboBox#SessionSelector::down-arrow {
    image: url(${SESSION_SELECTOR_ARROW});
    width: 12px;
    height: 12px;
}

QComboBox#SessionSelector:on::down-arrow {
    top: 1px;
}

QComboBox#SessionSelector QAbstractItemView,
QAbstractItemView#SessionSelectorPopup {
    background: #151922;
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 12px;
    padding: 6px;
    outline: 0;
    selection-background-color: rgba(80,140,255,0.18);
    selection-color: #ffffff;
}

QComboBox#SessionSelector QAbstractItemView::item,
QAbstractItemView#SessionSelectorPopup::item {
    min-height: 36px;
    border-radius: 8px;
    padding: 8px 10px;
    margin: 2px 0;
}

QComboBox#SessionSelector QAbstractItemView::item:hover,
QAbstractItemView#SessionSelectorPopup::item:hover {
    background: rgba(255,255,255,0.05);
}

QComboBox#SessionSelector QAbstractItemView::item:selected,
QAbstractItemView#SessionSelectorPopup::item:selected {
    background: rgba(80,140,255,0.18);
    color: #ffffff;
}

QTableWidget {
    background: #10141c;
    border: 1px solid #202734;
    border-radius: 12px;
    gridline-color: #202734;
}

QHeaderView::section {
    background: #151922;
    color: #c6d0df;
    border: none;
    border-bottom: 1px solid #202734;
    padding: 8px;
}

QScrollArea {
    background: transparent;
    border: none;
}

QGroupBox {
    background: transparent;
    border: none;
    margin-top: 18px;
    padding: 10px 0 0 0;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 0px;
    padding: 0;
    color: #dbe4f2;
}

QTabWidget::pane {
    border: none;
}

QTabBar::tab {
    background: transparent;
    color: #7f8aa0;
    border: 1px solid transparent;
    border-bottom: none;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    padding: 8px 14px;
    margin-right: 4px;
}

QTabBar::tab:selected {
    background: #1b2130;
    color: #f4f7fb;
    border-color: #1b2130;
}

QSplitter::handle {
    background: #0f131a;
    width: 4px;
}
"""


def apply_app_theme(app: QApplication) -> None:
    app.setStyleSheet(APP_STYLESHEET.replace("${SESSION_SELECTOR_ARROW}", SESSION_SELECTOR_ARROW))



