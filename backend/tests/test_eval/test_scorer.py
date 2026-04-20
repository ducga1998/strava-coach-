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
