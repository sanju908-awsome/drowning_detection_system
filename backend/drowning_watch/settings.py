from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    database_url: str = "sqlite:///./drowning_watch.db"
    data_dir: Path = Path("./data")
    upload_dir: Path = Path("./data/uploads")
    output_dir: Path = Path("./data/outputs")
    max_upload_mb: int = 500
    yolo_model: Path = Path("./models/drowning_best.pt")
    yolo_confidence: float = 0.25
    yolo_image_size: int = 640
    deepsort_max_age: int = 30
    deepsort_n_init: int = 3
    deepsort_max_cosine_distance: float = 0.3
    pose_enabled: bool = True
    pose_model: Path = Path("./models/pose_landmarker.task")
    risk_model: Path = Path("./models/risk_model.joblib")
    risk_min_observations: int = 30
    risk_min_probability: float = 0.7
    risk_warning_confirmation_frames: int = 5
    risk_emergency_confirmation_frames: int = 3
    risk_clear_confirmation_frames: int = 15
    cctv_rtsp_url: str = ""
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
