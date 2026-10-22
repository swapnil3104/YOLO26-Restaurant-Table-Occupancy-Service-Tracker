"""Unit tests for configuration validation."""

from smartserve.config import Settings


def test_default_settings():
    """Verify default settings load cleanly with expected defaults."""
    cfg = Settings()
    assert cfg.APP_NAME == "SmartServe AI"
    assert cfg.DEFAULT_CAMERA_ID == "CAM-01"
    assert cfg.DETECTOR_PROVIDER == "ultralytics"
    assert cfg.OCCUPANCY_PERSISTENCE_TIME_SEC > 0
    assert cfg.VACANCY_GRACE_SEC >= 120.0
    assert cfg.THRESHOLD_FIRST_ATTENDANCE_SEC > 0
    assert cfg.THRESHOLD_FOOD_DELIVERY_SEC > 0


def test_custom_settings_override():
    """Verify settings can be overridden with environment variables or kwargs."""
    custom = Settings(
        APP_ENV="testing",
        DEBUG=False,
        DEFAULT_CAMERA_ID="CAM-TEST",
        OCCUPANCY_PERSISTENCE_TIME_SEC=10.0,
    )
    assert custom.APP_ENV == "testing"
    assert custom.DEBUG is False
    assert custom.DEFAULT_CAMERA_ID == "CAM-TEST"
    assert custom.OCCUPANCY_PERSISTENCE_TIME_SEC == 10.0
