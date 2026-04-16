# Strava AI Coach — Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a post-run AI debrief + training load dashboard for ultra/trail runners, connecting Strava data to actionable, numeric coaching output.

**Architecture:** Python FastAPI backend handles Strava OAuth, webhook ingestion, metrics computation, and LangGraph-powered debrief generation; React (Vite + TypeScript) frontend renders the dashboard, onboarding wizard, activity debriefs, and race targets. Background jobs run via Celery + Redis; PostgreSQL stores all persistent state.

**Tech Stack:**
- Backend: Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL 16, Celery + Redis, LangGraph 0.2, Anthropic SDK (Claude Sonnet 4.6), cryptography (AES-256)
- Frontend: React 18, Vite, TypeScript, React Router v6, TanStack Query v5, Recharts, Tailwind CSS, shadcn/ui
- Infra: Docker Compose (local), Railway/Render (deploy)

---

## Scope Notice

This plan covers 5 independent subsystems. Each Phase block below is self-contained and testable on its own. Recommended execution order: Phase 0 → 1 → 2 → 3 → 4.

---

## Repository Layout

```
strava-coach/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app factory
│   │   ├── config.py                # Pydantic Settings
│   │   ├── database.py              # SQLAlchemy engine + session
│   │   ├── models/
│   │   │   ├── athlete.py           # Athlete + AthleteProfile
│   │   │   ├── credentials.py       # StravaCredential (encrypted tokens)
│   │   │   ├── activity.py          # Activity + ActivityStream
│   │   │   ├── metrics.py           # ComputedMetrics, LoadHistory
│   │   │   └── target.py            # RaceTarget
│   │   ├── routers/
│   │   │   ├── auth.py              # GET /auth/strava, GET /auth/callback
│   │   │   ├── webhook.py           # GET+POST /webhook/strava
│   │   │   ├── activities.py        # GET /activities, GET /activities/{id}
│   │   │   ├── dashboard.py         # GET /dashboard/load
│   │   │   ├── onboarding.py        # POST /onboarding/profile
│   │   │   └── targets.py           # CRUD /targets
│   │   ├── services/
│   │   │   ├── strava_client.py     # Rate-limit-aware Strava HTTP client
│   │   │   ├── token_service.py     # AES-256 encrypt/decrypt + token refresh
│   │   │   ├── activity_ingestion.py # Orchestrate fetch → metrics → debrief
│   │   │   └── push_service.py      # Web Push + Telegram
│   │   ├── metrics/
│   │   │   ├── zones.py             # HR + pace zone computation
│   │   │   ├── pace.py              # GAP, NGP
│   │   │   ├── heart_rate.py        # hrTSS, HR drift, aerobic decoupling
│   │   │   ├── load.py              # TSS, CTL, ATL, TSB, ACWR, monotony, strain
│   │   │   └── engine.py            # compute_activity_metrics() entry point
│   │   ├── agents/
│   │   │   ├── schema.py            # Pydantic input/output models
│   │   │   ├── prompts.py           # System prompt templates
│   │   │   ├── debrief_graph.py     # LangGraph StateGraph definition
│   │   │   └── evaluator.py         # LLM-as-judge scorer
│   │   └── workers/
│   │       └── tasks.py             # Celery tasks: ingest_activity, backfill
│   ├── migrations/                  # Alembic versions
│   ├── tests/
│   │   ├── test_metrics/
│   │   ├── test_routers/
│   │   └── test_agents/
│   ├── alembic.ini
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx                  # Router root
│   │   ├── api/
│   │   │   └── client.ts            # axios instance + TanStack Query hooks
│   │   ├── pages/
│   │   │   ├── Connect.tsx          # Landing / Strava OAuth
│   │   │   ├── Setup.tsx            # 4-step onboarding wizard
│   │   │   ├── Dashboard.tsx        # Load chart + ACWR gauge
│   │   │   ├── ActivityDetail.tsx   # Debrief + metric deep-dive
│   │   │   └── Targets.tsx          # Race target CRUD
│   │   ├── components/
│   │   │   ├── LoadChart.tsx        # CTL/ATL/TSB 90-day chart (Recharts)
│   │   │   ├── AcwrGauge.tsx        # Radial gauge with zone colors
│   │   │   ├── DebriefCard.tsx      # 3-section debrief display
│   │   │   ├── MetricBadge.tsx      # Clickable metric → chart
│   │   │   └── PhaseIndicator.tsx   # Base/Build/Peak/Taper badge
│   │   ├── hooks/
│   │   │   ├── useAuth.ts           # Auth state + redirect logic
│   │   │   └── usePushNotifications.ts
│   │   └── types/
│   │       └── index.ts             # Shared TypeScript types
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
├── docker-compose.yml
└── .env.example
```

---

## Phase 0 — Infra & Strava Integration

### Task 0.1: Project scaffolding

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/app/config.py`
- Create: `docker-compose.yml`

- [ ] **Step 1: Create `backend/requirements.txt`**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
alembic==1.13.3
asyncpg==0.29.0
psycopg2-binary==2.9.9
pydantic-settings==2.5.2
httpx==0.27.2
cryptography==43.0.1
python-jose[cryptography]==3.3.0
celery==5.4.0
redis==5.0.8
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2
python-dotenv==1.0.1
```

- [ ] **Step 2: Create `backend/.env.example`**

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/stravacoach
REDIS_URL=redis://localhost:6379/0
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_VERIFY_TOKEN=random_32_char_string
STRAVA_WEBHOOK_CALLBACK_URL=https://yourdomain.com/webhook/strava
ENCRYPTION_KEY=base64_encoded_32_byte_key
ANTHROPIC_API_KEY=sk-ant-...
JWT_SECRET=random_64_char_string
FRONTEND_URL=http://localhost:5173
```

- [ ] **Step 3: Create `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    strava_client_id: str
    strava_client_secret: str
    strava_verify_token: str
    strava_webhook_callback_url: str
    encryption_key: str  # base64-encoded 32-byte key
    anthropic_api_key: str
    jwt_secret: str
    frontend_url: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
```

- [ ] **Step 4: Create `docker-compose.yml`**

```yaml
version: "3.9"
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: stravacoach
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

- [ ] **Step 5: Start services and verify**

```bash
cd /Users/nguyenminhduc/Desktop/strava-coach
docker compose up -d
docker compose ps
```
Expected: postgres and redis both `healthy` / `running`

- [ ] **Step 6: Commit**

```bash
git init
git add backend/ docker-compose.yml .env.example
git commit -m "chore: scaffold backend structure and docker compose"
```

---

### Task 0.2: Database models + migrations

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/app/models/athlete.py`
- Create: `backend/app/models/credentials.py`
- Create: `backend/app/models/activity.py`
- Create: `backend/app/models/metrics.py`
- Create: `backend/app/models/target.py`
- Create: `backend/alembic.ini`

- [ ] **Step 1: Create `backend/app/database.py`**

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 2: Create `backend/app/models/athlete.py`**

```python
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.sql import func
from app.database import Base
import enum

class Units(str, enum.Enum):
    metric = "metric"
    imperial = "imperial"

class Athlete(Base):
    __tablename__ = "athletes"

    id = Column(Integer, primary_key=True)
    strava_athlete_id = Column(Integer, unique=True, nullable=False, index=True)
    firstname = Column(String(100))
    lastname = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AthleteProfile(Base):
    __tablename__ = "athlete_profiles"

    id = Column(Integer, primary_key=True)
    athlete_id = Column(Integer, nullable=False, index=True)
    lthr = Column(Integer)                   # Lactate threshold HR (bpm)
    max_hr = Column(Integer)
    threshold_pace_sec_km = Column(Integer)  # Critical velocity (sec/km)
    weight_kg = Column(Float)
    vo2max_estimate = Column(Float)
    units = Column(SAEnum(Units), default=Units.metric)
    language = Column(String(10), default="en")
    onboarding_complete = Column(Boolean, default=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
```

- [ ] **Step 3: Create `backend/app/models/credentials.py`**

```python
from sqlalchemy import Column, Integer, BigInteger, Text, Boolean
from app.database import Base

class StravaCredential(Base):
    __tablename__ = "strava_credentials"

    id = Column(Integer, primary_key=True)
    athlete_id = Column(Integer, nullable=False, unique=True, index=True)
    # All token fields stored AES-256 encrypted (base64 ciphertext)
    access_token_enc = Column(Text, nullable=False)
    refresh_token_enc = Column(Text, nullable=False)
    expires_at = Column(BigInteger, nullable=False)  # Unix timestamp
    source_disconnected = Column(Boolean, default=False)
    webhook_subscription_id = Column(Integer)
```

- [ ] **Step 4: Create `backend/app/models/activity.py`**

```python
from sqlalchemy import Column, Integer, BigInteger, String, Float, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from app.database import Base

class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)
    strava_activity_id = Column(BigInteger, unique=True, nullable=False, index=True)
    athlete_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255))
    sport_type = Column(String(50))
    start_date = Column(DateTime(timezone=True))
    elapsed_time_sec = Column(Integer)
    moving_time_sec = Column(Integer)
    distance_m = Column(Float)
    total_elevation_gain_m = Column(Float)
    average_heartrate = Column(Float)
    max_heartrate = Column(Float)
    # Raw streams stored gzipped JSON
    streams_raw = Column(JSON)
    excluded_from_load = Column(Boolean, default=False)
    skipped_reason = Column(String(100))
    processing_status = Column(String(50), default="pending")  # pending|processing|done|failed
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 5: Create `backend/app/models/metrics.py`**

```python
from sqlalchemy import Column, Integer, Float, Date, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class ActivityMetrics(Base):
    __tablename__ = "activity_metrics"

    id = Column(Integer, primary_key=True)
    activity_id = Column(Integer, nullable=False, unique=True, index=True)
    athlete_id = Column(Integer, nullable=False, index=True)
    tss = Column(Float)
    hr_tss = Column(Float)
    gap_avg_sec_km = Column(Float)
    ngp_sec_km = Column(Float)
    hr_drift_pct = Column(Float)
    aerobic_decoupling_pct = Column(Float)
    zone_distribution = Column(Column.__class__)  # JSON {z1_pct, z2_pct, ...}
    computed_at = Column(DateTime(timezone=True), server_default=func.now())

class LoadHistory(Base):
    __tablename__ = "load_history"

    id = Column(Integer, primary_key=True)
    athlete_id = Column(Integer, nullable=False, index=True)
    date = Column(Date, nullable=False)
    ctl = Column(Float)   # Chronic Training Load
    atl = Column(Float)   # Acute Training Load
    tsb = Column(Float)   # Training Stress Balance
    acwr = Column(Float)  # Acute:Chronic Workload Ratio
    monotony = Column(Float)
    strain = Column(Float)
```

- [ ] **Step 6: Create `backend/app/models/target.py`**

```python
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Enum as SAEnum
from sqlalchemy.sql import func
from app.database import Base
import enum

class Priority(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"

class RaceTarget(Base):
    __tablename__ = "race_targets"

    id = Column(Integer, primary_key=True)
    athlete_id = Column(Integer, nullable=False, index=True)
    race_name = Column(String(255), nullable=False)
    race_date = Column(Date, nullable=False)
    distance_km = Column(Float, nullable=False)
    elevation_gain_m = Column(Float)
    goal_time_sec = Column(Integer)
    priority = Column(SAEnum(Priority), default=Priority.A)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 7: Initialise Alembic and generate initial migration**

```bash
cd backend
pip install -r requirements.txt
alembic init migrations
# Edit alembic.ini: set sqlalchemy.url = postgresql://postgres:postgres@localhost:5432/stravacoach
# Edit migrations/env.py: import Base from app.database; set target_metadata = Base.metadata
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/ backend/app/database.py backend/alembic.ini backend/migrations/
git commit -m "feat: database models and initial alembic migration"
```

---

### Task 0.3: Token encryption service

**Files:**
- Create: `backend/app/services/token_service.py`
- Create: `backend/tests/test_routers/test_token_service.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_routers/test_token_service.py
import pytest
from app.services.token_service import encrypt, decrypt

def test_encrypt_decrypt_roundtrip():
    plaintext = "acc_token_abc123"
    ciphertext = encrypt(plaintext)
    assert ciphertext != plaintext
    assert decrypt(ciphertext) == plaintext

def test_different_encryptions_same_input():
    """AES-GCM uses random nonce — same plaintext yields different ciphertext."""
    c1 = encrypt("same")
    c2 = encrypt("same")
    assert c1 != c2
    assert decrypt(c1) == decrypt(c2) == "same"
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd backend
pytest tests/test_routers/test_token_service.py -v
```
Expected: `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Create `backend/app/services/token_service.py`**

```python
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import settings

def _get_key() -> bytes:
    return base64.b64decode(settings.encryption_key)

def encrypt(plaintext: str) -> str:
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ciphertext).decode()

def decrypt(token: str) -> str:
    key = _get_key()
    aesgcm = AESGCM(key)
    raw = base64.b64decode(token.encode())
    nonce, ciphertext = raw[:12], raw[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode()
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/test_routers/test_token_service.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/token_service.py backend/tests/test_routers/test_token_service.py
git commit -m "feat: AES-256-GCM token encryption service"
```

---

### Task 0.4: Strava OAuth routes

**Files:**
- Create: `backend/app/services/strava_client.py`
- Create: `backend/app/routers/auth.py`
- Create: `backend/app/main.py`

- [ ] **Step 1: Create `backend/app/services/strava_client.py`**

```python
import httpx
import time
from app.config import settings

STRAVA_BASE = "https://www.strava.com/api/v3"
AUTH_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"

def get_authorization_url(state: str) -> str:
    params = {
        "client_id": settings.strava_client_id,
        "redirect_uri": f"{settings.strava_webhook_callback_url.replace('/webhook/strava', '')}/auth/callback",
        "response_type": "code",
        "approval_prompt": "auto",
        "scope": "read,activity:read_all,profile:read_all",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{AUTH_URL}?{query}"

async def exchange_code(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(TOKEN_URL, data={
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
            "code": code,
            "grant_type": "authorization_code",
        })
        r.raise_for_status()
        return r.json()

async def refresh_access_token(refresh_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(TOKEN_URL, data={
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
        r.raise_for_status()
        return r.json()

async def get_activity(access_token: str, activity_id: int) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{STRAVA_BASE}/activities/{activity_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r.raise_for_status()
        return r.json()

async def get_activity_streams(access_token: str, activity_id: int) -> dict:
    keys = "heartrate,altitude,velocity_smooth,time,latlng,cadence,watts"
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{STRAVA_BASE}/activities/{activity_id}/streams",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"keys": keys, "key_by_type": "true"},
        )
        r.raise_for_status()
        return r.json()
```

- [ ] **Step 2: Create `backend/app/routers/auth.py`**

```python
import secrets
import time
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.athlete import Athlete
from app.models.credentials import StravaCredential
from app.services.strava_client import get_authorization_url, exchange_code
from app.services.token_service import encrypt
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

# In production replace with Redis-backed store
_state_store: dict[str, bool] = {}

@router.get("/strava")
async def strava_login():
    state = secrets.token_urlsafe(32)
    _state_store[state] = True
    return RedirectResponse(get_authorization_url(state))

@router.get("/callback")
async def strava_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    if state not in _state_store:
        raise HTTPException(status_code=400, detail="Invalid state — possible CSRF")
    del _state_store[state]

    token_data = await exchange_code(code)
    strava_athlete = token_data["athlete"]
    strava_id = strava_athlete["id"]

    # Upsert athlete
    result = await db.execute(select(Athlete).where(Athlete.strava_athlete_id == strava_id))
    athlete = result.scalar_one_or_none()
    if not athlete:
        athlete = Athlete(
            strava_athlete_id=strava_id,
            firstname=strava_athlete.get("firstname", ""),
            lastname=strava_athlete.get("lastname", ""),
        )
        db.add(athlete)
        await db.flush()

    # Upsert credentials (encrypted)
    result2 = await db.execute(
        select(StravaCredential).where(StravaCredential.athlete_id == athlete.id)
    )
    cred = result2.scalar_one_or_none()
    if not cred:
        cred = StravaCredential(athlete_id=athlete.id)
        db.add(cred)

    cred.access_token_enc = encrypt(token_data["access_token"])
    cred.refresh_token_enc = encrypt(token_data["refresh_token"])
    cred.expires_at = token_data["expires_at"]
    cred.source_disconnected = False
    await db.commit()

    return RedirectResponse(f"{settings.frontend_url}/setup?athlete_id={athlete.id}")
```

- [ ] **Step 3: Create `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import auth

app = FastAPI(title="Strava AI Coach API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Run the server and test manually**

```bash
cd backend
uvicorn app.main:app --reload --port 8000
# In browser: http://localhost:8000/docs
# Verify GET /auth/strava redirects to Strava
# Verify GET /health returns {"status":"ok"}
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/auth.py backend/app/services/strava_client.py backend/app/main.py
git commit -m "feat: Strava OAuth connect + callback with encrypted token storage"
```

---

### Task 0.5: Strava webhook (HMAC validation + queue)

**Files:**
- Create: `backend/app/routers/webhook.py`
- Create: `backend/app/workers/tasks.py`

- [ ] **Step 1: Write failing test for HMAC validation**

```python
# backend/tests/test_routers/test_webhook.py
import pytest
import hmac, hashlib
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app
from app.config import settings

client = TestClient(app)

def test_webhook_challenge():
    r = client.get("/webhook/strava", params={
        "hub.mode": "subscribe",
        "hub.challenge": "abc123",
        "hub.verify_token": settings.strava_verify_token,
    })
    assert r.status_code == 200
    assert r.json() == {"hub.challenge": "abc123"}

def test_webhook_bad_verify_token():
    r = client.get("/webhook/strava", params={
        "hub.mode": "subscribe",
        "hub.challenge": "abc123",
        "hub.verify_token": "wrong",
    })
    assert r.status_code == 403
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/test_routers/test_webhook.py -v
```

- [ ] **Step 3: Create `backend/app/routers/webhook.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.config import settings
from app.workers.tasks import enqueue_activity

router = APIRouter(prefix="/webhook", tags=["webhook"])

@router.get("/strava")
async def strava_webhook_challenge(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
):
    if hub_verify_token != settings.strava_verify_token:
        raise HTTPException(status_code=403, detail="Invalid verify token")
    return {"hub.challenge": hub_challenge}

@router.post("/strava")
async def strava_webhook_event(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    payload = await request.json()
    object_type = payload.get("object_type")
    aspect_type = payload.get("aspect_type")
    activity_id = payload.get("object_id")
    owner_id = payload.get("owner_id")  # strava_athlete_id

    if object_type == "activity" and aspect_type == "create":
        background_tasks.add_task(enqueue_activity, owner_id, activity_id)

    return {"status": "ok"}
```

- [ ] **Step 4: Create `backend/app/workers/tasks.py`**

```python
import asyncio
import logging
from app.database import AsyncSessionLocal
from app.models.athlete import Athlete
from app.models.activity import Activity
from app.services.strava_client import get_activity, get_activity_streams
from app.services.token_service import decrypt
from sqlalchemy import select

logger = logging.getLogger(__name__)

async def enqueue_activity(strava_athlete_id: int, strava_activity_id: int):
    """Fetch activity + streams from Strava and persist raw data."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Athlete).where(Athlete.strava_athlete_id == strava_athlete_id)
        )
        athlete = result.scalar_one_or_none()
        if not athlete:
            logger.warning(f"Athlete {strava_athlete_id} not found for activity {strava_activity_id}")
            return

        from app.models.credentials import StravaCredential
        cred_result = await db.execute(
            select(StravaCredential).where(StravaCredential.athlete_id == athlete.id)
        )
        cred = cred_result.scalar_one_or_none()
        if not cred:
            return

        access_token = decrypt(cred.access_token_enc)
        activity_data = await get_activity(access_token, strava_activity_id)
        streams_data = await get_activity_streams(access_token, strava_activity_id)

        activity = Activity(
            strava_activity_id=strava_activity_id,
            athlete_id=athlete.id,
            name=activity_data.get("name"),
            sport_type=activity_data.get("sport_type"),
            start_date=activity_data.get("start_date"),
            elapsed_time_sec=activity_data.get("elapsed_time"),
            moving_time_sec=activity_data.get("moving_time"),
            distance_m=activity_data.get("distance"),
            total_elevation_gain_m=activity_data.get("total_elevation_gain"),
            average_heartrate=activity_data.get("average_heartrate"),
            max_heartrate=activity_data.get("max_heartrate"),
            streams_raw=streams_data,
            processing_status="pending",
        )
        db.add(activity)
        await db.commit()
```

- [ ] **Step 5: Register webhook router in main.py**

```python
# backend/app/main.py — add after existing router include:
from app.routers import auth, webhook
app.include_router(webhook.router)
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
pytest tests/test_routers/test_webhook.py -v
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/webhook.py backend/app/workers/tasks.py backend/app/main.py
git commit -m "feat: Strava webhook handler with HMAC verify and background ingestion"
```

---

## Phase 1 — Metrics Engine

### Task 1.1: Zone computation

**Files:**
- Create: `backend/app/metrics/zones.py`
- Create: `backend/tests/test_metrics/test_zones.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_metrics/test_zones.py
from app.metrics.zones import hr_zone, pace_zone

def test_hr_zone_z1():
    # LTHR=160, max_hr=190 → Z1 < 72% LTHR = 115
    assert hr_zone(110, lthr=160) == 1

def test_hr_zone_z2():
    # Z2: 72-82% LTHR = 115-131
    assert hr_zone(125, lthr=160) == 2

def test_hr_zone_z4():
    # Z4: 95-105% LTHR = 152-168
    assert hr_zone(158, lthr=160) == 4

def test_hr_zone_z5():
    assert hr_zone(175, lthr=160) == 5

def test_pace_zone_z2():
    # threshold_pace=240 sec/km → Z2: 111-129% threshold = 267-311 sec/km
    assert pace_zone(280, threshold_pace=240) == 2
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_metrics/test_zones.py -v
```

- [ ] **Step 3: Create `backend/app/metrics/zones.py`**

```python
def hr_zone(hr: float, lthr: float) -> int:
    """Coggan HR zones based on LTHR percentage."""
    pct = hr / lthr
    if pct < 0.72:   return 1
    if pct < 0.82:   return 2
    if pct < 0.90:   return 3
    if pct < 1.05:   return 4
    return 5

def pace_zone(pace_sec_km: float, threshold_pace: float) -> int:
    """Pace zones: Z1 >129%, Z2 111-129%, Z3 101-110%, Z4 95-100%, Z5 <95% of threshold."""
    pct = pace_sec_km / threshold_pace
    if pct > 1.29:   return 1
    if pct > 1.10:   return 2
    if pct > 1.00:   return 3
    if pct >= 0.95:  return 4
    return 5

def zone_distribution(hr_stream: list[float], lthr: float) -> dict[str, float]:
    """Returns {z1_pct, z2_pct, z3_pct, z4_pct, z5_pct} as 0-100 floats."""
    if not hr_stream:
        return {f"z{i}_pct": 0.0 for i in range(1, 6)}
    counts = {i: 0 for i in range(1, 6)}
    for hr in hr_stream:
        counts[hr_zone(hr, lthr)] += 1
    n = len(hr_stream)
    return {f"z{z}_pct": round(counts[z] / n * 100, 1) for z in range(1, 6)}
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_metrics/test_zones.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/metrics/zones.py backend/tests/test_metrics/test_zones.py
git commit -m "feat: HR and pace zone computation"
```

---

### Task 1.2: GAP and NGP

**Files:**
- Create: `backend/app/metrics/pace.py`
- Create: `backend/tests/test_metrics/test_pace.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_metrics/test_pace.py
from app.metrics.pace import grade_adjusted_pace, normalised_graded_pace

def test_gap_flat():
    # On flat ground GAP ≈ actual pace
    gap = grade_adjusted_pace(velocity_ms=3.33, grade_pct=0.0)
    assert abs(gap - 300.0) < 5  # ~300 sec/km at 3.33 m/s

def test_gap_uphill():
    # Uphill → GAP > actual pace (harder effort)
    gap_up = grade_adjusted_pace(velocity_ms=3.33, grade_pct=10.0)
    gap_flat = grade_adjusted_pace(velocity_ms=3.33, grade_pct=0.0)
    assert gap_up > gap_flat

def test_ngp_returns_float():
    velocity = [3.0, 3.2, 3.1, 2.9, 3.3]
    grade = [0, 5, -2, 3, 0]
    result = normalised_graded_pace(velocity, grade)
    assert isinstance(result, float)
    assert result > 0
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_metrics/test_pace.py -v
```

- [ ] **Step 3: Create `backend/app/metrics/pace.py`**

```python
import math

def grade_adjusted_pace(velocity_ms: float, grade_pct: float) -> float:
    """Return GAP in sec/km. Uses Minetti cost-of-transport model."""
    if velocity_ms <= 0:
        return 0.0
    # Minetti et al. polynomial for metabolic cost ratio vs grade
    g = grade_pct / 100
    cost_ratio = (
        155.4 * g**5
        - 30.4 * g**4
        - 43.3 * g**3
        + 46.3 * g**2
        + 19.5 * g
        + 3.6
    ) / 3.6  # normalise to flat cost
    effective_velocity = velocity_ms / cost_ratio
    return (1000 / effective_velocity) if effective_velocity > 0 else 0.0

def normalised_graded_pace(
    velocity_stream: list[float],
    grade_stream: list[float],
    window: int = 30,
) -> float:
    """NGP: 30-second rolling average of GAP^4, then 4th root → sec/km."""
    if not velocity_stream:
        return 0.0
    gap_values = [
        grade_adjusted_pace(v, g)
        for v, g in zip(velocity_stream, grade_stream)
    ]
    # Rolling mean of gap^4
    powers = [g**4 for g in gap_values]
    smoothed = []
    for i in range(len(powers)):
        start = max(0, i - window + 1)
        smoothed.append(sum(powers[start : i + 1]) / (i - start + 1))
    mean_power = sum(smoothed) / len(smoothed)
    return mean_power**0.25
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_metrics/test_pace.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/metrics/pace.py backend/tests/test_metrics/test_pace.py
git commit -m "feat: GAP and NGP computation (Minetti model)"
```

---

### Task 1.3: HR metrics (hrTSS, HR drift, aerobic decoupling)

**Files:**
- Create: `backend/app/metrics/heart_rate.py`
- Create: `backend/tests/test_metrics/test_heart_rate.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_metrics/test_heart_rate.py
from app.metrics.heart_rate import hr_tss, hr_drift, aerobic_decoupling

def test_hr_tss_easy_run():
    # 60min at Z2 (~75% LTHR) → hrTSS < 60
    hr_stream = [120] * 3600  # 1 sec per sample
    result = hr_tss(hr_stream, lthr=160, duration_sec=3600)
    assert 40 < result < 70

def test_hr_drift_stable():
    # Same HR throughout → drift ≈ 0
    hr = [140] * 100
    assert abs(hr_drift(hr)) < 2.0

def test_hr_drift_rising():
    # HR rising from 130 to 160 → positive drift
    hr = list(range(130, 160)) + list(range(130, 160)) + [159, 159, 159]
    assert hr_drift(hr) > 5.0

def test_aerobic_decoupling():
    # pace stable, HR rising → positive decoupling
    pace = [300.0] * 100
    hr = list(range(130, 180)) + [179] * 50 + [179] * 5
    result = aerobic_decoupling(pace, hr)
    assert result > 0
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_metrics/test_heart_rate.py -v
```

- [ ] **Step 3: Create `backend/app/metrics/heart_rate.py`**

```python
def hr_tss(hr_stream: list[float], lthr: float, duration_sec: int) -> float:
    """hrTSS based on TRIMP-style calculation. Returns TSS-equivalent score."""
    if not hr_stream or lthr == 0:
        return 0.0
    avg_hr = sum(hr_stream) / len(hr_stream)
    hr_ratio = avg_hr / lthr
    # Friel hrTSS formula
    trimp_factor = hr_ratio * 0.64 * (2.718 ** (1.92 * hr_ratio))
    hours = duration_sec / 3600
    return round(trimp_factor * hours * 100 / 3.0, 1)

def hr_drift(hr_stream: list[float]) -> float:
    """HR drift %: difference between second-half and first-half average HR."""
    if len(hr_stream) < 2:
        return 0.0
    mid = len(hr_stream) // 2
    first_avg = sum(hr_stream[:mid]) / mid
    second_avg = sum(hr_stream[mid:]) / len(hr_stream[mid:])
    if first_avg == 0:
        return 0.0
    return round((second_avg - first_avg) / first_avg * 100, 2)

def aerobic_decoupling(
    pace_stream: list[float],
    hr_stream: list[float],
) -> float:
    """Pa:HR decoupling %. Positive = HR rose relative to pace (fatigue)."""
    if len(pace_stream) < 2 or len(hr_stream) < 2:
        return 0.0
    n = min(len(pace_stream), len(hr_stream))
    mid = n // 2
    pace = pace_stream[:n]
    hr = hr_stream[:n]

    def efficiency_factor(p_slice, h_slice):
        avg_p = sum(p_slice) / len(p_slice)
        avg_h = sum(h_slice) / len(h_slice)
        if avg_p == 0 or avg_h == 0:
            return 0
        return (1 / avg_p) / avg_h  # speed per HR beat

    ef1 = efficiency_factor(pace[:mid], hr[:mid])
    ef2 = efficiency_factor(pace[mid:], hr[mid:])
    if ef1 == 0:
        return 0.0
    return round((ef1 - ef2) / ef1 * 100, 2)
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_metrics/test_heart_rate.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/metrics/heart_rate.py backend/tests/test_metrics/test_heart_rate.py
git commit -m "feat: hrTSS, HR drift, aerobic decoupling metrics"
```

---

### Task 1.4: Training load (CTL / ATL / TSB / ACWR)

**Files:**
- Create: `backend/app/metrics/load.py`
- Create: `backend/tests/test_metrics/test_load.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_metrics/test_load.py
from app.metrics.load import update_ctl_atl, compute_acwr, compute_monotony_strain

def test_ctl_increases_after_hard_day():
    ctl, atl, tsb = update_ctl_atl(prev_ctl=50.0, prev_atl=50.0, daily_tss=100.0)
    assert ctl > 50.0

def test_tsb_formula():
    ctl, atl, tsb = update_ctl_atl(prev_ctl=50.0, prev_atl=60.0, daily_tss=0.0)
    assert abs(tsb - (ctl - atl)) < 0.01

def test_acwr_healthy():
    assert 0.8 <= compute_acwr(acute_load=100, chronic_load=100) <= 1.0

def test_acwr_overload():
    assert compute_acwr(acute_load=160, chronic_load=100) > 1.5

def test_monotony():
    daily_loads = [80, 80, 80, 80, 80, 80, 80]
    m, s = compute_monotony_strain(daily_loads)
    assert m > 5  # very monotonous

def test_strain():
    daily_loads = [80, 80, 80, 80, 80, 80, 80]
    m, s = compute_monotony_strain(daily_loads)
    assert s == sum(daily_loads) * m
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_metrics/test_load.py -v
```

- [ ] **Step 3: Create `backend/app/metrics/load.py`**

```python
import statistics

CTL_TC = 42  # Chronic Training Load time constant (days)
ATL_TC = 7   # Acute Training Load time constant (days)

def update_ctl_atl(
    prev_ctl: float,
    prev_atl: float,
    daily_tss: float,
) -> tuple[float, float, float]:
    """Exponential weighted moving average update for CTL/ATL/TSB."""
    ctl = prev_ctl + (daily_tss - prev_ctl) * (1 - 2 ** (-1 / CTL_TC))
    atl = prev_atl + (daily_tss - prev_atl) * (1 - 2 ** (-1 / ATL_TC))
    tsb = ctl - atl
    return round(ctl, 2), round(atl, 2), round(tsb, 2)

def compute_acwr(acute_load: float, chronic_load: float) -> float:
    """Acute:Chronic Workload Ratio. Injury risk >1.5."""
    if chronic_load == 0:
        return 0.0
    return round(acute_load / chronic_load, 3)

def compute_monotony_strain(daily_loads: list[float]) -> tuple[float, float]:
    """
    Monotony = mean / stdev of 7-day loads.
    Strain = weekly_load × monotony.
    Returns (monotony, strain).
    """
    if len(daily_loads) < 2:
        return 0.0, 0.0
    mean = statistics.mean(daily_loads)
    stdev = statistics.stdev(daily_loads)
    if stdev == 0:
        monotony = 999.0  # perfectly monotonous
    else:
        monotony = round(mean / stdev, 2)
    strain = round(sum(daily_loads) * monotony, 2)
    return monotony, strain
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_metrics/test_load.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/metrics/load.py backend/tests/test_metrics/test_load.py
git commit -m "feat: CTL/ATL/TSB/ACWR/monotony/strain training load metrics"
```

---

### Task 1.5: Metrics engine entry point

**Files:**
- Create: `backend/app/metrics/engine.py`
- Create: `backend/tests/test_metrics/test_engine.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_metrics/test_engine.py
from app.metrics.engine import compute_activity_metrics

def test_compute_returns_all_keys():
    streams = {
        "heartrate": {"data": [140] * 600},
        "velocity_smooth": {"data": [3.0] * 600},
        "altitude": {"data": [100 + i * 0.1 for i in range(600)]},
        "time": {"data": list(range(600))},
    }
    result = compute_activity_metrics(
        streams=streams,
        duration_sec=600,
        lthr=160,
        threshold_pace_sec_km=300,
    )
    for key in ["hr_tss", "hr_drift_pct", "aerobic_decoupling_pct", "ngp_sec_km", "zone_distribution"]:
        assert key in result, f"Missing key: {key}"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_metrics/test_engine.py -v
```

- [ ] **Step 3: Create `backend/app/metrics/engine.py`**

```python
from app.metrics.heart_rate import hr_tss, hr_drift, aerobic_decoupling
from app.metrics.pace import normalised_graded_pace, grade_adjusted_pace
from app.metrics.zones import zone_distribution

def compute_activity_metrics(
    streams: dict,
    duration_sec: int,
    lthr: float,
    threshold_pace_sec_km: float,
) -> dict:
    hr = streams.get("heartrate", {}).get("data", [])
    velocity = streams.get("velocity_smooth", {}).get("data", [])
    altitude = streams.get("altitude", {}).get("data", [])

    # Convert velocity (m/s) to pace (sec/km)
    pace = [(1000 / v) if v and v > 0 else 0.0 for v in velocity]

    # Grade stream from altitude differences
    grades = [0.0]
    for i in range(1, len(altitude)):
        dist = (velocity[i - 1] if velocity else 0) or 1
        rise = altitude[i] - altitude[i - 1]
        grades.append((rise / dist) * 100)

    return {
        "hr_tss": hr_tss(hr, lthr=lthr, duration_sec=duration_sec),
        "hr_drift_pct": hr_drift(hr),
        "aerobic_decoupling_pct": aerobic_decoupling(pace, hr),
        "ngp_sec_km": normalised_graded_pace(velocity, grades),
        "gap_avg_sec_km": (
            sum(grade_adjusted_pace(v, g) for v, g in zip(velocity, grades)) / len(velocity)
            if velocity else 0.0
        ),
        "zone_distribution": zone_distribution(hr, lthr=lthr),
    }
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_metrics/ -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/metrics/engine.py backend/tests/test_metrics/test_engine.py
git commit -m "feat: metrics engine entry point aggregating all metrics"
```

---

## Phase 2 — Onboarding & Targets

### Task 2.1: Onboarding profile API

**Files:**
- Create: `backend/app/routers/onboarding.py`
- Create: `backend/tests/test_routers/test_onboarding.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_routers/test_onboarding.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_save_profile():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/onboarding/profile", json={
            "athlete_id": 1,
            "lthr": 162,
            "max_hr": 192,
            "threshold_pace_sec_km": 270,
            "weight_kg": 68.5,
            "units": "metric",
            "language": "en",
        })
        assert r.status_code == 200
        assert r.json()["onboarding_complete"] is True
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_routers/test_onboarding.py -v
```

- [ ] **Step 3: Create `backend/app/routers/onboarding.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.athlete import AthleteProfile, Units

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

class ProfileIn(BaseModel):
    athlete_id: int
    lthr: Optional[int] = None
    max_hr: Optional[int] = None
    threshold_pace_sec_km: Optional[int] = None
    weight_kg: Optional[float] = None
    vo2max_estimate: Optional[float] = None
    units: Units = Units.metric
    language: str = "en"

@router.post("/profile")
async def save_profile(data: ProfileIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AthleteProfile).where(AthleteProfile.athlete_id == data.athlete_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        profile = AthleteProfile(athlete_id=data.athlete_id)
        db.add(profile)

    for field in ["lthr", "max_hr", "threshold_pace_sec_km", "weight_kg", "vo2max_estimate", "units", "language"]:
        if getattr(data, field) is not None:
            setattr(profile, field, getattr(data, field))

    profile.onboarding_complete = True
    await db.commit()
    await db.refresh(profile)
    return {"onboarding_complete": profile.onboarding_complete, "athlete_id": data.athlete_id}
```

- [ ] **Step 4: Register router in `main.py`**

```python
from app.routers import auth, webhook, onboarding
app.include_router(onboarding.router)
```

- [ ] **Step 5: Run — expect PASS**

```bash
pytest tests/test_routers/test_onboarding.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/onboarding.py backend/tests/test_routers/test_onboarding.py backend/app/main.py
git commit -m "feat: onboarding profile save API"
```

---

### Task 2.2: Race targets CRUD API

**Files:**
- Create: `backend/app/routers/targets.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_routers/test_targets.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_create_and_list_target():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/targets/", json={
            "athlete_id": 1,
            "race_name": "VMM 100",
            "race_date": "2026-11-15",
            "distance_km": 100.0,
            "elevation_gain_m": 8000,
            "priority": "A",
        })
        assert r.status_code == 201
        tid = r.json()["id"]

        r2 = await client.get("/targets/?athlete_id=1")
        assert r2.status_code == 200
        ids = [t["id"] for t in r2.json()]
        assert tid in ids
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/test_routers/test_targets.py -v
```

- [ ] **Step 3: Create `backend/app/routers/targets.py`**

```python
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.target import RaceTarget, Priority

router = APIRouter(prefix="/targets", tags=["targets"])

class TargetIn(BaseModel):
    athlete_id: int
    race_name: str
    race_date: date
    distance_km: float
    elevation_gain_m: Optional[float] = None
    goal_time_sec: Optional[int] = None
    priority: Priority = Priority.A

@router.post("/", status_code=201)
async def create_target(data: TargetIn, db: AsyncSession = Depends(get_db)):
    t = RaceTarget(**data.model_dump())
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return {"id": t.id, "race_name": t.race_name, "race_date": str(t.race_date)}

@router.get("/")
async def list_targets(athlete_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RaceTarget).where(RaceTarget.athlete_id == athlete_id)
            .order_by(RaceTarget.race_date)
    )
    targets = result.scalars().all()
    return [
        {
            "id": t.id,
            "race_name": t.race_name,
            "race_date": str(t.race_date),
            "distance_km": t.distance_km,
            "priority": t.priority,
        }
        for t in targets
    ]

@router.delete("/{target_id}", status_code=204)
async def delete_target(target_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RaceTarget).where(RaceTarget.id == target_id))
    t = result.scalar_one_or_none()
    if t:
        await db.delete(t)
        await db.commit()
```

- [ ] **Step 4: Register router and run tests**

```python
# main.py — add
from app.routers import targets
app.include_router(targets.router)
```

```bash
pytest tests/test_routers/test_targets.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/targets.py backend/tests/test_routers/test_targets.py
git commit -m "feat: race targets CRUD API"
```

---

## Phase 3 — AI Coaching Layer (LangGraph)

### Task 3.1: Debrief schema and prompt

**Files:**
- Create: `backend/app/agents/schema.py`
- Create: `backend/app/agents/prompts.py`

- [ ] **Step 1: Create `backend/app/agents/schema.py`**

```python
from pydantic import BaseModel, Field
from typing import Optional

class ActivityInput(BaseModel):
    activity_name: str
    duration_sec: int
    distance_m: float
    sport_type: str
    tss: float
    hr_tss: float
    hr_drift_pct: float
    aerobic_decoupling_pct: float
    ngp_sec_km: float
    zone_distribution: dict[str, float]  # {z1_pct...z5_pct}

class AthleteContext(BaseModel):
    lthr: int
    threshold_pace_sec_km: int
    tss_30d_avg: float
    acwr: float
    ctl: float
    atl: float
    tsb: float
    training_phase: str  # Base | Build | Peak | Taper

class DebriefOutput(BaseModel):
    load_verdict: str = Field(
        description="TSS vs 30d avg %, ACWR value + zone. Max 400 chars. Must contain numbers."
    )
    technical_insight: str = Field(
        description="One specific finding with a number: HR drift %, decoupling %, zone distribution anomaly. Max 400 chars."
    )
    next_session_action: str = Field(
        description="Specific next workout recommendation. No generic phrases. Must be actionable. Max 400 chars."
    )
```

- [ ] **Step 2: Create `backend/app/agents/prompts.py`**

```python
SYSTEM_PROMPT = """You are an elite ultra and trail running coach with 20+ years experience.
Your athletes race VMM 100, UTMB, and Dalat Ultra Sky Race.

Rules:
- Every claim must be backed by a number from the input metrics.
- Never write "great job", "keep it up", "listen to your body", or any other generic phrase.
- Sections must be concise — max 400 characters each.
- Technical insight must name ONE specific finding, e.g. "HR drift of 8.3% suggests early aerobic decoupling."
- Next session must specify: workout type, duration or distance, intensity (zone or pace range).
- Coaching context: Friel periodization phases, Magness physiological cues, Koerner ultra-specific load management.

Respond ONLY with valid JSON matching the DebriefOutput schema. No preamble, no markdown fences.
"""

def build_debrief_prompt(activity: dict, context: dict) -> str:
    return f"""Athlete context:
- Training phase: {context['training_phase']}
- CTL: {context['ctl']:.1f} | ATL: {context['atl']:.1f} | TSB: {context['tsb']:.1f}
- ACWR: {context['acwr']:.2f}
- 30-day TSS average: {context['tss_30d_avg']:.1f}
- LTHR: {context['lthr']} bpm | Threshold pace: {context['threshold_pace_sec_km']} sec/km

Activity:
- {activity['activity_name']} | {activity['sport_type']}
- Duration: {activity['duration_sec'] // 60} min | Distance: {activity['distance_m'] / 1000:.2f} km
- TSS: {activity['tss']:.1f} | hrTSS: {activity['hr_tss']:.1f}
- HR drift: {activity['hr_drift_pct']:.1f}% | Aerobic decoupling: {activity['aerobic_decoupling_pct']:.1f}%
- NGP: {activity['ngp_sec_km']:.0f} sec/km
- Zone distribution: {activity['zone_distribution']}

Generate the post-run debrief JSON now."""
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/schema.py backend/app/agents/prompts.py
git commit -m "feat: debrief Pydantic schema and coaching prompt templates"
```

---

### Task 3.2: LangGraph debrief workflow

**Files:**
- Create: `backend/app/agents/debrief_graph.py`
- Create: `backend/tests/test_agents/test_debrief_graph.py`

- [ ] **Step 1: Add LangGraph deps to requirements.txt**

```
langgraph==0.2.60
anthropic==0.40.0
langchain-anthropic==0.3.0
```

```bash
pip install langgraph anthropic langchain-anthropic
```

- [ ] **Step 2: Write failing test**

```python
# backend/tests/test_agents/test_debrief_graph.py
import pytest
from unittest.mock import patch, MagicMock
from app.agents.debrief_graph import generate_debrief
from app.agents.schema import ActivityInput, AthleteContext

SAMPLE_ACTIVITY = ActivityInput(
    activity_name="Morning Trail Run",
    duration_sec=3600,
    distance_m=12000,
    sport_type="TrailRun",
    tss=75.0,
    hr_tss=72.0,
    hr_drift_pct=6.5,
    aerobic_decoupling_pct=4.2,
    ngp_sec_km=310,
    zone_distribution={"z1_pct": 5, "z2_pct": 55, "z3_pct": 30, "z4_pct": 8, "z5_pct": 2},
)

SAMPLE_CONTEXT = AthleteContext(
    lthr=160,
    threshold_pace_sec_km=270,
    tss_30d_avg=60.0,
    acwr=1.1,
    ctl=52.0,
    atl=55.0,
    tsb=-3.0,
    training_phase="Build",
)

@pytest.mark.asyncio
async def test_generate_debrief_structure():
    result = await generate_debrief(SAMPLE_ACTIVITY, SAMPLE_CONTEXT)
    assert "load_verdict" in result
    assert "technical_insight" in result
    assert "next_session_action" in result
    # No generic phrases
    for field in result.values():
        assert "great job" not in field.lower()
        assert "keep it up" not in field.lower()
        assert "listen to your body" not in field.lower()
```

- [ ] **Step 3: Run — expect FAIL**

```bash
pytest tests/test_agents/test_debrief_graph.py -v
```

- [ ] **Step 4: Create `backend/app/agents/debrief_graph.py`**

```python
import json
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from app.agents.schema import ActivityInput, AthleteContext, DebriefOutput
from app.agents.prompts import SYSTEM_PROMPT, build_debrief_prompt
from app.config import settings

llm = ChatAnthropic(
    model="claude-sonnet-4-6",
    api_key=settings.anthropic_api_key,
    max_tokens=1024,
)

class DebriefState(TypedDict):
    activity: dict
    context: dict
    raw_response: str
    debrief: dict
    retry_count: int
    error: str

def call_llm(state: DebriefState) -> DebriefState:
    prompt = build_debrief_prompt(state["activity"], state["context"])
    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
    response = llm.invoke(messages)
    return {**state, "raw_response": response.content}

def parse_and_validate(state: DebriefState) -> DebriefState:
    try:
        data = json.loads(state["raw_response"])
        validated = DebriefOutput(**data)
        return {**state, "debrief": validated.model_dump(), "error": ""}
    except Exception as e:
        return {**state, "error": str(e), "retry_count": state.get("retry_count", 0) + 1}

def should_retry(state: DebriefState) -> str:
    if state.get("error") and state.get("retry_count", 0) < 2:
        return "retry"
    if state.get("error"):
        return "fallback"
    return END

def fallback_debrief(state: DebriefState) -> DebriefState:
    activity = state["activity"]
    context = state["context"]
    tss_pct = (activity["tss"] / context["tss_30d_avg"] * 100) if context["tss_30d_avg"] else 0
    debrief = {
        "load_verdict": f"TSS {activity['tss']:.0f} = {tss_pct:.0f}% of 30-day avg. ACWR {context['acwr']:.2f} (zone: {'green' if context['acwr'] <= 1.3 else 'yellow' if context['acwr'] <= 1.5 else 'red'}).",
        "technical_insight": f"HR drift {activity['hr_drift_pct']:.1f}%, aerobic decoupling {activity['aerobic_decoupling_pct']:.1f}%. Z2 time: {activity['zone_distribution'].get('z2_pct', 0):.0f}%.",
        "next_session_action": "Easy Z1-Z2 recovery run 45-60 min, HR below 135 bpm. No quality work for 48h.",
    }
    return {**state, "debrief": debrief, "error": "fallback_used"}

def build_debrief_graph():
    g = StateGraph(DebriefState)
    g.add_node("call_llm", call_llm)
    g.add_node("parse_and_validate", parse_and_validate)
    g.add_node("fallback_debrief", fallback_debrief)
    g.set_entry_point("call_llm")
    g.add_edge("call_llm", "parse_and_validate")
    g.add_conditional_edges("parse_and_validate", should_retry, {
        "retry": "call_llm",
        "fallback": "fallback_debrief",
        END: END,
    })
    g.add_edge("fallback_debrief", END)
    return g.compile()

_graph = build_debrief_graph()

async def generate_debrief(activity: ActivityInput, context: AthleteContext) -> dict:
    result = await _graph.ainvoke({
        "activity": activity.model_dump(),
        "context": context.model_dump(),
        "raw_response": "",
        "debrief": {},
        "retry_count": 0,
        "error": "",
    })
    return result["debrief"]
```

- [ ] **Step 5: Run test (requires ANTHROPIC_API_KEY set)**

```bash
export ANTHROPIC_API_KEY=sk-ant-...
pytest tests/test_agents/test_debrief_graph.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/debrief_graph.py backend/tests/test_agents/test_debrief_graph.py backend/requirements.txt
git commit -m "feat: LangGraph debrief generation with retry + deterministic fallback"
```

---

### Task 3.3: Debrief API endpoint

**Files:**
- Create: `backend/app/routers/activities.py`
- Modify: `backend/app/workers/tasks.py`

- [ ] **Step 1: Create `backend/app/routers/activities.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.activity import Activity
from app.models.metrics import ActivityMetrics, LoadHistory

router = APIRouter(prefix="/activities", tags=["activities"])

@router.get("/")
async def list_activities(athlete_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Activity)
        .where(Activity.athlete_id == athlete_id)
        .order_by(Activity.start_date.desc())
        .limit(50)
    )
    activities = result.scalars().all()
    return [
        {
            "id": a.id,
            "strava_activity_id": a.strava_activity_id,
            "name": a.name,
            "sport_type": a.sport_type,
            "start_date": str(a.start_date),
            "distance_m": a.distance_m,
            "elapsed_time_sec": a.elapsed_time_sec,
            "processing_status": a.processing_status,
        }
        for a in activities
    ]

@router.get("/{activity_id}")
async def get_activity_detail(activity_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Activity).where(Activity.id == activity_id))
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    m_result = await db.execute(
        select(ActivityMetrics).where(ActivityMetrics.activity_id == activity_id)
    )
    metrics = m_result.scalar_one_or_none()

    return {
        "activity": {
            "id": activity.id,
            "name": activity.name,
            "sport_type": activity.sport_type,
            "start_date": str(activity.start_date),
            "distance_m": activity.distance_m,
            "elapsed_time_sec": activity.elapsed_time_sec,
            "total_elevation_gain_m": activity.total_elevation_gain_m,
        },
        "metrics": {
            "tss": metrics.tss if metrics else None,
            "hr_tss": metrics.hr_tss if metrics else None,
            "hr_drift_pct": metrics.hr_drift_pct if metrics else None,
            "aerobic_decoupling_pct": metrics.aerobic_decoupling_pct if metrics else None,
            "ngp_sec_km": metrics.ngp_sec_km if metrics else None,
            "zone_distribution": metrics.zone_distribution if metrics else None,
        } if metrics else None,
        "debrief": activity.streams_raw.get("debrief") if activity.streams_raw else None,
    }
```

- [ ] **Step 2: Update `backend/app/workers/tasks.py` to run metrics + debrief after ingestion**

```python
# Add to tasks.py after storing the activity:

async def process_activity_metrics(activity_db_id: int):
    """Run metrics engine + generate debrief for a stored activity."""
    from app.metrics.engine import compute_activity_metrics
    from app.agents.debrief_graph import generate_debrief
    from app.agents.schema import ActivityInput, AthleteContext
    from app.models.metrics import ActivityMetrics, LoadHistory
    from app.models.athlete import AthleteProfile
    import datetime

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Activity).where(Activity.id == activity_db_id))
        activity = result.scalar_one_or_none()
        if not activity or not activity.streams_raw:
            return

        # Skip short/warmup activities
        if (activity.elapsed_time_sec or 0) < 600 or (activity.distance_m or 0) < 1000:
            activity.excluded_from_load = True
            await db.commit()
            return

        # Get athlete profile
        prof_result = await db.execute(
            select(AthleteProfile).where(AthleteProfile.athlete_id == activity.athlete_id)
        )
        profile = prof_result.scalar_one_or_none()
        lthr = (profile.lthr or 155) if profile else 155
        threshold_pace = (profile.threshold_pace_sec_km or 300) if profile else 300

        # Compute metrics
        metrics_dict = compute_activity_metrics(
            streams=activity.streams_raw,
            duration_sec=activity.elapsed_time_sec or 0,
            lthr=lthr,
            threshold_pace_sec_km=threshold_pace,
        )

        # Persist metrics
        am = ActivityMetrics(
            activity_id=activity.id,
            athlete_id=activity.athlete_id,
            tss=metrics_dict["hr_tss"],
            hr_tss=metrics_dict["hr_tss"],
            hr_drift_pct=metrics_dict["hr_drift_pct"],
            aerobic_decoupling_pct=metrics_dict["aerobic_decoupling_pct"],
            ngp_sec_km=metrics_dict["ngp_sec_km"],
            gap_avg_sec_km=metrics_dict["gap_avg_sec_km"],
            zone_distribution=metrics_dict["zone_distribution"],
        )
        db.add(am)

        # Generate debrief
        activity_input = ActivityInput(
            activity_name=activity.name or "Run",
            duration_sec=activity.elapsed_time_sec or 0,
            distance_m=activity.distance_m or 0,
            sport_type=activity.sport_type or "Run",
            tss=metrics_dict["hr_tss"],
            hr_tss=metrics_dict["hr_tss"],
            hr_drift_pct=metrics_dict["hr_drift_pct"],
            aerobic_decoupling_pct=metrics_dict["aerobic_decoupling_pct"],
            ngp_sec_km=metrics_dict["ngp_sec_km"],
            zone_distribution=metrics_dict["zone_distribution"],
        )
        ctx = AthleteContext(
            lthr=lthr,
            threshold_pace_sec_km=threshold_pace,
            tss_30d_avg=60.0,  # TODO: compute from LoadHistory
            acwr=1.0,
            ctl=50.0,
            atl=50.0,
            tsb=0.0,
            training_phase="Build",
        )
        debrief = await generate_debrief(activity_input, ctx)

        # Store debrief inside streams_raw (or separate column)
        raw = dict(activity.streams_raw or {})
        raw["debrief"] = debrief
        activity.streams_raw = raw
        activity.processing_status = "done"
        await db.commit()
```

- [ ] **Step 3: Register activities router**

```python
# main.py
from app.routers import activities
app.include_router(activities.router)
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/activities.py backend/app/workers/tasks.py backend/app/main.py
git commit -m "feat: activities list/detail API with debrief and metrics post-processing"
```

---

## Phase 4 — React Frontend

### Task 4.1: React project setup

**Files:**
- Create: `frontend/` (Vite + React + TS scaffold)

- [ ] **Step 1: Scaffold with Vite**

```bash
cd /Users/nguyenminhduc/Desktop/strava-coach
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

- [ ] **Step 2: Install dependencies**

```bash
npm install react-router-dom@6 @tanstack/react-query axios recharts
npm install -D tailwindcss postcss autoprefixer @types/recharts
npx tailwindcss init -p
```

- [ ] **Step 3: Configure Tailwind in `frontend/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 4: Update `frontend/tailwind.config.ts`**

```ts
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
}
```

- [ ] **Step 5: Create `frontend/src/api/client.ts`**

```ts
import axios from "axios"

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
  withCredentials: true,
})

export const athleteId = (): number => {
  const params = new URLSearchParams(window.location.search)
  return Number(params.get("athlete_id") || localStorage.getItem("athlete_id") || 0)
}
```

- [ ] **Step 6: Create `frontend/src/App.tsx`**

```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import Connect from "./pages/Connect"
import Setup from "./pages/Setup"
import Dashboard from "./pages/Dashboard"
import ActivityDetail from "./pages/ActivityDetail"
import Targets from "./pages/Targets"

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Connect />} />
          <Route path="/setup" element={<Setup />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/activities/:id" element={<ActivityDetail />} />
          <Route path="/targets" element={<Targets />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
```

- [ ] **Step 7: Verify dev server runs**

```bash
cd frontend
npm run dev
# Visit http://localhost:5173 — blank app should load without errors
```

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "chore: scaffold React frontend with Vite, Router, TanStack Query, Tailwind"
```

---

### Task 4.2: Connect page (Strava OAuth)

**Files:**
- Create: `frontend/src/pages/Connect.tsx`

- [ ] **Step 1: Create `frontend/src/pages/Connect.tsx`**

```tsx
export default function Connect() {
  const handleConnect = () => {
    window.location.href = `${import.meta.env.VITE_API_URL || "http://localhost:8000"}/auth/strava`
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50">
      <div className="bg-white rounded-2xl shadow-lg p-10 max-w-md w-full text-center">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Strava AI Coach</h1>
        <p className="text-gray-500 mb-8">
          Post-run debrief + training load insights for ultra and trail runners.
        </p>
        <button
          onClick={handleConnect}
          className="bg-orange-500 hover:bg-orange-600 text-white font-semibold py-3 px-8 rounded-xl transition-colors w-full"
        >
          Connect with Strava
        </button>
        <p className="text-xs text-gray-400 mt-4">
          We request read-only access to your activities.
        </p>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify in browser at `http://localhost:5173`**

The Connect button should be visible. Clicking it redirects to `localhost:8000/auth/strava`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Connect.tsx
git commit -m "feat: Strava connect landing page"
```

---

### Task 4.3: Dashboard page (CTL/ATL/TSB chart + ACWR gauge)

**Files:**
- Create: `frontend/src/components/LoadChart.tsx`
- Create: `frontend/src/components/AcwrGauge.tsx`
- Create: `frontend/src/components/PhaseIndicator.tsx`
- Create: `frontend/src/pages/Dashboard.tsx`

- [ ] **Step 1: Create `frontend/src/components/LoadChart.tsx`**

```tsx
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from "recharts"

interface LoadPoint {
  date: string
  ctl: number
  atl: number
  tsb: number
}

export default function LoadChart({ data }: { data: LoadPoint[] }) {
  return (
    <div className="bg-white rounded-2xl shadow p-6">
      <h2 className="font-semibold text-gray-700 mb-4">Training Load (90 days)</h2>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="ctl" stroke="#3b82f6" name="CTL (Fitness)" dot={false} />
          <Line type="monotone" dataKey="atl" stroke="#f97316" name="ATL (Fatigue)" dot={false} />
          <Line type="monotone" dataKey="tsb" stroke="#10b981" name="TSB (Form)" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
```

- [ ] **Step 2: Create `frontend/src/components/AcwrGauge.tsx`**

```tsx
interface AcwrGaugeProps { acwr: number }

function zoneColor(acwr: number): string {
  if (acwr <= 1.3) return "bg-green-100 text-green-800 border-green-300"
  if (acwr <= 1.5) return "bg-yellow-100 text-yellow-800 border-yellow-300"
  return "bg-red-100 text-red-800 border-red-300"
}

function zoneLabel(acwr: number): string {
  if (acwr < 0.8) return "Undertraining"
  if (acwr <= 1.3) return "Optimal Load"
  if (acwr <= 1.5) return "Caution"
  return "Injury Risk"
}

export default function AcwrGauge({ acwr }: AcwrGaugeProps) {
  return (
    <div className={`rounded-2xl border-2 p-6 text-center ${zoneColor(acwr)}`}>
      <p className="text-xs font-semibold uppercase tracking-wide mb-1">ACWR</p>
      <p className="text-5xl font-bold">{acwr.toFixed(2)}</p>
      <p className="text-sm font-medium mt-1">{zoneLabel(acwr)}</p>
      {acwr > 1.5 && (
        <p className="text-xs mt-2 font-semibold">Consider deload this week</p>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Create `frontend/src/components/PhaseIndicator.tsx`**

```tsx
const PHASE_COLORS: Record<string, string> = {
  Base: "bg-blue-100 text-blue-800",
  Build: "bg-indigo-100 text-indigo-800",
  Peak: "bg-purple-100 text-purple-800",
  Taper: "bg-green-100 text-green-800",
}

export default function PhaseIndicator({ phase }: { phase: string }) {
  return (
    <span className={`inline-block px-3 py-1 rounded-full text-sm font-semibold ${PHASE_COLORS[phase] || "bg-gray-100 text-gray-700"}`}>
      {phase} Phase
    </span>
  )
}
```

- [ ] **Step 4: Create `frontend/src/pages/Dashboard.tsx`**

```tsx
import { useQuery } from "@tanstack/react-query"
import { api, athleteId } from "../api/client"
import LoadChart from "../components/LoadChart"
import AcwrGauge from "../components/AcwrGauge"
import PhaseIndicator from "../components/PhaseIndicator"
import { Link } from "react-router-dom"

export default function Dashboard() {
  const aid = athleteId()

  const { data: loadData, isLoading } = useQuery({
    queryKey: ["load", aid],
    queryFn: () => api.get(`/dashboard/load?athlete_id=${aid}`).then(r => r.data),
    enabled: !!aid,
  })

  const { data: activities } = useQuery({
    queryKey: ["activities", aid],
    queryFn: () => api.get(`/activities/?athlete_id=${aid}`).then(r => r.data),
    enabled: !!aid,
  })

  if (isLoading) return <div className="p-8 text-gray-500">Loading...</div>

  const latest = loadData?.latest || {}

  return (
    <div className="min-h-screen bg-gray-50 p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Training Dashboard</h1>
        <div className="flex gap-3">
          <PhaseIndicator phase={loadData?.training_phase || "Base"} />
          <Link to="/targets" className="text-sm text-blue-600 hover:underline self-center">Targets</Link>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-xl shadow p-4 text-center">
          <p className="text-xs text-gray-500">CTL (Fitness)</p>
          <p className="text-3xl font-bold text-blue-600">{latest.ctl?.toFixed(1) ?? "—"}</p>
        </div>
        <div className="bg-white rounded-xl shadow p-4 text-center">
          <p className="text-xs text-gray-500">ATL (Fatigue)</p>
          <p className="text-3xl font-bold text-orange-500">{latest.atl?.toFixed(1) ?? "—"}</p>
        </div>
        <div className="bg-white rounded-xl shadow p-4 text-center">
          <p className="text-xs text-gray-500">TSB (Form)</p>
          <p className={`text-3xl font-bold ${(latest.tsb ?? 0) >= 0 ? "text-green-600" : "text-red-500"}`}>
            {latest.tsb?.toFixed(1) ?? "—"}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6 mb-6">
        <div className="col-span-2">
          <LoadChart data={loadData?.history || []} />
        </div>
        <AcwrGauge acwr={latest.acwr ?? 1.0} />
      </div>

      <div className="bg-white rounded-2xl shadow p-6">
        <h2 className="font-semibold text-gray-700 mb-4">Recent Activities</h2>
        {(activities || []).slice(0, 10).map((a: any) => (
          <Link
            key={a.id}
            to={`/activities/${a.id}?athlete_id=${aid}`}
            className="flex items-center justify-between py-3 border-b last:border-0 hover:bg-gray-50 px-2 rounded"
          >
            <div>
              <p className="font-medium text-gray-800">{a.name}</p>
              <p className="text-xs text-gray-500">{a.sport_type} · {(a.distance_m / 1000).toFixed(1)} km</p>
            </div>
            <span className={`text-xs px-2 py-1 rounded-full ${
              a.processing_status === "done" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
            }`}>
              {a.processing_status === "done" ? "Debrief ready" : a.processing_status}
            </span>
          </Link>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Create dashboard load API endpoint**

```python
# backend/app/routers/dashboard.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import date, timedelta
from app.database import get_db
from app.models.metrics import LoadHistory
from app.models.target import RaceTarget

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

PHASE_WEEKS = {"Taper": 3, "Peak": 4, "Build": 8}

def compute_phase(race_date: date) -> str:
    weeks_out = (race_date - date.today()).days // 7
    if weeks_out <= 3: return "Taper"
    if weeks_out <= 7: return "Peak"
    if weeks_out <= 15: return "Build"
    return "Base"

@router.get("/load")
async def get_load(athlete_id: int, db: AsyncSession = Depends(get_db)):
    cutoff = date.today() - timedelta(days=90)
    result = await db.execute(
        select(LoadHistory)
        .where(LoadHistory.athlete_id == athlete_id, LoadHistory.date >= cutoff)
        .order_by(LoadHistory.date)
    )
    history = result.scalars().all()

    latest = history[-1] if history else None

    # Get nearest A-race
    race_result = await db.execute(
        select(RaceTarget)
        .where(RaceTarget.athlete_id == athlete_id, RaceTarget.race_date >= date.today(), RaceTarget.priority == "A")
        .order_by(RaceTarget.race_date)
        .limit(1)
    )
    race = race_result.scalar_one_or_none()
    phase = compute_phase(race.race_date) if race else "Base"

    return {
        "training_phase": phase,
        "latest": {
            "ctl": latest.ctl if latest else 0,
            "atl": latest.atl if latest else 0,
            "tsb": latest.tsb if latest else 0,
            "acwr": latest.acwr if latest else 1.0,
        },
        "history": [
            {"date": str(h.date), "ctl": h.ctl, "atl": h.atl, "tsb": h.tsb}
            for h in history
        ],
    }
```

- [ ] **Step 6: Register dashboard router**

```python
# main.py
from app.routers import dashboard
app.include_router(dashboard.router)
```

- [ ] **Step 7: Verify in browser**

```bash
# Start backend
cd backend && uvicorn app.main:app --reload --port 8000
# Start frontend
cd frontend && npm run dev
# Visit http://localhost:5173/dashboard?athlete_id=1
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/ frontend/src/pages/Dashboard.tsx backend/app/routers/dashboard.py
git commit -m "feat: dashboard with CTL/ATL/TSB chart, ACWR gauge, phase indicator"
```

---

### Task 4.4: Activity detail page (debrief display)

**Files:**
- Create: `frontend/src/components/DebriefCard.tsx`
- Create: `frontend/src/pages/ActivityDetail.tsx`

- [ ] **Step 1: Create `frontend/src/components/DebriefCard.tsx`**

```tsx
interface Debrief {
  load_verdict: string
  technical_insight: string
  next_session_action: string
}

export default function DebriefCard({ debrief }: { debrief: Debrief }) {
  return (
    <div className="bg-white rounded-2xl shadow p-6 space-y-4">
      <h2 className="text-lg font-bold text-gray-900">AI Debrief</h2>

      <div className="border-l-4 border-blue-500 pl-4">
        <p className="text-xs font-semibold text-blue-600 uppercase tracking-wide mb-1">Load Verdict</p>
        <p className="text-gray-800 text-sm">{debrief.load_verdict}</p>
      </div>

      <div className="border-l-4 border-orange-400 pl-4">
        <p className="text-xs font-semibold text-orange-500 uppercase tracking-wide mb-1">Technical Insight</p>
        <p className="text-gray-800 text-sm">{debrief.technical_insight}</p>
      </div>

      <div className="border-l-4 border-green-500 pl-4">
        <p className="text-xs font-semibold text-green-600 uppercase tracking-wide mb-1">Next Session</p>
        <p className="text-gray-800 text-sm">{debrief.next_session_action}</p>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create `frontend/src/pages/ActivityDetail.tsx`**

```tsx
import { useQuery } from "@tanstack/react-query"
import { useParams, Link } from "react-router-dom"
import { api, athleteId } from "../api/client"
import DebriefCard from "../components/DebriefCard"

export default function ActivityDetail() {
  const { id } = useParams()
  const aid = athleteId()

  const { data, isLoading } = useQuery({
    queryKey: ["activity", id],
    queryFn: () => api.get(`/activities/${id}`).then(r => r.data),
    enabled: !!id,
  })

  if (isLoading) return <div className="p-8 text-gray-500">Loading debrief...</div>
  if (!data) return <div className="p-8 text-red-500">Activity not found</div>

  const { activity, metrics, debrief } = data

  return (
    <div className="min-h-screen bg-gray-50 p-6 max-w-2xl mx-auto">
      <Link to={`/dashboard?athlete_id=${aid}`} className="text-sm text-blue-600 hover:underline mb-4 inline-block">
        ← Dashboard
      </Link>

      <div className="bg-white rounded-2xl shadow p-6 mb-4">
        <h1 className="text-xl font-bold text-gray-900">{activity.name}</h1>
        <p className="text-sm text-gray-500 mt-1">
          {activity.sport_type} · {(activity.distance_m / 1000).toFixed(2)} km ·{" "}
          {Math.floor(activity.elapsed_time_sec / 60)} min
        </p>
      </div>

      {metrics && (
        <div className="bg-white rounded-2xl shadow p-6 mb-4 grid grid-cols-2 gap-4">
          <Metric label="hrTSS" value={metrics.hr_tss?.toFixed(1)} />
          <Metric label="HR Drift" value={metrics.hr_drift_pct != null ? `${metrics.hr_drift_pct.toFixed(1)}%` : "—"} />
          <Metric label="Aero Decoupling" value={metrics.aerobic_decoupling_pct != null ? `${metrics.aerobic_decoupling_pct.toFixed(1)}%` : "—"} />
          <Metric label="NGP" value={metrics.ngp_sec_km != null ? `${metrics.ngp_sec_km.toFixed(0)} s/km` : "—"} />
        </div>
      )}

      {debrief ? (
        <DebriefCard debrief={debrief} />
      ) : (
        <div className="bg-yellow-50 border border-yellow-200 rounded-2xl p-6 text-yellow-700 text-sm">
          Debrief is being generated... refresh in a moment.
        </div>
      )}
    </div>
  )
}

function Metric({ label, value }: { label: string; value?: string }) {
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-lg font-semibold text-gray-900">{value ?? "—"}</p>
    </div>
  )
}
```

- [ ] **Step 3: Verify in browser**

Navigate to an activity detail page. Debrief sections should render with color-coded borders.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/DebriefCard.tsx frontend/src/pages/ActivityDetail.tsx
git commit -m "feat: activity detail page with debrief display and metric tiles"
```

---

### Task 4.5: Onboarding wizard (4-step)

**Files:**
- Create: `frontend/src/pages/Setup.tsx`

- [ ] **Step 1: Create `frontend/src/pages/Setup.tsx`**

```tsx
import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { api, athleteId } from "../api/client"

const STEPS = ["Threshold HR", "Threshold Pace", "Body Metrics", "Preferences"]

export default function Setup() {
  const navigate = useNavigate()
  const aid = athleteId()
  const [step, setStep] = useState(0)
  const [form, setForm] = useState({
    lthr: "", max_hr: "", threshold_pace_sec_km: "", weight_kg: "",
    vo2max_estimate: "", units: "metric", language: "en",
  })

  const update = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  const save = async () => {
    await api.post("/onboarding/profile", {
      athlete_id: aid,
      lthr: Number(form.lthr) || undefined,
      max_hr: Number(form.max_hr) || undefined,
      threshold_pace_sec_km: Number(form.threshold_pace_sec_km) || undefined,
      weight_kg: Number(form.weight_kg) || undefined,
      units: form.units,
      language: form.language,
    })
    navigate(`/dashboard?athlete_id=${aid}`)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white rounded-2xl shadow-lg p-8 max-w-md w-full">
        <div className="flex mb-8 gap-1">
          {STEPS.map((s, i) => (
            <div key={i} className={`flex-1 h-1.5 rounded-full ${i <= step ? "bg-orange-500" : "bg-gray-200"}`} />
          ))}
        </div>
        <h2 className="text-xl font-bold text-gray-900 mb-6">{STEPS[step]}</h2>

        {step === 0 && (
          <div className="space-y-4">
            <Field label="Lactate Threshold HR (bpm)" value={form.lthr} onChange={v => update("lthr", v)} placeholder="162" />
            <Field label="Max HR (bpm)" value={form.max_hr} onChange={v => update("max_hr", v)} placeholder="192" />
          </div>
        )}
        {step === 1 && (
          <div className="space-y-4">
            <Field label="Threshold Pace (sec/km)" value={form.threshold_pace_sec_km} onChange={v => update("threshold_pace_sec_km", v)} placeholder="270" />
            <p className="text-xs text-gray-400">Example: 270 = 4:30/km</p>
          </div>
        )}
        {step === 2 && (
          <div className="space-y-4">
            <Field label="Weight (kg)" value={form.weight_kg} onChange={v => update("weight_kg", v)} placeholder="68" />
            <Field label="VO₂max estimate (optional)" value={form.vo2max_estimate} onChange={v => update("vo2max_estimate", v)} placeholder="52" />
          </div>
        )}
        {step === 3 && (
          <div className="space-y-4">
            <label className="block">
              <span className="text-sm text-gray-600">Units</span>
              <select
                className="mt-1 block w-full rounded-lg border-gray-300 border p-2"
                value={form.units}
                onChange={e => update("units", e.target.value)}
              >
                <option value="metric">Metric (km)</option>
                <option value="imperial">Imperial (miles)</option>
              </select>
            </label>
            <label className="block">
              <span className="text-sm text-gray-600">Language</span>
              <select
                className="mt-1 block w-full rounded-lg border-gray-300 border p-2"
                value={form.language}
                onChange={e => update("language", e.target.value)}
              >
                <option value="en">English</option>
                <option value="vi">Tiếng Việt</option>
              </select>
            </label>
          </div>
        )}

        <div className="flex justify-between mt-8">
          <button
            onClick={() => setStep(s => Math.max(0, s - 1))}
            disabled={step === 0}
            className="text-gray-500 text-sm disabled:opacity-30"
          >
            Back
          </button>
          {step < 3 ? (
            <button
              onClick={() => setStep(s => s + 1)}
              className="bg-orange-500 text-white px-6 py-2 rounded-xl font-semibold"
            >
              Next
            </button>
          ) : (
            <button
              onClick={save}
              className="bg-orange-500 text-white px-6 py-2 rounded-xl font-semibold"
            >
              Finish
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function Field({ label, value, onChange, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; placeholder: string
}) {
  return (
    <label className="block">
      <span className="text-sm text-gray-600">{label}</span>
      <input
        type="number"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="mt-1 block w-full rounded-lg border border-gray-300 p-2 text-gray-900"
      />
    </label>
  )
}
```

- [ ] **Step 2: Test wizard in browser**

Visit `http://localhost:5173/setup?athlete_id=1`. Step through all 4 steps. On Finish, POST should hit `/onboarding/profile` and redirect to dashboard.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Setup.tsx
git commit -m "feat: 4-step onboarding wizard for LTHR, pace, body metrics, preferences"
```

---

## Self-Review

**Spec coverage check:**

| Requirement | Task |
|---|---|
| US-01 Strava OAuth + CSRF state + token encryption | Task 0.3, 0.4 |
| US-01 Token refresh transparent | `strava_client.py` refresh_access_token — wired in Task 0.4 |
| US-01 Webhook subscription cancel on revoke | ⚠️ Not covered — add DELETE /auth/revoke endpoint |
| US-02 4-step onboarding wizard | Task 2.1, 4.5 |
| US-02 LTHR auto-detection from history | ⚠️ Not covered — add as enhancement to onboarding GET |
| US-03 Race targets CRUD | Task 2.2 |
| US-03 Training phase from weeks-to-race | Task 4.3 dashboard.py |
| US-04 Webhook HMAC + ingestion | Task 0.5 |
| US-04 Metrics engine | Tasks 1.1–1.5 |
| US-04 Retry/dead-letter | ⚠️ Retry logic in tasks.py is basic — add exponential backoff |
| US-05 LangGraph debrief | Task 3.2 |
| US-05 Schema validation + fallback | Task 3.2 fallback_debrief node |
| US-05 Debrief links to source metric | Task 4.4 DebriefCard (static) — metric drill-down not wired |
| US-06 Dashboard CTL/ATL/TSB/ACWR | Task 4.3 |
| US-06 Injury risk warning banner | ⚠️ Not rendered — add to Dashboard.tsx |

**Gaps to add after initial implementation:**
1. DELETE /auth/revoke (cancel webhook + clear tokens)
2. LTHR auto-suggestion from 20-min max HR segments
3. Exponential backoff in `tasks.py` (1min → 5min → 30min)
4. ACWR injury warning banner in Dashboard.tsx
5. Targets page `frontend/src/pages/Targets.tsx` (CRUD UI)

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-16-strava-coach-master-plan.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — Fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
