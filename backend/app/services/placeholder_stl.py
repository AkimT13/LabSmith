"""Tiny placeholder STL used by mock-mode generation.

Until M5 wires up real CadQuery output, mock mode needs *something* on disk so
the frontend 3D viewer has bytes to render. We ship a 10mm unit cube generated
in binary STL format. The bytes are deterministic — every mock generation
produces the exact same payload, which is fine: the point is to exercise the
viewer path, not to display the user's actual design.

Binary STL layout (per Wikipedia):
    UINT8[80]    – header (free-form, by convention non-"solid" prefix)
    UINT32       – number of triangles
    foreach triangle:
        REAL32[3]    – normal vector
        REAL32[9]    – three vertices (x, y, z each)
        UINT16       – attribute byte count (commonly 0)

For a cube: 12 triangles → 80 + 4 + 12 * (12 + 36 + 2) = 84 + 600 = 684 bytes.
"""
from __future__ import annotations

import struct
from functools import lru_cache

# Default cube edge length, mm. Picked to look reasonable in a default
# camera setup without dwarfing the grid.
DEFAULT_EDGE_MM = 10.0


def _build_unit_cube_stl(edge: float = DEFAULT_EDGE_MM) -> bytes:
    """Generate binary STL bytes for an axis-aligned cube centered on the origin."""
    half = edge / 2.0

    # 8 corners of the cube
    v = [
        (-half, -half, -half),  # 0
        (half, -half, -half),  # 1
        (half, half, -half),  # 2
        (-half, half, -half),  # 3
        (-half, -half, half),  # 4
        (half, -half, half),  # 5
        (half, half, half),  # 6
        (-half, half, half),  # 7
    ]

    # 12 triangles, 2 per face. (normal, v0, v1, v2)
    # Order chosen so each face is wound counter-clockwise when viewed from
    # outside the cube — matches the +X/+Y/+Z normal convention.
    faces = [
        # bottom (-Z)
        ((0.0, 0.0, -1.0), v[0], v[2], v[1]),
        ((0.0, 0.0, -1.0), v[0], v[3], v[2]),
        # top (+Z)
        ((0.0, 0.0, 1.0), v[4], v[5], v[6]),
        ((0.0, 0.0, 1.0), v[4], v[6], v[7]),
        # front (-Y)
        ((0.0, -1.0, 0.0), v[0], v[1], v[5]),
        ((0.0, -1.0, 0.0), v[0], v[5], v[4]),
        # back (+Y)
        ((0.0, 1.0, 0.0), v[2], v[3], v[7]),
        ((0.0, 1.0, 0.0), v[2], v[7], v[6]),
        # left (-X)
        ((-1.0, 0.0, 0.0), v[3], v[0], v[4]),
        ((-1.0, 0.0, 0.0), v[3], v[4], v[7]),
        # right (+X)
        ((1.0, 0.0, 0.0), v[1], v[2], v[6]),
        ((1.0, 0.0, 0.0), v[1], v[6], v[5]),
    ]

    header = b"LabSmith placeholder STL (mock mode unit cube)"
    out = bytearray()
    out += header.ljust(80, b"\x00")
    out += struct.pack("<I", len(faces))
    for normal, p0, p1, p2 in faces:
        out += struct.pack("<3f", *normal)
        out += struct.pack("<3f", *p0)
        out += struct.pack("<3f", *p1)
        out += struct.pack("<3f", *p2)
        out += struct.pack("<H", 0)
    return bytes(out)


@lru_cache(maxsize=1)
def get_placeholder_stl_bytes() -> bytes:
    """Cached so we only build the cube once per process."""
    return _build_unit_cube_stl()
