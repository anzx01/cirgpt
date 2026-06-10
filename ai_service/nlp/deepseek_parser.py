"""
DeepSeek-backed natural language to CircuitIR parser.

The model is used only to produce a constrained JSON IR. SKiDL/KiCad generation
continues to happen locally from the validated IR.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Iterable

import httpx

from app.config import settings
from nlp.circuit_ir import SUPPORTED_TYPES


REQUIRED_ROLES = {
    "led_current_limiter": {"supply", "current_limit"},
    "capacitor_discharge_led": {
        "supply",
        "charge_resistor",
        "discharge_resistor",
        "storage_capacitor",
        "led_resistor",
    },
    "rc_low_pass_filter": {"series_resistor", "shunt_capacitor"},
    "555_timer_blinker": {
        "supply",
        "timing_ra",
        "timing_rb",
        "timing_capacitor",
        "control_capacitor",
        "led_resistor",
    },
    "opamp_inverting": {"input_resistor", "feedback"},
    "opamp_non_inverting": {"gain_ground", "feedback"},
}


def deepseek_configured() -> bool:
    return bool(settings.DEEPSEEK_API_KEY)


async def parse_description_with_deepseek(description: str) -> Dict[str, Any]:
    """Parse natural language into validated CircuitIR via DeepSeek."""
    if not deepseek_configured():
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

    payload = {
        "model": settings.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": f"Return JSON CircuitIR for this request:\n{description}"},
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "temperature": 0.1,
        "max_tokens": 2500,
    }

    async with httpx.AsyncClient(timeout=settings.DEEPSEEK_TIMEOUT_SECONDS) as client:
        response = await client.post(
            f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    return validate_circuit_ir(parsed, description, source_mode="deepseek")


def validate_circuit_ir(ir: Dict[str, Any], description: str, source_mode: str = "unknown") -> Dict[str, Any]:
    """Validate and normalize the constrained CircuitIR shape used by EDA."""
    if not isinstance(ir, dict):
        raise ValueError("CircuitIR must be a JSON object")

    circuit_type = str(ir.get("circuit_type", "unsupported"))
    supported = bool(ir.get("supported", circuit_type in SUPPORTED_TYPES))

    if not supported or circuit_type == "unsupported":
        return {
            "schema_version": "1.0",
            "supported": False,
            "circuit_type": "unsupported",
            "title": str(ir.get("title") or "Unsupported circuit request"),
            "description": description,
            "components": [],
            "nets": [],
            "constraints": dict(ir.get("constraints") or {"supported_circuit_types": SUPPORTED_TYPES}),
            "source": {"mode": source_mode, "rationale": _as_string_list(ir.get("source", {}).get("rationale", []))},
            "warnings": _as_string_list(ir.get("warnings", ["Unsupported circuit request"])),
        }

    if circuit_type not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported CircuitIR type from model: {circuit_type}")

    components = ir.get("components")
    if not isinstance(components, list):
        raise ValueError("CircuitIR components must be a list")

    roles = {str(component.get("role")) for component in components if isinstance(component, dict)}
    missing = REQUIRED_ROLES.get(circuit_type, set()) - roles
    if missing:
        raise ValueError(f"CircuitIR missing required role(s): {', '.join(sorted(missing))}")

    normalized = {
        "schema_version": "1.0",
        "supported": True,
        "circuit_type": circuit_type,
        "title": str(ir.get("title") or circuit_type.replace("_", " ")),
        "description": str(ir.get("description") or description),
        "components": components,
        "nets": ir.get("nets") if isinstance(ir.get("nets"), list) else _nets_from_components(components),
        "constraints": ir.get("constraints") if isinstance(ir.get("constraints"), dict) else {},
        "source": {
            "mode": source_mode,
            "model": settings.DEEPSEEK_MODEL if source_mode == "deepseek" else None,
            "rationale": _as_string_list(ir.get("source", {}).get("rationale", []))
            if isinstance(ir.get("source"), dict)
            else [],
        },
        "warnings": _as_string_list(ir.get("warnings", [])),
    }
    return normalized


def _system_prompt() -> str:
    return """
You convert natural language circuit requests into strict JSON CircuitIR.
Return only a JSON object. The word JSON is important: no markdown, no prose.

CircuitIR schema:
{
  "schema_version": "1.0",
  "supported": true,
  "circuit_type": "one supported type",
  "title": "short title",
  "description": "original request",
  "components": [
    {"ref": "R1", "type": "resistor", "value": 1000, "unit": "ohm", "nodes": ["A", "B"], "role": "timing_ra"}
  ],
  "nets": [{"name": "A", "connections": ["R1.1"]}],
  "constraints": {},
  "source": {"mode": "deepseek", "rationale": ["brief calculation notes"]},
  "warnings": []
}

Use SI base values: ohm, F, V, A, Hz. Ground node is "0".
Only choose these supported circuit_type values:
led_current_limiter, capacitor_discharge_led, rc_low_pass_filter,
555_timer_blinker, opamp_inverting, opamp_non_inverting.
If the request cannot be mapped to one supported type, return supported=false
and circuit_type="unsupported".

Required component roles by circuit type:
- led_current_limiter: supply, current_limit, indicator
- capacitor_discharge_led: supply, charge_resistor, discharge_resistor,
  storage_capacitor, led_resistor, indicator
- rc_low_pass_filter: input_signal, series_resistor, shunt_capacitor
- 555_timer_blinker: supply, timer, timing_ra, timing_rb,
  timing_capacitor, control_capacitor, led_resistor, indicator
- opamp_inverting: input_signal, amplifier, input_resistor, feedback,
  positive_supply, negative_supply
- opamp_non_inverting: input_signal, amplifier, gain_ground, feedback,
  positive_supply, negative_supply

For 555 astable requests, include timing values:
R_A on role timing_ra, R_B on role timing_rb, timing C on timing_capacitor,
control capacitor on control_capacitor, LED resistor on led_resistor.
If exact values are unspecified, compute reasonable defaults and explain the
calculation briefly in source.rationale.
""".strip()


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [str(item) for item in value if item is not None]
    return []


def _nets_from_components(components: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    nets: Dict[str, list[str]] = {}
    for component in components:
        if not isinstance(component, dict):
            continue
        ref = str(component.get("ref", "?"))
        nodes = component.get("nodes") or []
        if not isinstance(nodes, list):
            continue
        for index, node in enumerate(nodes, start=1):
            nets.setdefault(str(node), []).append(f"{ref}.{index}")
    return [{"name": name, "connections": connections} for name, connections in sorted(nets.items())]
