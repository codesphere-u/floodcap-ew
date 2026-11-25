"""CLI for floodcap-ew."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from floodcap_ew.hydrology import RiverCrossSection, assess_flood_risk, render_cap_v12_xml


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="floodcap-ew",
        description="River-basin API/Manning flood early-warning & OASIS CAP v1.2 XML alert CLI.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_demo = sub.add_parser("demo", help="Simulate River Nyamwamba flash-flood assessment & CAP v1.2 XML")
    p_demo.add_argument("--xml", action="store_true", help="Output CAP v1.2 XML instead of JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        section = RiverCrossSection(
            station_id="UG-NYAMWAMBA-01",
            basin_name="River Nyamwamba (Kasese)",
            bottom_width_m=14.0,
            side_slope_z=1.5,
            bed_slope=0.004,
            manning_n=0.038,
            bankfull_depth_m=3.2,
            critical_flood_depth_m=4.0,
        )
        assessment = assess_flood_risk(
            section,
            current_stage_m=4.15,
            recent_daily_rain_mm=[12.0, 25.0, 40.0, 68.0, 95.0],
        )
        if args.xml:
            print(render_cap_v12_xml(assessment))
        else:
            print(
                json.dumps(
                    {
                        "station_id": assessment.station_id,
                        "severity": assessment.severity.value,
                        "discharge_m3_s": assessment.discharge_m3_s,
                        "api_mm": assessment.antecedent_precip_index_mm,
                        "headline": assessment.headline,
                        "sms_160": assessment.sms_160,
                    },
                    indent=2,
                )
            )
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
