"""Power-on simulation for design #73 (automatic plant watering controller).

Runs ngspice in batch mode (ngspice_con -b, per https://ngspice.sourceforge.io
/docs.html section 16.2 "Batch mode": execute a SPICE input file and exit).
Component values come verbatim from the design's CircuitIR; the parts the IR
names but cannot simulate directly get engineering models:

- soil sensor module  -> RSOIL SENSE->0, stepped 5k (wet) .. 500k (dry)
- LM393 comparator    -> open-collector behavioural subcircuit (switch)
- logic_level_nmos    -> NMOS model, VTO=2V (gate driven from 12V rail)
- 12V_water_pump      -> 20 ohm coil (~0.6 A at 12 V)
- 1N5819 / LED        -> diode models (schottky / Vf~2V)

Analysis: .op across the RSOIL sweep - one operating point per soil state.
"""
import os
import re
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Project-local ngspice first (START.bat puts Spice64/bin on PATH), then the
# micromamba env it was originally fetched with, then plain PATH lookup.
_CANDIDATES = [
    os.path.join(_REPO, "Spice64", "bin", "ngspice_con.exe"),
    r"G:\tmp\mm\envs\spice\Library\bin\ngspice_con.exe",
    "ngspice_con",
]
NGSPICE = next((c for c in _CANDIDATES if os.path.exists(c) or os.sep not in c), _CANDIDATES[0])

SOIL_VALUES = [5, 15, 25, 35, 45, 60, 80, 110, 150, 200, 300, 400, 500]

DECK = r"""
* automatic plant watering controller - power-on test (values from CircuitIR #73)
.model NML_NMOS NMOS(VTO=2.0 KP=8.0 L=100u W=200m RD=0.15 RS=0.05)
.model DFLY    D(IS=200u N=1.6 RS=0.04 BV=40)
.model DLED    D(IS=1e-12 N=3.4 RS=5)
* LM393 open-collector: OUT pulls low (2R) when IN- > IN+, else floats (pulled up by R4)
.subckt LM393 INP INN OUT VCC VGND
BDRV NCTL VGND V = (V(INN,INP) > 1m) ? 1 : 0
S1  OUT  VGND NCTL VGND SWOC
.model SWOC SW(VT=0.5 VH=0.05 RON=2 ROFF=100MEG)
.ends

V1  VCC 0    DC 12
RS  SENSE 0  __RSOIL__
R1  VCC SENSE 10k
C1  SENSE 0  100n
R2  VCC THRESH 47k
R3  THRESH 0  47k
XU1 SENSE THRESH CTRL VCC 0 LM393
R4  VCC CTRL 10k
R5  CTRL GATE 220
R6  GATE 0   100k
M1  PUMP_NEG GATE 0 0 NML_NMOS
RM1 VCC PUMP_NEG 20
D1  PUMP_NEG VCC DFLY
R7  CTRL LED_A 1k
D2  LED_A 0 DLED

.control
set noaskquit
op
wrdata power_on_result.dat v(sense) v(thresh) v(ctrl) v(gate) v(pump_neg) @rm1[i] @r7[i]
.endc
.end
"""


def run_point(ngspice: str, deck_dir: str, soil_kohm: int) -> list:
    deck = DECK.replace("__RSOIL__", f"{soil_kohm}k")
    deck_path = os.path.join(deck_dir, "power_on_deck.cir")
    result_path = os.path.join(deck_dir, "power_on_result.dat")
    if os.path.exists(result_path):
        os.remove(result_path)
    with open(deck_path, "w", encoding="utf-8") as fh:
        fh.write(deck)
    proc = subprocess.run(
        [ngspice, "-b", deck_path],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120, cwd=deck_dir,
    )
    if not os.path.exists(result_path):
        raise RuntimeError(
            f"no wrdata output for soil={soil_kohm}k, rc={proc.returncode}\n"
            + (proc.stdout or "")[-600:] + (proc.stderr or "")[-600:]
        )
    with open(result_path, encoding="utf-8", errors="replace") as fh:
        parts = fh.read().split()
    values = [float(p) for p in parts]
    # wrdata emits (scale, value) pairs; keep every second entry
    return values[1::2]


def main() -> int:
    deck_dir = os.path.dirname(os.path.abspath(__file__))
    results = []
    for soil_k in SOIL_VALUES:
        vec = run_point(NGSPICE, deck_dir, soil_k)
        results.append((soil_k, vec))

    print(f"ngspice: {NGSPICE}")
    print("power-on: V1 = 12V DC, sweeping soil sensor resistance (wet -> dry)")
    print()
    print(f"{'soilR':>7} {'state':>4} | {'V(sense)':>8} {'V(th)':>5} | {'V(ctrl)':>7} {'V(gate)':>7} | {'V(pump-)':>8} {'I(pump)':>8} {'I(led)':>7}")
    for soil_k, vec in results:
        soil = soil_k * 1000
        sense, thresh, ctrl, gate, pump_neg, i_pump, i_led = vec[:7]
        state = "WET" if sense < thresh else "DRY"
        print(
            f"{soil:>7.0f} {state:>4} | {sense:8.2f} {thresh:5.2f} | "
            f"{ctrl:7.2f} {gate:7.2f} | {pump_neg:8.2f} {abs(i_pump):8.3f} {abs(i_led):7.4f}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
