"""
KiCad/SKiDL artifact generation from CircuitIR.

The EDA service lives in this repository on G: during local development while
SKiDL is installed in the system Python on C:. SKiDL records script source
paths and can fail when it tries to make C:/G: paths relative, so this module
runs a small generator script from a real temporary directory on C: and returns
the generated KiCad artifacts as JSON.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_KICAD_ROOT = Path(r"G:\Program Files\KiCad\10.0")
DEFAULT_SYSTEM_PYTHON = Path(r"C:\Python313\python.exe")


class KiCadArtifactError(RuntimeError):
    """Raised when KiCad/SKiDL artifacts cannot be generated."""


def generate_kicad_artifacts(ir: Dict[str, Any]) -> Dict[str, Any]:
    """Generate KiCad schematic, SVG, SKiDL netlist, and ERC report."""
    if not ir.get("supported", False):
        raise KiCadArtifactError("Unsupported CircuitIR cannot be exported to KiCad")

    if ir.get("circuit_type") not in {
        "led_current_limiter",
        "capacitor_discharge_led",
        "rc_low_pass_filter",
        "555_timer_blinker",
        "opamp_inverting",
        "opamp_non_inverting",
    }:
        raise KiCadArtifactError(f"Unsupported CircuitIR type for KiCad export: {ir.get('circuit_type')}")

    python_exe = _find_python_with_skidl()
    kicad_root, kicad_cli = _find_kicad()

    work_root = Path(tempfile.gettempdir()) / "cirgpt_kicad"
    work_root.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="job_", dir=str(work_root)))
    script_path = work_dir / "generate_cirgpt_kicad.py"
    input_path = work_dir / "circuit_ir.json"
    output_path = work_dir / "result.json"

    input_path.write_text(json.dumps(ir), encoding="utf-8")
    script_path.write_text(_generator_script(), encoding="utf-8")

    env = os.environ.copy()
    env.update(_kicad_env(kicad_root, kicad_cli))
    env["PYTHONUTF8"] = "1"

    proc = subprocess.run(
        [str(python_exe), str(script_path), str(input_path), str(output_path)],
        cwd=str(work_dir),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )

    if proc.returncode != 0 or not output_path.exists():
        message = proc.stderr.strip() or proc.stdout.strip() or "KiCad/SKiDL generation failed"
        raise KiCadArtifactError(message)

    result = json.loads(output_path.read_text(encoding="utf-8"))
    if not result.get("success"):
        raise KiCadArtifactError(result.get("error", "KiCad/SKiDL generation failed"))

    result["generator"] = "skidl+kicad-cli"
    result["toolchain"] = {
        "python": str(python_exe),
        "kicad_root": str(kicad_root),
        "kicad_cli": str(kicad_cli),
        **result.get("toolchain", {}),
    }
    result["working_directory"] = str(work_dir)
    result["stdout"] = proc.stdout
    result["stderr"] = proc.stderr
    return result


def detect_kicad_toolchain() -> Dict[str, Any]:
    """Return local KiCad/SKiDL availability details for health checks."""
    details: Dict[str, Any] = {
        "skidl": {"status": "missing"},
        "kicad_cli": {"status": "missing"},
        "symbol_libraries": {"status": "missing"},
    }

    python_exe = _candidate_python_with_skidl()
    if python_exe:
        probe = subprocess.run(
            [
                str(python_exe),
                "-c",
                "import importlib.metadata; print(importlib.metadata.version('skidl'))",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        if probe.returncode == 0:
            details["skidl"] = {
                "status": "ok",
                "python": str(python_exe),
                "version": probe.stdout.strip(),
            }

    try:
        kicad_root, kicad_cli = _find_kicad()
        version = subprocess.run(
            [str(kicad_cli), "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        details["kicad_cli"] = {
            "status": "ok" if version.returncode == 0 else "error",
            "path": str(kicad_cli),
            "version": version.stdout.strip() or version.stderr.strip(),
        }
        symbol_dir = kicad_root / "share" / "kicad" / "symbols"
        required = ["Device.kicad_sym", "Timer.kicad_sym", "power.kicad_sym", "Switch.kicad_sym"]
        missing = [name for name in required if not (symbol_dir / name).exists()]
        details["symbol_libraries"] = {
            "status": "ok" if not missing else "missing",
            "path": str(symbol_dir),
            "missing": missing,
        }
    except Exception as exc:
        details["kicad_cli"] = {"status": "missing", "message": str(exc)}

    statuses = [item.get("status") for item in details.values()]
    details["status"] = "ok" if all(status == "ok" for status in statuses) else "degraded"
    return details


def _find_python_with_skidl() -> Path:
    python_exe = _candidate_python_with_skidl()
    if python_exe:
        return python_exe
    raise KiCadArtifactError(
        "SKiDL is not importable. Install SKiDL into system Python or set SKIDL_PYTHON."
    )


def _candidate_python_with_skidl() -> Optional[Path]:
    candidates: List[Path] = []
    env_python = os.environ.get("SKIDL_PYTHON")
    if env_python:
        candidates.append(Path(env_python))
    candidates.extend([
        DEFAULT_SYSTEM_PYTHON,
        Path(sys.executable),
    ])

    seen = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if not candidate.exists() and candidate.name.endswith(".exe"):
            continue
        try:
            probe = subprocess.run(
                [str(candidate), "-c", "import skidl"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            )
            if probe.returncode == 0:
                return candidate
        except OSError:
            continue
    return None


def _find_kicad() -> Tuple[Path, Path]:
    env_cli = os.environ.get("KICAD_CLI")
    if env_cli:
        cli = Path(env_cli)
        if cli.exists():
            return _root_from_cli(cli), cli

    env_root = os.environ.get("KICAD_ROOT")
    roots = [Path(env_root)] if env_root else []
    roots.append(DEFAULT_KICAD_ROOT)
    for root in roots:
        cli = root / "bin" / "kicad-cli.exe"
        if cli.exists():
            return root, cli

    which = shutil.which("kicad-cli")
    if which:
        cli = Path(which)
        return _root_from_cli(cli), cli

    raise KiCadArtifactError("KiCad CLI not found. Set KICAD_ROOT or KICAD_CLI.")


def _root_from_cli(cli: Path) -> Path:
    return cli.resolve().parents[1]


def _kicad_env(kicad_root: Path, kicad_cli: Path) -> Dict[str, str]:
    symbol_dir = kicad_root / "share" / "kicad" / "symbols"
    footprint_dir = kicad_root / "share" / "kicad" / "footprints"
    env = {
        "KICAD_ROOT": str(kicad_root),
        "KICAD_CLI": str(kicad_cli),
        "KICAD_SYMBOL_DIR": str(symbol_dir),
        "KICAD_FOOTPRINT_DIR": str(footprint_dir),
        "PATH": str(kicad_root / "bin") + os.pathsep + os.environ.get("PATH", ""),
    }
    for version in ("6", "7", "8", "9", "10"):
        env[f"KICAD{version}_SYMBOL_DIR"] = str(symbol_dir)
        env[f"KICAD{version}_FOOTPRINT_DIR"] = str(footprint_dir)
    return env


def _generator_script() -> str:
    return textwrap.dedent(
        r'''
        from __future__ import annotations

        import json
        import os
        import subprocess
        import sys
        from pathlib import Path

        from skidl import (
            KICAD9,
            POWER,
            Part,
            Net,
            ERC,
            generate_netlist,
            generate_schematic,
            reset,
            set_default_tool,
        )


        RES_FP = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal"
        CAP_FP = "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm"
        CPOL_FP = "Capacitor_THT:CP_Radial_D5.0mm_P2.00mm"
        LED_FP = "LED_THT:LED_D5.0mm"
        DIP8_FP = "Package_DIP:DIP-8_W7.62mm"
        SW_FP = "Button_Switch_THT:SW_PUSH_6mm"
        TP_FP = "TestPoint:TestPoint_THTPad_D1.5mm_Drill0.7mm"


        def main() -> int:
            input_path = Path(sys.argv[1])
            output_path = Path(sys.argv[2])
            try:
                ir = json.loads(input_path.read_text(encoding="utf-8"))
                result = generate(ir, output_path.parent)
                output_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                return 0
            except Exception as exc:
                output_path.write_text(
                    json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False),
                    encoding="utf-8",
                )
                return 1


        def generate(ir, work_dir: Path):
            setup_skidl()
            circuit_type = ir.get("circuit_type")
            builders = {
                "led_current_limiter": build_led,
                "capacitor_discharge_led": build_cap_discharge,
                "rc_low_pass_filter": build_rc_filter,
                "555_timer_blinker": build_555,
                "opamp_inverting": build_opamp,
                "opamp_non_inverting": build_opamp,
            }
            if circuit_type not in builders:
                raise ValueError(f"Unsupported CircuitIR type: {circuit_type}")

            builders[circuit_type](ir)

            safe_name = "".join(ch if ch.isalnum() else "_" for ch in circuit_type) or "circuit"
            top_name = f"{safe_name}_{os.getpid()}"
            net_path = work_dir / f"{top_name}.net"
            sch_path = work_dir / f"{top_name}.kicad_sch"
            svg_dir = work_dir / "svg"
            svg_dir.mkdir(exist_ok=True)
            erc_path = work_dir / f"{top_name}.erc.json"

            ERC()
            generate_netlist(file_=str(net_path), tool=KICAD9, do_backup=False)
            generate_schematic(
                filepath=str(work_dir),
                top_name=top_name,
                title=ir.get("title") or circuit_type,
                tool=KICAD9,
                auto_stub=True,
                auto_stub_fallback="labels",
            )
            layout_name = apply_readable_kicad_layout(ir, sch_path, net_path)

            kicad_cli = os.environ.get("KICAD_CLI") or "kicad-cli"
            svg_run = subprocess.run(
                [
                    kicad_cli,
                    "sch",
                    "export",
                    "svg",
                    "--exclude-drawing-sheet",
                    "--no-background-color",
                    "-o",
                    str(svg_dir),
                    str(sch_path),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            svg_files = sorted(svg_dir.glob("*.svg"), key=lambda path: path.stat().st_mtime, reverse=True)
            svg = svg_files[0].read_text(encoding="utf-8", errors="replace") if svg_files else ""
            svg = crop_svg_to_content(svg)

            erc_run = subprocess.run(
                [kicad_cli, "sch", "erc", "--format", "json", "-o", str(erc_path), str(sch_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            erc_json = erc_path.read_text(encoding="utf-8", errors="replace") if erc_path.exists() else ""

            return {
                "success": True,
                "svg": svg,
                "kicad_schematic": sch_path.read_text(encoding="utf-8", errors="replace"),
                "skidl_netlist": net_path.read_text(encoding="utf-8", errors="replace"),
                "erc_json": erc_json,
                "erc_summary": summarize_erc(erc_json),
                "paths": {
                    "schematic": str(sch_path),
                    "netlist": str(net_path),
                    "svg": str(svg_files[0]) if svg_files else None,
                    "erc": str(erc_path) if erc_path.exists() else None,
                },
                "commands": {
                    "svg_returncode": svg_run.returncode,
                    "svg_stdout": svg_run.stdout,
                    "svg_stderr": svg_run.stderr,
                    "erc_returncode": erc_run.returncode,
                    "erc_stdout": erc_run.stdout,
                    "erc_stderr": erc_run.stderr,
                },
                "toolchain": {"skidl_tool": "KICAD9"},
                "layout": layout_name,
            }


        def apply_readable_kicad_layout(ir, sch_path: Path, net_path: Path):
            """Replace SKiDL's cramped auto layout with a topology-driven KiCad sheet."""
            text = sch_path.read_text(encoding="utf-8", errors="replace")
            try:
                prefix, lib_symbols, blocks = split_kicad_schematic(text)
                net_text = net_path.read_text(encoding="utf-8", errors="replace")
                body = layout_for_circuit_type(ir, blocks)
                layout_name = f"cirgpt-layout:{ir.get('circuit_type')}"
                if not body:
                    body = layout_from_netlist(ir, lib_symbols, blocks, net_text, allow_buses=True)
                    layout_name = "cirgpt-layout:generic-topology"
            except Exception:
                return "skidl-auto"

            sch_path.write_text(prefix + lib_symbols + body + ")\n", encoding="utf-8")
            if validate_layout_net_equivalence(sch_path, net_text):
                return layout_name

            try:
                body = layout_from_netlist(
                    ir,
                    lib_symbols,
                    blocks,
                    net_text,
                    allow_buses=False,
                    allow_direct=False,
                )
                sch_path.write_text(prefix + lib_symbols + body + ")\n", encoding="utf-8")
                if validate_layout_net_equivalence(sch_path, net_text):
                    return "cirgpt-layout:generic-topology-label-safe"
            except Exception:
                pass

            sch_path.write_text(text, encoding="utf-8")
            return "skidl-auto"


        def layout_for_circuit_type(ir, blocks):
            layouts = {
                "led_current_limiter": layout_led,
                "capacitor_discharge_led": layout_cap_discharge,
                "rc_low_pass_filter": layout_rc_filter,
                "555_timer_blinker": layout_555,
                "opamp_inverting": layout_opamp,
                "opamp_non_inverting": layout_opamp,
            }
            layout = layouts.get(ir.get("circuit_type"))
            return layout(ir, blocks) if layout else ""


        def split_kicad_schematic(text):
            start = text.find("\n  (lib_symbols")
            if start < 0:
                raise ValueError("KiCad schematic is missing lib_symbols cache")
            lib_start = start + 1
            lib_end = find_matching_paren(text, text.find("(", lib_start))
            if lib_end < 0:
                raise ValueError("KiCad schematic lib_symbols block is malformed")
            blocks = top_level_blocks(text, lib_end + 1)
            return text[:lib_start], text[lib_start:lib_end + 1], blocks


        def top_level_blocks(text, start):
            import re

            blocks = []
            pos = start
            while True:
                match = re.search(r"\n  \(", text[pos:])
                if not match:
                    break
                block_start = pos + match.start() + 1
                paren_start = text.find("(", block_start)
                block_end = find_matching_paren(text, paren_start)
                if block_end < 0:
                    break
                blocks.append(text[block_start:block_end + 1])
                pos = block_end + 1
            return blocks


        def find_matching_paren(text, start):
            depth = 0
            in_string = False
            escaped = False
            for idx in range(start, len(text)):
                ch = text[idx]
                if in_string:
                    if escaped:
                        escaped = False
                    elif ch == "\\":
                        escaped = True
                    elif ch == '"':
                        in_string = False
                    continue
                if ch == '"':
                    in_string = True
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        return idx
            return -1


        def validate_layout_net_equivalence(sch_path: Path, source_net_text):
            """Check that KiCad's exported schematic netlist preserves SKiDL connectivity."""
            kicad_cli = os.environ.get("KICAD_CLI") or "kicad-cli"
            exported_path = sch_path.with_suffix(".layout.net")
            proc = subprocess.run(
                [
                    kicad_cli,
                    "sch",
                    "export",
                    "netlist",
                    "--format",
                    "kicadsexpr",
                    "-o",
                    str(exported_path),
                    str(sch_path),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            if proc.returncode != 0 or not exported_path.exists():
                return False

            _source_refs, source_pin_nets = parse_netlist_graph(source_net_text)
            _layout_refs, layout_pin_nets = parse_netlist_graph(
                exported_path.read_text(encoding="utf-8", errors="replace")
            )
            return same_pin_connectivity(source_pin_nets, layout_pin_nets)


        def same_pin_connectivity(source_pin_nets, layout_pin_nets):
            source = connectivity_partition(source_pin_nets)
            layout = connectivity_partition(layout_pin_nets)
            nodes = set(source) | set(layout)
            return all(source.get(node, frozenset({node})) == layout.get(node, frozenset({node})) for node in nodes)


        def connectivity_partition(pin_nets):
            nets = {}
            for node, net_name in pin_nets.items():
                ref, _pin = node
                if str(ref).startswith("#"):
                    continue
                nets.setdefault(net_name, set()).add(node)
            partition = {}
            for nodes in nets.values():
                frozen = frozenset(nodes)
                for node in nodes:
                    partition[node] = frozen
            return partition


        def q(value):
            return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


        def uid(name):
            import uuid
            return str(uuid.uuid5(uuid.NAMESPACE_URL, f"cirgpt:{name}"))


        def block_ref(block):
            import re

            match = re.search(r'\(property "Reference" "([^"]+)"', block)
            return match.group(1) if match else None


        def block_lib_id(block):
            import re

            match = re.search(r'\(lib_id "([^"]+)"', block)
            return match.group(1) if match else None


        def block_mirror(block):
            import re

            match = re.search(r'\n    \(mirror ([xy])\)', block)
            return match.group(1) if match else None


        def move_symbol(block, x, y, rot=None, prop_rot=None):
            import re

            at_pattern = r'(\n    \(at )([-+0-9.]+) ([-+0-9.]+) ([-+0-9.]+)(\))'
            match = re.search(at_pattern, block)
            if not match:
                return block

            old_x = float(match.group(2))
            old_y = float(match.group(3))
            old_rot = float(match.group(4))
            new_rot = old_rot if rot is None else float(rot)
            dx = float(x) - old_x
            dy = float(y) - old_y

            block = re.sub(
                at_pattern,
                lambda m: f"{m.group(1)}{float(x):g} {float(y):g} {new_rot:g}{m.group(5)}",
                block,
                count=1,
            )

            prop_pattern = r'(\n      \(at )([-+0-9.]+) ([-+0-9.]+) ([-+0-9.]+)(\))'

            def move_property(prop_match):
                prop_x = float(prop_match.group(2)) + dx
                prop_y = float(prop_match.group(3)) + dy
                property_rot = prop_rot
                if property_rot is None:
                    property_rot = new_rot if rot is not None else float(prop_match.group(4))
                return f"{prop_match.group(1)}{prop_x:g} {prop_y:g} {float(property_rot):g}{prop_match.group(5)}"

            return re.sub(prop_pattern, move_property, block)


        def place_ref(blocks, ref, x, y, rot=None, prop_rot=None):
            for block in blocks:
                if block.startswith("  (symbol") and block_ref(block) == ref:
                    return move_symbol(block, x, y, rot, prop_rot) + "\n"
            raise ValueError(f"Symbol reference not found: {ref}")


        def place_lib(blocks, lib_id, x, y, rot=None, occurrence=0, prop_rot=None):
            seen = 0
            for block in blocks:
                if block.startswith("  (symbol") and block_lib_id(block) == lib_id:
                    if seen == occurrence:
                        return move_symbol(block, x, y, rot, prop_rot) + "\n"
                    seen += 1
            raise ValueError(f"Symbol library id not found: {lib_id}")


        def effects(size="1.27 1.27", justify=None, hide=False):
            parts = [f"(font (size {size}))"]
            if justify:
                parts.append(f"(justify {justify})")
            if hide:
                parts.append("(hide yes)")
            return "(effects " + " ".join(parts) + ")"


        def prop(name, value, x, y, rot=0, hide=False, justify=None):
            return (
                f'    (property {q(name)} {q(value)}\n'
                f"      (at {x:g} {y:g} {rot:g})\n"
                f"      {effects(hide=hide, justify=justify)})\n"
            )


        def symbol_block(lib_id, ref, value_text, x, y, rot=0, pins=("1", "2"), footprint="", hide_ref=False):
            lines = [
                "  (symbol",
                f"    (lib_id {q(lib_id)})",
                f"    (at {x:g} {y:g} {rot:g})",
                "    (unit 1)",
                "    (exclude_from_sim no)",
                f"    (in_bom {'no' if ref.startswith('#') else 'yes'})",
                "    (on_board yes)",
                "    (dnp no)",
                "    (fields_autoplaced no)",
                f"    (uuid {uid('sym:' + ref)})",
            ]
            lines.append(prop("Reference", ref, x, y - 5.08, rot, hide=hide_ref))
            lines.append(prop("Value", value_text, x, y + 5.08, rot))
            lines.append(prop("Footprint", footprint, x, y, rot, hide=True))
            lines.append(prop("Datasheet", "~", x, y, rot, hide=True))
            for pin in pins:
                lines.append(f"    (pin {q(pin)} (uuid {uid('pin:' + ref + ':' + pin)}))")
            lines.append(
                f"    (instances (project {q('SKiDL-Generated')} "
                f"(path {q('/' + uid('sheet'))} (reference {q(ref)}) (unit 1))))"
            )
            lines.append("  )")
            return "\n".join(lines) + "\n"


        def power_block(name, ref, x, y, hide_ref=True):
            return symbol_block(f"power:{name}", ref, name, x, y, 0, pins=("1",), footprint="", hide_ref=hide_ref)


        def pwr_flag_block(ref, x, y):
            return symbol_block("power:PWR_FLAG", ref, "PWR_FLAG", x, y, 0, pins=("1",), footprint="", hide_ref=True)


        def wire(points):
            segments = []
            for start, end in zip(points, points[1:]):
                x1, y1 = start
                x2, y2 = end
                wire._seq = getattr(wire, "_seq", 0) + 1
                name = f"wire:{wire._seq}:{x1:g},{y1:g}:{x2:g},{y2:g}"
                segments.append(
                    "  (wire\n"
                    "    (pts\n"
                    f"      (xy {x1:g} {y1:g})\n"
                    f"      (xy {x2:g} {y2:g})\n"
                    "    )\n"
                    "    (stroke\n"
                    "      (width 0)\n"
                    "      (type default))\n"
                    f"    (uuid {uid(name)})\n"
                    "  )\n"
                )
            return "".join(segments)


        def junction(x, y):
            return (
                "  (junction\n"
                f"    (at {x:g} {y:g})\n"
                "    (diameter 0)\n"
                "    (color 0 0 0 0)\n"
                f"    (uuid {uid(f'junction:{x:g}:{y:g}')})\n"
                "  )\n"
            )


        def label(text, x, y, rot=0, justify="left", shape="input"):
            return (
                f"  (global_label {q(text)}\n"
                f"    (shape {shape})\n"
                f"    (at {x:g} {y:g} {rot:g})\n"
                f"    {effects(justify=justify)}\n"
                f"    (uuid {uid(f'label:{text}:{x:g}:{y:g}:{rot:g}')})\n"
                "  )\n"
            )


        def text_note(text, x, y):
            return (
                f"  (text {q(text)}\n"
                f"    (at {x:g} {y:g} 0)\n"
                f"    {effects(size='1.27 1.27')}\n"
                f"    (uuid {uid(f'text:{text}:{x:g}:{y:g}')})\n"
                "  )\n"
            )


        def no_connect(x, y):
            return f"  (no_connect (at {x:g} {y:g}) (uuid {uid(f'nc:{x:g}:{y:g}')}))\n"


        def layout_from_netlist(ir, lib_symbols, blocks, net_text, allow_buses=True, allow_direct=True):
            import math
            import re

            refs, pin_nets = parse_netlist_graph(net_text)
            ref_blocks = {
                block_ref(block): block
                for block in blocks
                if block.startswith("  (symbol") and block_ref(block)
            }
            refs = [ref for ref in refs if ref in ref_blocks]
            if not refs:
                raise ValueError("No schematic symbols were found for generic layout")

            lib_pins = parse_lib_symbol_pins(lib_symbols)
            positions = assign_generic_positions(refs, ref_blocks, lib_pins, pin_nets)
            b = ["\n"]

            for ref in refs:
                x, y, rot = positions[ref]
                b.append(place_ref(blocks, ref, x, y, rot, prop_rot=0))

            for start, end, net_name in power_symbol_wires(refs, ref_blocks, lib_pins, pin_nets, positions):
                b.append(wire([start, end]))
                mid_x = (start[0] + end[0]) / 2.0
                mid_y = (start[1] + end[1]) / 2.0
                b.append(label(display_net_name(net_name), mid_x, mid_y, 0, "left", "bidirectional"))

            core_x = core_center_x(refs, ref_blocks, lib_pins, positions)
            directly_wired = set()
            junction_points = set()
            if allow_buses:
                for points, pins, joints in multi_terminal_signal_buses(refs, ref_blocks, lib_pins, pin_nets, positions, core_x):
                    b.append(wire(points))
                    directly_wired.update(pins)
                    junction_points.update(joints)
            if allow_direct:
                for points, pins in direct_signal_wires(refs, ref_blocks, lib_pins, pin_nets, positions):
                    b.append(wire(points))
                    directly_wired.update(pins)
            for x, y in sorted(junction_points):
                b.append(junction(x, y))

            for ref in refs:
                if ref.startswith("#"):
                    continue
                b.append(ref_net_labels(ref, ref_blocks, lib_pins, pin_nets, positions, core_x, directly_wired))

            return "".join(b)


        def core_center_x(refs, ref_blocks, lib_pins, positions):
            core_refs = [
                ref for ref in refs
                if not ref.startswith("#")
                and len(lib_pins.get(block_lib_id(ref_blocks[ref]), {})) > 2
                and ref in positions
            ]
            if core_refs:
                return sum(positions[ref][0] for ref in core_refs) / len(core_refs)
            normal = [ref for ref in refs if not ref.startswith("#") and ref in positions]
            if normal:
                return sum(positions[ref][0] for ref in normal) / len(normal)
            return 139.7


        def ref_net_labels(ref, ref_blocks, lib_pins, pin_nets, positions, core_x, skip_pins):
            block = ref_blocks[ref]
            lib_id = block_lib_id(block)
            pins = lib_pins.get(lib_id, {})
            mirror = block_mirror(block)
            sx, sy, rot = positions[ref]
            by_net = {}
            chunks = []

            for pin in sorted(pins, key=pin_sort_key):
                if (ref, pin) in skip_pins:
                    continue
                dx, dy, _pin_rot = pins[pin]
                px, py, vx, vy = pin_position(sx, sy, rot, dx, dy, mirror)
                net_name = pin_nets.get((ref, pin))
                if not net_name:
                    chunks.append(no_connect(px, py))
                    continue
                by_net.setdefault(net_name, []).append({
                    "pin": pin,
                    "point": (px, py),
                    "vector": (vx, vy),
                })

            for net_name, records in by_net.items():
                chunks.append(grouped_label_for_records(ref, sx, records, net_name, core_x, len(pins) > 2))
            return "".join(chunks)


        def pin_sort_key(pin):
            try:
                return (0, int(pin))
            except (TypeError, ValueError):
                return (1, str(pin))


        def round_to_grid(value, grid=1.27):
            return round(float(value) / grid) * grid


        def grouped_label_for_records(ref, symbol_x, records, net_name, core_x, is_core):
            points = [record["point"] for record in records]
            vectors = [record["vector"] for record in records]
            avg_x = sum(x for x, _ in points) / len(points)
            avg_y = sum(y for _, y in points) / len(points)
            avg_vx = sum(x for x, _ in vectors) / len(vectors)
            avg_vy = sum(y for _, y in vectors) / len(vectors)

            if abs(avg_vx) >= abs(avg_vy) and abs(avg_vx) > 0.01:
                side = "left" if avg_vx < 0 else "right"
            elif abs(symbol_x - core_x) > 2.54:
                side = "left" if symbol_x < core_x else "right"
            else:
                side = "left" if avg_x <= symbol_x else "right"

            vertical_core_pin = is_core and abs(avg_vy) > abs(avg_vx) and abs(avg_vy) > 0.01
            if side == "left":
                label_x = min(x for x, _ in points) - 7.62
                justify = "right"
            else:
                label_x = max(x for x, _ in points) + 7.62
                justify = "left"
            if vertical_core_pin:
                label_y = round_to_grid(avg_y + (-7.62 if avg_vy < 0 else 7.62))
            else:
                label_y = round_to_grid(avg_y)

            chunks = []
            if vertical_core_pin:
                for px, py in points:
                    py = round_to_grid(py)
                    chunks.append(wire([(px, py), (px, label_y), (label_x, label_y)]))
            else:
                ys = sorted({round_to_grid(y) for _x, y in points} | {label_y})
                for px, py in points:
                    py = round_to_grid(py)
                    chunks.append(wire([(px, py), (label_x, py)]))
                if len(ys) > 1:
                    chunks.append(wire([(label_x, ys[0]), (label_x, ys[-1])]))
            chunks.append(label(display_net_name(net_name), label_x, label_y, 0, justify, "bidirectional"))
            return "".join(chunks)


        def power_symbol_wires(refs, ref_blocks, lib_pins, pin_nets, positions):
            by_net = {}
            for ref in refs:
                if not ref.startswith("#"):
                    continue
                block = ref_blocks[ref]
                lib_id = block_lib_id(block)
                pins = lib_pins.get(lib_id, {})
                mirror = block_mirror(block)
                sx, sy, rot = positions[ref]
                for pin, (dx, dy, _pin_rot) in pins.items():
                    net_name = pin_nets.get((ref, pin))
                    if not net_name:
                        continue
                    px, py, _vx, _vy = pin_position(sx, sy, rot, dx, dy, mirror)
                    by_net.setdefault(net_name, []).append((ref, (px, py)))

            wires = []
            for net_name, items in by_net.items():
                if len(items) < 2:
                    continue
                power_symbols = [
                    item for item in items
                    if block_lib_id(ref_blocks[item[0]]) != "power:PWR_FLAG"
                ]
                source = power_symbols[0][1] if power_symbols else items[0][1]
                for ref, point in items:
                    if point != source:
                        wires.append((source, point, net_name))
            return wires


        def direct_signal_wires(refs, ref_blocks, lib_pins, pin_nets, positions):
            by_net = {}
            for ref in refs:
                if ref.startswith("#"):
                    continue
                block = ref_blocks[ref]
                pins = lib_pins.get(block_lib_id(block), {})
                mirror = block_mirror(block)
                sx, sy, rot = positions[ref]
                for pin, (dx, dy, _pin_rot) in pins.items():
                    net_name = pin_nets.get((ref, pin))
                    if not net_name or is_power_net(net_name):
                        continue
                    px, py, _vx, _vy = pin_position(sx, sy, rot, dx, dy, mirror)
                    by_net.setdefault(net_name, []).append((ref, pin, (px, py)))

            routes = []
            for _net_name, records in by_net.items():
                if len(records) != 2:
                    continue
                first, second = records
                routes.append((
                    manhattan_points(first[2], second[2]),
                    {(first[0], first[1]), (second[0], second[1])},
                ))
            return routes


        def multi_terminal_signal_buses(refs, ref_blocks, lib_pins, pin_nets, positions, core_x):
            by_net = {}
            for ref in refs:
                if ref.startswith("#"):
                    continue
                block = ref_blocks[ref]
                pins = lib_pins.get(block_lib_id(block), {})
                mirror = block_mirror(block)
                is_core = len(pins) > 2
                sx, sy, rot = positions[ref]
                for pin, (dx, dy, _pin_rot) in pins.items():
                    net_name = pin_nets.get((ref, pin))
                    if not net_name or is_power_net(net_name):
                        continue
                    px, py, _vx, _vy = pin_position(sx, sy, rot, dx, dy, mirror)
                    by_net.setdefault(net_name, []).append({
                        "ref": ref,
                        "pin": pin,
                        "point": (px, py),
                        "is_core": is_core,
                    })

            candidates = []
            for net_name, records in by_net.items():
                if len(records) < 3 or len(records) > 6:
                    continue
                if not any(record["is_core"] for record in records):
                    continue
                xs = [record["point"][0] for record in records]
                same_left = max(xs) < core_x + 1.27
                same_right = min(xs) > core_x - 1.27
                if not (same_left or same_right):
                    continue

                if same_left:
                    trunk_x = round_to_grid((max(xs) + min(xs)) / 2.0)
                else:
                    trunk_x = round_to_grid((max(xs) + min(xs)) / 2.0)
                ys = sorted({record["point"][1] for record in records})
                candidates.append({
                    "net_name": net_name,
                    "records": records,
                    "side": "left" if same_left else "right",
                    "trunk_x": trunk_x,
                    "y_min": ys[0],
                    "y_max": ys[-1],
                    "core_count": sum(1 for record in records if record["is_core"]),
                })

            accepted = []
            for candidate in sorted(candidates, key=lambda item: (-item["core_count"], item["y_min"], item["net_name"])):
                overlaps = any(
                    candidate["side"] == other["side"]
                    and ranges_overlap(candidate["y_min"], candidate["y_max"], other["y_min"], other["y_max"], margin=2.54)
                    for other in accepted
                )
                if not overlaps:
                    accepted.append(candidate)

            routes = []
            for candidate in accepted:
                records = candidate["records"]
                trunk_x = candidate["trunk_x"]
                ys = sorted({record["point"][1] for record in records})
                pins = {(record["ref"], record["pin"]) for record in records}
                joints = {(trunk_x, record["point"][1]) for record in records}
                routes.append(([(trunk_x, ys[0]), (trunk_x, ys[-1])], pins, joints))
                for record in records:
                    px, py = record["point"]
                    routes.append(([(px, py), (trunk_x, py)], pins, joints))
            return routes


        def ranges_overlap(a_min, a_max, b_min, b_max, margin=0):
            return max(a_min, b_min) <= min(a_max, b_max) + margin


        def manhattan_points(p1, p2):
            x1, y1 = p1
            x2, y2 = p2
            if abs(x1 - x2) < 0.01 or abs(y1 - y2) < 0.01:
                return [p1, p2]
            mid_x = round_to_grid((x1 + x2) / 2.0)
            return [p1, (mid_x, y1), (mid_x, y2), p2]


        def is_power_net(net_name):
            name = display_net_name(net_name).upper()
            return name in {"GND", "VCC", "VDD", "VEE"} or name.startswith("+") or name.startswith("-")


        def parse_netlist_graph(net_text):
            import re

            refs = []
            components_match = re.search(r"\n\s*\(components\b", net_text)
            if components_match:
                block_start = net_text.find("(", components_match.start())
                block_end = find_matching_paren(net_text, block_start)
                component_block = net_text[block_start:block_end + 1]
                refs = re.findall(r'\(ref "([^"]+)"\)', component_block)

            pin_nets = {}
            for match in re.finditer(r"\n\s*\(net\b", net_text):
                start = net_text.find("(", match.start())
                end = find_matching_paren(net_text, start)
                if end < 0:
                    continue
                net_block = net_text[start:end + 1]
                name_match = re.search(r'\(name "([^"]+)"\)', net_block)
                if not name_match:
                    continue
                net_name = name_match.group(1)
                for node_match in re.finditer(r"\(node\b", net_block):
                    node_start = net_block.find("(", node_match.start())
                    node_end = find_matching_paren(net_block, node_start)
                    if node_end < 0:
                        continue
                    node_block = net_block[node_start:node_end + 1]
                    ref_match = re.search(r'\(ref "([^"]+)"\)', node_block)
                    pin_match = re.search(r'\(pin "([^"]+)"\)', node_block)
                    if ref_match and pin_match:
                        pin_nets[(ref_match.group(1), pin_match.group(1))] = net_name

            return refs, pin_nets


        def parse_lib_symbol_pins(lib_symbols):
            import re

            pin_map = {}
            for match in re.finditer(r'\n    \(symbol "', lib_symbols):
                start = lib_symbols.find("(", match.start())
                end = find_matching_paren(lib_symbols, start)
                if end < 0:
                    continue
                lib_block = lib_symbols[start:end + 1]
                id_match = re.search(r'\(symbol "([^"]+)"', lib_block)
                if not id_match:
                    continue
                lib_id = id_match.group(1)
                pins = {}
                for pin_match in re.finditer(r"\(pin\s+", lib_block):
                    pin_start = pin_match.start()
                    pin_end = find_matching_paren(lib_block, pin_start)
                    if pin_end < 0:
                        continue
                    pin_block = lib_block[pin_start:pin_end + 1]
                    num_match = re.search(r'\(number "([^"]+)"', pin_block)
                    at_match = re.search(r'\(at ([-+0-9.]+) ([-+0-9.]+) ([-+0-9.]+)\)', pin_block)
                    if num_match and at_match:
                        pins[num_match.group(1)] = (
                            float(at_match.group(1)),
                            float(at_match.group(2)),
                            float(at_match.group(3)),
                        )
                pin_map[lib_id] = pins
            return pin_map


        def assign_generic_positions(refs, ref_blocks, lib_pins, pin_nets):
            import math

            positions = {}
            normal_refs = [ref for ref in refs if not ref.startswith("#")]
            power_refs = [ref for ref in refs if ref.startswith("#")]

            core_refs = [
                ref for ref in normal_refs
                if len(lib_pins.get(block_lib_id(ref_blocks[ref]), {})) > 2
            ]
            passive_refs = [ref for ref in normal_refs if ref not in core_refs]

            for idx, ref in enumerate(core_refs or passive_refs[:1]):
                positions[ref] = (139.7, 96.52 + idx * 35.56, 0)
            passive_refs = [ref for ref in passive_refs if ref not in positions]

            left_refs = []
            right_refs = []
            if core_refs:
                core_ref = core_refs[0]
                core_lib = block_lib_id(ref_blocks[core_ref])
                core_pin_sides = {}
                for pin, (dx, _dy, _rot) in lib_pins.get(core_lib, {}).items():
                    net_name = pin_nets.get((core_ref, pin))
                    if net_name:
                        core_pin_sides[net_name] = "left" if dx < 0 else "right"
                for ref in passive_refs:
                    shared = {
                        net for (node_ref, _pin), net in pin_nets.items()
                        if node_ref == ref and net in core_pin_sides
                    }
                    if any(core_pin_sides[net] == "left" for net in shared):
                        left_refs.append(ref)
                    else:
                        right_refs.append(ref)
            else:
                split = math.ceil(len(passive_refs) / 2)
                left_refs = passive_refs[:split]
                right_refs = passive_refs[split:]

            if not core_refs and passive_refs[:1]:
                right_refs = [ref for ref in right_refs if ref not in positions]

            for idx, ref in enumerate(left_refs):
                positions[ref] = (95.25, 81.28 + idx * 25.4, 0)
            for idx, ref in enumerate(right_refs):
                lib_id = block_lib_id(ref_blocks[ref]) or ""
                rot = 180 if lib_id == "Device:LED" else 90
                positions[ref] = (181.61, 81.28 + idx * 25.4, rot)

            power_net_counts = {}
            for ref in power_refs:
                nets = [net for (node_ref, _pin), net in pin_nets.items() if node_ref == ref]
                net_name = display_net_name(nets[0]) if nets else ref
                idx = power_net_counts.get(net_name, 0)
                power_net_counts[net_name] = idx + 1
                if net_name == "GND":
                    y = 142.24
                elif net_name.startswith("-"):
                    y = 76.2
                else:
                    y = 63.5
                positions[ref] = (76.2 + idx * 15.24, y, 0)

            return positions


        def pin_position(symbol_x, symbol_y, symbol_rot, dx, dy, mirror=None):
            sx = float(dx)
            sy = -float(dy)
            if mirror == "x":
                sy = -sy
            elif mirror == "y":
                sx = -sx
            rot = int(round(float(symbol_rot))) % 360
            if rot == 90:
                rx, ry = sy, -sx
            elif rot == 180:
                rx, ry = -sx, -sy
            elif rot == 270:
                rx, ry = -sy, sx
            else:
                rx, ry = sx, sy
            return symbol_x + rx, symbol_y + ry, rx, ry


        def label_anchor(px, py, vx, vy):
            offset = 5.08
            if abs(vx) >= abs(vy):
                if vx < 0:
                    return px - offset, py, 0, "right"
                return px + offset, py, 0, "left"
            if vy < 0:
                return px, py - offset, 270, "right"
            return px, py + offset, 90, "left"


        def display_net_name(net_name):
            return "GND" if str(net_name) in {"0", "GND"} else str(net_name)


        def layout_opamp(ir, blocks):
            inverting = ir.get("circuit_type") == "opamp_inverting"
            gain = abs(float(ir.get("constraints", {}).get("gain", 10.0)))
            r_in = value(role(ir, "input_resistor"), 10_000.0)
            r_fb = value(role(ir, "feedback"), r_in * gain)
            b = ["\n"]
            gnd_y = 116.84 if inverting else 127
            b.append(place_ref(blocks, "TP1", 76.2, 106.68 if inverting else 101.6, 0))
            b.append(place_ref(blocks, "TP2", 193.04, 104.14, 0))
            if inverting:
                b.append(place_ref(blocks, "R1", 109.22, 106.68, 90))
            else:
                b.append(place_ref(blocks, "R1", 137.16, 119.38, 0))
            b.append(place_ref(blocks, "R2", 152.4, 78.74, 270))
            b.append(place_ref(blocks, "U1", 152.4, 104.14, 0))
            b.append(place_ref(blocks, "RLOAD", 180.34, 119.38, 180))
            b.append(place_lib(blocks, "power:+15V", 149.86, 96.52, 0, occurrence=0))
            b.append(place_lib(blocks, "power:-15V", 149.86, 111.76, 0, occurrence=0))
            b.append(place_lib(blocks, "power:GND", 137.16, gnd_y, 0, occurrence=0))
            b.append(place_lib(blocks, "power:GND", 180.34, 127, 0, occurrence=1))
            b.append(place_ref(blocks, "#FLG01", 157.48, 96.52, 0))
            b.append(place_ref(blocks, "#FLG02", 160.02, 111.76, 0))
            b.append(place_ref(blocks, "#FLG03", 144.78, gnd_y, 0))
            if inverting:
                b.append(wire([(76.2, 106.68), (105.41, 106.68)]))
                b.append(wire([(113.03, 106.68), (144.78, 106.68)]))
                b.append(wire([(144.78, 106.68), (144.78, 78.74), (148.59, 78.74)]))
                b.append(wire([(156.21, 78.74), (160.02, 78.74), (160.02, 104.14)]))
                b.append(wire([(144.78, 101.6), (137.16, 101.6), (137.16, 116.84), (144.78, 116.84)]))
            else:
                b.append(wire([(76.2, 101.6), (144.78, 101.6)]))
                b.append(wire([(144.78, 106.68), (137.16, 106.68), (137.16, 115.57)]))
                b.append(wire([(137.16, 123.19), (137.16, 127), (144.78, 127)]))
                b.append(wire([(144.78, 106.68), (144.78, 78.74), (148.59, 78.74)]))
                b.append(wire([(156.21, 78.74), (160.02, 78.74), (160.02, 104.14)]))
            b.append(wire([(160.02, 104.14), (180.34, 104.14), (193.04, 104.14)]))
            b.append(wire([(180.34, 104.14), (180.34, 115.57)]))
            b.append(wire([(180.34, 123.19), (180.34, 127)]))
            if inverting:
                b.append(wire([(180.34, 127), (144.78, 127), (144.78, 116.84)]))
            else:
                b.append(wire([(180.34, 127), (144.78, 127)]))
            b.append(wire([(149.86, 96.52), (157.48, 96.52)]))
            b.append(wire([(149.86, 111.76), (160.02, 111.76)]))
            b.append(label("+15V", 157.48, 96.52, 0, "left", "bidirectional"))
            b.append(label("-15V", 160.02, 111.76, 0, "left", "bidirectional"))
            b.append(label("GND", 144.78, gnd_y, 0, "left", "bidirectional"))
            b.append(junction(144.78, 106.68))
            b.append(junction(160.02, 104.14))
            b.append(junction(180.34, 104.14))
            b.append(no_connect(152.4, 111.76))
            b.append(no_connect(154.94, 111.76))
            b.append(no_connect(152.4, 101.6))
            b.append(text_note("Readable KiCad schematic generated from SKiDL netlist", 64, 58))
            return "".join(b)


        def layout_rc_filter(ir, blocks):
            r_val = value(role(ir, "series_resistor"), 10_000.0)
            c_val = value(role(ir, "shunt_capacitor"), 15.9e-9)
            b = ["\n"]
            b.append(place_ref(blocks, "TP1", 70, 100, 0))
            b.append(place_ref(blocks, "R1", 105, 100, 90))
            b.append(place_ref(blocks, "C1", 145, 112, 0))
            b.append(place_ref(blocks, "TP2", 180, 100, 0))
            b.append(place_lib(blocks, "power:GND", 145, 124, 0, occurrence=0))
            b.append(place_ref(blocks, "#FLG01", 134, 124, 0))
            b.append(wire([(70, 100), (101.19, 100)]))
            b.append(wire([(108.81, 100), (145, 100), (180, 100)]))
            b.append(wire([(145, 100), (145, 108.19)]))
            b.append(wire([(145, 115.81), (145, 124)]))
            b.append(junction(145, 100))
            b.append(label("IN", 62, 100, 0, "right"))
            b.append(label("OUT", 188, 100, 0, "left", "output"))
            b.append(text_note("RC low-pass filter", 66, 74))
            return "".join(b)


        def layout_led(ir, blocks):
            supply = value(role(ir, "supply"), 5.0)
            r_val = value(role(ir, "current_limit"), 150.0)
            v_label = voltage_label(supply)
            b = ["\n"]
            b.append(place_lib(blocks, f"power:{v_label}", 80, 78, 0, occurrence=0))
            b.append(place_ref(blocks, "#FLG01", 94, 78, 0))
            b.append(place_ref(blocks, "R1", 80, 100, 0))
            b.append(place_ref(blocks, "D1", 80, 122, 0))
            b.append(place_lib(blocks, "power:GND", 80, 140, 0, occurrence=0))
            b.append(place_ref(blocks, "#FLG02", 94, 140, 0))
            b.append(wire([(80, 78), (80, 96.19)]))
            b.append(wire([(80, 103.81), (80, 118.19)]))
            b.append(wire([(80, 125.81), (80, 140)]))
            b.append(text_note("LED current limiter", 58, 58))
            return "".join(b)


        def layout_cap_discharge(ir, blocks):
            supply = value(role(ir, "supply"), 5.0)
            rchg_val = value(role(ir, "charge_resistor"), 47.0)
            rdis_val = value(role(ir, "discharge_resistor"), 10_000.0)
            rled_val = value(role(ir, "led_resistor"), 330.0)
            c_val = value(role(ir, "storage_capacitor"), 100e-6)
            v_label = voltage_label(supply)
            b = ["\n"]
            b.append(place_lib(blocks, f"power:{v_label}", 68, 78, 0, occurrence=0))
            b.append(place_ref(blocks, "#FLG01", 82, 78, 0))
            b.append(place_ref(blocks, "S1", 96, 78, 0))
            b.append(place_ref(blocks, "RCHG", 126, 78, 90))
            b.append(place_ref(blocks, "C1", 154, 104, 0))
            b.append(place_ref(blocks, "RDIS", 174, 104, 0))
            b.append(place_ref(blocks, "RLED", 194, 78, 90))
            b.append(place_ref(blocks, "D1", 224, 78, 90))
            b.append(place_lib(blocks, "power:GND", 154, 124, 0, occurrence=0))
            b.append(place_lib(blocks, "power:GND", 174, 124, 0, occurrence=1))
            b.append(place_lib(blocks, "power:GND", 232, 104, 0, occurrence=2))
            b.append(place_ref(blocks, "#FLG02", 140, 124, 0))
            b.append(wire([(68, 78), (90.92, 78)]))
            b.append(wire([(101.08, 78), (122.19, 78)]))
            b.append(wire([(129.81, 78), (154, 78), (190.19, 78)]))
            b.append(wire([(154, 78), (154, 100.19)]))
            b.append(wire([(154, 107.81), (154, 124)]))
            b.append(wire([(174, 100.19), (174, 78)]))
            b.append(wire([(174, 107.81), (174, 124)]))
            b.append(wire([(197.81, 78), (220.19, 78)]))
            b.append(wire([(227.81, 78), (232, 78), (232, 104)]))
            b.append(junction(154, 78))
            b.append(label("CAP", 158, 74, 0, "left", "bidirectional"))
            b.append(text_note("Capacitor discharge LED fade", 62, 56))
            return "".join(b)


        def layout_555(ir, blocks):
            supply = value(role(ir, "supply"), 9.0)
            v_label = voltage_label(supply)
            b = ["\n"]

            # Core 555 astable layout. Coordinates are chosen to match the
            # KiCad Timer:NE555P symbol pin geometry on a 2.54 mm grid.
            b.append(place_ref(blocks, "U1", 140, 100, 0))
            b.append(place_ref(blocks, "R1", 104, 93.65, 0))
            b.append(place_ref(blocks, "R2", 104, 101.27, 0))
            b.append(place_ref(blocks, "C1", 104, 108.89, 0))
            b.append(place_ref(blocks, "C2", 116, 89.84, 0))
            b.append(place_ref(blocks, "R3", 180, 100, 90))
            b.append(place_ref(blocks, "D1", 195.08, 100, 180))
            b.append(place_lib(blocks, f"power:{v_label}", 158, 82.22, 0, occurrence=0))
            b.append(place_lib(blocks, "power:GND", 140, 128, 0, occurrence=0))
            b.append(place_ref(blocks, "#FLG01", 172, 82.22, 0))
            b.append(place_ref(blocks, "#FLG02", 126, 128, 0))

            # +V rail: supply, power flag, timing resistor, 555 VCC, and reset.
            b.append(wire([(104, 89.84), (104, 82.22), (122, 82.22), (142.54, 82.22), (172, 82.22)]))
            b.append(wire([(142.54, 89.84), (142.54, 82.22)]))
            b.append(wire([(129.84, 94.92), (122, 94.92), (122, 82.22)]))
            b.append(label(v_label, 150.16, 82.22, 0, "left", "bidirectional"))
            b.append(junction(122, 82.22))
            b.append(junction(142.54, 82.22))

            # Timing network: R1/R2/C1 and the 555 discharge/threshold/trigger pins.
            b.append(wire([(104, 97.46), (129.84, 97.46)]))
            b.append(wire([(104, 105.08), (129.84, 105.08)]))
            b.append(wire([(129.84, 102.54), (124, 102.54), (124, 105.08)]))
            b.append(junction(104, 97.46))
            b.append(junction(104, 105.08))
            b.append(junction(124, 105.08))

            # Control-voltage bypass kept away from the adjacent VCC pin.
            b.append(wire([(140, 89.84), (140, 86.03), (116, 86.03)]))
            b.append(wire([(116, 93.65), (116, 128)]))

            # Output LED branch.
            b.append(wire([(150.16, 100), (176.19, 100)]))
            b.append(wire([(183.81, 100), (191.27, 100)]))
            b.append(wire([(198.89, 100), (212, 100), (212, 128)]))

            # Ground rail for the 555, timing capacitor, control capacitor, LED, and flag.
            b.append(wire([(104, 112.7), (104, 128), (212, 128)]))
            b.append(wire([(140, 110.16), (140, 128)]))
            b.append(wire([(126, 128), (140, 128)]))
            b.append(junction(116, 128))
            b.append(junction(140, 128))
            b.append(text_note("555 astable LED blinker", 82, 58))
            return "".join(b)


        def crop_svg_to_content(svg):
            """Crop KiCad's page-sized SVG viewBox down to visible schematic content."""
            if not svg:
                return svg

            import re

            number = r"[-+]?(?:\d+\.\d+|\d+|\.\d+)(?:[eE][-+]?\d+)?"
            points = []

            def add_point(x, y):
                try:
                    points.append((float(x), float(y)))
                except (TypeError, ValueError):
                    pass

            def attr(tag, name):
                match = re.search(rf'\b{name}="([^"]+)"', tag)
                return match.group(1) if match else None

            def hidden(tag):
                return (
                    'opacity="0"' in tag
                    or 'stroke-opacity="0"' in tag
                    or 'display="none"' in tag
                    or 'visibility="hidden"' in tag
                )

            for tag in re.findall(r"<path\b[^>]*>", svg, flags=re.IGNORECASE | re.DOTALL):
                if hidden(tag):
                    continue
                data = attr(tag, "d") or ""
                values = re.findall(number, data)
                for i in range(0, len(values) - 1, 2):
                    add_point(values[i], values[i + 1])

            for tag in re.findall(r"<(?:polyline|polygon)\b[^>]*>", svg, flags=re.IGNORECASE | re.DOTALL):
                if hidden(tag):
                    continue
                values = re.findall(number, attr(tag, "points") or "")
                for i in range(0, len(values) - 1, 2):
                    add_point(values[i], values[i + 1])

            for tag in re.findall(r"<line\b[^>]*>", svg, flags=re.IGNORECASE | re.DOTALL):
                if hidden(tag):
                    continue
                add_point(attr(tag, "x1"), attr(tag, "y1"))
                add_point(attr(tag, "x2"), attr(tag, "y2"))

            for tag in re.findall(r"<rect\b[^>]*>", svg, flags=re.IGNORECASE | re.DOTALL):
                if hidden(tag):
                    continue
                x = attr(tag, "x")
                y = attr(tag, "y")
                w = attr(tag, "width")
                h = attr(tag, "height")
                try:
                    x = float(x or 0)
                    y = float(y or 0)
                    w = float(w or 0)
                    h = float(h or 0)
                except ValueError:
                    continue
                # Ignore full-page background rectangles if KiCad emits one.
                if x == 0 and y == 0 and w > 200 and h > 150:
                    continue
                add_point(x, y)
                add_point(x + w, y + h)

            for tag in re.findall(r"<circle\b[^>]*>", svg, flags=re.IGNORECASE | re.DOTALL):
                if hidden(tag):
                    continue
                cx = attr(tag, "cx")
                cy = attr(tag, "cy")
                r = attr(tag, "r")
                try:
                    cx = float(cx or 0)
                    cy = float(cy or 0)
                    r = float(r or 0)
                except ValueError:
                    continue
                add_point(cx - r, cy - r)
                add_point(cx + r, cy + r)

            # KiCad uses hidden text plus visible stroked paths. Only include visible text.
            for tag in re.findall(r"<text\b[^>]*>", svg, flags=re.IGNORECASE | re.DOTALL):
                if hidden(tag):
                    continue
                add_point(attr(tag, "x"), attr(tag, "y"))

            if not points:
                return svg

            min_x = min(x for x, _ in points)
            min_y = min(y for _, y in points)
            max_x = max(x for x, _ in points)
            max_y = max(y for _, y in points)

            if max_x <= min_x or max_y <= min_y:
                return svg

            pad = 4.0
            min_x -= pad
            min_y -= pad
            max_x += pad
            max_y += pad
            width = max_x - min_x
            height = max_y - min_y

            svg = re.sub(r'\swidth="[^"]+"', f' width="{width:.4f}mm"', svg, count=1)
            svg = re.sub(r'\sheight="[^"]+"', f' height="{height:.4f}mm"', svg, count=1)
            svg = re.sub(
                r'\sviewBox="[^"]+"',
                f' viewBox="{min_x:.4f} {min_y:.4f} {width:.4f} {height:.4f}"',
                svg,
                count=1,
            )
            return svg


        def setup_skidl():
            reset()
            set_default_tool(KICAD9)


        def role(ir, role_name, default=None):
            for comp in ir.get("components", []):
                if comp.get("role") == role_name:
                    return comp
            return default


        def value(comp, default):
            if not comp:
                return default
            try:
                return float(comp.get("value", default))
            except (TypeError, ValueError):
                return default


        def fmt_res(ohms):
            ohms = float(ohms)
            if abs(ohms) >= 1_000_000:
                return f"{ohms / 1_000_000:g}M"
            if abs(ohms) >= 1_000:
                return f"{ohms / 1_000:g}k"
            return f"{ohms:g}"


        def fmt_cap(farads):
            farads = float(farads)
            if abs(farads) >= 1e-3:
                return f"{farads:g}F"
            if abs(farads) >= 1e-6:
                return f"{farads * 1e6:g}uF"
            if abs(farads) >= 1e-9:
                return f"{farads * 1e9:g}nF"
            return f"{farads * 1e12:g}pF"


        def net(name, power=False):
            n = Net(name)
            if name.upper() in {"GND", "VCC", "VDD", "VEE", "+5V", "+9V", "+15V", "-15V"} or power:
                n.drive = POWER
            return n


        def resistor(ref, val):
            return Part("Device", "R", ref=ref, value=fmt_res(val), footprint=RES_FP)


        def capacitor(ref, val):
            fp = CPOL_FP if float(val) >= 1e-6 else CAP_FP
            return Part("Device", "C", ref=ref, value=fmt_cap(val), footprint=fp)


        def led(ref="D1"):
            return Part("Device", "LED", ref=ref, value="LED", footprint=LED_FP)


        def power_symbol(name, ref):
            part_name = name
            if name == "VCC":
                part_name = "VCC"
            elif name == "GND":
                part_name = "GND"
            p = Part("power", part_name, ref=ref)
            p.footprint = ":"
            return p


        def pwr_flag(ref):
            p = Part("power", "PWR_FLAG", ref=ref)
            p.footprint = ":"
            return p


        def add_power(vcc, gnd, label="VCC"):
            ps = power_symbol(label, "#PWR01")
            gs = power_symbol("GND", "#PWR02")
            pf_v = pwr_flag("#FLG01")
            pf_g = pwr_flag("#FLG02")
            ps[1] += vcc
            gs[1] += gnd
            pf_v[1] += vcc
            pf_g[1] += gnd


        def build_led(ir):
            supply = value(role(ir, "supply"), 5.0)
            r_val = value(role(ir, "current_limit"), 150.0)
            vcc = net(voltage_label(supply), True)
            gnd = net("GND", True)
            led_a = net("LED_A")
            add_power(vcc, gnd, voltage_label(supply))

            r1 = resistor("R1", r_val)
            d1 = led("D1")
            r1[1] += vcc
            r1[2] += led_a
            d1[2] += led_a
            d1[1] += gnd


        def build_rc_filter(ir):
            r_val = value(role(ir, "series_resistor"), 10_000.0)
            c_val = value(role(ir, "shunt_capacitor"), 15.9e-9)
            in_net = net("IN")
            out_net = net("OUT")
            gnd = net("GND", True)
            gs = power_symbol("GND", "#PWR01")
            pf = pwr_flag("#FLG01")
            gs[1] += gnd
            pf[1] += gnd

            r1 = resistor("R1", r_val)
            c1 = capacitor("C1", c_val)
            tp_in = Part("Connector", "TestPoint", ref="TP1", value="IN", footprint=TP_FP)
            tp_out = Part("Connector", "TestPoint", ref="TP2", value="OUT", footprint=TP_FP)
            r1[1] += in_net
            r1[2] += out_net
            c1[1] += out_net
            c1[2] += gnd
            tp_in[1] += in_net
            tp_out[1] += out_net


        def build_cap_discharge(ir):
            supply = value(role(ir, "supply"), 5.0)
            rchg_val = value(role(ir, "charge_resistor"), 47.0)
            rdis_val = value(role(ir, "discharge_resistor"), 10_000.0)
            rled_val = value(role(ir, "led_resistor"), 330.0)
            c_val = value(role(ir, "storage_capacitor"), 100e-6)

            vcc = net(voltage_label(supply), True)
            gnd = net("GND", True)
            charge = net("CHARGE")
            cap = net("CAP")
            led_a = net("LED_A")
            add_power(vcc, gnd, voltage_label(supply))

            sw = Part("Switch", "SW_Push", ref="S1", value="PUSH", footprint=SW_FP)
            rchg = resistor("RCHG", rchg_val)
            c1 = capacitor("C1", c_val)
            rdis = resistor("RDIS", rdis_val)
            rled = resistor("RLED", rled_val)
            d1 = led("D1")

            sw[1] += vcc
            sw[2] += charge
            rchg[1] += charge
            rchg[2] += cap
            c1[1] += cap
            c1[2] += gnd
            rdis[1] += cap
            rdis[2] += gnd
            rled[1] += cap
            rled[2] += led_a
            d1[2] += led_a
            d1[1] += gnd


        def build_555(ir):
            supply = value(role(ir, "supply"), 9.0)
            r1_val = value(role(ir, "timing_ra"), 1_000.0)
            r2_val = value(role(ir, "timing_rb"), 71_500.0)
            c1_val = value(role(ir, "timing_capacitor"), 10e-6)
            c2_val = value(role(ir, "control_capacitor"), 10e-9)
            rled_val = value(role(ir, "led_resistor"), 470.0)

            vcc = net(voltage_label(supply), True)
            gnd = net("GND", True)
            thresh = net("THRESH_TRIG")
            disch = net("DISCH")
            ctrl = net("CTRL")
            out = net("OUT")
            led_a = net("LED_A")
            add_power(vcc, gnd, voltage_label(supply))

            u1 = Part("Timer", "NE555P", ref="U1", value="NE555P", footprint=DIP8_FP)
            r1 = resistor("R1", r1_val)
            r2 = resistor("R2", r2_val)
            c1 = capacitor("C1", c1_val)
            c2 = capacitor("C2", c2_val)
            r3 = resistor("R3", rled_val)
            d1 = led("D1")

            u1["GND"] += gnd
            u1["VCC"] += vcc
            u1["~{RST}"] += vcc
            u1["TRIG"] += thresh
            u1["THRES"] += thresh
            u1["DISCH"] += disch
            u1["CONT"] += ctrl
            u1["OUT"] += out

            r1[1] += vcc
            r1[2] += disch
            r2[1] += disch
            r2[2] += thresh
            c1[1] += thresh
            c1[2] += gnd
            c2[1] += ctrl
            c2[2] += gnd
            r3[1] += out
            r3[2] += led_a
            d1[2] += led_a
            d1[1] += gnd


        def build_opamp(ir):
            supply = abs(float(ir.get("constraints", {}).get("supply_voltage_v", 15.0)))
            gain = abs(float(ir.get("constraints", {}).get("gain", 10.0)))
            inverting = ir.get("circuit_type") == "opamp_inverting"
            vcc = net("+15V", True)
            vee = net("-15V", True)
            gnd = net("GND", True)
            inn = net("IN")
            out = net("OUT")
            summing = net("SUM")

            pos = power_symbol("+15V", "#PWR01")
            neg = power_symbol("-15V", "#PWR02")
            gs = power_symbol("GND", "#PWR03")
            pf1 = pwr_flag("#FLG01")
            pf2 = pwr_flag("#FLG02")
            pf3 = pwr_flag("#FLG03")
            pos[1] += vcc
            neg[1] += vee
            gs[1] += gnd
            pf1[1] += vcc
            pf2[1] += vee
            pf3[1] += gnd

            u1 = Part("Amplifier_Operational", "LM741", ref="U1", value="LM741", footprint=DIP8_FP)
            r_in = value(role(ir, "input_resistor"), 10_000.0)
            r_fb = value(role(ir, "feedback"), r_in * gain)
            r1 = resistor("R1", r_in)
            r2 = resistor("R2", r_fb)
            rload = resistor("RLOAD", 100_000.0)
            tp_in = Part("Connector", "TestPoint", ref="TP1", value="IN", footprint=TP_FP)
            tp_out = Part("Connector", "TestPoint", ref="TP2", value="OUT", footprint=TP_FP)

            u1["V+"] += vcc
            u1["V-"] += vee
            u1[6] += out
            rload[1] += out
            rload[2] += gnd
            tp_in[1] += inn
            tp_out[1] += out

            if inverting:
                u1["+"] += gnd
                u1["-"] += summing
                r1[1] += inn
                r1[2] += summing
                r2[1] += out
                r2[2] += summing
            else:
                u1["+"] += inn
                u1["-"] += summing
                r1[1] += summing
                r1[2] += gnd
                r2[1] += out
                r2[2] += summing

        def voltage_label(voltage):
            rounded = round(float(voltage))
            if abs(float(voltage) - rounded) < 1e-6:
                candidate = f"+{rounded}V"
                if candidate in {"+5V", "+9V", "+15V"}:
                    return candidate
            return "VCC"


        def summarize_erc(erc_text):
            if not erc_text:
                return {"status": "unknown", "errors": 0, "warnings": 0, "violations": []}
            try:
                data = json.loads(erc_text)
            except json.JSONDecodeError:
                return {"status": "unknown", "errors": 0, "warnings": 0, "violations": []}

            violations = []
            errors = 0
            warnings = 0
            for sheet in data.get("sheets", []):
                for violation in sheet.get("violations", []):
                    severity = violation.get("severity", "warning")
                    if severity == "error":
                        errors += 1
                    elif severity == "warning":
                        warnings += 1
                    violations.append({
                        "severity": severity,
                        "type": violation.get("type"),
                        "description": violation.get("description"),
                    })

            status = "passed" if errors == 0 and warnings == 0 else ("failed" if errors else "warning")
            return {
                "status": status,
                "errors": errors,
                "warnings": warnings,
                "violations": violations[:20],
            }


        if __name__ == "__main__":
            raise SystemExit(main())
        '''
    ).strip() + "\n"
