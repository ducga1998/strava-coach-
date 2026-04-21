import httpx
import pytest

from app.services.plan_import import (
    InvalidSheetURL,
    SheetFetchError,
    fetch_plan_sheet,
    is_valid_sheet_url,
)


def test_valid_sheet_url_accepted():
    url = "https://docs.google.com/spreadsheets/d/abc123/pub?output=csv"
    assert is_valid_sheet_url(url)


def test_valid_sheet_url_with_gid_accepted():
    url = (
        "https://docs.google.com/spreadsheets/d/abc/pub?"
        "gid=0&single=true&output=csv"
    )
    assert is_valid_sheet_url(url)


def test_non_google_host_rejected():
    assert not is_valid_sheet_url("https://example.com/sheet.csv")


def test_http_instead_of_https_rejected():
    url = "http://docs.google.com/spreadsheets/d/abc/pub?output=csv"
    assert not is_valid_sheet_url(url)


def test_output_not_csv_rejected():
    url = "https://docs.google.com/spreadsheets/d/abc/pub?output=xlsx"
    assert not is_valid_sheet_url(url)


@pytest.mark.asyncio
async def test_fetch_rejects_non_google_url():
    with pytest.raises(InvalidSheetURL):
        await fetch_plan_sheet("https://evil.example.com/sheet.csv")


@pytest.mark.asyncio
async def test_fetch_returns_text_on_200():
    csv_body = "date,workout_type\n2026-04-22,easy\n"
    mock_response = httpx.Response(200, text=csv_body)

    async def handler(_request: httpx.Request) -> httpx.Response:
        return mock_response

    transport = httpx.MockTransport(handler)
    url = "https://docs.google.com/spreadsheets/d/abc/pub?output=csv"
    result = await fetch_plan_sheet(url, transport=transport)
    assert result == csv_body


@pytest.mark.asyncio
async def test_fetch_raises_on_non_200():
    mock_response = httpx.Response(403, text="forbidden")

    async def handler(_request: httpx.Request) -> httpx.Response:
        return mock_response

    transport = httpx.MockTransport(handler)
    url = "https://docs.google.com/spreadsheets/d/abc/pub?output=csv"
    with pytest.raises(SheetFetchError, match="403"):
        await fetch_plan_sheet(url, transport=transport)


@pytest.mark.asyncio
async def test_fetch_raises_on_timeout():
    async def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    transport = httpx.MockTransport(handler)
    url = "https://docs.google.com/spreadsheets/d/abc/pub?output=csv"
    with pytest.raises(SheetFetchError, match="timeout"):
        await fetch_plan_sheet(url, transport=transport)
