"""Tests for API soil saturation, Manning channel discharge, OASIS CAP v1.2 XML & CLI."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import pytest

from floodcap_ew import (
    FloodSeverity,
    RiverCrossSection,
    assess_flood_risk,
    compute_antecedent_precip_index,
    manning_discharge_m3_s,
    render_cap_v12_xml,
)
from floodcap_ew.cli import main as cli_main


def test_manning_discharge_and_api_decay_and_cap_v12_xml() -> None:
    # Rectangular channel: b=10m, d=2m, z=0 -> A=20, P=14, R=10/7, n=0.04, S=0.0025 (sqrt=0.05)
    rect = RiverCrossSection("ST-1", "Test Basin", 10.0, 0.0, 0.0025, 0.04, 3.0, 3.8)
    q = manning_discharge_m3_s(rect, 2.0)
    assert 31.0 <= q <= 32.5

    api = compute_antecedent_precip_index([50.0, 0.0], decay_k=0.8)
    assert api == 40.0

    extreme = assess_flood_risk(rect, current_stage_m=4.0, recent_daily_rain_mm=[30.0, 60.0, 80.0])
    assert extreme.severity == FloodSeverity.EXTREME
    assert len(extreme.sms_160) <= 160 and extreme.sms_160.isascii()

    xml_str = render_cap_v12_xml(extreme)
    root = ET.fromstring(xml_str)
    assert root.tag == "{urn:oasis:names:tc:emergency:cap:1.2}alert"
    assert "Extreme" in xml_str


def test_cli_demo_json_and_xml(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["demo"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["severity"] == "Extreme"
    assert cli_main(["demo", "--xml"]) == 0
    xml_out = capsys.readouterr().out
    assert "urn:oasis:names:tc:emergency:cap:1.2" in xml_out
