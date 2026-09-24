"""Content bbox of an exported KiCad SVG, with transforms applied.

KiCad 10 exports rotated symbols/labels inside <g transform="rotate(...)">
groups. A tag-by-tag regex scan cannot see the transform chain, so it reads
pre-transform coordinates and once produced a crop box with ~185mm of
phantom margin. This module walks the real XML tree with a 2D affine matrix
stack, so every point lands where it actually renders.
"""
from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from typing import List, Optional, Tuple

_NUM = r"-?\d+\.?\d*"
_PAIR_RE = re.compile(rf"({_NUM})[ ,]+({_NUM})")
_CMD_RE = re.compile(r"([MLmlHhVvAaCcSsQqTtZz])([^MLmlHhVvAaCcSsQqTtZz]*)")


def _path_points(d: str, m):
    """World-space points of a path's coordinate-bearing commands.

    A naive all-numbers pairing misreads arc commands ('A rx ry rot laf sf
    x y' — the radii/flags get paired into phantom coordinates), which once
    pushed a bbox 165mm below the real drawing.
    """
    pts = []
    cx = cy = 0.0
    for cmd, argstr in _CMD_RE.findall(d):
        nums = [float(v) for v in re.findall(_NUM, argstr)]
        rel = cmd.islower()
        if cmd in "MmLlTt":
            for i in range(0, len(nums) - 1, 2):
                x, y = nums[i], nums[i + 1]
                if rel:
                    x += cx
                    y += cy
                pts.append(_apply(m, x, y))
                cx, cy = x, y
        elif cmd in "Hh":
            for v in nums:
                x = v + cx if rel else v
                pts.append(_apply(m, x, cy))
                cx = x
        elif cmd in "Vv":
            for v in nums:
                y = v + cy if rel else v
                pts.append(_apply(m, cx, y))
                cy = y
        elif cmd in "Aa":
            for i in range(0, len(nums) - 6, 7):
                x, y = nums[i + 5], nums[i + 6]
                if rel:
                    x += cx
                    y += cy
                pts.append(_apply(m, x, y))
                cx, cy = x, y
        elif cmd in "Cc":
            for i in range(0, len(nums) - 5, 6):
                for j in (0, 2, 4):  # control points + endpoint
                    x, y = nums[i + j], nums[i + j + 1]
                    if rel:
                        x += cx
                        y += cy
                    pts.append(_apply(m, x, y))
                ex, ey = nums[i + 4], nums[i + 5]
                cx, cy = (cx + ex, cy + ey) if rel else (ex, ey)
        elif cmd in "QqSs":
            for i in range(0, len(nums) - 3, 4):
                for j in (0, 2):
                    x, y = nums[i + j], nums[i + j + 1]
                    if rel:
                        x += cx
                        y += cy
                    pts.append(_apply(m, x, y))
                ex, ey = nums[i + 2], nums[i + 3]
                cx, cy = (cx + ex, cy + ey) if rel else (ex, ey)
    return pts


def _mat_mul(m1, m2):
    """Compose transforms: apply m1, then m2."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return [
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    ]


def _parse_transform(s: str):
    m = [1, 0, 0, 1, 0, 0]
    for name, args in re.findall(r"(matrix|translate|scale|rotate)\(([^)]*)\)", s or ""):
        vals = [float(v) for v in re.findall(_NUM, args)]
        if name == "matrix" and len(vals) >= 6:
            t = vals[:6]
        elif name == "translate" and vals:
            t = [1, 0, 0, 1, vals[0], vals[1] if len(vals) > 1 else 0]
        elif name == "scale" and vals:
            sx = vals[0]
            sy = vals[1] if len(vals) > 1 else sx
            t = [sx, 0, 0, sy, 0, 0]
        elif name == "rotate" and vals:
            a = math.radians(vals[0])
            cos, sin = math.cos(a), math.sin(a)
            rot = [cos, sin, -sin, cos, 0, 0]
            if len(vals) == 3:
                cx, cy = vals[1], vals[2]
                t = _mat_mul(
                    _mat_mul([1, 0, 0, 1, cx, cy], rot), [1, 0, 0, 1, -cx, -cy]
                )
            else:
                t = rot
        else:
            continue
        m = _mat_mul(m, t)
    return m


def _apply(m, x: float, y: float) -> Tuple[float, float]:
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def _invisible(el) -> bool:
    style = el.get("style") or ""
    return (
        el.get("opacity") == "0"
        or el.get("stroke-opacity") == "0"
        or el.get("fill-opacity") == "0"
        or el.get("display") == "none"
        or el.get("visibility") == "hidden"
        or "display:none" in style.replace(" ", "")
        or "display: none" in style
        or "visibility:hidden" in style.replace(" ", "")
        or "opacity:0" in style.replace(" ", "")
    )


# Subtrees that never render where they sit in the document.
_NON_RENDERING = {"defs", "clippath", "mask", "symbol", "pattern", "marker", "title", "desc"}


def content_bbox(svg: str) -> Optional[Tuple[float, float, float, float]]:
    """Rendered-geometry bbox (min_x, min_y, max_x, max_y) or None.

    Text is included with an approximate width (char count * 1.1mm) since
    labels legitimately extend past their symbol bodies.
    """
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return None
    pts: List[Tuple[float, float]] = []

    def walk(el, m):
        tag = el.tag.split("}")[-1].lower()
        if tag in _NON_RENDERING or _invisible(el):
            return
        m = _mat_mul(m, _parse_transform(el.get("transform", "")))
        if tag == "path":
            pts.extend(_path_points(el.get("d") or "", m))
        elif tag in ("polyline", "polygon"):
            for a, b in _PAIR_RE.findall(el.get("points") or ""):
                pts.append(_apply(m, float(a), float(b)))
        elif tag == "line":
            for ax, ay in ((el.get("x1"), el.get("y1")), (el.get("x2"), el.get("y2"))):
                try:
                    pts.append(_apply(m, float(ax), float(ay)))
                except (TypeError, ValueError):
                    pass
        elif tag == "rect":
            try:
                x, y = float(el.get("x") or 0), float(el.get("y") or 0)
                w, h = float(el.get("width") or 0), float(el.get("height") or 0)
            except ValueError:
                w = 0
            if w or h:
                for dx, dy in ((0, 0), (w, 0), (0, h), (w, h)):
                    pts.append(_apply(m, x + dx, y + dy))
        elif tag == "circle":
            try:
                cx, cy, r = (
                    float(el.get("cx") or 0),
                    float(el.get("cy") or 0),
                    float(el.get("r") or 0),
                )
            except ValueError:
                r = -1
            if r >= 0:
                for dx, dy in ((-r, 0), (r, 0), (0, -r), (0, r)):
                    pts.append(_apply(m, cx + dx, cy + dy))
        elif tag == "text":
            try:
                p = _apply(m, float(el.get("x") or 0), float(el.get("y") or 0))
            except ValueError:
                p = None
            if p is not None:
                text = "".join(el.itertext())
                pts.append(p)
                pts.append((p[0] + len(text) * 1.1, p[1]))
                pts.append((p[0], p[1] + 1.5))
        for child in el:
            walk(child, m)

    walk(root, [1, 0, 0, 1, 0, 0])
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if max(xs) <= min(xs) or max(ys) <= min(ys):
        return None
    return (min(xs), min(ys), max(xs), max(ys))
