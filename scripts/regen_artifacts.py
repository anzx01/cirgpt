"""Regenerate every artifact of all completed designs from stored CircuitIR.

Re-runs the EDA pipeline stages (schematic / simulation / PCB / BOM /
validation / artifacts / cost) against the current toolchain, without
spending AI generation. Per-design failures are reported and skipped.

Usage (from backend/):
    ./venv/Scripts/python.exe ../scripts/regen_artifacts.py [design_id ...]
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.utils.database import SessionLocal  # noqa: E402
from app.services.circuit_service import CircuitService  # noqa: E402
from models import CircuitDesign  # noqa: E402


async def refresh(svc: CircuitService, design: CircuitDesign) -> dict:
    sch = await svc._generate_schematic(design.netlist, design.circuit_ir)
    sim = await svc._simulate_circuit(design.netlist, design.circuit_ir)
    pcb = await svc._generate_pcb(design.netlist, design.circuit_ir)
    bom = await svc._generate_bom(design.netlist, f"Circuit_{design.id}")
    validation = svc._build_validation_report(design.circuit_ir, sim, pcb, sch)
    artifacts = svc._build_artifacts(
        netlist=design.netlist,
        schematic_svg=sch.get("svg"),
        kicad_schematic=sch.get("kicad_schematic"),
        skidl_netlist=sch.get("skidl_netlist"),
        erc_json=sch.get("erc_json"),
        simulation_result=sim.get("results"),
        pcb_layout=pcb.get("layout"),
        bom=bom.get("bom"),
        validation=validation,
    )
    design.schematic_svg = sch.get("svg")
    design.schematic_pages = sch.get("schematic_pages")
    design.simulation_results = sim.get("results")
    design.simulation_status = sim.get("results", {}).get("status")
    design.pcb_layout = pcb.get("layout")
    design.pcb_image = pcb.get("layout", {}).get("visualization")
    design.bom = bom.get("bom")
    design.estimated_cost = bom.get("bom", {}).get("summary", {}).get("total_cost")
    design.validation = validation
    design.artifacts = artifacts
    return {
        "sim": (sim.get("results") or {}).get("status"),
        "pcb_comps": len((pcb.get("layout") or {}).get("components") or []),
        "bom_cost": design.estimated_cost,
    }


async def main() -> None:
    ids = [int(a) for a in sys.argv[1:] if a.isdigit()]
    db = SessionLocal()
    svc = CircuitService(db)
    query = db.query(CircuitDesign).filter(
        CircuitDesign.status == "completed", CircuitDesign.circuit_ir.isnot(None)
    )
    rows = query.filter(CircuitDesign.id.in_(ids)).all() if ids else query.all()
    rows.sort(key=lambda r: r.id)
    print(f"regenerating {len(rows)} designs", flush=True)

    failed = []
    for design in rows:
        try:
            async with asyncio.timeout(300):
                info = await refresh(svc, design)
            db.commit()
            print(f"#{design.id}: sim={info['sim']} pcb={info['pcb_comps']} "
                  f"cost=${info['bom_cost']}", flush=True)
        except Exception as exc:
            db.rollback()
            failed.append((design.id, str(exc)[:120]))
            print(f"#{design.id}: FAILED {str(exc)[:160]}", flush=True)

    print(f"done: {len(rows) - len(failed)} ok, {len(failed)} failed", flush=True)
    for fid, err in failed:
        print(f"  failed #{fid}: {err}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
