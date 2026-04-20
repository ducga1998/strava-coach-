from dataclasses import dataclass

from app.agents.schema import ActivityInput, AthleteContext, RaceTargetContext


@dataclass(frozen=True)
class Fixture:
    id: str
    name: str
    activity: ActivityInput
    context: AthleteContext
    expected_signals: dict


def _vmm_target(weeks_out: int, phase: str) -> RaceTargetContext:
    return RaceTargetContext(
        race_name="VMM",
        weeks_out=weeks_out,
        distance_km=160.0,
        goal_time_sec=None,
        training_phase=phase,
    )


F1 = Fixture(
    id="F1",
    name="Easy Z2 base run",
    activity=ActivityInput(
        activity_name="Morning Easy Run",
        duration_sec=3600,
        distance_m=10000,
        sport_type="Run",
        tss=45.0,
        hr_tss=45.0,
        hr_drift_pct=2.0,
        aerobic_decoupling_pct=4.0,
        ngp_sec_km=330,
        zone_distribution={"z1_pct": 30, "z2_pct": 60, "z3_pct": 5, "z4_pct": 0, "z5_pct": 0},
        elevation_gain_m=80.0,
        cadence_avg=178.0,
    ),
    context=AthleteContext(
        lthr=160, threshold_pace_sec_km=270, tss_30d_avg=55.0,
        acwr=1.0, ctl=52.0, atl=52.0, tsb=0.0,
        training_phase="Base", race_target=_vmm_target(24, "Base"),
    ),
    expected_signals={
        "acwr_band": "green",
        "expected_carb_protein_ratio": "3:1",
        "must_flag_junk_miles": False,
        "must_flag_vert_debt": False,
        "must_recommend_deload": False,
        "must_recommend_volume_increase": False,
    },
)

F2 = Fixture(
    id="F2",
    name="Overreach hard session",
    activity=ActivityInput(
        activity_name="Hard Tempo",
        duration_sec=4500,
        distance_m=12500,
        sport_type="Run",
        tss=110.0,
        hr_tss=110.0,
        hr_drift_pct=9.0,
        aerobic_decoupling_pct=7.0,
        ngp_sec_km=265,
        zone_distribution={"z1_pct": 5, "z2_pct": 25, "z3_pct": 40, "z4_pct": 25, "z5_pct": 5},
        elevation_gain_m=120.0,
        cadence_avg=176.0,
    ),
    context=AthleteContext(
        lthr=162, threshold_pace_sec_km=265, tss_30d_avg=78.0,
        acwr=1.4, ctl=70.0, atl=98.0, tsb=-18.0,
        training_phase="Build", race_target=_vmm_target(16, "Build"),
    ),
    expected_signals={
        "acwr_band": "caution",
        "expected_carb_protein_ratio": "4:1",
        "must_flag_junk_miles": True,
        "must_flag_vert_debt": False,
        "must_recommend_deload": False,
        "must_recommend_volume_increase": False,
    },
)

F3 = Fixture(
    id="F3",
    name="Long mountain decoupling",
    activity=ActivityInput(
        activity_name="Long Mountain Run",
        duration_sec=14400,
        distance_m=22000,
        sport_type="TrailRun",
        tss=165.0,
        hr_tss=165.0,
        hr_drift_pct=6.0,
        aerobic_decoupling_pct=35.0,
        ngp_sec_km=480,
        zone_distribution={"z1_pct": 50, "z2_pct": 35, "z3_pct": 12, "z4_pct": 3, "z5_pct": 0},
        elevation_gain_m=800.0,
        cadence_avg=172.0,
    ),
    context=AthleteContext(
        lthr=158, threshold_pace_sec_km=280, tss_30d_avg=95.0,
        acwr=1.1, ctl=78.0, atl=86.0, tsb=-10.0,
        training_phase="Build", race_target=_vmm_target(12, "Peak"),
    ),
    expected_signals={
        "acwr_band": "green",
        "expected_carb_protein_ratio": "4:1",
        "must_flag_junk_miles": False,
        "must_flag_vert_debt": True,
        "must_recommend_deload": False,
        "must_recommend_volume_increase": False,
    },
)

F4 = Fixture(
    id="F4",
    name="Danger zone — overtrained",
    activity=ActivityInput(
        activity_name="Long Tempo",
        duration_sec=5400,
        distance_m=14000,
        sport_type="Run",
        tss=130.0,
        hr_tss=130.0,
        hr_drift_pct=8.5,
        aerobic_decoupling_pct=12.0,
        ngp_sec_km=270,
        zone_distribution={"z1_pct": 10, "z2_pct": 30, "z3_pct": 45, "z4_pct": 12, "z5_pct": 3},
        elevation_gain_m=200.0,
        cadence_avg=174.0,
    ),
    context=AthleteContext(
        lthr=160, threshold_pace_sec_km=270, tss_30d_avg=80.0,
        acwr=1.6, ctl=65.0, atl=104.0, tsb=-32.0,
        training_phase="Peak", race_target=_vmm_target(8, "Peak"),
    ),
    expected_signals={
        "acwr_band": "injury risk",
        "expected_carb_protein_ratio": "4:1",
        "must_flag_junk_miles": False,
        "must_flag_vert_debt": False,
        "must_recommend_deload": True,
        "must_recommend_volume_increase": False,
    },
)

F5 = Fixture(
    id="F5",
    name="Underload recovery week",
    activity=ActivityInput(
        activity_name="Recovery Jog",
        duration_sec=1800,
        distance_m=5000,
        sport_type="Run",
        tss=30.0,
        hr_tss=30.0,
        hr_drift_pct=1.0,
        aerobic_decoupling_pct=2.0,
        ngp_sec_km=360,
        zone_distribution={"z1_pct": 60, "z2_pct": 35, "z3_pct": 5, "z4_pct": 0, "z5_pct": 0},
        elevation_gain_m=50.0,
        cadence_avg=176.0,
    ),
    context=AthleteContext(
        lthr=160, threshold_pace_sec_km=275, tss_30d_avg=70.0,
        acwr=0.7, ctl=48.0, atl=33.0, tsb=15.0,
        training_phase="Base", race_target=_vmm_target(20, "Base"),
    ),
    expected_signals={
        "acwr_band": "underload",
        "expected_carb_protein_ratio": "3:1",
        "must_flag_junk_miles": False,
        "must_flag_vert_debt": False,
        "must_recommend_deload": False,
        "must_recommend_volume_increase": True,
    },
)

ALL_FIXTURES: tuple[Fixture, ...] = (F1, F2, F3, F4, F5)
_BY_ID = {f.id: f for f in ALL_FIXTURES}


def get_fixture(fixture_id: str) -> Fixture:
    return _BY_ID[fixture_id]
