"""Structured output contract for the depth agent.

Kept deliberately flat: Gemini structured output supports a subset of JSON Schema.
Bounding boxes follow Gemini's convention: [ymin, xmin, ymax, xmax] normalised to 0-1000.
"""

from typing import Literal

from pydantic import BaseModel, Field

DepthBand = Literal["lt15", "15to30", "30to60", "gt60", "insufficient_evidence"]
BANDS: tuple[str, ...] = ("lt15", "15to30", "30to60", "gt60")
VehicleClass = Literal["two_wheeler", "car", "ambulance", "bus"]
VEHICLE_CLASSES: tuple[str, ...] = ("two_wheeler", "car", "ambulance", "bus")
Passability = Literal["yes", "caution", "no", "unknown"]


class ReferenceObject(BaseModel):
    type: str = Field(description="Object name, matching the reference table where possible")
    known_height_cm: float = Field(description="Height of the reference feature from the road")
    box_2d: list[int] = Field(description="[ymin, xmin, ymax, xmax] normalised 0-1000")
    submerged_fraction: float = Field(
        description="Fraction of the reference feature's height that is under water, 0-1"
    )
    depth_estimate_cm: float = Field(description="Water depth implied by this object alone")
    note: str = Field(description="Short reasoning, e.g. 'water reaches hub centre'")


class DepthAssessment(BaseModel):
    is_flood_scene: bool = Field(
        description="True if the photo shows standing or moving water on a road or street"
    )
    reference_objects: list[ReferenceObject]
    waterline_box_2d: list[int] | None = Field(
        default=None, description="Box around the clearest visible waterline, 0-1000"
    )
    depth_cm_min: float | None = None
    depth_cm_max: float | None = None
    depth_band: DepthBand
    confidence: float = Field(
        description="0-1; lower when reference objects disagree or are unclear"
    )
    water_flow: Literal["still", "moving", "unknown"]
    explanation: str = Field(description="At most two plain-language sentences")
    lighting: Literal["day", "dusk", "night", "unknown"]
    rain_visible: bool
