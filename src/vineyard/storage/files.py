"""Output directory helpers for run artifacts."""

from pathlib import Path

from vineyard.config import settings


class OutputDir:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.path = settings.output_dir(run_id)

    def ensure(self) -> Path:
        self.path.mkdir(parents=True, exist_ok=True, mode=0o700)
        return self.path

    def write(self, relative_path: str, content: str | bytes) -> Path:
        self.ensure()
        target = self.path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content)
        return target

    def list_files(self) -> list[Path]:
        if not self.path.exists():
            return []
        return sorted(p for p in self.path.rglob("*") if p.is_file())
