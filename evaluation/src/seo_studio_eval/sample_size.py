import json
from math import ceil, sqrt
from pathlib import Path
from statistics import NormalDist
from typing import Literal

from pydantic import BaseModel, Field

from .hashing import sha256_file
from .protocol_freeze import ProtocolFreezeContract


class RQ1Sensitivity(BaseModel):
    reference_rate: float
    comparison_rate: float
    independent_claims_per_condition: int
    images_by_icc: dict[str, int]


class RQ2Sensitivity(BaseModel):
    discordant_pair_rate: float
    paired_images_before_reserve: int
    paired_images_with_reserve: int


class RQ3Sensitivity(BaseModel):
    standardized_effect: float
    paired_images_with_reserve: int


class SampleSizeSummary(BaseModel):
    status: Literal["decision_required", "decision_recorded"]
    selected_decision: str | None
    protocol_id: str
    protocol_sha256: str
    alpha_two_sided: float
    target_power: float
    reserve_rate: float
    average_claims_per_output_assumption: float
    rq1: list[RQ1Sensitivity] = Field(min_length=1)
    rq2: list[RQ2Sensitivity] = Field(min_length=1)
    rq3: RQ3Sensitivity
    conclusions: list[str] = Field(min_length=1)
    decision_options: list[str] = Field(min_length=1)


def build_sample_size_sensitivity(
    protocol_path: Path,
    output_path: Path,
) -> tuple[SampleSizeSummary, Path]:
    protocol = ProtocolFreezeContract.model_validate_json(protocol_path.read_text())
    effects = {effect.rq_id: effect.threshold for effect in protocol.meaningful_effects}
    alpha = 0.05
    power = 0.80
    reserve = 0.10
    claims_per_output = 6.0
    z_alpha = NormalDist().inv_cdf(1 - alpha / 2)
    z_power = NormalDist().inv_cdf(power)

    rq1_rows: list[RQ1Sensitivity] = []
    rq1_delta = effects["RQ1"]
    for reference_rate in (0.10, 0.15, 0.20):
        comparison_rate = reference_rate - rq1_delta
        pooled = (reference_rate + comparison_rate) / 2
        claims = ceil(
            (
                z_alpha * sqrt(2 * pooled * (1 - pooled))
                + z_power
                * sqrt(
                    reference_rate * (1 - reference_rate)
                    + comparison_rate * (1 - comparison_rate)
                )
            )
            ** 2
            / rq1_delta**2
        )
        images_by_icc = {
            f"{icc:.2f}": ceil(
                claims * (1 + (claims_per_output - 1) * icc) / claims_per_output * (1 + reserve)
            )
            for icc in (0.05, 0.10, 0.20)
        }
        rq1_rows.append(
            RQ1Sensitivity(
                reference_rate=reference_rate,
                comparison_rate=comparison_rate,
                independent_claims_per_condition=claims,
                images_by_icc=images_by_icc,
            )
        )

    rq2_rows: list[RQ2Sensitivity] = []
    rq2_delta = effects["RQ2"]
    for discordant_rate in (0.15, 0.25, 0.35):
        paired_raw = (
            (
                z_alpha * sqrt(discordant_rate)
                + z_power * sqrt(discordant_rate - rq2_delta**2)
            )
            ** 2
            / rq2_delta**2
        )
        rq2_rows.append(
            RQ2Sensitivity(
                discordant_pair_rate=discordant_rate,
                paired_images_before_reserve=ceil(paired_raw),
                paired_images_with_reserve=ceil(paired_raw * (1 + reserve)),
            )
        )

    rq3_standardized_effect = effects["RQ3"] / 1.0
    rq3_images = ceil(((z_alpha + z_power) / rq3_standardized_effect) ** 2 * (1 + reserve))

    decision_recorded = protocol.dataset.sample_size_approved
    summary = SampleSizeSummary(
        status="decision_recorded" if decision_recorded else "decision_required",
        selected_decision=(
            protocol.dataset.analysis_intent if decision_recorded else None
        ),
        protocol_id=protocol.protocol_id,
        protocol_sha256=sha256_file(protocol_path),
        alpha_two_sided=alpha,
        target_power=power,
        reserve_rate=reserve,
        average_claims_per_output_assumption=claims_per_output,
        rq1=rq1_rows,
        rq2=rq2_rows,
        rq3=RQ3Sensitivity(
            standardized_effect=rq3_standardized_effect,
            paired_images_with_reserve=rq3_images,
        ),
        conclusions=[
            f"The selected {protocol.dataset.primary_claim_images}-image RQ1 population covers the displayed 100- and 120-image low-rate scenarios but not the 160-image high-clustering scenario or the displayed moderate-rate scenarios.",
            f"The selected {protocol.dataset.primary_claim_images}-image controlled RQ2 population reaches the favorable 127-pair scenario but not the higher-discordance scenarios.",
            f"The selected {protocol.dataset.context_ablation_images}-image RQ3 subset reaches the 35-pair planning value under the one-point paired-standard-deviation assumption.",
            "The approved design is estimation-first: effect sizes and confidence intervals are primary, and null findings are not evidence of equivalence when meaningful effects remain compatible with the interval.",
            "These are design sensitivities, not post-hoc power calculations and not evidence of a model effect.",
        ],
        decision_options=[
            "Increase the final and human-annotated populations and resource the additional reviewer burden.",
            "Retain the feasible population but approve a larger minimum meaningful effect before primary output inspection.",
            "Retain the five-point target as estimation-only and explicitly label the study underpowered for confirmatory detection.",
        ],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    return summary, output_path
