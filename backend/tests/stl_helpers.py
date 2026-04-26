from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class StlBounds:
    width: float
    depth: float
    height: float


def assert_valid_stl(data: bytes) -> StlBounds:
    vertices = _read_vertices(data)
    assert vertices, "STL contained no vertices"

    xs = [vertex[0] for vertex in vertices]
    ys = [vertex[1] for vertex in vertices]
    zs = [vertex[2] for vertex in vertices]
    bounds = StlBounds(
        width=max(xs) - min(xs),
        depth=max(ys) - min(ys),
        height=max(zs) - min(zs),
    )
    assert bounds.width > 0
    assert bounds.depth > 0
    assert bounds.height > 0
    return bounds


def assert_close(actual: float, expected: float, *, tolerance: float = 0.75) -> None:
    assert math.isclose(actual, expected, abs_tol=tolerance), (
        f"expected {actual:.3f} to be within {tolerance:.3f} of {expected:.3f}"
    )


def _read_vertices(data: bytes) -> list[tuple[float, float, float]]:
    if len(data) >= 84:
        triangle_count = struct.unpack("<I", data[80:84])[0]
        expected_length = 84 + triangle_count * 50
        if triangle_count > 0 and expected_length == len(data):
            return _read_binary_vertices(data, triangle_count)
    return _read_ascii_vertices(data)


def _read_binary_vertices(data: bytes, triangle_count: int) -> list[tuple[float, float, float]]:
    vertices: list[tuple[float, float, float]] = []
    offset = 84
    for _ in range(triangle_count):
        offset += 12
        for _vertex_index in range(3):
            vertices.append(struct.unpack("<fff", data[offset : offset + 12]))
            offset += 12
        offset += 2
    return vertices


def _read_ascii_vertices(data: bytes) -> list[tuple[float, float, float]]:
    text = data.decode("utf-8", errors="ignore")
    vertices: list[tuple[float, float, float]] = []
    for match in re.finditer(
        r"vertex\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)",
        text,
    ):
        vertices.append((float(match.group(1)), float(match.group(2)), float(match.group(3))))
    return vertices
