import sys

from PySide6.QtWidgets import QApplication

from app.db.database import Database
from app.services.capture_service import CaptureService
from app.services.project_service import ProjectService
from app.services.record_service import RecordService
from app.services.repository_factory import RepositoryFactory
from app.services.session_service import SessionService
from app.ui.main_window import MainWindow


def main() -> int:
    db = Database()
    db.initialize()

    repositories = RepositoryFactory(db)
    project_service = ProjectService(repositories.projects)
    session_service = SessionService(repositories.sessions, repositories.projects)
    capture_service = CaptureService()
    record_service = RecordService(repositories.records, repositories.sessions, capture_service)

    app = QApplication(sys.argv)
    window = MainWindow(
        project_service=project_service,
        session_service=session_service,
        record_service=record_service,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
