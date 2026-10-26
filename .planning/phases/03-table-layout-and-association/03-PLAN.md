# Phase 3: Table Layout and Association Plan

## Phase Goal
Implement normalized polygon table layout configurations, persistent storage surviving restarts, point-in-polygon spatial association of person tracking contact anchors, ambiguity resolution for adjacent/overlapping table boundaries, table capacity validations, debug visualizer overlays for restaurant zones, and admin REST APIs for floorplan management.

## Requirements Covered
- **FR-03: Table Layout and Association (PRD / Rules Section 5)**:
  - Table configuration schema:
    - Unique `table_code` (e.g. `T-01`, `T-02`).
    - Human-readable name/label and seating capacity.
    - Associated `camera_id`.
    - Normalized polygon vertices `[(x, y), ...]` with $0.0 \le x, y \le 1.0$ (invariant to stream resolution changes).
    - Section assignment (e.g., "Main Dining", "Patio", "Bar").
  - Persistent layout storage:
    - Table configurations persist to disk (`tables.json`) and survive application restarts.
    - In-memory cache with atomic file writes for durability.
  - Spatial Association Engine:
    - Evaluates detection bottom-center ground contact points `(cx, y2)` against table polygons.
    - Ray-casting and OpenCV point-in-polygon testing for arbitrary convex and concave polygons.
    - Ambiguity handling: When a person's contact point falls into overlapping regions or multiple adjacent table buffers, flags track as `AMBIGUOUS` unassigned rather than forcing an arbitrary table assignment.
    - Track deduplication: Enforces Rule 5.5 — never count one track more than once for a table in the same observation window.
    - Capacity validation: Identifies when associated patron count exceeds table capacity.
  - Visualizer Overlays:
    - Renders translucent table polygons with table codes, capacity, and current occupant counts.
    - Distinguishes assigned patrons (linked to table) vs. ambiguous/unassigned patrons.
  - Admin & Floorplan REST API:
    - CRUD endpoints for tables under `/api/v1/tables`.
    - Association test endpoint for testing layouts against candidate detections.
  - Verification & Fixtures:
    - Reusable fixtures with adjacent tables, overlapping boundaries, and edge cases.
    - Automated unit and integration test suite.
    - Standalone demo script `scripts/demo_table_association.py`.

## Tasks Breakdown

1. **Table Layout Data Models & Schemas (`src/smartserve/tables/schema.py`)**:
   - `Point`: Normalized 2D coordinate `(x, y)` with boundary validation `[0.0, 1.0]`.
   - `TablePolygon`: Sequence of normalized points, validating minimum 3 vertices, bounding box calculation, and polygon area.
   - `TableConfig`: Table metadata (`id`, `code`, `name`, `camera_id`, `capacity`, `polygon`, `section`, `is_active`, `metadata`).
   - `TableLayout`: Collection of `TableConfig` entries with uniqueness and validation constraints.
   - `AssociationStatus`: Enum (`ASSOCIATED`, `AMBIGUOUS`, `UNASSIGNED`).
   - `TrackAssociation`: Model encapsulating `track_id`, `table_id`, `status`, `confidence`, `anchor_point`, `distance_to_edge`, `competing_tables`.

2. **Persistent Layout Manager (`src/smartserve/tables/manager.py`)**:
   - `TableLayoutManager`: CRUD operations for table definitions.
   - Loads from / persists to JSON file (`config/tables.json` or path in settings).
   - Atomic persistence via temporary file swap to prevent corruption on crash.
   - Default layout bootstrapping for initial setup.

3. **Spatial Table Association Engine (`src/smartserve/tables/associator.py`)**:
   - `SpatialTableAssociator`:
     - Point-in-polygon test (ray-casting + `cv2.pointPolygonTest`).
     - Anchor mapping: Uses person's bottom-center contact point `bbox.bottom_center`.
     - Multi-table proximity and ambiguity detection: If a detection is within multiple polygons or competing thresholds, flag as `AMBIGUOUS` with candidate list.
     - Deduplication: Single track ID associated with at most one table per frame.
     - Summary aggregation: Maps each table to associated tracks and counts.

4. **Visualizer Enhancements (`src/smartserve/vision/visualizer.py`)**:
   - `draw_table_zones_overlay()`: Renders polygons, table ID tags, capacities, and occupant counts.
   - Color code tables based on occupancy status or default floor layout scheme.
   - Connect associated patrons to table centroids with subtle guidelines.

5. **REST API Endpoints (`src/smartserve/api/routes/tables.py`)**:
   - `GET /api/v1/tables` (filter by camera_id).
   - `GET /api/v1/tables/{table_id}`.
   - `POST /api/v1/tables` (create).
   - `PUT /api/v1/tables/{table_id}` (update).
   - `DELETE /api/v1/tables/{table_id}` (delete).
   - `POST /api/v1/tables/associate` (test spatial association on candidate detections).
   - Register router in `src/smartserve/main.py`.

6. **Demonstration Utility (`scripts/demo_table_association.py`)**:
   - Standalone script simulating patrons walking between tables, sitting down, and crossing ambiguous borders.
   - Live rendering with table polygons, track IDs, and association telemetry.

7. **Comprehensive Unit & Integration Tests (`tests/test_table_association.py`)**:
   - Unit tests for schema validation (valid/invalid coordinates, capacity >= 1, duplicate table codes).
   - Unit tests for persistence and restart recovery.
   - Spatial tests: inside convex/concave polygon, outside, on boundary.
   - Ambiguity tests: overlapping tables, adjacent table boundary dispute.
   - Deduplication tests: duplicate track avoidance.
   - Capacity overflow alerts.
   - API endpoint integration tests using `httpx.AsyncClient` / `TestClient`.

## Verification Criteria
- [ ] Table configuration survives application restart (disk persistence tested).
- [ ] Point-in-polygon association accurately maps bottom-center contact point to configured tables.
- [ ] Ambiguous tracks (e.g. overlapping regions or equal competing distances) are flagged `AMBIGUOUS` / unassigned without forcing a guess.
- [ ] No track ID is assigned to multiple tables in the same frame.
- [ ] Visualizer renders polygon zones and association badges.
- [ ] REST API allows table layout CRUD operations with proper validation.
- [ ] 100% of test suite passes.
