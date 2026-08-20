"""Runtime configuration for the Wakili scaffold."""

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    model: str = os.getenv("WAKILI_MODEL", "local-scaffold")
    corpus_path: Path = Path(os.getenv("WAKILI_CORPUS_PATH", "data/raw"))


settings = Settings()
