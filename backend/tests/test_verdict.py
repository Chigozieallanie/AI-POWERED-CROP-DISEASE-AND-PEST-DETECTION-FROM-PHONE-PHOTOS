import json
from pathlib import Path

import pytest

from app.verdict import LeafScore, plant_verdict

DATA = json.loads((Path(__file__).parents[2] / "content/verdict_cases.json").read_text())


@pytest.mark.parametrize("case", DATA["cases"], ids=lambda case: case["name"])
def test_shared_verdict_cases(case):
    leaves = [LeafScore(label, score) for label, score in case["leaves"]]
    verdict = plant_verdict(leaves, DATA["thresholds"], DATA["experimental"])
    assert verdict.state == case["state"]
    assert [[f.label, f.certainty, f.leaf_count] for f in verdict.findings] == case["findings"]
