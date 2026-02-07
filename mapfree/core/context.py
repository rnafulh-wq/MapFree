from pathlib import Path


class ProjectContext:
    def __init__(self, project_path, image_path, profile):
        self.project_path = Path(project_path)
        self.image_path = Path(image_path)
        self.profile = profile

        self.database_path = self.project_path / "database.db"
        self.sparse_path = self.project_path / "sparse"
        self.dense_path = self.project_path / "dense"

    def prepare(self):
        self.project_path.mkdir(parents=True, exist_ok=True)
        self.sparse_path.mkdir(exist_ok=True)
        self.dense_path.mkdir(exist_ok=True)
