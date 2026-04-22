import httpx
import pytest

from app.services.plan_import import (
    InvalidSheetURL,
    SheetFetchError,
    _normalize_sheet_url,  # NEW
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


def test_edit_url_with_gid_query_accepted():
    url = "https://docs.google.com/spreadsheets/d/abc/edit?gid=123"
    assert is_valid_sheet_url(url)


def test_edit_url_with_gid_fragment_accepted():
    url = "https://docs.google.com/spreadsheets/d/abc/edit#gid=123"
    assert is_valid_sheet_url(url)


def test_edit_url_without_gid_accepted():
    url = "https://docs.google.com/spreadsheets/d/abc/edit"
    assert is_valid_sheet_url(url)


def test_edit_url_with_usp_share_accepted():
    url = "https://docs.google.com/spreadsheets/d/abc/edit?usp=sharing"
    assert is_valid_sheet_url(url)


def test_export_format_csv_accepted():
    url = "https://docs.google.com/spreadsheets/d/abc/export?format=csv"
    assert is_valid_sheet_url(url)


def test_export_format_csv_with_gid_accepted():
    url = "https://docs.google.com/spreadsheets/d/abc/export?format=csv&gid=456"
    assert is_valid_sheet_url(url)


def test_export_format_xlsx_rejected():
    url = "https://docs.google.com/spreadsheets/d/abc/export?format=xlsx"
    assert not is_valid_sheet_url(url)


def test_random_docs_path_rejected():
    url = "https://docs.google.com/spreadsheets/d/abc/view"
    assert not is_valid_sheet_url(url)


def test_normalize_pub_url_unchanged():
    url = "https://docs.google.com/spreadsheets/d/abc/pub?output=csv"
    assert _normalize_sheet_url(url) == url


def test_normalize_pub_url_with_gid_unchanged():
    url = "https://docs.google.com/spreadsheets/d/abc/pub?gid=0&single=true&output=csv"
    assert _normalize_sheet_url(url) == url


def test_normalize_export_url_unchanged():
    url = "https://docs.google.com/spreadsheets/d/abc/export?format=csv&gid=5"
    assert _normalize_sheet_url(url) == url


def test_normalize_edit_url_no_gid_to_export():
    url = "https://docs.google.com/spreadsheets/d/abc/edit"
    assert (
        _normalize_sheet_url(url)
        == "https://docs.google.com/spreadsheets/d/abc/export?format=csv"
    )


def test_normalize_edit_url_with_query_gid_to_export():
    url = "https://docs.google.com/spreadsheets/d/abc/edit?gid=123"
    assert (
        _normalize_sheet_url(url)
        == "https://docs.google.com/spreadsheets/d/abc/export?format=csv&gid=123"
    )


def test_normalize_edit_url_with_fragment_gid_to_export():
    url = "https://docs.google.com/spreadsheets/d/abc/edit#gid=123"
    assert (
        _normalize_sheet_url(url)
        == "https://docs.google.com/spreadsheets/d/abc/export?format=csv&gid=123"
    )


def test_normalize_edit_url_with_usp_sharing_to_export():
    url = "https://docs.google.com/spreadsheets/d/abc/edit?usp=sharing"
    assert (
        _normalize_sheet_url(url)
        == "https://docs.google.com/spreadsheets/d/abc/export?format=csv"
    )


def test_normalize_edit_url_with_both_usp_and_gid():
    url = "https://docs.google.com/spreadsheets/d/abc/edit?usp=sharing&gid=42"
    assert (
        _normalize_sheet_url(url)
        == "https://docs.google.com/spreadsheets/d/abc/export?format=csv&gid=42"
    )


@pytest.mark.asyncio
async def test_fetch_converts_edit_url_to_export_before_request():
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, text="date\n2026-04-22\n")

    transport = httpx.MockTransport(handler)
    url = "https://docs.google.com/spreadsheets/d/abc/edit?gid=7"
    await fetch_plan_sheet(url, transport=transport)
    assert captured["url"] == (
        "https://docs.google.com/spreadsheets/d/abc/export?format=csv&gid=7"
    )


@pytest.mark.asyncio
async def test_fetch_leaves_pub_url_untouched():
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, text="date\n2026-04-22\n")

    transport = httpx.MockTransport(handler)
    url = "https://docs.google.com/spreadsheets/d/abc/pub?output=csv"
    await fetch_plan_sheet(url, transport=transport)
    assert captured["url"] == url
