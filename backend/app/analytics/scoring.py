from __future__ import annotations
from dataclasses import dataclass

WEIGHTS = {"financial_quality": .20, "growth": .20, "valuation": .20, "balance_sheet": .15, "business_quality": .15, "risk": .10}
METHODOLOGY_VERSION = "v1.0"


def clamp(score: float) -> float:
    return max(0.0, min(10.0, float(score)))


@dataclass(frozen=True)
class ScoreCard:
    financial_quality: float
    growth: float
    valuation: float
    balance_sheet: float
    business_quality: float
    risk: float

    @property
    def overall(self) -> float:
        return round(sum(clamp(getattr(self, key)) * weight for key, weight in WEIGHTS.items()), 2)

    def as_dict(self) -> dict:
        return {**{key: clamp(getattr(self, key)) for key in WEIGHTS}, "overall_score": self.overall, "methodology_version": METHODOLOGY_VERSION,
                "methodology": "0-10 factor rules; business quality/risk inputs are documented rule-based assessments."}
