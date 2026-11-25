"""floodcap-ew — River-basin API/Manning flood early-warning & OASIS CAP v1.2 XML engine."""

from floodcap_ew.hydrology import (
    FloodAssessment,
    FloodSeverity,
    RiverCrossSection,
    assess_flood_risk,
    compute_antecedent_precip_index,
    manning_discharge_m3_s,
    render_cap_v12_xml,
)

__version__ = "0.1.0"

__all__ = [
    "FloodAssessment",
    "FloodSeverity",
    "RiverCrossSection",
    "__version__",
    "assess_flood_risk",
    "compute_antecedent_precip_index",
    "manning_discharge_m3_s",
    "render_cap_v12_xml",
]
