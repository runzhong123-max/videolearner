import sys

from PySide6.QtWidgets import QApplication

from app.db.database import Database
from app.services.project_service import ProjectService
from app.services.repository_factory import RepositoryFactory
from app.services.session_service import SessionService
from app.ui.main_window import MainWindow


def main() -> int:
    db = Database()
    db.initialize()

    repositories = RepositoryFactory(db)
    project_service = ProjectService(repositories.projects)
    session_service = SessionService(repositories.sessions, repositories.projects)

    app = QApplication(sys.argv)
    window = MainWindow(project_service=project_service, session_service=session_service)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
