import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client(): return TestClient(app)
from app.services.schedule_normalizer import from_weekly_table, resolve

def test_known_code_multiple_days_and_consecutive_slots():
    slots, display, source, warnings = resolve("24M12")
    assert source == "decoded_code" and not warnings
    assert display == "Segunda-feira, 08:00–09:50; Quarta-feira, 08:00–09:50"
    assert len(slots) == 2

def test_multiple_blocks_and_night_shift():
    _, display, source, _ = resolve("35T45 35N1")
    assert source == "decoded_code"
    assert "Terça-feira, 16:00–17:50" in display
    assert "Quinta-feira, 19:00–19:50" in display

def test_unknown_and_missing_are_not_invented():
    assert resolve("35X99")[1:3] == (None, "unresolved")
    assert resolve(None)[1:3] == (None, "unresolved")

def test_weekly_table_precedes_conflicting_code_and_groups_rows():
    table = [["Horários", "Seg", "Ter", "Qua"], ["08:00 - 08:55", "FGA0001", "---", "---"], ["08:55 - 09:50", "FGA0001", "---", "---"]]
    explicit = from_weekly_table(table, {"FGA0001"})["FGA0001"]
    slots, display, source, warnings = resolve("24T45", explicit)
    assert source == "receipt_table"
    assert display == "Segunda-feira, 08:00–09:50"
    assert warnings and slots[0]["source"] == "receipt_table"

def test_manual_discipline_decodes_known_code(client):
    response = client.post("/api/disciplines", json={"code": "FGA0001", "name": "Teste", "schedule_code": "24M12"})
    assert response.status_code == 201
    assert response.json()["schedule_display"] == "Segunda-feira, 08:00–09:50; Quarta-feira, 08:00–09:50"
