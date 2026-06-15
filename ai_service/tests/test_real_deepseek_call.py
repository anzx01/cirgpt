"""
Real API A/B test for the DeepSeek parser.

For each prompt and each registered system prompt version (v1_strict, v2_freeform),
this script:
  1. Calls DeepSeek via the same code path as the FastAPI router
     (nlp.deepseek.parse_description_with_deepseek).
  2. Records the raw upstream response, the prompt used, the validated IR, and
     basic per-version statistics.
  3. Writes a JSON report to tests/output/real_deepseek_ab_<timestamp>.json
     so the difference can be reviewed offline.

Setup:
  1. Set DEEPSEEK_API_KEY in ai_service/.env or in your shell.
  2. From ai_service/ run:
       python -m tests.test_real_deepseek_call [--prompts-only v2_freeform] [--skip]

Run a single side with --prompts-only or skip the call entirely with --skip
to just emit the would-be prompts (useful when the key is unavailable).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nlp.deepseek_parser import active_prompt_version, parse_description_with_deepseek  # noqa: E402
from nlp.prompts.registry import PROMPT_REGISTRY, get_active_system_prompt  # noqa: E402
from app.config import settings  # noqa: E402


SAMPLE_PROMPTS = [
    "Design a 555 timer LED blinker circuit, 9V supply, 1 Hz",
    "Design a track circuit tester receiver front end for 25Hz phase-sensitive "
    "track circuits, isolated ADC, EN 50129, IP54",
    "Design an isolated 24V to 5V DC-DC converter for industrial sensors, 1W, "
    "IEC 61850-3",
    "Design a LoRa end-node with STM32, BME280, solar charger",
    "Design a 3-phase BLDC motor driver using an STM32F4 and gate driver",
]


def _now() -> str:
    return _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _summarize_ir(ir: dict) -> dict:
    return {
        "circuit_type": ir.get("circuit_type"),
        "supported": ir.get("supported"),
        "component_count": len(ir.get("components") or []),
        "net_count": len(ir.get("nets") or []),
        "subsystem_count": len(ir.get("subsystems") or []),
        "open_question_count": len(ir.get("open_questions") or []),
        "warning_count": len(ir.get("warnings") or []),
        "has_compliance_standards": bool(ir.get("compliance_standards")),
        "has_operating_envelope": bool(ir.get("operating_envelope")),
        "has_design_notes": bool(ir.get("design_notes")),
        "source_mode": (ir.get("source") or {}).get("mode"),
        "prompt_version": (ir.get("source") or {}).get("prompt_version"),
        "model": (ir.get("source") or {}).get("model"),
    }


def _maybe_switch_prompt(version: str) -> str:
    os.environ["DEEPSEEK_PROMPT_VERSION"] = version
    return version


def _record_prompt_only(prompt_text: str) -> dict:
    return {
        "kind": "prompt_only",
        "timestamp": _now(),
        "description": prompt_text,
        "active_prompt_version": active_prompt_version(),
        "system_prompt_length": len(get_active_system_prompt()),
    }


def _run_call(description: str) -> dict:
    started = time.time()
    record: dict = {
        "kind": "live_call",
        "timestamp": _now(),
        "description": description,
        "active_prompt_version": active_prompt_version(),
        "model": settings.DEEPSEEK_MODEL,
        "base_url": settings.DEEPSEEK_BASE_URL,
    }
    try:
        ir, raw = parse_description_with_deepseek(description, return_raw=True)
        elapsed = time.time() - started
        record["elapsed_seconds"] = round(elapsed, 3)
        record["validated_ir_summary"] = _summarize_ir(ir)
        record["raw_response_status"] = "ok"
        record["raw_response_keys"] = sorted(list((raw or {}).keys()))
        if "usage" in (raw or {}):
            record["token_usage"] = (raw or {}).get("usage")
        choices = (raw or {}).get("choices") or []
        if choices:
            msg = (choices[0] or {}).get("message") or {}
            record["finish_reason"] = (choices[0] or {}).get("finish_reason")
            record["raw_message_text_length"] = len(msg.get("content") or "")
    except Exception as exc:  # noqa: BLE001
        record["raw_response_status"] = "error"
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["traceback"] = traceback.format_exc(limit=4)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompts-only", action="store_true",
                        help="Skip the API call; only dump prompts.")
    parser.add_argument("--skip", action="store_true",
                        help="Skip the API call without changing behavior.")
    parser.add_argument("--version", choices=sorted(PROMPT_REGISTRY.keys()),
                        help="Run only the named prompt version.")
    parser.add_argument("--prompts", nargs="*",
                        help="Override the default sample prompts.")
    args = parser.parse_args()

    if not settings.DEEPSEEK_API_KEY and not (args.prompts_only or args.skip):
        print("WARNING: DEEPSEEK_API_KEY is empty. Falling back to --prompts-only mode.")
        args.prompts_only = True

    prompts = args.prompts if args.prompts else SAMPLE_PROMPTS
    versions = [args.version] if args.version else sorted(PROMPT_REGISTRY.keys())

    report = {
        "generated_at": _now(),
        "active_default_prompt": active_prompt_version(),
        "model": settings.DEEPSEEK_MODEL,
        "base_url": settings.DEEPSEEK_BASE_URL,
        "prompt_versions": list(PROMPT_REGISTRY.keys()),
        "runs": [],
    }

    for version in versions:
        _maybe_switch_prompt(version)
        for description in prompts:
            print(f"[{version}] {description[:80]}")
            if args.prompts_only or args.skip:
                record = _record_prompt_only(description)
            else:
                record = _run_call(description)
            record["prompt_version"] = version
            report["runs"].append(record)
            if "error" in record:
                print(f"  -> ERROR {record['error']}")
            elif record.get("validated_ir_summary"):
                s = record["validated_ir_summary"]
                print(f"  -> type={s['circuit_type']} comps={s['component_count']} subs={s['subsystem_count']} t={record['elapsed_seconds']}s")
            else:
                print("  -> prompt-only record emitted")

    out_dir = ROOT / "tests" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"real_deepseek_ab_{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nReport written to: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
