from app.models.project import Project
from app.repositories.project_repository import ProjectRepository
from app.services.errors import ServiceError


class ProjectService:
    def __init__(self, project_repository: ProjectRepository):
        self.project_repository = project_repository

    def list_projects(self) -> list[Project]:
        return self.project_repository.list_all()

    def get_project(self, project_id: int) -> Project | None:
        return self.project_repository.get_by_id(project_id)

    def create_project(
        self,
        name: str,
        description: str = "",
        source: str = "",
        goal: str = "",
        tags: str = "",
    ) -> Project:
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ServiceError("项目名称不能为空。")

        project_id = self.project_repository.create(
            name=cleaned_name,
            description=description.strip(),
            source=source.strip(),
            goal=goal.strip(),
            tags=tags.strip(),
        )
        project = self.project_repository.get_by_id(project_id)
        if project is None:
            raise ServiceError("创建项目失败，请重试。")
        return project

    def update_project(
        self,
        project_id: int,
        name: str,
        description: str = "",
        source: str = "",
        goal: str = "",
        tags: str = "",
    ) -> Project:
        existing = self.project_repository.get_by_id(project_id)
        if existing is None:
            raise ServiceError("项目不存在。")

        cleaned_name = name.strip()
        if not cleaned_name:
            raise ServiceError("项目名称不能为空。")

        updated = self.project_repository.update(
            project_id,
            name=cleaned_name,
            description=description.strip(),
            source=source.strip(),
            goal=goal.strip(),
            tags=tags.strip(),
        )
        if not updated:
            raise ServiceError("更新项目失败。")

        project = self.project_repository.get_by_id(project_id)
        if project is None:
            raise ServiceError("更新后项目读取失败。")
        return project

    def delete_project(self, project_id: int) -> None:
        deleted = self.project_repository.delete(project_id)
        if not deleted:
            raise ServiceError("删除项目失败，项目可能不存在。")
