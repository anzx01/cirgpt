"""
AI service router for circuit design
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
import logging

from nlp.circuit_ir import (
    parse_description_to_ir,
    classify_request,
    refusal_ir,
    normalize_real_parts,
    pair_usb_data_nets,
)
from nlp.circuit_generator import generate_circuit_design
from nlp.deepseek_parser import deepseek_configured, parse_description_with_deepseek
from nlp.explainer import build_rule_explanation, explain_circuit_with_deepseek
from nlp.reviser import revise_circuit_with_deepseek

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["AI"])


class ParseRequest(BaseModel):
    """Request for parsing natural language"""
    description: str


class GenerateRequest(BaseModel):
    """Request for generating circuit design"""
    requirements: Dict[str, Any]


class ExplainRequest(BaseModel):
    """Request for explaining a generated circuit from its CircuitIR"""
    description: str
    circuit_ir: Dict[str, Any]


class ReviseRequest(BaseModel):
    """Request for revising a circuit from chat instruction"""
    description: str
    circuit_ir: Dict[str, Any]
    instruction: str
    chat_history: List[Dict[str, Any]] = []
    images: List[Dict[str, Any]] = []  # [{name, mime_type, data_base64}]


class ParseResponse(BaseModel):
    """Response from parsing"""
    requirements: Dict[str, Any]
    success: bool
    message: str


class GenerateResponse(BaseModel):
    """Response from generating circuit"""
    netlist: str
    success: bool
    message: str


@router.post("/parse", response_model=ParseResponse)
async def parse_natural_language(request: ParseRequest) -> ParseResponse:
    """
    Parse natural language description into circuit requirements

    Args:
        request: Parse request with description

    Returns:
        Parsed requirements
    """
    try:
        logger.info(f"Parsing: {request.description[:100]}...")

        parser_warnings = []
        raw_response = None
        if deepseek_configured():
            try:
                requirements, raw_response = await parse_description_with_deepseek(request.description, return_raw=True)
                cls = classify_request(request.description.lower())
                if cls["refusals"]:
                    # DeepSeek will happily draft anything, but v1 generators
                    # cannot realize parts outside the registry — refuse
                    # rather than emit a placeholder presented as the request.
                    requirements = refusal_ir(request.description, cls["refusals"])
                    parser_warnings.append(
                        "DeepSeek drafted this request, but v1 cannot realize the named parts; no placeholder was generated."
                    )
                elif not requirements.get("supported", False) and request.description.strip():
                    # DeepSeek explicitly judged this request unsupported. Keep
                    # that verdict — overriding it with a rule-based generic
                    # draft would fabricate a result the request never asked for.
                    parser_warnings.append(
                        "DeepSeek judged this request unsupported; no fallback draft was generated."
                    )
                else:
                    # 登记器件规范化 + USB 数据线配对 + 限制披露（如板框尺寸无法保证）
                    requirements = normalize_real_parts(requirements, request.description.lower())
                    requirements = pair_usb_data_nets(requirements)
                    for note in cls["disclosures"]:
                        requirements.setdefault("warnings", []).append("限制披露：" + note)
            except Exception as exc:
                logger.warning(f"DeepSeek parsing failed, falling back to rule parser: {exc}")
                requirements = parse_description_to_ir(request.description)
                parser_warnings.append("DeepSeek parsing failed; rule-based parser was used.")
        else:
            requirements = parse_description_to_ir(request.description)

        if parser_warnings:
            requirements.setdefault("warnings", []).extend(parser_warnings)

        # Surface the raw DeepSeek payload as a top-level key so the frontend
        # "Show raw DeepSeek response" button can render it without needing to
        # dig into source.raw_response. None when DeepSeek was not used.
        if raw_response is not None:
            requirements["raw_deepseek_response"] = raw_response

        logger.info(f"Successfully parsed requirements")
        return ParseResponse(
            requirements=requirements,
            success=requirements.get("supported", False),
            message="Successfully parsed natural language description"
            if requirements.get("supported", False)
            else (requirements.get("warnings") or ["Unsupported circuit request"])[0]
        )

    except Exception as e:
        logger.error(f"Error parsing natural language: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse description: {str(e)}"
        )


@router.post("/generate", response_model=GenerateResponse)
async def generate_circuit(request: GenerateRequest) -> GenerateResponse:
    """
    Generate circuit netlist from requirements

    Args:
        request: Generate request with requirements

    Returns:
        Generated netlist
    """
    try:
        logger.info("Generating circuit design")

        # Compatibility endpoint. The KiCad-first v1 pipeline generates SPICE
        # in the EDA service from CircuitIR, but older clients may still call
        # this endpoint directly.
        netlist = generate_circuit_design(request.requirements)

        logger.info("Successfully generated netlist")
        return GenerateResponse(
            netlist=netlist,
            success=True,
            message="Successfully generated circuit design"
        )

    except Exception as e:
        logger.error(f"Error generating circuit: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate circuit: {str(e)}"
        )


@router.post("/explain", summary="Explain a generated circuit from its CircuitIR")
async def explain_circuit(request: ExplainRequest) -> Dict[str, Any]:
    """Generate a structured Chinese walkthrough (原理/连接/器件作用) of a
    generated circuit.

    Prefers the DeepSeek narrative; falls back to a deterministic structural
    summary of the IR when DeepSeek is unavailable. The ``source`` field
    tells the two apart ("deepseek" vs "rule") so the UI can disclose the
    downgrade honestly.
    """
    circuit_ir = request.circuit_ir or {}
    if not circuit_ir.get("components"):
        raise HTTPException(
            status_code=400,
            detail="circuit_ir.components is empty; nothing to explain",
        )

    source = "rule"
    warning = None
    try:
        explanation = await explain_circuit_with_deepseek(request.description, circuit_ir)
        source = "deepseek"
    except Exception as exc:
        logger.warning(f"DeepSeek explanation failed, using structural summary: {exc}")
        explanation = build_rule_explanation(circuit_ir)
        warning = f"AI 解读生成失败（{exc}），已回退为电路结构摘要。"

    explanation["source"] = source
    if warning:
        explanation.setdefault("warnings", []).append(warning)

    return {"explanation": explanation, "source": source, "success": True}


@router.post("/revise", summary="Revise a circuit from a chat instruction")
async def revise_circuit(request: ReviseRequest) -> Dict[str, Any]:
    """Apply one natural-language modification instruction to a CircuitIR.

    Returns the complete validated revised IR plus a Chinese revision
    summary. There is no rule-based fallback: when DeepSeek fails the
    error propagates so the caller keeps the old circuit untouched.
    """
    circuit_ir = request.circuit_ir or {}
    if not circuit_ir.get("components"):
        raise HTTPException(
            status_code=400,
            detail="circuit_ir.components is empty; nothing to revise",
        )

    try:
        result = await revise_circuit_with_deepseek(
            request.description,
            circuit_ir,
            request.instruction,
            chat_history=request.chat_history,
            images=request.images,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Circuit revision failed: {exc}")
        raise HTTPException(status_code=502, detail=f"修改电路失败：{exc}")

    return {
        "circuit_ir": result["circuit_ir"],
        "revision_summary": result["revision_summary"],
        "success": True,
    }


@router.get("/models")
async def list_models() -> Dict[str, Any]:
    """
    List available AI models

    Returns:
        List of models
    """
    try:
        return {
            "models": [
                {
                    "name": "DeepSeek",
                    "version": "chat-completions",
                    "description": "Optional large-model parser that returns validated CircuitIR JSON",
                    "status": "active" if deepseek_configured() else "not_configured"
                },
                {
                    "name": "CircuitBERT",
                    "version": "1.0",
                    "description": "Local/rule fallback circuit design understanding",
                    "status": "active"
                }
            ]
        }
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list models: {str(e)}"
        )
