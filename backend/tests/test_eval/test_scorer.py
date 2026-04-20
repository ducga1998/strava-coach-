from eval.scorer import score_specificity


def test_specificity_all_fields_have_numbers() -> None:
    debrief = {
        "load_verdict": "TSS 110 over 80 average. ACWR 1.4.",
        "technical_insight": "HR drift 9%. Z3 40%.",
        "next_session_action": "60 min Z2, HR < 150.",
        "nutrition_protocol": "60g carb in 45 min.",
        "vmm_projection": "VMM 30h15m, CTL 70.",
    }
    assert score_specificity(debrief) == 3


def test_specificity_three_fields_missing_numbers() -> None:
    debrief = {
        "load_verdict": "Solid effort today.",
        "technical_insight": "Good aerobic work.",
        "next_session_action": "Recover well.",
        "nutrition_protocol": "60g carb in 45 min.",
        "vmm_projection": "VMM 30h15m.",
    }
    assert score_specificity(debrief) == 0


def test_specificity_one_field_missing_number() -> None:
    debrief = {
        "load_verdict": "TSS 110.",
        "technical_insight": "HR drift 9%.",
        "next_session_action": "Recover well.",
        "nutrition_protocol": "60g carb in 45 min.",
        "vmm_projection": "VMM 30h15m.",
    }
    assert score_specificity(debrief) == 2


from eval.scorer import score_no_generics


def test_no_generics_clean_output() -> None:
    debrief = {
        "load_verdict": "TSS 110 over 80 average.",
        "technical_insight": "HR drift 9%.",
        "next_session_action": "60 min Z2.",
        "nutrition_protocol": "60g carb in 45 min.",
        "vmm_projection": "VMM 30h15m.",
    }
    assert score_no_generics(debrief) == 3


def test_no_generics_contains_great_job() -> None:
    debrief = {
        "load_verdict": "Great job today!",
        "technical_insight": "HR drift 9%.",
        "next_session_action": "60 min Z2.",
        "nutrition_protocol": "60g carb.",
        "vmm_projection": "VMM 30h15m.",
    }
    assert score_no_generics(debrief) == 0


def test_no_generics_listen_to_body_anywhere() -> None:
    debrief = {
        "load_verdict": "TSS 110.",
        "technical_insight": "HR drift 9%. Listen to your body next time.",
        "next_session_action": "60 min Z2.",
        "nutrition_protocol": "60g carb.",
        "vmm_projection": "VMM 30h15m.",
    }
    assert score_no_generics(debrief) == 0


from eval.scorer import score_acwr_band


def test_acwr_band_correct_green() -> None:
    debrief = {"load_verdict": "ACWR 1.0 → green band. CTL 52.", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "", "vmm_projection": ""}
    assert score_acwr_band(debrief, expected_band="green") == 3


def test_acwr_band_correct_caution() -> None:
    debrief = {"load_verdict": "ACWR 1.4 → caution. Reduce next.", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "", "vmm_projection": ""}
    assert score_acwr_band(debrief, expected_band="caution") == 3


def test_acwr_band_wrong_label() -> None:
    debrief = {"load_verdict": "ACWR 1.4 → green band.", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "", "vmm_projection": ""}
    assert score_acwr_band(debrief, expected_band="caution") == 0


def test_acwr_band_injury_risk_alias() -> None:
    debrief = {"load_verdict": "ACWR 1.6 — danger zone today.", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "", "vmm_projection": ""}
    assert score_acwr_band(debrief, expected_band="injury risk") == 3


from eval.scorer import score_nutrition_ratio


def test_nutrition_ratio_4to1_for_high_tss() -> None:
    debrief = {"load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "Tỷ lệ 4:1 carb:protein. 80g carb + 20g protein.", "vmm_projection": ""}
    assert score_nutrition_ratio(debrief, tss=120) == 3


def test_nutrition_ratio_3to1_for_low_tss() -> None:
    debrief = {"load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "3:1 ratio: 45g carb + 15g protein.", "vmm_projection": ""}
    assert score_nutrition_ratio(debrief, tss=50) == 3


def test_nutrition_ratio_wrong_for_high_tss() -> None:
    debrief = {"load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "3:1 ratio works fine.", "vmm_projection": ""}
    assert score_nutrition_ratio(debrief, tss=120) == 0


def test_nutrition_ratio_missing_pattern() -> None:
    debrief = {"load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": "Eat phở and drink water.", "vmm_projection": ""}
    assert score_nutrition_ratio(debrief, tss=50) == 0


from eval.scorer import score_vmm_math


def test_vmm_math_within_3h_of_formula() -> None:
    # CTL 70 → multiplier 2.6, threshold_pace 270 sec/km
    # flat = 160000 / (270*2.6) sec * 60 / 60 = ~228 min = 3.8h flat
    # + elevation = (10000/10)*60 = 60000 sec = 16.67h
    # total ≈ 20.4h
    debrief = {"vmm_projection": "VMM 160km projection: 20h30m (trained).", "load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": ""}
    assert score_vmm_math(debrief, ctl=70, threshold_pace_sec_km=270) == 3


def test_vmm_math_within_6h_partial_credit() -> None:
    debrief = {"vmm_projection": "VMM 160km projection: 26h00m.", "load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": ""}
    assert score_vmm_math(debrief, ctl=70, threshold_pace_sec_km=270) == 2


def test_vmm_math_no_time_pattern_zero() -> None:
    debrief = {"vmm_projection": "Insufficient data.", "load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": ""}
    assert score_vmm_math(debrief, ctl=70, threshold_pace_sec_km=270) == 0


def test_vmm_math_extreme_outlier_zero() -> None:
    debrief = {"vmm_projection": "VMM 160km projection: 50h00m.", "load_verdict": "", "technical_insight": "", "next_session_action": "", "nutrition_protocol": ""}
    assert score_vmm_math(debrief, ctl=70, threshold_pace_sec_km=270) == 0


from eval.scorer import score_actionability


def test_actionability_full_prescription() -> None:
    debrief = {"next_session_action": "Easy 60 min Z2 run, HR cap LTHR-15.", "load_verdict": "", "technical_insight": "", "nutrition_protocol": "", "vmm_projection": ""}
    assert score_actionability(debrief) == 3


def test_actionability_missing_hr_cue() -> None:
    debrief = {"next_session_action": "Easy 60 min Z2 run.", "load_verdict": "", "technical_insight": "", "nutrition_protocol": "", "vmm_projection": ""}
    assert score_actionability(debrief) == 2


def test_actionability_only_zone() -> None:
    debrief = {"next_session_action": "Run in Z2.", "load_verdict": "", "technical_insight": "", "nutrition_protocol": "", "vmm_projection": ""}
    assert score_actionability(debrief) == 1


def test_actionability_vague() -> None:
    debrief = {"next_session_action": "Recover well.", "load_verdict": "", "technical_insight": "", "nutrition_protocol": "", "vmm_projection": ""}
    assert score_actionability(debrief) == 0


def test_actionability_vietnamese_duration() -> None:
    debrief = {"next_session_action": "Chạy 75 phút Z2, giữ HR dưới LTHR.", "load_verdict": "", "technical_insight": "", "nutrition_protocol": "", "vmm_projection": ""}
    assert score_actionability(debrief) == 3


from eval.scorer import DeterministicScores, score_deterministic
from eval.fixtures import F2


def test_score_deterministic_full_pass() -> None:
    debrief = {
        "load_verdict": "TSS 110 over 78 avg. ACWR 1.4 → caution.",
        "technical_insight": "HR drift 9%. Z3 40% — junk miles.",
        "next_session_action": "60 min Z2, HR < LTHR-15.",
        "nutrition_protocol": "TSS 110 = 660 kcal. 4:1 ratio: 80g carb + 20g protein in 30 phút.",
        "vmm_projection": "VMM 160km: 20h30m (trained).",
    }
    scores = score_deterministic(debrief, F2)
    assert isinstance(scores, DeterministicScores)
    assert scores.specificity == 3
    assert scores.no_generics == 3
    assert scores.acwr_band == 3
    assert scores.nutrition_ratio == 3
    assert scores.vmm_math == 3
    assert scores.actionability == 3
    assert scores.total == 18
