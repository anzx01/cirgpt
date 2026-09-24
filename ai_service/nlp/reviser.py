"""
Circuit revision service (chat-driven circuit editing).

Sends the current CircuitIR plus one modification instruction to DeepSeek
and returns a validated, complete revised IR with a Chinese revision
summary. There is intentionally NO rule-based fallback: a rule parser
cannot understand an arbitrary edit instruction, so a DeepSeek failure is
surfaced as an error and the caller keeps the old circuit untouched.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from nlp.deepseek_parser import deepseek_configured, validate_circuit_ir
from nlp.explainer import slim_circuit_ir
from nlp.prompts.revise import CIRCUIT_REVISE_SYSTEM_PROMPT

# How many recent chat turns to include as context. Older turns are dropped
# to bound prompt size; the IR itself carries the accumulated circuit state.
_MAX_HISTORY_TURNS = 6

# DeepSeek occasionally emits broken JSON (truncated mid-string) or a lazy
# empty IR for simple instructions; retrying with a slightly higher
# temperature reliably recovers.
_MAX_ATTEMPTS = 3
_RETRY_TEMPERATURES = [0.1, 0.25, 0.4]


def _parse_model_output(content: str) -> Dict[str, Any]:
    """Tolerantly parse the model's JSON reply.

    Accepts: {"circuit_ir": {...}, "revision_summary": "..."}, a fenced
    ```json block of the same shape, or a bare CircuitIR object returned
    without the requested wrapper. Raises ValueError on unusable output.
    """
    text = content.strip()
    if text.startswith("```"):
        # strip markdown fences the model sometimes adds despite the rules
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    parsed = json.loads(text)  # raises on truncated/malformed JSON
    if not isinstance(parsed, dict):
        raise ValueError("revision output is not a JSON object")

    if isinstance(parsed.get("circuit_ir"), dict):
        if not parsed["circuit_ir"].get("components"):
            raise ValueError("revision output has an empty components array")
        return parsed
    # Model skipped the wrapper and returned the IR directly
    if parsed.get("components"):
        return {"circuit_ir": parsed, "revision_summary": parsed.get("description", "")}
    raise ValueError("revision output has no usable circuit_ir/components")


async def revise_circuit_with_deepseek(
    description: str,
    circuit_ir: Dict[str, Any],
    instruction: str,
    chat_history: Optional[List[Dict[str, Any]]] = None,
    images: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Revise the circuit per one instruction.

    ``images`` entries ({name, mime_type, data_base64}) are sent to the
    vision-capable model alongside the text instruction.

    Returns {"circuit_ir": validated_ir, "revision_summary": str}.
    Raises on any failure (no fallback by design).
    """
    if not deepseek_configured():
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

    history_text = ""
    recent = [m for m in (chat_history or []) if isinstance(m, dict) and m.get("role") in ("user", "assistant")]
    for msg in recent[-_MAX_HISTORY_TURNS:]:
        speaker = "用户" if msg.get("role") == "user" else "工程师"
        history_text += f"{speaker}: {msg.get('content')}\n"
    if history_text:
        history_text = "\n最近的对话记录（供上下文参考）：\n" + history_text

    user_text = (
        f"用户的原始需求：\n{description}\n\n"
        f"当前电路 IR：\n{json.dumps(slim_circuit_ir(circuit_ir), ensure_ascii=False)}\n"
        f"{history_text}\n"
        f"新的修改指令：\n{instruction}"
    )

    clean_images = [
        img for img in (images or [])
        if isinstance(img, dict) and img.get("data_base64")
    ]
    if clean_images:
        image_note = "\n".join(
            f"（附图 {i + 1}：{img.get('name') or 'image'}）"
            for i, img in enumerate(clean_images)
        )
        # Vision content parts: the text first (grounding), then each image.
        user_content = [
            {"type": "text", "text": user_text + f"\n用户随指令附带了图片，请结合图片内容理解修改要求：\n{image_note}"}
        ] + [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{img.get('mime_type') or 'image/png'};base64,{img['data_base64']}"
                },
            }
            for img in clean_images
        ]
    else:
        user_content = user_text

    last_error: Optional[Exception] = None
    for attempt in range(_MAX_ATTEMPTS):
        payload = {
            "model": settings.DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": CIRCUIT_REVISE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "temperature": _RETRY_TEMPERATURES[min(attempt, len(_RETRY_TEMPERATURES) - 1)],
            # A full multi-subsystem IR easily exceeds 4000 tokens of JSON.
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

        choice = data["choices"][0]
        if choice.get("finish_reason") == "length":
            last_error = ValueError("模型输出被 max_tokens 截断，JSON 不完整")
            continue
        content = choice["message"]["content"]

        try:
            parsed = _parse_model_output(content)
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            continue

        raw_ir = parsed["circuit_ir"]
        raw_ir["source"] = dict(raw_ir.get("source") or {}, mode="deepseek",
                                prompt_version="revise_v1", model=payload["model"])

        try:
            revised = validate_circuit_ir(raw_ir, description, source_mode="deepseek")
        except Exception as exc:  # noqa: BLE001 - validator rejections are retryable
            last_error = exc
            continue
        if not revised.get("supported", False):
            last_error = ValueError(
                "修改后的电路未通过结构校验：" + str((revised.get("warnings") or ["unknown"])[0]))
            continue

        return {
            "circuit_ir": revised,
            "revision_summary": str(parsed.get("revision_summary") or "电路已按指令修改。").strip(),
        }

    raise last_error if last_error else RuntimeError("revision failed after retries")
