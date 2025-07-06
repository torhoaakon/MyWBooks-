import tomllib
from functools import cache
from pathlib import Path

from pydantic import BaseModel


class FoldersConfig(BaseModel):
    cache_dir: Path
    # log_dir: Path


class AppSectrets(BaseModel):
    pass


class AppConfig(BaseModel):
    folders: FoldersConfig
    # maybe? secrets: AppSectrets


def loadConfig(config_filepath: Path) -> AppConfig:
    with open(config_filepath, "rb") as f:
        raw = tomllib.load(f)
    return AppConfig(**raw)
