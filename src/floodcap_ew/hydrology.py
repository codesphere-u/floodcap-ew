"""Hydrologic API saturation, Manning open-channel stage-discharge & OASIS CAP v1.2 flood alerts."""

from __future__ import annotations

import math
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class FloodSeverity(StrEnum):
    MINOR = "Minor"
    MODERATE = "Moderate"
    SEVERE = "Severe"
    EXTREME = "Extreme"


@dataclass(frozen=True)
class RiverCrossSection:
    """Trapezoidal river-channel geometry for Manning open-channel hydraulics."""

    station_id: str
    basin_name: str
    bottom_width_m: float
    side_slope_z: float  # Horizontal:vertical bank slope (0.0 for rectangular channel)
    bed_slope: float  # Dimensionless S (m/m)
    manning_n: float  # Roughness coefficient (0.030-0.050 for natural rivers)
    bankfull_depth_m: float  # Stage at which river overtops banks
    critical_flood_depth_m: float  # Stage requiring immediate evacuation


@dataclass(frozen=True)
class FloodAssessment:
    station_id: str
    basin_name: str
    stage_m: float
    discharge_m3_s: float
    bankfull_discharge_m3_s: float
    antecedent_precip_index_mm: float
    stage_ratio_to_bankfull: float
    severity: FloodSeverity
    urgency: str  # Future | Expected | Immediate
    certainty: str  # Possible | Likely | Observed
    headline: str
    instruction: str
    sms_160: str


def compute_antecedent_precip_index(
    daily_rain_mm: list[float],
    *,
    decay_k: float = 0.85,
) -> float:
    """Compute Antecedent Precipitation Index API_t = k * API_{t-1} + P_t (mm)."""
    if not 0.0 < decay_k < 1.0:
        raise ValueError("decay_k must be in (0, 1)")
    api = 0.0
    for rain in daily_rain_mm:
        api = decay_k * api + max(0.0, rain)
    return round(api, 2)


def manning_discharge_m3_s(section: RiverCrossSection, depth_m: float) -> float:
    """Compute open-channel discharge Q = (1/n) * A * R^(2/3) * S^(1/2) in m^3/s."""
    if depth_m <= 0.0:
        return 0.0
    if section.manning_n <= 0 or section.bed_slope <= 0 or section.bottom_width_m <= 0:
        raise ValueError("manning_n, bed_slope, and bottom_width_m must be > 0")

    area = (section.bottom_width_m + section.side_slope_z * depth_m) * depth_m
    wetted_perimeter = section.bottom_width_m + 2.0 * depth_m * math.sqrt(1.0 + section.side_slope_z**2)
    hydraulic_radius = area / wetted_perimeter
    q: float = (
        (1.0 / section.manning_n)
        * area
        * float(hydraulic_radius ** (2.0 / 3.0))
        * math.sqrt(section.bed_slope)
    )
    return round(q, 3)


def assess_flood_risk(
    section: RiverCrossSection,
    *,
    current_stage_m: float,
    recent_daily_rain_mm: list[float],
    api_saturation_threshold_mm: float = 85.0,
) -> FloodAssessment:
    """Combine Manning river-stage hydraulics and API soil saturation into an actionable flood alert."""
    q_cur = manning_discharge_m3_s(section, current_stage_m)
    q_bank = manning_discharge_m3_s(section, section.bankfull_depth_m)
    api = compute_antecedent_precip_index(recent_daily_rain_mm)
    ratio = (current_stage_m / section.bankfull_depth_m) if section.bankfull_depth_m > 0 else 0.0

    if current_stage_m >= section.critical_flood_depth_m:
        sev, urg, cert = FloodSeverity.EXTREME, "Immediate", "Observed"
        headline = f"EXTREME FLOOD EMERGENCY: {section.basin_name} ({current_stage_m:.2f}m)"
        instruction = "Evacuate low-lying riverbanks and floodplains immediately to designated high ground."
    elif current_stage_m >= section.bankfull_depth_m:
        sev, urg, cert = FloodSeverity.SEVERE, "Immediate", "Observed"
        headline = f"SEVERE FLOOD WARNING: {section.basin_name} overtopping banks"
        instruction = "Move livestock, grain stores, and families away from river crossings and bridges."
    elif ratio >= 0.80 or (ratio >= 0.65 and api >= api_saturation_threshold_mm):
        sev, urg, cert = FloodSeverity.MODERATE, "Expected", "Likely"
        headline = f"FLOOD WATCH: {section.basin_name} rising with saturated soils (API {api:.0f}mm)"
        instruction = "Prepare emergency kit, monitor river gauge, and avoid crossing swollen streams."
    else:
        sev, urg, cert = FloodSeverity.MINOR, "Future", "Possible"
        headline = f"NORMAL RIVER STATUS: {section.basin_name} within safe channel"
        instruction = "No immediate flood action required; continue routine rainfall monitoring."

    sms = (
        f"FLOOD {sev.value.upper()} {section.basin_name}: Stage {current_stage_m:.1f}m "
        f"(Q={q_cur:.0f}m3/s, API={api:.0f}mm). {instruction}"
    )[:160]

    return FloodAssessment(
        station_id=section.station_id,
        basin_name=section.basin_name,
        stage_m=round(current_stage_m, 2),
        discharge_m3_s=q_cur,
        bankfull_discharge_m3_s=q_bank,
        antecedent_precip_index_mm=api,
        stage_ratio_to_bankfull=round(ratio, 3),
        severity=sev,
        urgency=urg,
        certainty=cert,
        headline=headline,
        instruction=instruction,
        sms_160=sms,
    )


def render_cap_v12_xml(
    assessment: FloodAssessment,
    *,
    sender: str = "alerts@codesphere-u.org",
    area_desc: str | None = None,
) -> str:
    """Serialize a FloodAssessment into a standards-compliant OASIS CAP v1.2 XML alert."""
    ns = "urn:oasis:names:tc:emergency:cap:1.2"
    ET.register_namespace("", ns)
    root = ET.Element(f"{{{ns}}}alert")

    def _sub(parent: ET.Element, tag: str, text: str) -> ET.Element:
        el = ET.SubElement(parent, f"{{{ns}}}{tag}")
        el.text = text
        return el

    _sub(root, "identifier", f"CAP-{assessment.station_id}-{uuid.uuid4().hex[:8]}")
    _sub(root, "sender", sender)
    _sub(root, "sent", datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S+00:00"))
    _sub(root, "status", "Actual")
    _sub(root, "msgType", "Alert")
    _sub(root, "scope", "Public")

    info = ET.SubElement(root, f"{{{ns}}}info")
    _sub(info, "category", "Met")
    _sub(info, "event", "Riverine Flood")
    _sub(info, "urgency", assessment.urgency)
    _sub(info, "severity", assessment.severity.value)
    _sub(info, "certainty", assessment.certainty)
    _sub(info, "headline", assessment.headline)
    _sub(
        info,
        "description",
        (
            f"Station {assessment.station_id} recorded stage {assessment.stage_m}m "
            f"(discharge {assessment.discharge_m3_s} m3/s; API {assessment.antecedent_precip_index_mm} mm)."
        ),
    )
    _sub(info, "instruction", assessment.instruction)

    area = ET.SubElement(info, f"{{{ns}}}area")
    _sub(area, "areaDesc", area_desc or assessment.basin_name)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)
