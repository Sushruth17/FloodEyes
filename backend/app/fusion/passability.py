"""Deterministic passability rules. The model estimates depth; code decides safety."""

from app.config import CityConfig
from app.models.depth import BANDS, VEHICLE_CLASSES


def effective_band(band: str, water_flow: str) -> str:
    """Moving water is treated as one band deeper."""
    if band not in BANDS:
        return band
    if water_flow == "moving":
        return BANDS[min(BANDS.index(band) + 1, len(BANDS) - 1)]
    return band


def passability_for(band: str, water_flow: str, city: CityConfig) -> dict[str, str]:
    eff = effective_band(band, water_flow)
    if eff not in city.passability:
        return {v: "unknown" for v in VEHICLE_CLASSES}
    return {v: city.passability[eff][v] for v in VEHICLE_CLASSES}


def car_passable(band: str, water_flow: str, city: CityConfig) -> bool | None:
    """Binary car passability used by the go/no-go metric. 'caution' counts as passable."""
    verdict = passability_for(band, water_flow, city)["car"]
    if verdict == "unknown":
        return None
    return verdict != "no"
