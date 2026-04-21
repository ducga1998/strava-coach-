"""Regression guard: the two code paths that historically called Strava
outside the webhook flow must not silently come back.

If these tests fail, someone has re-introduced a rate-limit-burning trigger
— audit before "fixing" them.
"""
from __future__ import annotations

import inspect

from app.routers import auth, dashboard


def test_dashboard_router_has_no_backfill_reference() -> None:
    """dashboard.py must not import or call enqueue_backfill.

    This is the canonical 'polling' path we removed. Re-introducing it
    would mean every dashboard refresh can trigger ~21 Strava reads.
    """
    source = inspect.getsource(dashboard)
    assert "enqueue_backfill" not in source, (
        "dashboard.py must not reference enqueue_backfill — it re-introduces "
        "the dashboard-refresh rate-limit-burn bug. See "
        "docs/superpowers/specs/2026-04-21-webhook-only-ingest-design.md."
    )
    assert "BackgroundTasks" not in source, (
        "dashboard.py must not take a BackgroundTasks parameter — the "
        "endpoint is now a pure DB read. If you need background work on "
        "the dashboard, open a new design doc first."
    )


def test_auth_callback_is_the_only_new_backfill_trigger() -> None:
    """auth.py is the ONLY route that should call enqueue_backfill.

    If any other router starts calling it without a design-doc update,
    flag it here.
    """
    source = inspect.getsource(auth)
    assert "enqueue_backfill" in source, (
        "auth.py must import enqueue_backfill — it's the one-time trigger "
        "point for new-athlete history backfill."
    )
    assert "backfilled_at is None" in source, (
        "auth callback must gate the backfill on backfilled_at being null, "
        "otherwise every OAuth reconnect re-fires a backfill."
    )
