from datetime import date

import pytest

from app.services.plan_import import ParsedEntry, ParseError, parse_plan_csv


VALID_CSV = """date,workout_type,planned_tss,planned_duration_min,planned_distance_km,planned_elevation_m,description
2026-04-22,long,180,240,35,1200,"4h trail Z2, practice fueling every 30min"
2026-04-23,recovery,40,45,7,50,"flat, HR < LTHR-30"
2026-04-24,rest,,,,,
2026-04-25,interval,95,75,12,150,"20min WU / 6x800m @ 5k pace 2min rest / 15min CD"
"""


def test_valid_csv_parses_all_rows():
    entries, errors = parse_plan_csv(VALID_CSV)
    assert errors == []
    assert len(entries) == 4


def test_blank_numeric_cells_become_none():
    entries, _ = parse_plan_csv(VALID_CSV)
    rest = next(e for e in entries if e.workout_type == "rest")
    assert rest.planned_tss is None
    assert rest.planned_duration_min is None
    assert rest.description is None


def test_dates_parsed_as_date_objects():
    entries, _ = parse_plan_csv(VALID_CSV)
    assert entries[0].date == date(2026, 4, 22)


def test_bad_workout_type_rejects_row_not_file():
    csv = (
        "date,workout_type,planned_tss,planned_duration_min,"
        "planned_distance_km,planned_elevation_m,description\n"
        "2026-04-22,fartlek,60,45,7,,\n"
        "2026-04-23,easy,50,40,6,,\n"
    )
    entries, errors = parse_plan_csv(csv)
    assert len(entries) == 1
    assert entries[0].workout_type == "easy"
    assert len(errors) == 1
    assert errors[0].row_number == 2
    assert "fartlek" in errors[0].reason


def test_bad_date_rejects_row():
    csv = (
        "date,workout_type,planned_tss,planned_duration_min,"
        "planned_distance_km,planned_elevation_m,description\n"
        "next monday,easy,,,,,\n"
    )
    entries, errors = parse_plan_csv(csv)
    assert entries == []
    assert len(errors) == 1
    assert "date" in errors[0].reason.lower()


def test_non_numeric_in_numeric_cell_rejects_row():
    csv = (
        "date,workout_type,planned_tss,planned_duration_min,"
        "planned_distance_km,planned_elevation_m,description\n"
        "2026-04-22,easy,abc,45,7,,\n"
    )
    entries, errors = parse_plan_csv(csv)
    assert entries == []
    assert len(errors) == 1
    assert "planned_tss" in errors[0].reason


def test_missing_header_column_raises():
    csv = "date,workout_type\n2026-04-22,easy\n"
    with pytest.raises(ValueError, match="missing required column"):
        parse_plan_csv(csv)


def test_extra_trailing_columns_ignored():
    csv = (
        "date,workout_type,planned_tss,planned_duration_min,"
        "planned_distance_km,planned_elevation_m,description,extra1,extra2\n"
        "2026-04-22,easy,50,40,6,,note,junk1,junk2\n"
    )
    entries, errors = parse_plan_csv(csv)
    assert len(entries) == 1
    assert errors == []


def test_description_truncated_at_1000_chars():
    long_desc = "a" * 1500
    csv = (
        "date,workout_type,planned_tss,planned_duration_min,"
        "planned_distance_km,planned_elevation_m,description\n"
        f"2026-04-22,easy,50,40,6,,\"{long_desc}\"\n"
    )
    entries, _ = parse_plan_csv(csv)
    assert len(entries[0].description) == 1000


def test_workout_type_lowercased():
    csv = (
        "date,workout_type,planned_tss,planned_duration_min,"
        "planned_distance_km,planned_elevation_m,description\n"
        "2026-04-22,LONG,180,240,35,1200,hi\n"
    )
    entries, _ = parse_plan_csv(csv)
    assert entries[0].workout_type == "long"


def test_duplicate_dates_both_kept_in_output():
    # Dedupe happens in the upsert step, not the parser.
    csv = (
        "date,workout_type,planned_tss,planned_duration_min,"
        "planned_distance_km,planned_elevation_m,description\n"
        "2026-04-22,easy,50,,,,\n"
        "2026-04-22,tempo,100,,,,\n"
    )
    entries, errors = parse_plan_csv(csv)
    assert len(entries) == 2
    assert errors == []
