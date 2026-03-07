from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QVBoxLayout,
)


class _ZoomableGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHints(self.renderHints())
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class ImageViewerDialog(QDialog):
    def __init__(self, image_path: Path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setWindowTitle(f"图片查看 - {image_path.name}")
        self.resize(1100, 760)

        self.scene = QGraphicsScene(self)
        self.view = _ZoomableGraphicsView(self)
        self.view.setScene(self.scene)
        self.tip_label = QLabel("双击预览图进入。滚轮缩放，拖拽平移，ESC 退出。")

        layout = QVBoxLayout(self)
        layout.addWidget(self.tip_label)
        layout.addWidget(self.view, 1)

        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._load_image()

    def _load_image(self) -> None:
        self.scene.clear()
        self._pixmap_item = None

        pixmap = QPixmap(str(self.image_path))
        if pixmap.isNull():
            self.tip_label.setText("图片加载失败。")
            return

        self._pixmap_item = self.scene.addPixmap(pixmap)
        self.view.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def has_image(self) -> bool:
        return self._pixmap_item is not None
