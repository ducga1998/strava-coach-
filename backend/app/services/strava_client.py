import asyncio
import logging
import time
from collections.abc import Mapping
from typing import NotRequired, Protocol, TypedDict, cast
from urllib.parse import urlencode

import httpx

from app.config import settings


logger = logging.getLogger(__name__)

STRAVA_BASE_URL = "https://www.strava.com/api/v3"
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STREAM_KEYS = "heartrate,altitude,velocity_smooth,time,latlng,cadence,watts"

# 429 retry policy. 4 attempts with capped exponential backoff covers the
# common case of a short-window burst (15-min limit). A persistent daily-cap
# 429 will still surface as HTTPStatusError after the retries exhaust — that
# case is not recoverable by waiting minutes.
_RETRY_MAX_ATTEMPTS = 4
_RETRY_DEFAULT_BACKOFF_SEC = 5.0
_RETRY_MAX_BACKOFF_SEC = 60.0


def _retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return min(float(retry_after), _RETRY_MAX_BACKOFF_SEC)
        except ValueError:
            pass
    return min(_RETRY_DEFAULT_BACKOFF_SEC * (2 ** attempt), _RETRY_MAX_BACKOFF_SEC)


class StravaAthletePayload(TypedDict, total=False):
    id: int
    firstname: str
    lastname: str
    profile: str
    city: str
    country: str


class StravaTokenPayload(TypedDict):
    access_token: str
    refresh_token: str
    expires_at: int
    athlete: StravaAthletePayload


class StravaRefreshPayload(TypedDict):
    """Token response from refresh_token grant (no athlete object)."""

    access_token: str
    refresh_token: str
    expires_at: int


class StravaActivityPayload(TypedDict, total=False):
    id: int
    name: str
    sport_type: str
    start_date: str
    elapsed_time: int
    moving_time: int
    distance: float
    total_elevation_gain: float
    average_heartrate: float
    max_heartrate: float


class StravaStreamValue(TypedDict):
    data: list[object]


StravaStreamPayload = dict[str, StravaStreamValue]


class StravaClientProtocol(Protocol):
    async def exchange_code(self, code: str) -> StravaTokenPayload:
        raise NotImplementedError

    async def refresh_access_token(self, refresh_token: str) -> StravaRefreshPayload:
        raise NotImplementedError

    async def get_athlete_activities(
        self, access_token: str, per_page: int = 10
    ) -> list[StravaActivityPayload]:
        raise NotImplementedError

    async def get_activity(
        self, access_token: str, activity_id: int
    ) -> StravaActivityPayload:
        raise NotImplementedError

    async def get_activity_streams(
        self, access_token: str, activity_id: int
    ) -> StravaStreamPayload:
        raise NotImplementedError

    async def update_activity_description(
        self, access_token: str, strava_activity_id: int, description: str
    ) -> None:
        raise NotImplementedError


class StravaPayloadError(ValueError):
    pass


class StravaOAuthError(Exception):
    """Strava returned an error for the token request (e.g. bad code, secret, or redirect config)."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def get_authorization_url(state: str) -> str:
    params = {
        "client_id": settings.strava_client_id,
        "redirect_uri": settings.strava_auth_callback_url,
        "response_type": "code",
        "approval_prompt": "auto",
        "scope": "read,activity:read_all,activity:write,profile:read_all",
        "state": state,
    }
    return f"{STRAVA_AUTH_URL}?{urlencode(params)}"


class StravaClient:
    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client

    async def exchange_code(self, code: str) -> StravaTokenPayload:
        data = await self._post_token({"code": code, "grant_type": "authorization_code"})
        return self._parse_token_payload(data)

    async def refresh_access_token(self, refresh_token: str) -> StravaRefreshPayload:
        data = await self._post_token(
            {"refresh_token": refresh_token, "grant_type": "refresh_token"}
        )
        return self._parse_refresh_payload(data)

    async def get_athlete_activities(
        self, access_token: str, per_page: int = 10
    ) -> list[StravaActivityPayload]:
        data = await self._get_json(
            f"{STRAVA_BASE_URL}/athlete/activities",
            access_token,
            {"per_page": str(per_page), "page": "1"},
        )
        if not isinstance(data, list):
            raise StravaPayloadError("athlete activities response must be an array")
        return [cast(StravaActivityPayload, item) for item in data if isinstance(item, dict)]

    async def get_activity(
        self, access_token: str, activity_id: int
    ) -> StravaActivityPayload:
        data = await self._get_json(
            f"{STRAVA_BASE_URL}/activities/{activity_id}", access_token, {}
        )
        if not isinstance(data, dict):
            raise StravaPayloadError("activity response must be an object")
        return cast(StravaActivityPayload, data)

    async def get_activity_streams(
        self, access_token: str, activity_id: int
    ) -> StravaStreamPayload:
        try:
            data = await self._get_json(
                f"{STRAVA_BASE_URL}/activities/{activity_id}/streams",
                access_token,
                {"keys": STREAM_KEYS, "key_by_type": "true"},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return cast(StravaStreamPayload, {})
            raise
        if not isinstance(data, dict):
            raise StravaPayloadError("streams response must be an object")
        return cast(StravaStreamPayload, data)

    async def update_activity_description(
        self, access_token: str, strava_activity_id: int, description: str
    ) -> None:
        await self._request(
            "PUT",
            f"{STRAVA_BASE_URL}/activities/{strava_activity_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"description": description},
        )

    async def _post_token(self, values: Mapping[str, str]) -> object:
        payload = {
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
            **values,
        }
        if self._client is not None:
            response = await self._client.post(STRAVA_TOKEN_URL, data=payload)
        else:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(STRAVA_TOKEN_URL, data=payload)
        if response.status_code >= 400:
            raise StravaOAuthError(_format_strava_token_error(response))
        return response.json()

    async def _get_json(
        self, url: str, access_token: str, params: Mapping[str, str]
    ) -> object:
        response = await self._request(
            "GET", url, headers={"Authorization": f"Bearer {access_token}"}, params=params
        )
        return response.json()

    async def _request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        # Retry on 429 up to _RETRY_MAX_ATTEMPTS times, honouring Retry-After
        # if Strava sends it. Webhook ingestion was silently losing activities
        # when Strava briefly rate-limited the app (200 req/15min short, or
        # 1000 reads/day). With this, transient 429 bursts get absorbed; a
        # hard daily cap still surfaces after the retries exhaust.
        for attempt in range(_RETRY_MAX_ATTEMPTS):
            response = await self._send_once(method, url, **kwargs)
            if response.status_code != 429 or attempt == _RETRY_MAX_ATTEMPTS - 1:
                response.raise_for_status()
                return response
            delay = _retry_delay_seconds(response, attempt)
            logger.warning(
                "Strava 429 on %s %s — retry %d/%d in %.1fs",
                method,
                url,
                attempt + 1,
                _RETRY_MAX_ATTEMPTS - 1,
                delay,
            )
            await asyncio.sleep(delay)
        response.raise_for_status()  # unreachable but keeps the type checker happy
        return response

    async def _send_once(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        if self._client is not None:
            return await self._client.request(method, url, **kwargs)
        async with httpx.AsyncClient(timeout=15.0) as client:
            return await client.request(method, url, **kwargs)

    @staticmethod
    def _parse_token_payload(data: object) -> StravaTokenPayload:
        if not isinstance(data, dict):
            raise StravaPayloadError("token response must be an object")
        athlete = data.get("athlete")
        if not isinstance(athlete, dict):
            raise StravaPayloadError("token response missing athlete")
        if athlete.get("id") is None:
            raise StravaPayloadError("token response athlete missing id")
        access = data.get("access_token")
        refresh = data.get("refresh_token")
        if not isinstance(access, str) or not isinstance(refresh, str) or not access or not refresh:
            raise StravaPayloadError("token response missing access_token or refresh_token")
        expires_at = data.get("expires_at")
        if expires_at is None and data.get("expires_in") is not None:
            try:
                expires_at = int(time.time()) + int(data["expires_in"])
            except (TypeError, ValueError) as exc:
                raise StravaPayloadError("token response has invalid expires_in") from exc
        if expires_at is None:
            raise StravaPayloadError("token response missing expires_at")
        try:
            expires_int = int(expires_at)
        except (TypeError, ValueError) as exc:
            raise StravaPayloadError("token response has invalid expires_at") from exc
        normalized = {
            **data,
            "athlete": athlete,
            "access_token": access,
            "refresh_token": refresh,
            "expires_at": expires_int,
        }
        return cast(StravaTokenPayload, normalized)

    @staticmethod
    def _parse_refresh_payload(data: object) -> StravaRefreshPayload:
        if not isinstance(data, dict):
            raise StravaPayloadError("token response must be an object")
        access = data.get("access_token")
        refresh = data.get("refresh_token")
        if not isinstance(access, str) or not isinstance(refresh, str) or not access or not refresh:
            raise StravaPayloadError("token response missing access_token or refresh_token")
        expires_at = data.get("expires_at")
        if expires_at is None and data.get("expires_in") is not None:
            try:
                expires_at = int(time.time()) + int(data["expires_in"])
            except (TypeError, ValueError) as exc:
                raise StravaPayloadError("token response has invalid expires_in") from exc
        if expires_at is None:
            raise StravaPayloadError("token response missing expires_at")
        try:
            expires_int = int(expires_at)
        except (TypeError, ValueError) as exc:
            raise StravaPayloadError("token response has invalid expires_at") from exc
        return cast(
            StravaRefreshPayload,
            {"access_token": access, "refresh_token": refresh, "expires_at": expires_int},
        )


async def exchange_code(code: str) -> StravaTokenPayload:
    return await StravaClient().exchange_code(code)


async def refresh_access_token(refresh_token: str) -> StravaRefreshPayload:
    return await StravaClient().refresh_access_token(refresh_token)


def _format_strava_token_error(response: httpx.Response) -> str:
    try:
        body = response.json()
        if isinstance(body, dict):
            msg = body.get("message")
            errors = body.get("errors")
            if msg:
                parts: list[str] = [str(msg)]
                if isinstance(errors, list) and errors:
                    parts.append(str(errors))
                return ": ".join(parts)
    except ValueError:
        pass
    reason = response.reason_phrase or "error"
    return f"HTTP {response.status_code} {reason}"
