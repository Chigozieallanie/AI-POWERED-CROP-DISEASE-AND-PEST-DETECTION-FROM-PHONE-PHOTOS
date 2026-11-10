"""Plant verdict rules from section 5.2 of the design.

The app has a Dart copy of these rules. Both must pass content/verdict_cases.json.
"""

from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

HEALTHY = "healthy"
MIN_LEAVES_FOR_CONFIDENCE = 3


@dataclass(frozen=True)
class LeafScore:
    label: str
    score: float


@dataclass(frozen=True)
class Finding:
    label: str
    certainty: str
    leaf_count: int
    experimental: bool


@dataclass(frozen=True)
class PlantVerdict:
    state: str
    accepted_leaves: int
    findings: list[Finding]


def _certainty(count: int, accepted: int, experimental: bool) -> str:
    if count == 1 or accepted < MIN_LEAVES_FOR_CONFIDENCE:
        return "weak"
    if not experimental and count >= 3 and count * 2 >= accepted:
        return "very_likely"
    return "likely"


def plant_verdict(
    leaves: Sequence[LeafScore],
    thresholds: Mapping[str, float],
    experimental: Collection[str] = (),
) -> PlantVerdict:
    accepted = len(leaves)
    # A label with no threshold never counts, so a bad model card fails safe.
    counts = Counter(
        leaf.label for leaf in leaves if leaf.score >= thresholds.get(leaf.label, float("inf"))
    )

    findings = [
        Finding(label, _certainty(count, accepted, label in experimental), count, label in experimental)
        for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if label != HEALTHY
    ]
    if findings:
        state = (
            "problem_found"
            if any(finding.certainty != "weak" for finding in findings)
            else "weak_evidence"
        )
        return PlantVerdict(state, accepted, findings)
    if accepted >= MIN_LEAVES_FOR_CONFIDENCE and counts[HEALTHY] == accepted:
        return PlantVerdict("healthy", accepted, [])
    return PlantVerdict("not_sure", accepted, [])
