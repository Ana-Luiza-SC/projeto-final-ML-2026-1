import pytest

from app.services.academic_calculator import (
    calculate_attendance,
    calculate_grade_simulation,
    classify_academic_status,
    classify_attendance_risk,
    classify_grade_risk,
    grade_to_mention,
    normalize_weight,
)


def test_grade_to_mention_boundaries():
    assert grade_to_mention(9.0) == "SS"
    assert grade_to_mention(7.0) == "MS"
    assert grade_to_mention(5.0) == "MM"
    assert grade_to_mention(3.0) == "MI"
    assert grade_to_mention(0.1) == "II"
    assert grade_to_mention(0.0) == "SR"


def test_grade_validation_errors():
    with pytest.raises(ValueError):
        grade_to_mention(10.1)
    with pytest.raises(ValueError):
        grade_to_mention(-0.1)


def test_weight_normalization():
    assert normalize_weight(30) == pytest.approx(0.3)
    assert normalize_weight(0.3) == pytest.approx(0.3)


def test_grade_simulation_core_values():
    result = calculate_grade_simulation(
        [
            {"name": "P1", "weight": 30, "grade": 8.0},
            {"name": "P2", "weight": 0.2, "grade": 6.0},
            {"name": "Final", "weight": 50, "grade": None},
        ],
        target_average=7.0,
    )

    assert result["current_contribution"] == pytest.approx(3.6)
    assert result["completed_weight"] == pytest.approx(0.5)
    assert result["remaining_weight"] == pytest.approx(0.5)
    assert result["partial_average"] == pytest.approx(7.2)
    assert result["required_average_on_remaining"] == pytest.approx(6.8)


def test_grade_risk_low_and_high():
    assert classify_grade_risk(6.0) == "low"
    assert classify_grade_risk(8.1) == "high"


def test_unreachable_target_warning():
    result = calculate_grade_simulation(
        [
            {"name": "P1", "weight": 80, "grade": 1.0},
            {"name": "P2", "weight": 20, "grade": None},
        ],
        target_average=5.0,
    )

    assert result["required_average_on_remaining"] > 10
    assert "Meta inalcançável" in result["warnings"][0]


def test_attendance_by_classes():
    result = calculate_attendance(total_classes=20, missed_classes=4)

    assert result["source"] == "classes"
    assert result["absence_percentage"] == pytest.approx(0.2)
    assert result["frequency"] == pytest.approx(0.8)


def test_attendance_by_class_hours():
    result = calculate_attendance(total_class_hours=60, missed_class_hours=6)

    assert result["source"] == "class_hours"
    assert result["absence_percentage"] == pytest.approx(0.1)
    assert result["frequency"] == pytest.approx(0.9)


def test_attendance_risk_levels():
    assert classify_attendance_risk(0.15) == "low"
    assert classify_attendance_risk(0.20) == "medium"
    assert classify_attendance_risk(0.26) == "high"


def test_attendance_failure_risk_below_75_percent():
    result = calculate_attendance(total_classes=20, missed_classes=6)

    assert result["frequency"] == pytest.approx(0.7)
    assert result["risk_level"] == "high"
    assert result["status"] == "risk_of_failure_by_attendance"


def test_unknown_attendance():
    result = calculate_attendance()

    assert result["status"] == "unknown"
    assert result["frequency"] is None
    assert result["risk_level"] == "unknown"


def test_does_not_assert_final_approval_when_attendance_unknown():
    grade_result = calculate_grade_simulation(
        [{"name": "P1", "weight": 100, "grade": 9.0}],
        target_average=5.0,
    )
    attendance = calculate_attendance()
    status = classify_academic_status(grade_result, attendance)

    assert status["status"] == "insufficient_attendance_data"
    assert "não é possível afirmar aprovação final" in status["message"]

def test_grouped_assessment_89_times_40_percent_times_60_percent():
    result = calculate_grade_simulation([{"name": "mTAI", "grade": 8.9, "group_final_weight": 40, "group_weight": 60, "status": "completed"}])
    assert result["completed_weight"] == pytest.approx(0.24)
    assert result["current_contribution"] == pytest.approx(2.136)
    assert result["partial_average"] == pytest.approx(8.9)
    assert result["remaining_weight"] == pytest.approx(0.76)
    assert result["current_mention"] is None
