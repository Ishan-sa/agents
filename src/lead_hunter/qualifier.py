from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .config import Thresholds
from .models import Business, Tier

Verdict = Literal["qualify", "reject"]


@dataclass(frozen=True)
class QualifyResult:
    verdict: Verdict
    tier: Tier | None
    reason: str


def qualify(business: Business, site_score: int) -> QualifyResult:
    if business.permanently_closed:
        return QualifyResult("reject", None, "business permanently closed")

    if business.maps_reviews < Thresholds.REVIEWS_DEAD_BELOW:
        return QualifyResult(
            "reject", None,
            f"only {business.maps_reviews} reviews — likely dead or fake",
        )

    if business.maps_rating < Thresholds.RATING_REJECT_BELOW:
        return QualifyResult(
            "reject", None,
            f"rating {business.maps_rating:.1f} too low — would hurt association",
        )

    if site_score <= Thresholds.SITE_SCORE_REJECT_MAX:
        return QualifyResult(
            "reject", None,
            f"site already good (score {site_score}) — not a fit",
        )

    if business.maps_reviews < Thresholds.REVIEWS_MIN:
        return QualifyResult(
            "reject", None,
            f"only {business.maps_reviews} reviews — below minimum viability",
        )

    is_hot = (
        site_score >= Thresholds.SITE_SCORE_HOT_MIN
        and business.maps_rating >= Thresholds.RATING_MIN
    )
    tier: Tier = "hot" if is_hot else "warm"
    return QualifyResult(
        "qualify", tier,
        f"site_score={site_score}, reviews={business.maps_reviews}, rating={business.maps_rating:.1f}",
    )
