from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl, Signal
from PySide6.QtGui import QDrag, QMouseEvent, QPixmap
from PySide6.QtWidgets import QLabel


class ImagePreviewLabel(QLabel):
    open_requested = Signal()
    context_menu_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_file_path: Path | None = None
        self._drag_start_pos: QPoint | None = None

    def set_image_file_path(self, path: Path | None) -> None:
        self._image_file_path = path
        if path is not None:
            self.setToolTip(str(path))
        else:
            self.setToolTip("")

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._image_file_path is not None:
            self.open_requested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._drag_start_pos is None
            or self._image_file_path is None
            or not self._image_file_path.exists()
            or not (event.buttons() & Qt.MouseButton.LeftButton)
        ):
            super().mouseMoveEvent(event)
            return

        if (event.pos() - self._drag_start_pos).manhattanLength() < 8:
            super().mouseMoveEvent(event)
            return

        drag = QDrag(self)
        mime_data = self.build_mime_data_for_path(self._image_file_path)
        drag.setMimeData(mime_data)

        pixmap = self.pixmap()
        if pixmap is not None and not pixmap.isNull():
            drag.setPixmap(pixmap.scaled(180, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

        drag.exec(Qt.DropAction.CopyAction)
        self._drag_start_pos = None

    def contextMenuEvent(self, event) -> None:
        self.context_menu_requested.emit(event.globalPos())

    @staticmethod
    def build_mime_data_for_path(path: Path) -> QMimeData:
        mime_data = QMimeData()
        file_url = QUrl.fromLocalFile(str(path))
        mime_data.setUrls([file_url])
        mime_data.setText(str(path))
        return mime_data
