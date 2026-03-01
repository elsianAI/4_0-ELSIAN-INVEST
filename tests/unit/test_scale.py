"""Tests for ScaleCascade."""

from elsian.normalize.scale import ScaleCascade, detect_scale_from_text


def test_detect_thousands():
    assert detect_scale_from_text("in thousands") == "thousands"


def test_detect_millions():
    assert detect_scale_from_text("in millions") == "millions"
    assert detect_scale_from_text("$M") == "millions"


def test_detect_billions():
    assert detect_scale_from_text("in billions") == "billions"


def test_detect_none():
    assert detect_scale_from_text("some random text") is None


def test_cascade_raw_notes_wins():
    sc = ScaleCascade()
    scale, conf = sc.infer(raw_notes="amounts in thousands")
    assert scale == "thousands"
    assert conf == "high"


def test_cascade_header_second():
    sc = ScaleCascade()
    scale, conf = sc.infer(raw_notes="", header="$M table header")
    assert scale == "millions"
    assert conf == "high"


def test_cascade_preflight_third():
    sc = ScaleCascade()
    scale, conf = sc.infer(preflight_scale="millions")
    assert scale == "millions"
    assert conf == "medium"


def test_cascade_fallback():
    sc = ScaleCascade()
    scale, conf = sc.infer()
    assert scale == "raw"
    assert conf == "low"
