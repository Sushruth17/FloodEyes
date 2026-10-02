"""Depth agent: one photo in, a validated DepthAssessment out.

Used directly by the evaluation harness and wrapped as an ADK step in the report pipeline.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from string import Template

from google.genai import types
from pydantic import ValidationError

from app.config import CityConfig, get_settings
from app.models.depth import DepthAssessment
from app.services.gemini import get_client

PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass
class DepthResult:
    assessment: DepthAssessment | None
    model: str
    prompt_version: str
    latency_ms: int
    input_tokens: int
    output_tokens: int  # includes thinking tokens, which are billed as output
    raw_text: str
    error: str | None = None


def reference_table(city: CityConfig) -> str:
    return "\n".join(
        f"- {r.object}: {r.height_cm:g} cm (typical range {r.range_cm[0]:g}-{r.range_cm[1]:g})"
        for r in city.reference_heights
    )


def build_prompt(prompt_version: str, city: CityConfig, caption: str | None) -> str:
    template = Template((PROMPTS_DIR / f"depth_{prompt_version}.md").read_text())
    return template.substitute(
        city_context=city.city_context,
        reference_table=reference_table(city),
        caption=(caption or "").replace('"', "'"),
    )


async def assess_depth(
    image_jpeg: bytes,
    city: CityConfig,
    caption: str | None = None,
    *,
    model: str | None = None,
    prompt_version: str = "v2",
    thinking_level: str | None = None,
    media_resolution: str | None = None,
) -> DepthResult:
    model = model or get_settings().depth_model
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=DepthAssessment.model_json_schema(),
        thinking_config=(
            types.ThinkingConfig(thinking_level=thinking_level) if thinking_level else None
        ),
        media_resolution=media_resolution,
    )
    contents = [
        types.Part.from_bytes(data=image_jpeg, mime_type="image/jpeg"),
        build_prompt(prompt_version, city, caption),
    ]

    started = time.perf_counter()
    response = await get_client().aio.models.generate_content(
        model=model, contents=contents, config=config
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    usage = response.usage_metadata
    input_tokens = (usage.prompt_token_count or 0) if usage else 0
    output_tokens = (
        ((usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)) if usage else 0
    )
    raw = response.text or ""

    assessment, error = None, None
    try:
        assessment = DepthAssessment.model_validate_json(raw)
    except ValidationError as e:
        error = f"schema_validation: {e.error_count()} errors"

    return DepthResult(
        assessment=assessment,
        model=model,
        prompt_version=prompt_version,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        raw_text=raw,
        error=error,
    )
