from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl, Signal
from PySide6.QtGui import QDrag, QMouseEvent, QPixmap, QResizeEvent
from PySide6.QtWidgets import QLabel


class ImagePreviewLabel(QLabel):
    open_requested = Signal()
    context_menu_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_file_path: Path | None = None
        self._drag_start_pos: QPoint | None = None
        self._source_pixmap: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setScaledContents(False)

    def set_image_file_path(self, path: Path | None) -> None:
        self._image_file_path = path
        if path is not None:
            self.setToolTip(str(path))
        else:
            self.setToolTip("")

    def setPixmap(self, pixmap: QPixmap) -> None:  # noqa: N802
        if pixmap.isNull():
            self._source_pixmap = None
            super().setPixmap(QPixmap())
            return

        self._source_pixmap = QPixmap(pixmap)
        self._refresh_scaled_pixmap()

    def clear(self) -> None:
        self._source_pixmap = None
        super().clear()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._refresh_scaled_pixmap()

    def _refresh_scaled_pixmap(self) -> None:
        if self._source_pixmap is None or self._source_pixmap.isNull():
            return

        target_size = self.contentsRect().size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            return

        dpr = self.devicePixelRatioF()
        scaled = self._source_pixmap.scaled(
            int(target_size.width() * dpr),
            int(target_size.height() * dpr),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(dpr)
        super().setPixmap(scaled)

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
