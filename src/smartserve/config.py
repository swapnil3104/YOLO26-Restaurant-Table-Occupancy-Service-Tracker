"""Application configuration using Pydantic Settings."""

from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_ENV: str = "development"
    APP_NAME: str = "SmartServe AI"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "default-insecure-dev-secret-key-change-in-production"
    ALLOWED_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./smartserve.db"
    DATABASE_ECHO: bool = False

    # Vision & Camera Ingestion
    DEFAULT_CAMERA_ID: str = "CAM-01"
    DEFAULT_CAMERA_SOURCE: str = "0"
    CAMERA_RECONNECT_MAX_ATTEMPTS: int = 5
    CAMERA_RECONNECT_INITIAL_DELAY_SEC: float = 1.0
    CAMERA_HEALTH_CHECK_INTERVAL_SEC: float = 5.0
    FRAME_SAMPLE_RATE_HZ: float = 5.0
    INFERENCE_FRAME_WIDTH: int = 1280
    INFERENCE_FRAME_HEIGHT: int = 720

    # Model & Tracking
    DETECTOR_PROVIDER: str = "ultralytics"
    MODEL_WEIGHTS_PATH: str = "yolo11n.pt"
    DETECTION_CONFIDENCE_THRESHOLD: float = 0.45
    DETECTION_CLASSES: List[str] = ["person"]
    TRACKER_TYPE: str = "bytetrack"
    TRACKER_MAX_AGE_FRAMES: int = 30

    # Business Rules & Occupancy Timers (seconds)
    OCCUPANCY_PERSISTENCE_TIME_SEC: float = 5.0
    VACANCY_GRACE_SEC: float = 180.0
    TRACKER_OCCLUSION_GRACE_SEC: float = 3.0

    # Service Alerts Thresholds (seconds)
    THRESHOLD_FIRST_ATTENDANCE_SEC: float = 300.0       # 5 minutes
    THRESHOLD_FOOD_DELIVERY_SEC: float = 1200.0         # 20 minutes
    THRESHOLD_TABLE_OCCUPANCY_MAX_SEC: float = 7200.0   # 2 hours

    # Retention
    EVENT_RETENTION_DAYS: int = 90
    RAW_VIDEO_RETENTION_DAYS: int = 0
    ANONYMIZE_EXPORTS: bool = True


settings = Settings()
