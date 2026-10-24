"""Versioned prompt registry. Each prompt is `<name>.md` whose first line is `version: <n>`."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    text: str

    @property
    def tag(self) -> str:
        return f"{self.name}@v{self.version}"


@lru_cache
def load(name: str) -> Prompt:
    path = PROMPT_DIR / f"{name}.md"
    if not path.is_file():
        raise KeyError(f"no prompt named {name!r}")
    first, _, rest = path.read_text(encoding="utf-8").partition("\n")
    if not first.startswith("version:"):
        raise ValueError(f"prompt {name!r} must start with 'version: <n>'")
    return Prompt(name, first.removeprefix("version:").strip(), rest.strip())
