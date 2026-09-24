"""
Circuit explanation service.

Turns a generated CircuitIR into a structured, human-readable walkthrough
(原理/连接关系/器件作用) for the schematic side panel.

Two providers:
- DeepSeek (preferred): prompt in nlp/prompts/explain.py, strict JSON out.
- Rule-based fallback: deterministic structural summary derived directly
  from the IR. It is NOT an AI narrative and is always labeled
  source="rule" so the UI can disclose the downgrade honestly.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

import httpx

from app.config import settings
from nlp.deepseek_parser import deepseek_configured
from nlp.prompts.explain import CIRCUIT_EXPLAIN_SYSTEM_PROMPT

# Fields the explanation prompt actually needs; everything else (notably
# source.raw_response, which can be tens of KB) is dropped to keep the
# request small.
_SLIM_COMPONENT_FIELDS = (
    "ref", "type", "value", "unit", "nodes", "role", "subsystem", "notes",
)


def slim_circuit_ir(circuit_ir: Dict[str, Any]) -> Dict[str, Any]:
    """Project a stored CircuitIR down to what the explainer prompt needs."""
    slim: Dict[str, Any] = {
        k: circuit_ir.get(k)
        for k in ("circuit_type", "title", "description", "subsystems",
                  "constraints", "design_notes")
        if circuit_ir.get(k)
    }
    components = []
    for comp in circuit_ir.get("components") or []:
        if not isinstance(comp, dict):
            continue
        components.append({k: comp[k] for k in _SLIM_COMPONENT_FIELDS if comp.get(k) is not None})
    slim["components"] = components
    slim["nets"] = [
        net for net in (circuit_ir.get("nets") or [])
        if isinstance(net, dict) and (net.get("name") or net.get("connections"))
    ]
    return slim


def _normalize_explanation(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce the model output into the schema; fill missing keys."""
    def str_list(value) -> List[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(item) for item in value if item]
        return []

    roles = []
    for item in raw.get("component_roles") or []:
        if isinstance(item, dict) and item.get("ref"):
            roles.append({
                "ref": str(item.get("ref")),
                "role": str(item.get("role") or ""),
                "purpose": str(item.get("purpose") or ""),
            })

    nets = []
    for item in raw.get("net_walkthrough") or []:
        if isinstance(item, dict) and item.get("net"):
            nets.append({
                "net": str(item.get("net")),
                "description": str(item.get("description") or ""),
            })

    subsystems = []
    for item in raw.get("subsystems") or []:
        if isinstance(item, dict) and item.get("name"):
            subsystems.append({
                "name": str(item.get("name")),
                "function": str(item.get("function") or ""),
            })
        elif isinstance(item, str):
            subsystems.append({"name": item, "function": ""})

    return {
        "summary": str(raw.get("summary") or "").strip(),
        "how_it_works": str_list(raw.get("how_it_works")),
        "component_roles": roles,
        "net_walkthrough": nets,
        "subsystems": subsystems,
        "design_notes": str_list(raw.get("design_notes")),
    }


async def explain_circuit_with_deepseek(
    description: str,
    circuit_ir: Dict[str, Any],
) -> Dict[str, Any]:
    """Ask DeepSeek to explain the generated circuit. Returns the normalized
    explanation dict (without source labeling; the caller adds it)."""
    if not deepseek_configured():
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

    slim = slim_circuit_ir(circuit_ir)
    user_content = (
        f"用户的原始需求：\n{description}\n\n"
        f"生成的电路 IR（这就是要解释的电路）：\n{json.dumps(slim, ensure_ascii=False)}"
    )

    payload = {
        "model": settings.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": CIRCUIT_EXPLAIN_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "temperature": 0.3,
        "max_tokens": 4096,
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
    if not isinstance(parsed, dict):
        raise ValueError("DeepSeek explanation is not a JSON object")
    explanation = _normalize_explanation(parsed)
    if not explanation["summary"] and not explanation["how_it_works"]:
        raise ValueError("DeepSeek explanation is empty")
    explanation["source_detail"] = {
        "model": payload["model"],
        "prompt_version": "explain_v1",
    }
    return explanation


def build_rule_explanation(circuit_ir: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic structural summary straight from the IR.

    This is a factual listing (types, values, roles, connectivity), not an
    AI narrative. The caller must surface source="rule" so the UI can
    disclose that the AI narrative is unavailable.
    """
    components = [c for c in (circuit_ir.get("components") or []) if isinstance(c, dict)]
    nets = [n for n in (circuit_ir.get("nets") or []) if isinstance(n, dict)]

    roles = []
    for comp in components:
        ref = comp.get("ref") or "?"
        ctype = comp.get("type") or "器件"
        value = comp.get("value")
        unit = comp.get("unit") or ""
        label = f"{ctype}" + (f"（{value}{unit}）" if value is not None else "")
        purpose = comp.get("role") or ""
        note = comp.get("notes")
        if note:
            purpose = f"{purpose}——{note}" if purpose else str(note)
        roles.append({"ref": ref, "role": label, "purpose": purpose})

    net_walkthrough = []
    for net in nets:
        name = net.get("name")
        conns = net.get("connections") or []
        if not name or not conns:
            continue
        net_walkthrough.append({
            "net": name,
            "description": f"连接：{', '.join(str(c) for c in conns[:12])}"
                           + (" 等" if len(conns) > 12 else ""),
        })

    subsystems = [
        {"name": s.get("name") or "", "function": s.get("function") or s.get("description") or ""}
        for s in (circuit_ir.get("subsystems") or [])
        if isinstance(s, dict)
    ]

    title = circuit_ir.get("title") or circuit_ir.get("circuit_type") or "电路"
    summary = (
        f"该设计共包含 {len(components)} 个器件、{len(nets)} 个网络。"
        f"（以下为基于电路 IR 的结构摘要，AI 解读当前不可用）"
    )

    return {
        "summary": summary,
        "how_it_works": [
            f"电路标题：{title}。" + (circuit_ir.get("description") or ""),
            "AI 电路解读未能生成，以上内容是直接从电路结构（CircuitIR）提取的"
            "确定性摘要：器件清单、每个器件的类型/取值/角色、以及每个网络的连接对象。",
        ],
        "component_roles": roles,
        "net_walkthrough": net_walkthrough,
        "subsystems": subsystems,
        "design_notes": [str(n) for n in (circuit_ir.get("design_notes") or []) if n],
        "source_detail": {"model": None, "prompt_version": "rule_structural_summary"},
    }
