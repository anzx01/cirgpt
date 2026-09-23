"""
DeepSeek-backed natural language to CircuitIR parser.

The model is used only to produce a constrained JSON IR. SKiDL/KiCad generation
continues to happen locally from the validated IR.

V2 change:
- System prompt comes from the prompts registry (v2_freeform by default).
  v1_strict is still available for A/B comparison via DEEPSEEK_PROMPT_VERSION.
- The validator no longer rejects free-form circuit_type values. It still
  enforces hard role checks for the 6 legacy "template" types so the existing
  EDA generators can rely on a stable contract for those.
- New optional rich-metadata fields are accepted and forwarded untouched:
  domain, compliance_standards, subsystems, test_points, operating_envelope,
  interfaces, design_notes, open_questions, plus per-component optional fields
  (tolerance_pct, voltage_rating_v, power_rating_w, package, manufacturer,
  manufacturer_part, subsystem, notes).
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable

import httpx

from app.config import settings
from nlp.circuit_ir import SUPPORTED_TYPES
from nlp.prompts.registry import active_prompt_name, get_active_system_prompt


# Hard role checks apply only to the legacy template types. For free-form
# types (or the legacy "generic_circuit") we only require a non-empty
# component list with at least one node-bearing component.
LEGACY_TEMPLATE_ROLES = {
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


_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def deepseek_configured() -> bool:
    return bool(settings.DEEPSEEK_API_KEY)


def active_prompt_version() -> str:
    """Name of the currently active system prompt version."""
    return active_prompt_name()


async def parse_description_with_deepseek(
    description: str,
    return_raw: bool = False,
):
    """Parse natural language into validated CircuitIR via DeepSeek.

    When ``return_raw`` is True, returns a tuple of (validated_ir, raw_response).
    Otherwise returns only the validated IR (legacy behavior).
    """
    if not deepseek_configured():
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

    system_prompt = get_active_system_prompt()

    payload = {
        "model": settings.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Return JSON CircuitIR for this request:\n{description}"},
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "temperature": 0.1,
        # Complex multi-subsystem circuits exceed 4000 tokens of JSON and get
        # truncated mid-string; 8192 leaves headroom.
        "max_tokens": 8192,
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

    # Stash the raw upstream payload **inside the IR's `source` dict before
    # validation** so that the validator's "rebuild source" step preserves it.
    # Otherwise the 114-line post-mutation in the previous version was lost
    # when validate_circuit_ir rebuilt `source` from scratch.
    source_block = parsed.get("source") if isinstance(parsed.get("source"), dict) else {}
    source_block["raw_response"] = data
    source_block["raw_message_text"] = content
    source_block["raw_request"] = {
        "model": payload["model"],
        "messages": payload["messages"],
        "temperature": payload["temperature"],
        "max_tokens": payload["max_tokens"],
        "response_format": payload["response_format"],
    }
    parsed["source"] = source_block

    validated = validate_circuit_ir(parsed, description, source_mode="deepseek")

    if return_raw:
        return validated, data
    return validated


def _normalize_circuit_type(raw: Any) -> str:
    """Normalize a free-form circuit_type string.

    Rules:
    - None / empty -> "unsupported"
    - Strip whitespace, lowercase
    - Replace any non [a-z0-9_] with "_"
    - Collapse repeated underscores and trim leading/trailing "_"
    - If still empty -> "unsupported"
    - Cap at 60 characters
    """
    if raw is None:
        return "unsupported"
    text = str(raw).strip().lower()
    if not text:
        return "unsupported"
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        return "unsupported"
    return text[:60]


def validate_circuit_ir(ir: Dict[str, Any], description: str, source_mode: str = "unknown") -> Dict[str, Any]:
    """Validate and normalize the constrained CircuitIR shape used by EDA.

    V2 behavior:
    - Accept any snake_case circuit_type. Legacy 6 template types still
      trigger hard role checks (so existing EDA generators remain correct).
    - Free-form types only require a non-empty list of components with at
      least one valid node pair. Warnings are added for missing best-effort
      fields but the IR is not rejected.
    - Rich-metadata fields are preserved verbatim.
    """
    if not isinstance(ir, dict):
        raise ValueError("CircuitIR must be a JSON object")

    raw_type = ir.get("circuit_type", "unsupported")
    circuit_type = _normalize_circuit_type(raw_type)
    source = ir.get("source") if isinstance(ir.get("source"), dict) else {}
    raw_components = ir.get("components")
    has_components = isinstance(raw_components, list) and any(isinstance(item, dict) for item in raw_components)
    explicit_supported = ir.get("supported")
    if isinstance(explicit_supported, bool):
        supported = explicit_supported
    else:
        supported = circuit_type != "unsupported" or has_components

    if not supported or circuit_type == "unsupported":
        if has_components and description.strip():
            circuit_type = _normalize_circuit_type(raw_type) if raw_type else "generic_circuit"
            if not circuit_type or circuit_type == "unsupported":
                circuit_type = "generic_circuit"
            supported = True
        else:
            unsupported_source: Dict[str, Any] = dict(source) if isinstance(source, dict) else {}
            unsupported_source["mode"] = source_mode
            unsupported_source["model"] = settings.DEEPSEEK_MODEL if source_mode == "deepseek" else None
            unsupported_source["rationale"] = _as_string_list(source.get("rationale", []))
            return {
                "schema_version": "1.0",
                "supported": False,
                "circuit_type": "unsupported",
                "title": str(ir.get("title") or "Unsupported circuit request"),
                "description": description,
                "components": [],
                "nets": [],
                "constraints": dict(ir.get("constraints") or {}),
                "source": unsupported_source,
                "warnings": _as_string_list(ir.get("warnings", ["Unsupported circuit request"])),
            }

    components = _normalize_components(ir.get("components"))

    if not components:
        no_components_source: Dict[str, Any] = dict(source) if isinstance(source, dict) else {}
        no_components_source["mode"] = source_mode
        no_components_source["model"] = settings.DEEPSEEK_MODEL if source_mode == "deepseek" else None
        no_components_source["rationale"] = _as_string_list(source.get("rationale", []))
        return {
            "schema_version": "1.0",
            "supported": False,
            "circuit_type": "unsupported",
            "title": str(ir.get("title") or "Unsupported circuit request"),
            "description": description,
            "components": [],
            "nets": [],
            "constraints": dict(ir.get("constraints") or {}),
            "source": no_components_source,
            "warnings": _as_string_list(ir.get("warnings", ["CircuitIR did not include components."])),
        }

    warnings: list[str] = _as_string_list(ir.get("warnings", []))

    # Hard role check: only for the 6 legacy template types. Free-form types
    # (including the legacy "generic_circuit") skip this and rely on warnings.
    if circuit_type in LEGACY_TEMPLATE_ROLES:
        roles = {str(component.get("role")) for component in components if isinstance(component, dict)}
        missing = LEGACY_TEMPLATE_ROLES[circuit_type] - roles
        if missing:
            raise ValueError(f"CircuitIR missing required role(s): {', '.join(sorted(missing))}")
    elif circuit_type not in SUPPORTED_TYPES and circuit_type != "generic_circuit":
        warnings.append(
            f"自由形态电路类型 '{circuit_type}'：通用元件由 KiCad 库标准符号生成，"
            "登记器件（ESP32-C3/USB-C/AMS1117）使用真实符号与引脚。"
        )

    if not _SNAKE_CASE_RE.match(circuit_type):
        warnings.append(
            f"电路类型名 '{circuit_type}' 已规范化为 snake_case。"
        )

    # 供电 lint：仅当既没有供电角色、也没有任何电源链器件（源/电池/
    # 稳压/USB-C 供电口）时才提示——有电源链时这只是模型没打 role 标签，
    # 对用户是噪音
    _power_chain_types = {
        "voltage_source", "battery", "ldo_ams1117", "usb_c_power_connector",
    }
    has_power_part = any(
        str(c.get("type") or "").lower() in _power_chain_types
        for c in components if isinstance(c, dict)
    )
    if not has_power_part and not any(
        "supply" == str(c.get("role")) for c in components if isinstance(c, dict)
    ):
        warnings.append("描述中未包含任何供电来源（电源、电池或供电接口），请确认供电方式。")

    nets = ir.get("nets") if isinstance(ir.get("nets"), list) else _nets_from_components(components)
    constraints = ir.get("constraints") if isinstance(ir.get("constraints"), dict) else {}

    # Rebuild the source block. Always overwrite the well-known fields, but
    # preserve any extra fields the upstream parser may have attached (e.g.
    # raw_response / raw_message_text / raw_request that the DeepSeek parser
    # stashes for the debug UI).
    new_source: Dict[str, Any] = dict(source) if isinstance(source, dict) else {}
    new_source["mode"] = source_mode
    new_source["model"] = settings.DEEPSEEK_MODEL if source_mode == "deepseek" else None
    new_source["rationale"] = _as_string_list(source.get("rationale", []))
    new_source["prompt_version"] = active_prompt_version()

    normalized: Dict[str, Any] = {
        "schema_version": "1.0",
        "supported": True,
        "circuit_type": circuit_type,
        "title": str(ir.get("title") or circuit_type.replace("_", " "))[:120],
        "description": str(ir.get("description") or description),
        "components": components,
        "nets": nets,
        "constraints": constraints,
        "source": new_source,
        "warnings": warnings,
    }

    # Forward optional rich metadata verbatim when present.
    for optional_field in (
        "domain",
        "compliance_standards",
        "subsystems",
        "test_points",
        "operating_envelope",
        "interfaces",
        "design_notes",
        "open_questions",
    ):
        value = ir.get(optional_field)
        if value is not None:
            normalized[optional_field] = value

    return normalized


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [str(item) for item in value if item is not None]
    return []


def _normalize_components(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, list):
        return []

    components: list[Dict[str, Any]] = []
    for index, component in enumerate(value, start=1):
        if not isinstance(component, dict):
            continue

        nodes = component.get("nodes")
        if not isinstance(nodes, list):
            nodes = []
        nodes = [str(node) for node in nodes if node is not None]
        if not nodes:
            continue

        ref = str(component.get("ref") or f"X{index}")
        ctype = str(component.get("type") or "module")
        role = str(component.get("role") or ctype)
        unit = str(component.get("unit") or "")

        normalized_component: Dict[str, Any] = {
            "ref": ref,
            "type": ctype,
            "value": component.get("value", ""),
            "unit": unit,
            "nodes": nodes,
            "role": role,
        }

        # Forward optional per-component metadata untouched.
        for optional_field in (
            "tolerance_pct",
            "voltage_rating_v",
            "power_rating_w",
            "current_rating_a",
            "package",
            "manufacturer",
            "manufacturer_part",
            "subsystem",
            "notes",
            "dnp",
        ):
            if optional_field in component and component[optional_field] is not None:
                normalized_component[optional_field] = component[optional_field]

        components.append(normalized_component)

    return components


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
