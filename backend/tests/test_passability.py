from app.config import load_city
from app.fusion.passability import car_passable, effective_band, passability_for

CITY = load_city("blr")


def test_still_water_bands():
    assert passability_for("lt15", "still", CITY)["car"] == "yes"
    assert passability_for("15to30", "still", CITY)["car"] == "caution"
    assert passability_for("30to60", "still", CITY)["car"] == "no"
    assert passability_for("30to60", "still", CITY)["bus"] == "caution"
    assert passability_for("15to30", "still", CITY)["two_wheeler"] == "no"


def test_moving_water_is_one_band_deeper():
    assert effective_band("15to30", "moving") == "30to60"
    assert effective_band("gt60", "moving") == "gt60"
    assert passability_for("15to30", "moving", CITY)["car"] == "no"


def test_car_passable_binary():
    assert car_passable("15to30", "still", CITY) is True  # caution counts as passable
    assert car_passable("30to60", "unknown", CITY) is False
    assert car_passable("insufficient_evidence", "unknown", CITY) is None


def test_reference_table_loads():
    assert len(CITY.reference_heights) >= 15
