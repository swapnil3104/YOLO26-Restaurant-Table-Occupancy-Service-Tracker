# Phase 3: Table Layout and Association Summary

**Phase Completed:** Phase 3 — Table Layout and Association  
**Date:** 2026-10-22  
**Status:** Complete  

## Deliverables Completed

1. **Table Configuration Schemas (`src/smartserve/tables/schema.py`)**:
   - `Point`: Normalized 2D coordinate $(x, y) \in [0.0, 1.0]$.
   - `TablePolygon`: Geometric polygon container with validation (minimum 3 vertices), axis-aligned bounding box calculation, centroid calculation via polygon moments, and shoelace area calculation.
   - `TableConfig`: Comprehensive table definition including stable internal ID, normalized uppercase code (`T-01`), display name, camera mapping (`camera_id`), guest seating capacity ($\ge 1$), floor section, and active status.
   - `TableLayout`: Collection model with fast indexed lookup by ID and code, and camera-level filtering (`for_camera`).
   - `AssociationStatus`: Enumeration (`ASSOCIATED`, `AMBIGUOUS`, `UNASSIGNED`).
   - `TrackAssociation` & `TableAssociationResult`: Batch and per-detection association telemetry models with distance to edge, competing table lists, and capacity alerts.

2. **Persistent Layout Manager (`src/smartserve/tables/manager.py`)**:
   - `TableLayoutManager`: CRUD operations (`list_tables`, `get_table`, `get_table_by_code`, `add_table`, `update_table`, `delete_table`, `reset_to_defaults`).
   - Persistent storage to JSON (`config/tables.json` configurable via `settings.TABLE_LAYOUT_PATH`).
   - Atomic disk persistence using temporary file rename (`os.replace`) to ensure crash durability and corruption prevention across restarts.
   - Automatic default floorplan bootstrapping for standard 4-table restaurant layout.

3. **Spatial Table Association Engine (`src/smartserve/tables/associator.py`)**:
   - Evaluates person bottom-center contact anchor `(cx, y2)` against table polygons (modeling patron ground/seat contact as recommended in `Docs/RULES.md` Section 5).
   - Arbitrary convex and concave polygon evaluation via ray-casting (`point_in_polygon_raycast`) and OpenCV signed distance testing (`cv2.pointPolygonTest`).
   - **Ambiguity Handling**:
     - When contact points fall into overlapping table regions, deep interior points are disambiguated by relative containment depth; equally competing tables are flagged `AMBIGUOUS` with the list of candidate tables.
     - When contact points fall into narrow boundary seams or gaps between adjacent tables, tracks are flagged `AMBIGUOUS` rather than arbitrarily assigned.
   - **Deduplication**: Strictly enforces Rule 5.5 — never counts the same track ID more than once for a table in the same observation window.
   - **Capacity Monitoring**: Flags over-capacity tables when associated patron count exceeds configured seating capacity.

4. **Visualizer Enhancements (`src/smartserve/vision/visualizer.py`)**:
   - `draw_table_zones_overlay()`: Renders translucent table polygon interiors, contrasting zone borders, and table badges (`T-01 (2/4p)`).
   - `draw_spatial_association_overlay()`: Renders complete floorplan with patron contact points, link lines to table centroids, amber warning markers for ambiguous patrons, muted neutral markers for unassigned aisle passers-by, and capacity alert banners.

5. **REST API Endpoints (`src/smartserve/api/routes/tables.py`)**:
   - `GET /api/v1/tables`: List configured tables (with optional `camera_id` filter).
   - `GET /api/v1/tables/{table_id}`: Retrieve table details and polygon vertices.
   - `POST /api/v1/tables`: Create table with validation (returns 201 Created).
   - `PUT /api/v1/tables/{table_id}`: Update table configuration.
   - `DELETE /api/v1/tables/{table_id}`: Remove table.
   - `POST /api/v1/tables/reset-defaults`: Reset floorplan to standard layout.
   - `POST /api/v1/tables/associate`: Test spatial association against candidate detections.
   - Wired into main application router in `src/smartserve/main.py`.

6. **Demonstration Utility (`scripts/demo_table_association.py`)**:
   - Interactive CLI tool simulating patrons seated at tables, patrons walking down central aisles, ambiguous patrons on adjacent boundaries, and over-capacity warnings.
   - Outputs formatted telemetry reports and renders debug visualization frames.

7. **Automated Unit & Integration Test Suite (`tests/test_table_association.py`)**:
   - 15 comprehensive automated tests (42 total project tests passing in ~2.3s):
     - Normalized point and polygon boundary validation.
     - Shoelace polygon area, moment centroid, and bounding box tests.
     - Layout disk persistence and restart recovery.
     - Ray-cast and signed distance tests on convex and concave (L-shaped) geometries.
     - Clear patron association inside table polygons.
     - Unassigned patron identification for aisle passers-by.
     - Ambiguous patron identification on adjacent seams and overlapping boundaries.
     - Track deduplication and capacity overflow warning triggers.
     - Visualizer rendering tests.
     - REST API CRUD and `/associate` endpoint integration tests via FastAPI TestClient.

## Next Phase
**Phase 4: Occupancy State Machine and Sessions** — Build the temporal occupancy state machine (`AVAILABLE`, `POSSIBLY_OCCUPIED`, `OCCUPIED`, `POSSIBLY_VACANT`, `CLEANING_REQUIRED`, `OUT_OF_SERVICE`), configure occupancy confirmation and vacancy grace periods, manage session lifecycles, and maintain smoothed customer count estimates.
