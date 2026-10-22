# 🍽️ SmartServe AI — Restaurant Table Occupancy & Service Tracker

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 20+](https://img.shields.io/badge/node-20+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.3+-61DAFB.svg)](https://react.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An intelligent, computer-vision platform for dining operations. SmartServe AI tracks table occupancy states, estimates guest counts, monitors waiter attendance intervals, measures food-serving speed, and alerts managers to overdue service thresholds in real time.

---

## 🏗️ Architecture & Core Principles

- **Separation of Observations vs. Business Facts:** Computer vision detections are treated as transient candidates, while operational events (table occupancy, waiter greeting, food served) require temporal verification or authorized staff confirmation.
- **Provider-Agnostic Vision Pipeline:** Decoupled `BaseDetector` and `BaseTracker` interfaces allow seamless switching between Ultralytics YOLO models (YOLO11, YOLOv8) and trackers (ByteTrack, BoT-SORT) without rewriting core logic.
- **Privacy-by-Design:** Raw video is processed in memory and discarded by default. No continuous video or unauthorized biometric data is retained.

---

## 📦 Prerequisites

- **Python:** 3.11 or higher (Python 3.11/3.12 recommended for full PyTorch / Ultralytics compatibility)
- **Node.js:** v20.0+ or v22.0+ (with npm v10+)
- **Git**

---

## 🚀 Quickstart & Local Setup

### 1. Clone the Repository & Configure Environment
```bash
git clone https://github.com/swapnil3104/YOLO26-Restaurant-Table-Occupancy-Service-Tracker.git
cd YOLO26-Restaurant-Table-Occupancy-Service-Tracker

# Copy example configuration to .env
cp .env.example .env
```

### 2. Backend Setup
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On macOS / Linux:
source .venv/bin/activate

# Install package in editable mode with development dependencies
pip install -e ".[dev]"
```

### 3. Run Backend Tests & Linting
```bash
# Run backend test suite
pytest

# Run linting with Ruff
ruff check .
```

### 4. Start the Backend API Server
```bash
uvicorn smartserve.main:app --reload --host 0.0.0.0 --port 8000
```
- API Documentation (Swagger UI): [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### 5. Frontend Dashboard Setup
```bash
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```
- Web Dashboard: [http://localhost:5173](http://localhost:5173)

---

## 📁 Repository Structure

```text
├── Docs/                     # Specifications: PRD, Architecture, Design, Rules, Tasks
├── frontend/                 # React 18 + TypeScript + Vite Dashboard
│   ├── src/
│   │   ├── types/            # TypeScript domain interfaces
│   │   ├── App.tsx           # Floor grid & operations dashboard
│   │   ├── main.tsx          # Application root
│   │   └── index.css         # Custom design tokens & styling
│   ├── package.json
│   └── vite.config.ts
├── src/smartserve/           # Backend Core Python Package
│   ├── api/                  # FastAPI routers, dependencies & WebSockets
│   ├── vision/               # Ingestion, detector adapters, tracking
│   ├── occupancy/            # State machine & session manager
│   ├── events/               # Event schemas & validation
│   ├── rules/                # Timers, thresholds & alert logic
│   ├── analytics/            # Performance metrics & reports
│   ├── database/             # SQLAlchemy models & repositories
│   ├── security/             # Role-based access control
│   ├── config.py             # Typed Pydantic Settings
│   └── main.py               # FastAPI entrypoint
├── tests/                    # Pytest test suite
├── .env.example              # Environment variable template
├── .gitignore                # Git ignore rules
├── pyproject.toml            # Python packaging, dependencies, and tool configs
└── README.md
```

---

## 🛡️ License

This project is licensed under the MIT License.
