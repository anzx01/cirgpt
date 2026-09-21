import json
import sqlite3
import sys

conn = sqlite3.connect("app.db")
cur = conn.cursor()
cur.execute(
    "SELECT id, description, status, progress, current_step, error_message, "
    "circuit_ir, parsed_requirements, length(schematic_svg) "
    "FROM circuit_designs WHERE id=?",
    (sys.argv[1] if len(sys.argv) > 1 else "72",),
)
row = cur.fetchone()
if not row:
    print("design not found")
    raise SystemExit
(_id, desc, status, progress, step, err, ir_raw, req_raw, svg_len) = row
print("description :", desc)
print("status      :", status, "| progress:", progress, "| step:", step)
print("error       :", err)
print("svg_len     :", svg_len)

ir = None
if ir_raw:
    ir = json.loads(ir_raw) if isinstance(ir_raw, str) else ir_raw
    print("\n--- CircuitIR ---")
    print("circuit_type:", ir.get("circuit_type"), "| supported:", ir.get("supported"))
    comps = ir.get("components", [])
    print("components  :", len(comps))
    for c in comps:
        print(
            "  -", c.get("ref"), "|", c.get("type"), "|", c.get("value"),
            "| subsystem:", c.get("subsystem"), "| nodes:", c.get("nodes"),
        )
    nets = ir.get("nets", [])
    print("nets        :", len(nets))

if req_raw:
    req = json.loads(req_raw) if isinstance(req_raw, str) else req_raw
    print("\n--- parsed_requirements (truncated) ---")
    print(json.dumps(req, ensure_ascii=False)[:800])
