import json
import sqlite3

conn = sqlite3.connect("app.db")
cur = conn.cursor()
cur.execute(
    "SELECT id, status, length(circuit_ir), length(schematic_svg), error_message "
    "FROM circuit_designs ORDER BY id DESC LIMIT 6"
)
for r in cur.fetchall():
    print(r)

cur.execute(
    "SELECT id, circuit_ir FROM circuit_designs "
    "WHERE circuit_ir IS NOT NULL AND circuit_ir != '' ORDER BY id DESC LIMIT 1"
)
row = cur.fetchone()
if row:
    raw = row[1]
    ir = json.loads(raw) if isinstance(raw, str) else raw
    with open("/tmp/replay_ir.json", "w", encoding="utf-8") as fh:
        json.dump(ir, fh, ensure_ascii=False)
    print(
        "dumped design",
        row[0],
        "| type:",
        ir.get("circuit_type"),
        "| supported:",
        ir.get("supported"),
        "| components:",
        len(ir.get("components", [])),
    )
else:
    print("NO IR FOUND IN DB")
