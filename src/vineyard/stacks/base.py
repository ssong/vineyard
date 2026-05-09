"""Stack profile protocol + registry."""

from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path

from vineyard.config import StackName
from vineyard.models.handoff import AuthChoice, BuildPreferences, DBChoice, PaymentsChoice


@dataclass(frozen=True)
class StackProfile:
    name: StackName
    display_name: str
    description: str
    container_image: str
    default_auth: AuthChoice
    default_payments: PaymentsChoice
    default_db: DBChoice
    rubric_path: Path
    system_prompt_path: Path
    prompt_dir: Path
    file_extensions: tuple[str, ...] = field(default_factory=tuple)
    # Shell commands the VALIDATE phase runs against the generated codebase.
    # Each one runs sequentially in the same sandbox session; first non-zero
    # exit code stops the chain.
    validate_commands: tuple[str, ...] = field(default_factory=tuple)

    def rubric(self) -> str:
        return self.rubric_path.read_text()

    def system_prompt(self) -> str:
        return self.system_prompt_path.read_text()

    def prompt_fragment(self, phase: str) -> str:
        candidate = self.prompt_dir / f"{phase}.md"
        return candidate.read_text() if candidate.exists() else ""

    def default_preferences(self) -> BuildPreferences:
        return BuildPreferences(
            stack=self.name,
            auth=self.default_auth,
            payments=self.default_payments,
            db=self.default_db,
        )


class StackRegistry:
    def __init__(self) -> None:
        self._stacks: dict[StackName, StackProfile] = {}

    def register(self, profile: StackProfile) -> None:
        self._stacks[profile.name] = profile

    def get(self, name: StackName) -> StackProfile:
        if name not in self._stacks:
            raise KeyError(f"Unknown stack: {name}. Registered: {sorted(self._stacks)}")
        return self._stacks[name]

    def all(self) -> list[StackProfile]:
        return list(self._stacks.values())


registry = StackRegistry()


def _stack_dir(name: str) -> Path:
    """Resolve the on-disk directory for a stack package."""
    return Path(str(files(f"vineyard.stacks.{name}")))
