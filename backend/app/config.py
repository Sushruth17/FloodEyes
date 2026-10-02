"""Settings and city configuration. Model IDs live here and nowhere else."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
CITIES_DIR = REPO_ROOT / "backend" / "cities"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    gemini_backend: Literal["aistudio", "vertex"] = "aistudio"
    gemini_api_key: str | None = None
    google_cloud_project: str | None = None
    google_cloud_location: str = "global"

    depth_model: str = "gemini-3.8-flash"
    trust_model: str = "gemini-3.8-flash"
    control_room_model: str = "gemini-3.1-pro-preview"
    fallback_model: str = "gemini-3.8-flash"
    embedding_model: str = "gemini-embedding-2-preview"

    default_city: str = "blr"


@lru_cache
def get_settings() -> Settings:
    return Settings()


class ReferenceHeight(BaseModel):
    object: str
    height_cm: float
    range_cm: tuple[float, float]
    verified: bool = False


class CityConfig(BaseModel):
    id: str
    name: str
    timezone: str
    city_context: str
    languages: list[str]
    decay_tau_min: int
    reference_heights: list[ReferenceHeight]
    passability: dict[str, dict[str, str]]


@lru_cache
def load_city(city_id: str) -> CityConfig:
    with open(CITIES_DIR / f"{city_id}.yaml") as f:
        return CityConfig.model_validate(yaml.safe_load(f))
