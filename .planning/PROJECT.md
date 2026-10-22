# SmartServe AI

**Real-Time Restaurant Table Occupancy & Service Tracker**

## Overview
SmartServe AI is an edge-capable computer vision platform that automates table occupancy monitoring, customer counting, service interval tracking (waiter first attendance, food-serving speed), and threshold alerting for restaurant dining operations.

## Core Architecture Principles
1. **Separation of Concerns:** Visual observations (detections, tracks) are never conflated with confirmed operational business events.
2. **Provider-Agnostic Vision:** The detector and tracker interfaces decouple model weights (Ultralytics YOLO11/YOLOv8/custom) from table association logic.
3. **Decoupled Concurrency:** Frame ingestion and YOLO inference run asynchronously from API endpoints and WebSocket event dispatchers.
4. **Privacy-First:** Continuous video is discarded by default; only timestamped metadata, metrics, and anonymized audit records are persisted.

## Technology Stack
- **Backend:** Python 3.11+, FastAPI, OpenCV, Ultralytics YOLO, ByteTrack/BoT-SORT, SQLAlchemy, asyncpg/aiosqlite, Pydantic v2
- **Frontend:** React 18, TypeScript, Vite, Vanilla CSS design tokens, Lucide icons
- **Database:** PostgreSQL (with SQLite fallback for local developer prototyping)
- **Real-Time:** WebSockets for live table state broadcasts
