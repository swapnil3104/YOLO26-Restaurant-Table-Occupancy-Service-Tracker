import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from smartserve.database.base import Base
from smartserve.database.models import Restaurant, User
from smartserve.database.session import get_db
from smartserve.events.schema import UserRole
from smartserve.main import app


def test_phase8_frontend_build_artifacts_exist():
    """Verify that Vite & TypeScript compilation artifacts exist and are non-empty."""
    dist_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
    index_html = os.path.join(dist_dir, "index.html")
    assert os.path.isdir(dist_dir), f"Dist directory {dist_dir} does not exist"
    assert os.path.isfile(index_html), f"index.html {index_html} does not exist"
    with open(index_html, encoding="utf-8") as f:
        content = f.read()
    assert '<div id="root"></div>' in content
    assert "SmartServe" in content


def test_phase8_component_structure_and_exports():
    """Verify that all Phase 8 components exist in frontend/src."""
    src_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "src")

    expected_files = [
        "pages/SurveillancePage.tsx",
        "pages/SurveillanceVisionPage.tsx",
        "components/surveillance/StandardCctvView.tsx",
        "components/surveillance/TrackingView.tsx",
        "components/surveillance/SourceManager.tsx",
        "components/surveillance/CameraGrid.tsx",
        "components/surveillance/CameraCard.tsx",
        "components/surveillance/CentralKpiPanel.tsx",
        "components/surveillance/FloorKpiPanel.tsx",
        "components/surveillance/MonitoringStatus.tsx",
        "components/common/ErrorBoundary.tsx",
        "components/common/LoadingSkeleton.tsx",
        "components/common/ActionableFailureCard.tsx",
        "components/common/MediaPlayer.tsx",
    ]

    for rel_path in expected_files:
        full_path = os.path.join(src_dir, rel_path)
        assert os.path.isfile(full_path), f"Required Phase 8 component missing: {rel_path}"


@pytest.mark.anyio
async def test_phase8_surveillance_endpoints_contract():
    """Verify all backend endpoints queried by the Surveillance & Vision views."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        rest = Restaurant(restaurant_id="rest_p8", name="P8 Test Bistro")
        session.add(rest)
        mgr = User(
            user_id="usr_mgr_p8",
            restaurant_id="rest_p8",
            username="manager_p8",
            display_name="Patty Manager",
            role=UserRole.MANAGER.value,
            active=True,
        )
        session.add(mgr)
        await session.commit()

        app.dependency_overrides[get_db] = lambda: session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # 1. Cameras feed list (public/staff)
                res_cams = await client.get("/api/v1/cameras")
                assert res_cams.status_code == 200
                cams = res_cams.json()
                assert isinstance(cams, list)

                # 2. Floor analytics requires authenticated user
                res_unauth = await client.get("/api/v1/analytics/floors?floor=ALL")
                assert res_unauth.status_code in (401, 403)

                res_analytics = await client.get(
                    "/api/v1/analytics/floors?floor=ALL",
                    headers={"X-User-ID": "usr_mgr_p8"},
                )
                assert res_analytics.status_code == 200
                analytics = res_analytics.json()
                assert "central" in analytics
                assert "floors" in analytics
                assert "shift_history" in analytics

                # 3. CV Telemetry metadata endpoint for active camera
                if cams:
                    cam_id = cams[0]["camera_id"]
                    res_cv = await client.get(f"/api/v1/cameras/{cam_id}/cv-metadata")
                    assert res_cv.status_code == 200
                    cv_data = res_cv.json()
                    assert "camera_id" in cv_data
                    assert "model" in cv_data
                    assert "inference_latency_ms" in cv_data
                    assert "fps" in cv_data
        finally:
            app.dependency_overrides.pop(get_db, None)
