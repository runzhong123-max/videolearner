from datetime import datetime

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.project import Project
from app.models.session import Session
from app.services.note_service import NoteService
from app.services.project_service import ProjectService
from app.services.record_service import RecordService
from app.services.session_service import SessionService
from app.ui.view_helpers import record_preview_text
from app.utils.datetime_utils import format_cn_datetime


class LibraryPage(QWidget):
    def __init__(
        self,
        project_service: ProjectService,
        session_service: SessionService,
        record_service: RecordService,
        note_service: NoteService | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.project_service = project_service
        self.session_service = session_service
        self.record_service = record_service
        self.note_service = note_service
        self.current_project: Project | None = None

        self.title_label = QLabel("资料库")
        self.title_label.setProperty("role", "pageTitle")
        self.subtitle_label = QLabel("查看历史学习 Session，快速回看学习轨迹。")
        self.subtitle_label.setProperty("role", "pageSubtitle")
        self.scope_label = QLabel("范围：全部项目")
        self.scope_label.setProperty("role", "muted")
        self.summary_label = QLabel("0 个学习 Session")
        self.summary_label.setProperty("role", "badge")

        self.session_list = QListWidget()
        self.session_list.setObjectName("CardList")
        self.session_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.session_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.empty_title_label = QLabel("资料库还是空的")
        self.empty_title_label.setProperty("role", "emptyTitle")
        self.empty_body_label = QLabel("先从学习页开始一次学习记录，资料库会自动显示对应的 Session 卡片。")
        self.empty_body_label.setProperty("role", "emptyBody")
        self.empty_body_label.setWordWrap(True)

        self.empty_card = QWidget()
        self.empty_card.setObjectName("PanelCard")
        empty_layout = QVBoxLayout(self.empty_card)
        empty_layout.setContentsMargins(28, 28, 28, 28)
        empty_layout.setSpacing(8)
        empty_layout.addWidget(self.empty_title_label)
        empty_layout.addWidget(self.empty_body_label)
        empty_layout.addStretch(1)

        self.refresh_btn = QPushButton("刷新资料库")
        self.refresh_btn.setProperty("variant", "ghost")
        self.refresh_btn.clicked.connect(self.refresh_view)

        header_row = QHBoxLayout()
        header_row.addWidget(self.scope_label)
        header_row.addWidget(self.summary_label)
        header_row.addStretch(1)
        header_row.addWidget(self.refresh_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)
        layout.addLayout(header_row)
        layout.addWidget(self.session_list, 1)
        layout.addWidget(self.empty_card)

        self.refresh_view()

    def set_current_project(self, project: Project | None) -> None:
        self.current_project = project
        if project is None:
            self.scope_label.setText("范围：全部项目")
        else:
            self.scope_label.setText(f"范围：当前项目 / {project.name}")
        self.refresh_view()

    def refresh_view(self) -> None:
        self.session_list.clear()

        session_pairs: list[tuple[Project, Session]] = []
        for project in self.project_service.list_projects():
            if self.current_project is not None and project.id != self.current_project.id:
                continue
            for session in self.session_service.list_sessions_by_project(project.id):
                session_pairs.append((project, session))

        session_pairs.sort(key=lambda item: item[1].started_at, reverse=True)
        self.summary_label.setText(f"{len(session_pairs)} 个学习 Session")

        for project, session in session_pairs:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 126))
            self.session_list.addItem(item)
            self.session_list.setItemWidget(item, self._build_card_widget(project, session))

        has_items = bool(session_pairs)
        self.session_list.setVisible(has_items)
        self.empty_card.setVisible(not has_items)

    def _build_card_widget(self, project: Project, session: Session) -> QWidget:
        records = self.record_service.list_records_by_session(session.id)
        record_count = len(records)
        latest_preview = "暂无记录"
        if records:
            latest_preview = record_preview_text(records[-1], max_len=96)

        title = session.title.strip() or f"Session #{session.id}"
        started = format_cn_datetime(session.started_at)
        duration_text = self._build_duration_text(session.started_at, session.ended_at)
        note_text = "已生成笔记" if self.note_service and self.note_service.get_latest_note_for_session(session.id) else "未生成笔记"

        card = QWidget()
        card.setObjectName("PanelCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        title_label = QLabel(title)
        title_label.setProperty("role", "cardTitle")
        note_badge = QLabel(note_text)
        note_badge.setProperty("role", "badge")
        top_row.addWidget(title_label)
        top_row.addStretch(1)
        top_row.addWidget(note_badge)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(14)
        for text in [
            f"日期：{started}",
            f"项目：{project.name}",
            f"记录数量：{record_count}",
            f"学习时长：{duration_text}",
        ]:
            label = QLabel(text)
            label.setProperty("role", "cardMeta")
            meta_row.addWidget(label)
        meta_row.addStretch(1)

        recent_label = QLabel(f"最近记录：{latest_preview}")
        recent_label.setProperty("role", "cardBody")
        recent_label.setWordWrap(True)

        layout.addLayout(top_row)
        layout.addLayout(meta_row)
        layout.addWidget(recent_label)
        return card

    @staticmethod
    def _build_duration_text(started_at: datetime, ended_at: datetime | None) -> str:
        end_time = ended_at or datetime.now(started_at.tzinfo)
        total_seconds = max(0, int((end_time - started_at).total_seconds()))
        hours, remainder = divmod(total_seconds, 3600)
        minutes = remainder // 60
        if hours > 0:
            return f"{hours}小时{minutes}分钟"
        if minutes > 0:
            return f"{minutes}分钟"
        return "不足 1 分钟"
