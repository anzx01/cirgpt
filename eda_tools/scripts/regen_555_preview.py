"""Regenerate the 555 blinker schematic preview.

Builds the canonical blinker CircuitIR (ai_service rules generator, 9V/1Hz)
and drives the MCP authoring path, so label-placement changes can be
re-rendered and eyeballed against the same circuit.

Usage (eda_tools venv python):
    python eda_tools/scripts/regen_555_preview.py [out_svg]
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
AI_SERVICE = ROOT.parent / "ai_service"
if str(AI_SERVICE) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE))

from nlp.circuit_ir import _timer_555_ir  # noqa: E402
from mcp_schematic import generate_kicad_artifacts_via_mcp  # noqa: E402


async def main() -> int:
    out_svg = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "sch_555_preview.svg"
    ir = _timer_555_ir("9V 1Hz")
    result = await generate_kicad_artifacts_via_mcp(ir)
    svg = Path(result["paths"]["svg"])
    out_svg.write_text(svg.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    print(f"svg: {svg} -> {out_svg}")
    print("erc:", result["erc_summary"].get("error_count"), "errors,",
          result["erc_summary"].get("warning_count"), "warnings")
    print("workdir:", result["working_directory"])
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
