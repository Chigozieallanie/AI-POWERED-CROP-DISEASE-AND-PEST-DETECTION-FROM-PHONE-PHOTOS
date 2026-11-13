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


def test_center_square_crop_keeps_centre():
    from PIL import Image

    from app.inference import center_square

    image = Image.new("RGB", (400, 300))
    image.putpixel((200, 150), (255, 0, 0))
    cropped = center_square(image, 0.6)
    assert cropped.size == (180, 180)
    assert cropped.getpixel((90, 90)) == (255, 0, 0)
    assert center_square(image, 1.0).size == (300, 300)
