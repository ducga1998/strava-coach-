# Admin Dashboard — Login Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Slice 1 of the admin dashboard from `docs/superpowers/specs/2026-04-20-admin-dashboard-design.md`: all admin DB tables created, admin auth fully working end-to-end (backend + frontend), a CLI to create the first admin, and a manual acceptance run where the user logs in, lands on an admin home page, reloads to confirm session persistence, and logs out.

**Architecture:** Parallel admin module inside the existing FastAPI app (`backend/app/admin/`) with its own models, routers, and auth dependency. Frontend ships a lazy-loaded `/admin/*` chunk with email+password login, guarded by an HttpOnly session cookie. All six admin tables plus `athletes.disabled_at` are created in a single Alembic migration so later slices don't need schema churn; only `admins` / `admin_sessions` are *used* in this slice.

**Tech Stack:** FastAPI 0.115, SQLAlchemy 2 async, Alembic 1.13, argon2-cffi (new), pytest + pytest-asyncio, React 18 + Vite, TanStack Query 5, axios 1.12, React Router 6.

---

## File Structure

### New backend files
```
backend/app/admin/
├── __init__.py                     # empty marker
├── auth.py                         # password hashing, session create/validate, require_admin dep
├── cli.py                          # python -m app.admin.cli create-admin ...
├── models.py                       # Admin, AdminSession, PromptVersion, DebriefRun, DebriefRating, DebriefAutoFlag
├── schemas.py                      # LoginRequest, MeResponse, ChangePasswordRequest
├── routers/
│   ├── __init__.py
│   └── admin_auth.py               # /admin/auth/login, /logout, /me, /change-password
└── services/
    ├── __init__.py
    └── admin_invite.py             # create admin row + generate random password

backend/migrations/versions/
└── 002_admin_dashboard.py          # all admin tables + athletes.disabled_at + seed prompt v1

backend/tests/test_admin/
├── __init__.py
├── conftest.py                     # admin fixture, authed-client fixture
├── test_auth_module.py             # password/session unit tests
├── test_auth_router.py             # login/logout/me/change-password integration tests
└── test_cli.py                     # create-admin command test
```

### Modified backend files
- `backend/requirements.txt` — add `argon2-cffi==23.1.0`
- `backend/app/main.py` — register admin auth router
- `backend/app/models/athlete.py` — add `disabled_at: Mapped[datetime | None]`
- `backend/app/config.py` — add `admin_session_lifetime_days: int = 14`
- `backend/tests/conftest.py` — `import app.admin.models` so SQLite create_all picks up admin tables

### New frontend files
```
frontend/src/admin/
├── AdminApp.tsx                    # Suspense-ready app root; wraps routes in RequireAdmin except login
├── api.ts                          # axios instance (withCredentials) + TanStack Query hooks
├── types.ts                        # Admin, LoginRequest, MeResponse, etc.
├── components/
│   ├── AdminNav.tsx                # sidebar with Home / (placeholders) / Logout
│   └── RequireAdmin.tsx            # calls /admin/auth/me; 401 → redirect /admin/login
└── pages/
    ├── Login.tsx
    └── Home.tsx                    # minimal "Welcome, {name}" shell (full stats come in Slice 5)
```

### Modified frontend files
- `frontend/src/App.tsx` — add lazy `/admin/*` route

---

## Task 1: Add argon2-cffi dependency

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add argon2-cffi to requirements.txt**

Append one line to `backend/requirements.txt` so total is 21 lines:

```
argon2-cffi==23.1.0
```

- [ ] **Step 2: Install**

Run:
```bash
cd backend && pip install -r requirements.txt
```

Expected: `Successfully installed argon2-cffi-23.1.0 argon2-cffi-bindings-...`

- [ ] **Step 3: Verify import**

Run:
```bash
cd backend && python -c "from argon2 import PasswordHasher; print(PasswordHasher().hash('x'))"
```

Expected: a string starting with `$argon2id$v=19$m=65536,t=3,p=4$...`

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add argon2-cffi for admin password hashing"
```

---

## Task 2: Admin module skeleton + SQLAlchemy models

Create every admin table plus `athletes.disabled_at` as SQLAlchemy models. Tests verify `Base.metadata.create_all` succeeds with the new models registered.

**Files:**
- Create: `backend/app/admin/__init__.py`
- Create: `backend/app/admin/models.py`
- Create: `backend/app/admin/routers/__init__.py`
- Create: `backend/app/admin/services/__init__.py`
- Create: `backend/tests/test_admin/__init__.py`
- Create: `backend/tests/test_admin/conftest.py`
- Create: `backend/tests/test_admin/test_models.py`
- Modify: `backend/app/models/athlete.py` — add `disabled_at`
- Modify: `backend/tests/conftest.py` — import admin models

- [ ] **Step 1: Create empty package markers**

```bash
mkdir -p backend/app/admin/routers backend/app/admin/services backend/tests/test_admin
touch backend/app/admin/__init__.py
touch backend/app/admin/routers/__init__.py
touch backend/app/admin/services/__init__.py
touch backend/tests/test_admin/__init__.py
```

- [ ] **Step 2: Write failing test for admin model schema**

Create `backend/tests/test_admin/test_models.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.admin.models import (
    Admin,
    AdminSession,
    PromptVersion,
    DebriefRun,
    DebriefRating,
    DebriefAutoFlag,
    Thumb,
)
from app.models.athlete import Athlete


@pytest.mark.asyncio
async def test_admin_tables_created(db_session: AsyncSession) -> None:
    """All admin tables should be creatable via Base.metadata.create_all."""
    result = await db_session.execute(select(Admin))
    assert result.all() == []
    result = await db_session.execute(select(AdminSession))
    assert result.all() == []
    result = await db_session.execute(select(PromptVersion))
    assert result.all() == []
    result = await db_session.execute(select(DebriefRun))
    assert result.all() == []
    result = await db_session.execute(select(DebriefRating))
    assert result.all() == []
    result = await db_session.execute(select(DebriefAutoFlag))
    assert result.all() == []


@pytest.mark.asyncio
async def test_athlete_has_disabled_at(db_session: AsyncSession) -> None:
    athlete = Athlete(strava_athlete_id=42, firstname="Test")
    db_session.add(athlete)
    await db_session.flush()
    assert athlete.disabled_at is None


def test_thumb_enum_values() -> None:
    assert Thumb.up.value == "up"
    assert Thumb.down.value == "down"
```

- [ ] **Step 3: Run test to verify it fails**

Run:
```bash
cd backend && pytest tests/test_admin/test_models.py -v
```

Expected: `ImportError: cannot import name 'Admin' from 'app.admin.models'` (or ModuleNotFoundError).

- [ ] **Step 4: Create admin models**

Create `backend/app/admin/models.py`:

```python
import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.activity import Activity
    from app.models.athlete import Athlete


class Thumb(str, enum.Enum):
    up = "up"
    down = "down"


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sessions: Mapped[list["AdminSession"]] = relationship(
        back_populates="admin", cascade="all, delete-orphan"
    )


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(
        ForeignKey("admins.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    admin: Mapped[Admin] = relationship(back_populates="sessions")


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("admins.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # PostgreSQL partial unique index: at most one active version.
        # Enforced in the Alembic migration (Task 3). Declared here for docs.
        Index(
            "ix_prompt_versions_unique_active",
            "is_active",
            unique=True,
            postgresql_where="is_active",
        ),
    )


class DebriefRun(Base):
    __tablename__ = "debrief_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    athlete_id: Mapped[int] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt_version_id: Mapped[int] = mapped_column(
        ForeignKey("prompt_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_use_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # JSONB in Postgres, JSON in sqlite (for in-memory tests in conftest).
    raw_output: Mapped[dict | None] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class DebriefRating(Base):
    __tablename__ = "debrief_ratings"

    debrief_run_id: Mapped[int] = mapped_column(
        ForeignKey("debrief_runs.id", ondelete="CASCADE"), primary_key=True
    )
    admin_id: Mapped[int] = mapped_column(
        ForeignKey("admins.id", ondelete="SET NULL"), nullable=True
    )
    thumb: Mapped[Thumb] = mapped_column(Enum(Thumb, name="thumb"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DebriefAutoFlag(Base):
    __tablename__ = "debrief_auto_flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    debrief_run_id: Mapped[int] = mapped_column(
        ForeignKey("debrief_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_name: Mapped[str] = mapped_column(String(50), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 5: Add `disabled_at` to Athlete model**

Modify `backend/app/models/athlete.py`. After the existing `created_at` column on class `Athlete` (line ~37), add:

```python
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 6: Register admin models in test conftest**

Modify `backend/tests/conftest.py`. Replace line 11 (`import app.models`) with:

```python
import app.models  # noqa: F401
import app.admin.models  # noqa: F401
```

- [ ] **Step 7: Create test_admin/conftest.py (empty for now; fixtures added in later tasks)**

Create `backend/tests/test_admin/conftest.py`:

```python
"""Admin test fixtures (populated in later tasks)."""
```

- [ ] **Step 8: Run test to verify it passes**

Run:
```bash
cd backend && pytest tests/test_admin/test_models.py -v
```

Expected: all three tests PASS.

- [ ] **Step 9: Verify full suite still passes**

Run:
```bash
cd backend && pytest tests/ -v
```

Expected: all tests pass (previously 27 + 3 new = 30 minimum).

- [ ] **Step 10: Commit**

```bash
git add backend/app/admin/ backend/app/models/athlete.py backend/tests/conftest.py backend/tests/test_admin/
git commit -m "feat: admin SQLAlchemy models + athletes.disabled_at column"
```

---

## Task 3: Alembic migration for admin tables

**Files:**
- Create: `backend/migrations/versions/002_admin_dashboard.py`

- [ ] **Step 1: Create the migration file**

Create `backend/migrations/versions/002_admin_dashboard.py`:

```python
"""Admin dashboard: admins, sessions, prompt versions, debrief runs/ratings/flags + athletes.disabled_at + seed prompt v1.

Revision ID: 002_admin_dashboard
Revises: 001_athlete_profile
Create Date: 2026-04-20

"""
from typing import Sequence, Union

from alembic import op

revision: str = "002_admin_dashboard"
down_revision: Union[str, None] = "001_athlete_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEED_PROMPT_V1_NAME = "baseline-vmm"
SEED_PROMPT_V1_MODEL = "claude-sonnet-4-6"
# The body of prompt v1 is the original hardcoded SYSTEM_PROMPT from
# backend/app/agents/prompts.py, copied verbatim so seed is self-contained.
# After creating the file, REPLACE the three-dot line below with the exact
# string value of SYSTEM_PROMPT from that file (everything inside the outer
# triple-quotes, newlines preserved, no leading/trailing whitespace added).
SEED_PROMPT_V1_BODY = r"""...PASTE FULL SYSTEM_PROMPT VALUE HERE..."""


def upgrade() -> None:
    op.execute("ALTER TABLE athletes ADD COLUMN IF NOT EXISTS disabled_at TIMESTAMPTZ")

    op.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            name VARCHAR(100),
            disabled_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_login_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_admins_email ON admins (email)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_sessions (
            id SERIAL PRIMARY KEY,
            admin_id INTEGER NOT NULL REFERENCES admins(id) ON DELETE CASCADE,
            token_hash VARCHAR(64) UNIQUE NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            revoked_at TIMESTAMPTZ,
            user_agent VARCHAR(255),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_admin_sessions_token_hash ON admin_sessions (token_hash)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_admin_sessions_expires_at ON admin_sessions (expires_at)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS prompt_versions (
            id SERIAL PRIMARY KEY,
            version_number INTEGER UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            system_prompt TEXT NOT NULL,
            model VARCHAR(50) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT FALSE,
            notes TEXT,
            created_by INTEGER REFERENCES admins(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            activated_at TIMESTAMPTZ,
            deactivated_at TIMESTAMPTZ
        )
    """)
    # Partial unique index: at most one active version at a time.
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_prompt_versions_unique_active
        ON prompt_versions (is_active) WHERE is_active
    """)

    op.execute("DO $$ BEGIN CREATE TYPE thumb AS ENUM ('up', 'down'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS debrief_runs (
            id SERIAL PRIMARY KEY,
            activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
            athlete_id INTEGER NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
            prompt_version_id INTEGER NOT NULL REFERENCES prompt_versions(id) ON DELETE RESTRICT,
            model VARCHAR(50) NOT NULL,
            input_tokens INTEGER,
            output_tokens INTEGER,
            latency_ms INTEGER NOT NULL,
            tool_use_ok BOOLEAN NOT NULL,
            fallback_used BOOLEAN NOT NULL,
            raw_output JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_debrief_runs_activity_id ON debrief_runs (activity_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_debrief_runs_athlete_id ON debrief_runs (athlete_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_debrief_runs_prompt_version_id ON debrief_runs (prompt_version_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_debrief_runs_created_at ON debrief_runs (created_at DESC)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS debrief_ratings (
            debrief_run_id INTEGER PRIMARY KEY REFERENCES debrief_runs(id) ON DELETE CASCADE,
            admin_id INTEGER REFERENCES admins(id) ON DELETE SET NULL,
            thumb thumb NOT NULL,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS debrief_auto_flags (
            id SERIAL PRIMARY KEY,
            debrief_run_id INTEGER NOT NULL REFERENCES debrief_runs(id) ON DELETE CASCADE,
            rule_name VARCHAR(50) NOT NULL,
            detail TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_debrief_auto_flags_debrief_run_id ON debrief_auto_flags (debrief_run_id)")

    # Seed prompt v1 from the original hardcoded SYSTEM_PROMPT. Safe if re-run:
    # ON CONFLICT (version_number) DO NOTHING.
    op.execute(f"""
        INSERT INTO prompt_versions (version_number, name, system_prompt, model, is_active, notes, activated_at)
        VALUES (1, '{SEED_PROMPT_V1_NAME}', $seed_v1${SEED_PROMPT_V1_BODY}$seed_v1$, '{SEED_PROMPT_V1_MODEL}', TRUE, 'Initial prompt seeded from code.', now())
        ON CONFLICT (version_number) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS debrief_auto_flags")
    op.execute("DROP TABLE IF EXISTS debrief_ratings")
    op.execute("DROP TABLE IF EXISTS debrief_runs")
    op.execute("DROP TYPE IF EXISTS thumb")
    op.execute("DROP TABLE IF EXISTS prompt_versions")
    op.execute("DROP TABLE IF EXISTS admin_sessions")
    op.execute("DROP TABLE IF EXISTS admins")
    op.execute("ALTER TABLE athletes DROP COLUMN IF EXISTS disabled_at")
```

**IMPORTANT — before running the migration**, replace the `SEED_PROMPT_V1_BODY` placeholder with the real prompt body. Concrete command:

```bash
# Verify the current SYSTEM_PROMPT value first
cd backend && python -c "from app.agents.prompts import SYSTEM_PROMPT; print(SYSTEM_PROMPT)" | head -5
```

Then open the migration file and paste the full `SYSTEM_PROMPT` string (the entire value assigned in `app/agents/prompts.py` — everything between the outer triple-quotes, newlines preserved) into the `SEED_PROMPT_V1_BODY = r"""..."""` slot. Keep the `$seed_v1$...$seed_v1$` dollar-quoted wrapper in the `INSERT` so PostgreSQL doesn't choke on apostrophes inside the body.

- [ ] **Step 2: Ensure docker compose postgres is up**

Run:
```bash
docker compose up -d postgres
```

Expected: postgres container is healthy on :5432.

- [ ] **Step 3: Apply migration**

Run:
```bash
cd backend && alembic upgrade head
```

Expected output includes: `Running upgrade 001_athlete_profile -> 002_admin_dashboard, Admin dashboard...`

- [ ] **Step 4: Verify schema**

Run:
```bash
docker compose exec postgres psql -U postgres -d stravacoach -c "\dt" -c "SELECT version_number, name, model, is_active FROM prompt_versions"
```

Expected: lists `admins`, `admin_sessions`, `prompt_versions`, `debrief_runs`, `debrief_ratings`, `debrief_auto_flags` plus existing tables; and one row in `prompt_versions`: `1 | baseline-vmm | claude-sonnet-4-6 | t`.

- [ ] **Step 5: Test downgrade**

Run:
```bash
cd backend && alembic downgrade -1 && alembic upgrade head
```

Expected: both succeed without error.

- [ ] **Step 6: Commit**

```bash
git add backend/migrations/versions/002_admin_dashboard.py
git commit -m "feat: alembic migration for admin tables + seed prompt v1"
```

---

## Task 4: Password hashing + session module

All pure crypto/session logic in one file. TDD.

**Files:**
- Create: `backend/app/admin/auth.py`
- Create: `backend/tests/test_admin/test_auth_module.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_admin/test_auth_module.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import auth as admin_auth
from app.admin.models import Admin, AdminSession


def test_hash_password_returns_argon2id_string() -> None:
    h = admin_auth.hash_password("correcthorsebatterystaple")
    assert h.startswith("$argon2id$")


def test_verify_password_correct() -> None:
    h = admin_auth.hash_password("correcthorsebatterystaple")
    assert admin_auth.verify_password(h, "correcthorsebatterystaple") is True


def test_verify_password_wrong() -> None:
    h = admin_auth.hash_password("correcthorsebatterystaple")
    assert admin_auth.verify_password(h, "wrong") is False


def test_generate_session_token_is_urlsafe_and_unique() -> None:
    a = admin_auth.generate_session_token()
    b = admin_auth.generate_session_token()
    assert a != b
    assert len(a) >= 32
    assert all(c.isalnum() or c in "-_" for c in a)


def test_hash_token_is_deterministic_hex_sha256() -> None:
    t = "some-session-token"
    assert admin_auth.hash_token(t) == admin_auth.hash_token(t)
    assert len(admin_auth.hash_token(t)) == 64


@pytest.mark.asyncio
async def test_create_session_stores_hashed_token(db_session: AsyncSession) -> None:
    admin = Admin(email="a@example.com", password_hash=admin_auth.hash_password("x" * 12))
    db_session.add(admin)
    await db_session.flush()

    raw_token = await admin_auth.create_session(db_session, admin, lifetime_days=14)

    row = (await db_session.execute(select(AdminSession))).scalar_one()
    assert row.token_hash == admin_auth.hash_token(raw_token)
    assert row.token_hash != raw_token
    assert row.revoked_at is None
    assert row.expires_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_lookup_session_returns_admin(db_session: AsyncSession) -> None:
    admin = Admin(email="a@example.com", password_hash=admin_auth.hash_password("x" * 12))
    db_session.add(admin)
    await db_session.flush()

    raw_token = await admin_auth.create_session(db_session, admin, lifetime_days=14)
    found = await admin_auth.lookup_admin_by_session(db_session, raw_token)
    assert found is not None
    assert found.id == admin.id


@pytest.mark.asyncio
async def test_lookup_session_rejects_expired(db_session: AsyncSession) -> None:
    admin = Admin(email="a@example.com", password_hash=admin_auth.hash_password("x" * 12))
    db_session.add(admin)
    await db_session.flush()
    raw_token = admin_auth.generate_session_token()
    expired = AdminSession(
        admin_id=admin.id,
        token_hash=admin_auth.hash_token(raw_token),
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db_session.add(expired)
    await db_session.flush()

    found = await admin_auth.lookup_admin_by_session(db_session, raw_token)
    assert found is None


@pytest.mark.asyncio
async def test_lookup_session_rejects_revoked(db_session: AsyncSession) -> None:
    admin = Admin(email="a@example.com", password_hash=admin_auth.hash_password("x" * 12))
    db_session.add(admin)
    await db_session.flush()
    raw_token = await admin_auth.create_session(db_session, admin, lifetime_days=14)
    session = (await db_session.execute(select(AdminSession))).scalar_one()
    session.revoked_at = datetime.now(timezone.utc)
    await db_session.flush()

    found = await admin_auth.lookup_admin_by_session(db_session, raw_token)
    assert found is None


@pytest.mark.asyncio
async def test_lookup_session_rejects_disabled_admin(db_session: AsyncSession) -> None:
    admin = Admin(
        email="a@example.com",
        password_hash=admin_auth.hash_password("x" * 12),
        disabled_at=datetime.now(timezone.utc),
    )
    db_session.add(admin)
    await db_session.flush()
    raw_token = await admin_auth.create_session(db_session, admin, lifetime_days=14)

    found = await admin_auth.lookup_admin_by_session(db_session, raw_token)
    assert found is None


@pytest.mark.asyncio
async def test_revoke_session(db_session: AsyncSession) -> None:
    admin = Admin(email="a@example.com", password_hash=admin_auth.hash_password("x" * 12))
    db_session.add(admin)
    await db_session.flush()
    raw_token = await admin_auth.create_session(db_session, admin, lifetime_days=14)

    await admin_auth.revoke_session(db_session, raw_token)
    row = (await db_session.execute(select(AdminSession))).scalar_one()
    assert row.revoked_at is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd backend && pytest tests/test_admin/test_auth_module.py -v
```

Expected: `ImportError: cannot import ... from 'app.admin.auth'`.

- [ ] **Step 3: Implement `auth.py`**

Create `backend/app/admin/auth.py`:

```python
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import Admin, AdminSession
from app.database import get_db

_hasher = PasswordHasher()

SESSION_COOKIE_NAME = "admin_session"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(hashed: str, password: str) -> bool:
    try:
        _hasher.verify(hashed, password)
        return True
    except VerifyMismatchError:
        return False


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def create_session(
    db: AsyncSession,
    admin: Admin,
    lifetime_days: int,
    user_agent: str | None = None,
) -> str:
    raw = generate_session_token()
    session = AdminSession(
        admin_id=admin.id,
        token_hash=hash_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(days=lifetime_days),
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(session)
    await db.flush()
    return raw


async def lookup_admin_by_session(db: AsyncSession, raw_token: str) -> Admin | None:
    row = (
        await db.execute(
            select(AdminSession).where(AdminSession.token_hash == hash_token(raw_token))
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    if row.revoked_at is not None:
        return None
    if row.expires_at <= datetime.now(timezone.utc):
        return None
    admin = await db.get(Admin, row.admin_id)
    if admin is None or admin.disabled_at is not None:
        return None
    return admin


async def revoke_session(db: AsyncSession, raw_token: str) -> None:
    row = (
        await db.execute(
            select(AdminSession).where(AdminSession.token_hash == hash_token(raw_token))
        )
    ).scalar_one_or_none()
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        await db.flush()


async def require_admin(
    request: Request,
    admin_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> Admin:
    if not admin_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    admin = await lookup_admin_by_session(db, admin_session)
    if admin is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return admin
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd backend && pytest tests/test_admin/test_auth_module.py -v
```

Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/admin/auth.py backend/tests/test_admin/test_auth_module.py
git commit -m "feat: admin password hashing + session management (argon2id + sha256 tokens)"
```

---

## Task 5: Admin invite service (used by CLI)

**Files:**
- Create: `backend/app/admin/services/admin_invite.py`
- Create: `backend/tests/test_admin/test_admin_invite.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_admin/test_admin_invite.py`:

```python
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import auth as admin_auth
from app.admin.models import Admin
from app.admin.services.admin_invite import create_admin, AdminAlreadyExists


@pytest.mark.asyncio
async def test_create_admin_returns_generated_password(db_session: AsyncSession) -> None:
    result = await create_admin(db_session, email="a@example.com", name="Alice")
    assert result.email == "a@example.com"
    assert len(result.generated_password) >= 16
    # Stored hash verifies against the generated password
    row = (await db_session.execute(select(Admin))).scalar_one()
    assert admin_auth.verify_password(row.password_hash, result.generated_password)
    assert row.name == "Alice"


@pytest.mark.asyncio
async def test_create_admin_lowercases_email(db_session: AsyncSession) -> None:
    await create_admin(db_session, email="Alice@Example.COM", name=None)
    row = (await db_session.execute(select(Admin))).scalar_one()
    assert row.email == "alice@example.com"


@pytest.mark.asyncio
async def test_create_admin_rejects_duplicate(db_session: AsyncSession) -> None:
    await create_admin(db_session, email="a@example.com", name=None)
    with pytest.raises(AdminAlreadyExists):
        await create_admin(db_session, email="a@example.com", name=None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd backend && pytest tests/test_admin/test_admin_invite.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement the service**

Create `backend/app/admin/services/admin_invite.py`:

```python
import secrets
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import auth as admin_auth
from app.admin.models import Admin


class AdminAlreadyExists(Exception):
    pass


@dataclass
class CreatedAdmin:
    email: str
    name: str | None
    generated_password: str


async def create_admin(
    db: AsyncSession,
    email: str,
    name: str | None,
) -> CreatedAdmin:
    normalised = email.strip().lower()
    existing = (
        await db.execute(select(Admin).where(Admin.email == normalised))
    ).scalar_one_or_none()
    if existing is not None:
        raise AdminAlreadyExists(normalised)
    password = secrets.token_urlsafe(18)
    admin = Admin(
        email=normalised,
        password_hash=admin_auth.hash_password(password),
        name=name,
    )
    db.add(admin)
    await db.flush()
    return CreatedAdmin(email=normalised, name=name, generated_password=password)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd backend && pytest tests/test_admin/test_admin_invite.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/admin/services/admin_invite.py backend/tests/test_admin/test_admin_invite.py
git commit -m "feat: admin invite service (creates admin row + generates random password)"
```

---

## Task 6: `python -m app.admin.cli create-admin` CLI

**Files:**
- Create: `backend/app/admin/cli.py`
- Create: `backend/tests/test_admin/test_cli.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_admin/test_cli.py`:

```python
import asyncio
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import cli as admin_cli
from app.admin.models import Admin


@pytest.mark.asyncio
async def test_create_admin_command_prints_password(
    db_session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    class _Ctx:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *a):
            # Don't close — fixture owns the session.
            pass

    def fake_open_session():
        return _Ctx()

    with patch.object(admin_cli, "_open_session", fake_open_session):
        await admin_cli.run(["create-admin", "--email", "a@example.com", "--name", "Alice"])

    captured = capsys.readouterr()
    assert "a@example.com" in captured.out
    assert "Generated password:" in captured.out

    row = (await db_session.execute(select(Admin))).scalar_one()
    assert row.email == "a@example.com"
    assert row.name == "Alice"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd backend && pytest tests/test_admin/test_cli.py -v
```

Expected: ImportError on `app.admin.cli`.

- [ ] **Step 3: Implement the CLI**

Create `backend/app/admin/cli.py`:

```python
import argparse
import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.services.admin_invite import AdminAlreadyExists, create_admin
from app.database import SessionLocal


@asynccontextmanager
async def _open_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def _cmd_create_admin(email: str, name: str | None) -> int:
    async with _open_session() as db:
        try:
            result = await create_admin(db, email=email, name=name)
            await db.commit()
        except AdminAlreadyExists:
            print(f"error: admin '{email}' already exists", file=sys.stderr)
            return 1
    print(f"Created admin: {result.email}")
    print(f"Generated password: {result.generated_password}")
    print("Share out of band. Admin should log in and change it immediately.")
    return 0


async def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.admin.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p_create = sub.add_parser("create-admin", help="Create a new admin account")
    p_create.add_argument("--email", required=True)
    p_create.add_argument("--name", default=None)

    args = parser.parse_args(argv)
    if args.command == "create-admin":
        return await _cmd_create_admin(email=args.email, name=args.name)
    return 2


def main() -> None:  # pragma: no cover
    sys.exit(asyncio.run(run(sys.argv[1:])))


if __name__ == "__main__":  # pragma: no cover
    main()
```

- [ ] **Step 4: Check `SessionLocal` is exported from `app.database`**

Run:
```bash
cd backend && python -c "from app.database import SessionLocal; print(SessionLocal)"
```

If this errors with `ImportError`, open `backend/app/database.py` and confirm the async sessionmaker is exported under a name. If it's called something else (e.g. `async_session_maker`), replace `SessionLocal` in the CLI with that name. If no sessionmaker is exported, add this to `backend/app/database.py`:

```python
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
```

and export it. Commit the database change separately with message `chore: export SessionLocal from app.database`.

- [ ] **Step 5: Run test to verify it passes**

Run:
```bash
cd backend && pytest tests/test_admin/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/admin/cli.py backend/tests/test_admin/test_cli.py
git commit -m "feat: admin CLI — create-admin subcommand"
```

---

## Task 7: Config setting for session lifetime

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`

- [ ] **Step 1: Add setting to `Settings` class**

Open `backend/app/config.py`. Add within the `Settings` class, near other integer settings:

```python
    admin_session_lifetime_days: int = 14
```

- [ ] **Step 2: Document in .env.example**

Append to `backend/.env.example`:

```
# Admin dashboard
ADMIN_SESSION_LIFETIME_DAYS=14
```

- [ ] **Step 3: Verify config loads**

Run:
```bash
cd backend && python -c "from app.config import settings; print(settings.admin_session_lifetime_days)"
```

Expected: `14`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/config.py backend/.env.example
git commit -m "chore: add admin_session_lifetime_days config (default 14)"
```

---

## Task 8: Admin auth schemas

**Files:**
- Create: `backend/app/admin/schemas.py`

- [ ] **Step 1: Create schemas file**

Create `backend/app/admin/schemas.py`:

```python
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class MeResponse(BaseModel):
    id: int
    email: str
    name: str | None


class ChangePasswordRequest(BaseModel):
    current: str = Field(min_length=1, max_length=256)
    new: str = Field(min_length=12, max_length=256)
```

- [ ] **Step 2: Check pydantic has EmailStr support**

Run:
```bash
cd backend && python -c "from pydantic import EmailStr; print(EmailStr)"
```

If this fails with `ImportError: email-validator is not installed`, add to `backend/requirements.txt`:

```
email-validator==2.2.0
```

Then `pip install -r requirements.txt`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/admin/schemas.py backend/requirements.txt
git commit -m "feat: admin auth request/response schemas"
```

---

## Task 9: Admin auth router — `POST /admin/auth/login`

**Files:**
- Create: `backend/app/admin/routers/admin_auth.py`
- Create: `backend/tests/test_admin/test_auth_router.py`
- Modify: `backend/app/main.py` — register router

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_admin/test_auth_router.py`:

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import auth as admin_auth
from app.admin.models import Admin


@pytest.fixture
def seed_admin(db_session: AsyncSession):
    import asyncio
    async def _seed():
        admin = Admin(
            email="alice@example.com",
            password_hash=admin_auth.hash_password("correctpassword"),
            name="Alice",
        )
        db_session.add(admin)
        await db_session.flush()
        return admin

    return asyncio.run(_seed())


def test_login_success(client: TestClient, seed_admin: Admin) -> None:
    response = client.post(
        "/admin/auth/login",
        json={"email": "alice@example.com", "password": "correctpassword"},
    )
    assert response.status_code == 200
    assert response.cookies.get(admin_auth.SESSION_COOKIE_NAME)
    assert response.json() == {"id": seed_admin.id, "email": "alice@example.com", "name": "Alice"}


def test_login_wrong_password(client: TestClient, seed_admin: Admin) -> None:
    response = client.post(
        "/admin/auth/login",
        json={"email": "alice@example.com", "password": "wrong"},
    )
    assert response.status_code == 401
    assert response.cookies.get(admin_auth.SESSION_COOKIE_NAME) is None


def test_login_unknown_email(client: TestClient) -> None:
    response = client.post(
        "/admin/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )
    assert response.status_code == 401


def test_login_case_insensitive_email(client: TestClient, seed_admin: Admin) -> None:
    response = client.post(
        "/admin/auth/login",
        json={"email": "ALICE@EXAMPLE.COM", "password": "correctpassword"},
    )
    assert response.status_code == 200


def test_login_disabled_admin_rejected(
    client: TestClient, seed_admin: Admin, db_session: AsyncSession
) -> None:
    import asyncio
    from datetime import datetime, timezone
    from sqlalchemy import select

    async def _disable():
        # Re-fetch in this loop to avoid cross-loop detached-instance issues.
        fresh = (
            await db_session.execute(
                select(Admin).where(Admin.email == "alice@example.com")
            )
        ).scalar_one()
        fresh.disabled_at = datetime.now(timezone.utc)
        await db_session.flush()

    asyncio.run(_disable())
    response = client.post(
        "/admin/auth/login",
        json={"email": "alice@example.com", "password": "correctpassword"},
    )
    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd backend && pytest tests/test_admin/test_auth_router.py::test_login_success -v
```

Expected: 404 (route doesn't exist) or ImportError.

- [ ] **Step 3: Implement the login endpoint**

Create `backend/app/admin/routers/admin_auth.py`:

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import auth as admin_auth
from app.admin.models import Admin
from app.admin.schemas import ChangePasswordRequest, LoginRequest, MeResponse
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


def _cookie_kwargs() -> dict:
    # In tests (starlette TestClient) SameSite/Secure don't interfere with
    # cookie round-trips; in prod we want HttpOnly + Secure + SameSite=Lax.
    return {
        "httponly": True,
        "secure": not settings.frontend_url.startswith("http://localhost"),
        "samesite": "lax",
        "path": "/admin",
    }


@router.post("/login", response_model=MeResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    normalised = payload.email.lower()
    admin = (
        await db.execute(select(Admin).where(Admin.email == normalised))
    ).scalar_one_or_none()
    if admin is None or admin.disabled_at is not None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not admin_auth.verify_password(admin.password_hash, payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    raw_token = await admin_auth.create_session(
        db,
        admin,
        lifetime_days=settings.admin_session_lifetime_days,
        user_agent=request.headers.get("user-agent"),
    )
    admin.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    response.set_cookie(
        key=admin_auth.SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=settings.admin_session_lifetime_days * 24 * 3600,
        **_cookie_kwargs(),
    )
    return MeResponse(id=admin.id, email=admin.email, name=admin.name)
```

- [ ] **Step 4: Register router in main.py**

Modify `backend/app/main.py`. Add to the imports block near line 8:

```python
from app.admin.routers import admin_auth
```

Inside `register_routes`, add before the closing brace:

```python
    api.include_router(admin_auth.router)
```

- [ ] **Step 5: Run login tests to verify they pass**

Run:
```bash
cd backend && pytest tests/test_admin/test_auth_router.py -v -k login
```

Expected: 5 login tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/admin/routers/admin_auth.py backend/app/main.py backend/tests/test_admin/test_auth_router.py
git commit -m "feat: POST /admin/auth/login with argon2 verify + session cookie"
```

---

## Task 10: `GET /admin/auth/me` + `POST /admin/auth/logout`

**Files:**
- Modify: `backend/app/admin/routers/admin_auth.py`
- Modify: `backend/tests/test_admin/test_auth_router.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_admin/test_auth_router.py`:

```python
def _login(client: TestClient) -> None:
    r = client.post(
        "/admin/auth/login",
        json={"email": "alice@example.com", "password": "correctpassword"},
    )
    assert r.status_code == 200


def test_me_without_cookie_returns_401(client: TestClient) -> None:
    assert client.get("/admin/auth/me").status_code == 401


def test_me_returns_current_admin(client: TestClient, seed_admin: Admin) -> None:
    _login(client)
    response = client.get("/admin/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_logout_revokes_session(client: TestClient, seed_admin: Admin) -> None:
    _login(client)
    response = client.post("/admin/auth/logout")
    assert response.status_code == 204
    # Subsequent /me should now 401
    assert client.get("/admin/auth/me").status_code == 401


def test_logout_without_cookie_is_noop(client: TestClient) -> None:
    assert client.post("/admin/auth/logout").status_code == 204
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd backend && pytest tests/test_admin/test_auth_router.py -v -k "me or logout"
```

Expected: 404 on `/me` and `/logout`.

- [ ] **Step 3: Add endpoints**

Append to `backend/app/admin/routers/admin_auth.py`:

```python
@router.get("/me", response_model=MeResponse)
async def me(admin: Admin = Depends(admin_auth.require_admin)) -> MeResponse:
    return MeResponse(id=admin.id, email=admin.email, name=admin.name)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Response:
    raw = request.cookies.get(admin_auth.SESSION_COOKIE_NAME)
    if raw:
        await admin_auth.revoke_session(db, raw)
        await db.commit()
    response.delete_cookie(admin_auth.SESSION_COOKIE_NAME, path="/admin")
    response.status_code = 204
    return response
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd backend && pytest tests/test_admin/test_auth_router.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/admin/routers/admin_auth.py backend/tests/test_admin/test_auth_router.py
git commit -m "feat: GET /admin/auth/me + POST /admin/auth/logout"
```

---

## Task 11: `POST /admin/auth/change-password`

**Files:**
- Modify: `backend/app/admin/routers/admin_auth.py`
- Modify: `backend/tests/test_admin/test_auth_router.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_admin/test_auth_router.py`:

```python
def test_change_password_success(client: TestClient, seed_admin: Admin) -> None:
    _login(client)
    response = client.post(
        "/admin/auth/change-password",
        json={"current": "correctpassword", "new": "brand-new-12chars"},
    )
    assert response.status_code == 204
    # Old password no longer works
    client.cookies.clear()
    r = client.post(
        "/admin/auth/login",
        json={"email": "alice@example.com", "password": "correctpassword"},
    )
    assert r.status_code == 401
    # New password works
    r = client.post(
        "/admin/auth/login",
        json={"email": "alice@example.com", "password": "brand-new-12chars"},
    )
    assert r.status_code == 200


def test_change_password_rejects_wrong_current(
    client: TestClient, seed_admin: Admin
) -> None:
    _login(client)
    response = client.post(
        "/admin/auth/change-password",
        json={"current": "wrong", "new": "brand-new-12chars"},
    )
    assert response.status_code == 400


def test_change_password_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/admin/auth/change-password",
        json={"current": "x" * 12, "new": "y" * 12},
    )
    assert response.status_code == 401


def test_change_password_rejects_too_short(
    client: TestClient, seed_admin: Admin
) -> None:
    _login(client)
    response = client.post(
        "/admin/auth/change-password",
        json={"current": "correctpassword", "new": "short"},
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Run to verify they fail**

Run:
```bash
cd backend && pytest tests/test_admin/test_auth_router.py -v -k change_password
```

Expected: 4 failing with 404.

- [ ] **Step 3: Implement change-password**

Append to `backend/app/admin/routers/admin_auth.py`:

```python
@router.post("/change-password", status_code=204)
async def change_password(
    payload: ChangePasswordRequest,
    admin: Admin = Depends(admin_auth.require_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if not admin_auth.verify_password(admin.password_hash, payload.current):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    admin.password_hash = admin_auth.hash_password(payload.new)
    await db.commit()
    return Response(status_code=204)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd backend && pytest tests/test_admin/test_auth_router.py -v
```

Expected: 13 tests PASS in this file.

- [ ] **Step 5: Run the full suite**

Run:
```bash
cd backend && pytest tests/ -v
```

Expected: existing 27 + new admin tests all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/admin/routers/admin_auth.py backend/tests/test_admin/test_auth_router.py
git commit -m "feat: POST /admin/auth/change-password (verify current + 12-char min)"
```

---

## Task 12: Frontend — admin types

**Files:**
- Create: `frontend/src/admin/types.ts`

- [ ] **Step 1: Create types file**

Create `frontend/src/admin/types.ts`:

```typescript
export type Admin = {
  id: number
  email: string
  name: string | null
}

export type LoginRequest = {
  email: string
  password: string
}

export type ChangePasswordRequest = {
  current: string
  new: string
}

export type LoginError = {
  detail: string
}
```

- [ ] **Step 2: Typecheck**

Run:
```bash
cd frontend && npm run typecheck
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/admin/types.ts
git commit -m "feat: admin types (mirrors backend schemas.py)"
```

---

## Task 13: Frontend — admin api client

**Files:**
- Create: `frontend/src/admin/api.ts`

- [ ] **Step 1: Create axios instance + hooks**

Create `frontend/src/admin/api.ts`:

```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import axios, { AxiosError } from "axios"
import type { Admin, ChangePasswordRequest, LoginError, LoginRequest } from "./types"

const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

export const adminHttp = axios.create({
  baseURL: apiUrl,
  withCredentials: true, // send admin_session cookie
})

export const adminQueryKeys = {
  me: ["admin", "me"] as const,
}

export function useAdminMe() {
  return useQuery<Admin, AxiosError<LoginError>>({
    queryKey: adminQueryKeys.me,
    queryFn: async () => {
      const { data } = await adminHttp.get<Admin>("/admin/auth/me")
      return data
    },
    retry: false,
    staleTime: 60_000,
  })
}

export function useAdminLogin() {
  const qc = useQueryClient()
  return useMutation<Admin, AxiosError<LoginError>, LoginRequest>({
    mutationFn: async (body) => {
      const { data } = await adminHttp.post<Admin>("/admin/auth/login", body)
      return data
    },
    onSuccess: (data) => {
      qc.setQueryData(adminQueryKeys.me, data)
    },
  })
}

export function useAdminLogout() {
  const qc = useQueryClient()
  return useMutation<void, AxiosError>({
    mutationFn: async () => {
      await adminHttp.post("/admin/auth/logout")
    },
    onSuccess: () => {
      qc.setQueryData(adminQueryKeys.me, null)
      qc.invalidateQueries({ queryKey: adminQueryKeys.me })
    },
  })
}

export function useAdminChangePassword() {
  return useMutation<void, AxiosError<LoginError>, ChangePasswordRequest>({
    mutationFn: async (body) => {
      await adminHttp.post("/admin/auth/change-password", body)
    },
  })
}
```

- [ ] **Step 2: Typecheck**

Run:
```bash
cd frontend && npm run typecheck
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/admin/api.ts
git commit -m "feat: admin api client (axios + TanStack Query hooks)"
```

---

## Task 14: Frontend — RequireAdmin guard + AdminNav

**Files:**
- Create: `frontend/src/admin/components/RequireAdmin.tsx`
- Create: `frontend/src/admin/components/AdminNav.tsx`

- [ ] **Step 1: Create RequireAdmin component**

Create `frontend/src/admin/components/RequireAdmin.tsx`:

```typescript
import { ReactNode } from "react"
import { Navigate, useLocation } from "react-router-dom"
import { useAdminMe } from "../api"

type Props = { children: ReactNode }

export default function RequireAdmin({ children }: Props) {
  const location = useLocation()
  const { data, isLoading, isError } = useAdminMe()

  if (isLoading) {
    return <div className="p-8 text-slate-500">Checking session…</div>
  }
  if (isError || !data) {
    return <Navigate to="/admin/login" state={{ from: location.pathname }} replace />
  }
  return <>{children}</>
}
```

- [ ] **Step 2: Create AdminNav**

Create `frontend/src/admin/components/AdminNav.tsx`:

```typescript
import { Link, useNavigate } from "react-router-dom"
import { useAdminLogout, useAdminMe } from "../api"

export default function AdminNav() {
  const { data } = useAdminMe()
  const logout = useAdminLogout()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout.mutateAsync()
    navigate("/admin/login", { replace: true })
  }

  return (
    <nav className="flex h-14 items-center justify-between border-b border-slate-200 px-6">
      <div className="flex items-center gap-6">
        <span className="font-semibold">Admin</span>
        <Link to="/admin" className="text-sm text-slate-700 hover:text-slate-900">
          Home
        </Link>
        <span className="text-sm text-slate-400">Users</span>
        <span className="text-sm text-slate-400">Prompts</span>
        <span className="text-sm text-slate-400">Debriefs</span>
      </div>
      <div className="flex items-center gap-4 text-sm text-slate-600">
        <span>{data?.name ?? data?.email}</span>
        <button
          onClick={handleLogout}
          className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100"
        >
          Logout
        </button>
      </div>
    </nav>
  )
}
```

- [ ] **Step 3: Typecheck**

Run:
```bash
cd frontend && npm run typecheck
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/admin/components/
git commit -m "feat: RequireAdmin guard + AdminNav shell"
```

---

## Task 15: Frontend — Login page

**Files:**
- Create: `frontend/src/admin/pages/Login.tsx`

- [ ] **Step 1: Create Login page**

Create `frontend/src/admin/pages/Login.tsx`:

```typescript
import { FormEvent, useState } from "react"
import { Navigate, useNavigate } from "react-router-dom"
import { useAdminLogin, useAdminMe } from "../api"

export default function Login() {
  const { data: me } = useAdminMe()
  const login = useAdminLogin()
  const navigate = useNavigate()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  if (me) return <Navigate to="/admin" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    try {
      await login.mutateAsync({ email, password })
      navigate("/admin", { replace: true })
    } catch {
      // react-query holds the error; UI reads login.error below
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm space-y-4 rounded-xl bg-white p-8 shadow"
      >
        <h1 className="text-xl font-semibold">Admin login</h1>

        <label className="block">
          <span className="mb-1 block text-sm text-slate-700">Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full rounded border border-slate-300 px-3 py-2"
            autoFocus
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-sm text-slate-700">Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="w-full rounded border border-slate-300 px-3 py-2"
          />
        </label>

        {login.isError && (
          <div className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">
            {login.error?.response?.data?.detail ?? "Login failed"}
          </div>
        )}

        <button
          type="submit"
          disabled={login.isPending}
          className="w-full rounded bg-slate-900 py-2 text-white disabled:bg-slate-400"
        >
          {login.isPending ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  )
}
```

- [ ] **Step 2: Typecheck**

Run:
```bash
cd frontend && npm run typecheck
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/admin/pages/Login.tsx
git commit -m "feat: admin login page"
```

---

## Task 16: Frontend — Home page

**Files:**
- Create: `frontend/src/admin/pages/Home.tsx`

- [ ] **Step 1: Create Home page (minimal shell)**

Create `frontend/src/admin/pages/Home.tsx`:

```typescript
import { useAdminMe } from "../api"

export default function Home() {
  const { data } = useAdminMe()
  return (
    <div className="p-8">
      <h1 className="mb-2 text-2xl font-semibold">Welcome, {data?.name ?? data?.email}</h1>
      <p className="text-slate-600">
        Admin dashboard home. Overview stats land in a later slice.
      </p>
    </div>
  )
}
```

- [ ] **Step 2: Typecheck**

Run:
```bash
cd frontend && npm run typecheck
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/admin/pages/Home.tsx
git commit -m "feat: admin home page shell"
```

---

## Task 17: Frontend — AdminApp + lazy route in App.tsx

**Files:**
- Create: `frontend/src/admin/AdminApp.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create AdminApp**

Create `frontend/src/admin/AdminApp.tsx`:

```typescript
import { Route, Routes } from "react-router-dom"
import AdminNav from "./components/AdminNav"
import RequireAdmin from "./components/RequireAdmin"
import Home from "./pages/Home"
import Login from "./pages/Login"

function Protected({ children }: { children: React.ReactNode }) {
  return (
    <RequireAdmin>
      <div className="min-h-screen bg-white">
        <AdminNav />
        {children}
      </div>
    </RequireAdmin>
  )
}

export default function AdminApp() {
  return (
    <Routes>
      <Route path="login" element={<Login />} />
      <Route path="" element={<Protected><Home /></Protected>} />
      <Route path="*" element={<Protected><Home /></Protected>} />
    </Routes>
  )
}
```

- [ ] **Step 2: Add lazy route to App.tsx**

Modify `frontend/src/App.tsx`. Replace current contents with:

```typescript
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { lazy, Suspense } from "react"
import { BrowserRouter, Route, Routes } from "react-router-dom"
import ActivityDetail from "./pages/ActivityDetail"
import Connect from "./pages/Connect"
import Dashboard from "./pages/Dashboard"
import Home from "./pages/Home"
import Setup from "./pages/Setup"
import Targets from "./pages/Targets"

const AdminApp = lazy(() => import("./admin/AdminApp"))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/connect" element={<Connect />} />
          <Route path="/setup" element={<Setup />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/activities/:id" element={<ActivityDetail />} />
          <Route path="/targets" element={<Targets />} />
          <Route
            path="/admin/*"
            element={
              <Suspense fallback={<div className="p-8">Loading admin…</div>}>
                <AdminApp />
              </Suspense>
            }
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
```

- [ ] **Step 3: Typecheck**

Run:
```bash
cd frontend && npm run typecheck
```

Expected: no errors.

- [ ] **Step 4: Build**

Run:
```bash
cd frontend && npm run build
```

Expected: build succeeds and shows an `admin-*.js` chunk separate from the main bundle.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/admin/AdminApp.tsx frontend/src/App.tsx
git commit -m "feat: lazy-loaded /admin/* routes wired into App.tsx"
```

---

## Task 18: Manual acceptance — login slice end-to-end

This task is **not code** — it verifies the slice works for a real user.

- [ ] **Step 1: Start infrastructure**

Run:
```bash
docker compose up -d
```

Expected: postgres + redis healthy.

- [ ] **Step 2: Ensure migration is applied**

Run:
```bash
cd backend && alembic upgrade head
```

Expected: at `002_admin_dashboard`.

- [ ] **Step 3: Create first admin**

Run:
```bash
cd backend && python -m app.admin.cli create-admin --email=duncan@example.com --name="Duncan"
```

Expected:
```
Created admin: duncan@example.com
Generated password: <random 24ish-char string>
Share out of band. ...
```

Copy the generated password.

- [ ] **Step 4: Start backend**

Run in a separate terminal:
```bash
cd backend && uvicorn app.main:app --reload --port 8000
```

Verify `curl http://localhost:8000/health` returns `{"status":"ok"}`.

- [ ] **Step 5: Start frontend**

Run in a third terminal:
```bash
cd frontend && npm run dev
```

- [ ] **Step 6: Walk through the login flow**

1. Open `http://localhost:5173/admin` in a browser.
2. Expect redirect to `http://localhost:5173/admin/login`.
3. Enter `duncan@example.com` + the generated password, click **Sign in**.
4. Expect redirect to `http://localhost:5173/admin` showing *"Welcome, Duncan"* + top nav.
5. Open browser devtools → Application → Cookies → verify `admin_session` cookie exists with `HttpOnly=true`, `Path=/admin`.
6. Reload the page. Expect the welcome screen still shown (no redirect to login).
7. Click **Logout**. Expect redirect to `/admin/login`. Cookie is gone.
8. Reload `http://localhost:5173/admin` (the protected route). Expect redirect to login.
9. Try login with wrong password. Expect the red error message *"Invalid credentials"*.

- [ ] **Step 7: Verify from DB**

Run:
```bash
docker compose exec postgres psql -U postgres -d stravacoach -c \
  "SELECT email, name, last_login_at IS NOT NULL AS has_logged_in FROM admins; \
   SELECT COUNT(*) FROM admin_sessions WHERE revoked_at IS NULL AND expires_at > now();"
```

Expected after Step 6:
- One admin with `has_logged_in = t`.
- Zero active sessions (because the walkthrough ended with a logout).

- [ ] **Step 8: Record outcome**

If all steps pass, the login slice is done. If any step fails, open a regression note in the spec's **Open Questions / Follow-ups** section describing what broke so Slice 2 work can't start on a bad foundation.

---

## Completion checklist

When all 18 tasks are done:

- [ ] `pytest backend/tests/` passes with ≥ 27 + admin tests green
- [ ] `npm run typecheck` passes on frontend
- [ ] `npm run build` produces a separate `admin-*.js` chunk
- [ ] `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` cycles cleanly
- [ ] Manual acceptance walk-through (Task 18) succeeds end-to-end
- [ ] Slice commit graph is clean; next slice (Users) starts from a green main

When these are green, move on to Slice 2 (Users management) — a new plan document.
