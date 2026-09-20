#!/usr/bin/env python3
"""
Render assets/og-image.png (1200x630) from stats.json + the SAME vendored
topology the site map uses (assets/vendor/states-albers-10m.json).

Why this exists (2026-09-20): the post-load protocol refreshes the og-image
whenever a headline number changes, but every previous render lived in a
session scratchpad and was lost -- so the image sat at "341K+" while the
feed passed 343K. This is the committed, reproducible renderer.

Design (docs/PLAYBOOKS/website.md tokens -- never improvise new colours):
  bg #0a1128 · card #111a36 · teal #7fd4c8 · ink #eaf1fb · body #c7d2ea
  · muted #8fa3c7 · map ramp (low->high) #14384c #1d5560 #2a7873 #46a58f
  #7fd4c8 · map gray #2a3350 (no-list / unloaded states).
Layout: left column = letter-spaced wordmark, teal title, coverage line,
"NNNK+ records · refreshed <cadence>", Georgia-serif tagline; right = the
gap map, states filled by the site's 5-step ramp (thresholds 20/40/60/80).

Usage (from the site repo root, after publish_stats wrote stats.json):
    python3 tools/render_og.py            # writes assets/og-image.png
    python3 tools/render_og.py --out /tmp/preview.png
Requires matplotlib + Pillow (both in the pipeline venv). Output is
palette-quantized (256 colours) like every other flat-art PNG on the site.
"""
from __future__ import annotations

import argparse
import json
import os
import random

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Polygon  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BG, TEAL, INK, BODY, MUTED = "#0a1128", "#7fd4c8", "#eaf1fb", "#c7d2ea", "#8fa3c7"
RAMP = ["#14384c", "#1d5560", "#2a7873", "#46a58f", "#7fd4c8"]
GRAY = "#2a3350"

NAME_TO_POSTAL = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
    "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
    "Puerto Rico": "PR",
}


def step(gap_pct: float) -> int:
    """Same thresholds as assets/site-map.js."""
    return 4 if gap_pct >= 80 else 3 if gap_pct >= 60 else 2 if gap_pct >= 40 else 1 if gap_pct >= 20 else 0


def decode_topology(topo: dict) -> dict[str, list[list[tuple[float, float]]]]:
    """TopoJSON -> {postal: [ring, ...]} in the pre-projected 975x610 space."""
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:          # delta-encoded, quantized
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)

    def ring(arc_ids):
        out = []
        for i in arc_ids:
            pts = arcs[i] if i >= 0 else list(reversed(arcs[~i]))
            out.extend(pts if not out else pts[1:])
        return out

    shapes = {}
    for geom in topo["objects"]["states"]["geometries"]:
        postal = NAME_TO_POSTAL.get(geom["properties"]["name"])
        if not postal:
            continue
        polys = geom["arcs"] if geom["type"] == "MultiPolygon" else [geom["arcs"]]
        shapes[postal] = [ring(poly[0]) for poly in polys]   # exterior rings only
    return shapes


def headline(n: int) -> str:
    return f"{n // 1000}K+"


def render(stats_path: str, topo_path: str, out_path: str) -> None:
    stats = json.load(open(stats_path))
    shapes = decode_topology(json.load(open(topo_path)))
    gaps = {g["state"]: g for g in stats["state_gaps"]}
    cadence = stats.get("refresh_cadence", "weekly")

    fig = plt.figure(figsize=(12, 6.3), dpi=100)
    fig.patch.set_facecolor(BG)
    rng = random.Random(7)                       # faint starfield, deterministic
    ax_bg = fig.add_axes([0, 0, 1, 1]); ax_bg.set_axis_off()
    ax_bg.set_xlim(0, 1200); ax_bg.set_ylim(0, 630)
    ax_bg.scatter([rng.uniform(0, 1200) for _ in range(90)],
                  [rng.uniform(0, 630) for _ in range(90)],
                  s=[rng.uniform(1, 4) for _ in range(90)], c="#2f3b55", lw=0)

    # --- map (right ~57% of the canvas) ---
    ax = fig.add_axes([0.455, 0.05, 0.545, 0.90]); ax.set_axis_off()
    ax.set_xlim(-10, 985); ax.set_ylim(620, -10)  # topology y grows downward
    for postal, rings in shapes.items():
        if postal == "PR":
            continue
        g = gaps.get(postal)
        fill = RAMP[step(g["gap_pct"])] if g else GRAY
        for r in rings:
            ax.add_patch(Polygon(r, closed=True, facecolor=fill, edgecolor=BG, lw=0.7))

    # --- text (left column) ---
    sans_bold = font_manager.FontProperties(family=["Helvetica", "Arial", "DejaVu Sans"], weight="bold")
    sans = font_manager.FontProperties(family=["Helvetica", "Arial", "DejaVu Sans"])
    serif_bold = font_manager.FontProperties(family=["Georgia", "DejaVu Serif"], weight="bold")
    t = lambda y, s, fp, size, color: ax_bg.text(72, y, s, fontproperties=fp, fontsize=size, color=color, va="center")
    t(468, "r o s t e r p r o o f", sans, 30, INK)
    t(392, "Unified Provider Exclusions", sans_bold, 23, TEAL)
    dc = " + DC" if stats.get("includes_dc") else ""
    t(324, f"Federal + SAM + {stats['states']} States{dc}", sans, 22, INK)
    t(280, f"{headline(stats['records_total'])} records  ·  refreshed {cadence}", sans, 17, MUTED)
    t(165, "Half of state exclusions never", serif_bold, 23, INK)
    t(127, "reach the federal list.", serif_bold, 23, INK)

    tmp = out_path + ".rgb.png"
    fig.savefig(tmp, dpi=100, facecolor=BG)
    plt.close(fig)
    Image.open(tmp).convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT).save(out_path, optimize=True)
    os.remove(tmp)
    print(f"wrote {out_path} ({os.path.getsize(out_path)//1024} KB): "
          f"{headline(stats['records_total'])} records, {stats['states']} states{dc}, refreshed {cadence}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", default=os.path.join(ROOT, "stats.json"))
    ap.add_argument("--topo", default=os.path.join(ROOT, "assets", "vendor", "states-albers-10m.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "assets", "og-image.png"))
    a = ap.parse_args()
    render(a.stats, a.topo, a.out)
