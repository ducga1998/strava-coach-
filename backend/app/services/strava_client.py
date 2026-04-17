from collections.abc import Mapping
from typing import NotRequired, Protocol, TypedDict, cast
from urllib.parse import urlencode

import httpx

from app.config import settings


STRAVA_BASE_URL = "https://www.strava.com/api/v3"
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STREAM_KEYS = "heartrate,altitude,velocity_smooth,time,latlng,cadence,watts"


class StravaAthletePayload(TypedDict, total=False):
    id: int
    firstname: str
    lastname: str


class StravaTokenPayload(TypedDict):
    access_token: str
    refresh_token: str
    expires_at: int
    athlete: StravaAthletePayload


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

    async def refresh_access_token(self, refresh_token: str) -> StravaTokenPayload:
        raise NotImplementedError

    async def get_activity(
        self, access_token: str, activity_id: int
    ) -> StravaActivityPayload:
        raise NotImplementedError

    async def get_activity_streams(
        self, access_token: str, activity_id: int
    ) -> StravaStreamPayload:
        raise NotImplementedError


class StravaPayloadError(ValueError):
    pass


def get_authorization_url(state: str) -> str:
    params = {
        "client_id": settings.strava_client_id,
        "redirect_uri": settings.strava_auth_callback_url,
        "response_type": "code",
        "approval_prompt": "auto",
        "scope": "read,activity:read_all,profile:read_all",
        "state": state,
    }
    return f"{STRAVA_AUTH_URL}?{urlencode(params)}"


class StravaClient:
    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client

    async def exchange_code(self, code: str) -> StravaTokenPayload:
        data = await self._post_token({"code": code, "grant_type": "authorization_code"})
        return self._parse_token_payload(data)

    async def refresh_access_token(self, refresh_token: str) -> StravaTokenPayload:
        data = await self._post_token(
            {"refresh_token": refresh_token, "grant_type": "refresh_token"}
        )
        return self._parse_token_payload(data)

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
        data = await self._get_json(
            f"{STRAVA_BASE_URL}/activities/{activity_id}/streams",
            access_token,
            {"keys": STREAM_KEYS, "key_by_type": "true"},
        )
        if not isinstance(data, dict):
            raise StravaPayloadError("streams response must be an object")
        return cast(StravaStreamPayload, data)

    async def _post_token(self, values: Mapping[str, str]) -> object:
        payload = {
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
            **values,
        }
        response = await self._request("POST", STRAVA_TOKEN_URL, data=payload)
        return response.json()

    async def _get_json(
        self, url: str, access_token: str, params: Mapping[str, str]
    ) -> object:
        response = await self._request(
            "GET", url, headers={"Authorization": f"Bearer {access_token}"}, params=params
        )
        return response.json()

    async def _request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        if self._client is not None:
            response = await self._client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response

    @staticmethod
    def _parse_token_payload(data: object) -> StravaTokenPayload:
        if not isinstance(data, dict):
            raise StravaPayloadError("token response must be an object")
        if not isinstance(data.get("athlete"), dict):
            raise StravaPayloadError("token response missing athlete")
        return cast(StravaTokenPayload, data)


async def exchange_code(code: str) -> StravaTokenPayload:
    return await StravaClient().exchange_code(code)


async def refresh_access_token(refresh_token: str) -> StravaTokenPayload:
    return await StravaClient().refresh_access_token(refresh_token)
