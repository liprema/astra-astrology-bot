"""
High-Resolution Vintage Pop-Art / Rider-Waite Tarot Spread Renderer for ARCANA ("Аркана"):
1. Every Tarot card is rendered in the exact aesthetic of the user's reference ("THE MARGARITA."):
   - Cream rounded outer card with crisp black ink border
   - Sky-blue/pastel scenic frame with radiating yellow Sun (with inner contour arc) in top-left
   - Fluffy white clouds with inner contour arcs & 4-pointed golden stars with vertical shine lines
   - Two multi-armed green saguaro cacti on the left and two on the right
   - Vintage skull at the base with a black crow perched on top and a layered red rose beside it
   - Bold central suit/archetype artwork (Coral Goblet with lime wheel & salted rim, Silver Sword & Crown,
     Blossoming Flame Wand, Golden Pentacle Star, or Mystic Sun-Wheel)
   - Top Roman Numeral framed between horizontal serif overline & underline bars
   - Bottom white title banner with bold uppercase serif title + trailing period (`.`)
2. The entire spread sheet is framed as a Vintage Cream Poster (#faf6ee) with Celestial Sun & Crescent Moon
   in the header and structured vintage cream cards with pastel medallions on the right!
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Dict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches


INK = "#1a1917"
CREAM_CARD = "#f7f4e6"
POSTER_BG = "#faf6ee"
CARD_BOX_BG = "#f5efe2"
BORDER_TAN = "#cbbba0"
GOLD_ACCENT = "#b58338"
INK_MUTED = "#5a534a"

SKY_PALETTE = {
    "Огонь": "#d9f0f7",
    "Вода": "#d4eef7",
    "Воздух": "#dfeff5",
    "Земля": "#e0f2ea",
}


def _draw_sparkle_poster(ax, cx: float, cy: float, rx: float, ry: float, col: str = GOLD_ACCENT, z: float = 4) -> None:
    pts = [
        (cx, cy + ry),
        (cx + rx * 0.25, cy + ry * 0.25),
        (cx + rx, cy),
        (cx + rx * 0.25, cy - ry * 0.25),
        (cx, cy - ry),
        (cx - rx * 0.25, cy - ry * 0.25),
        (cx - rx, cy),
        (cx - rx * 0.25, cy + ry * 0.25),
    ]
    ax.add_patch(patches.Polygon(pts, closed=True, facecolor=col, edgecolor="none", zorder=z))


def _draw_poster_box(ax, x: float, y: float, w: float, h: float, title: str = "") -> None:
    box = patches.FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.006,rounding_size=0.015",
        facecolor=CARD_BOX_BG,
        edgecolor=BORDER_TAN,
        linewidth=1.4,
        zorder=1,
    )
    ax.add_patch(box)
    if title:
        ax.text(
            x + w / 2.0,
            y + h - 0.018,
            title,
            color=INK,
            fontsize=9.5,
            fontweight="bold",
            family="serif",
            ha="center",
            va="top",
            zorder=3,
        )
        half_s = min(w * 0.44, len(title) * 0.0052 + 0.025)
        _draw_sparkle_poster(ax, x + w / 2.0 - half_s, y + h - 0.025, 0.005, 0.007, GOLD_ACCENT, z=4)
        _draw_sparkle_poster(ax, x + w / 2.0 + half_s, y + h - 0.025, 0.005, 0.007, GOLD_ACCENT, z=4)
        ax.plot([x + 0.018, x + w - 0.018], [y + h - 0.040, y + h - 0.040], color=BORDER_TAN, linewidth=0.9, zorder=2)


def _draw_celestial_sun_header(ax, cx: float, cy: float, r_x: float, r_y: float) -> None:
    for i in range(16):
        ang = math.radians(i * 22.5)
        r_len = 1.72 if i % 2 == 0 else 1.36
        w_ang = 0.11 if i % 2 == 0 else 0.08
        tri = [
            (cx + r_x * 0.88 * math.cos(ang - w_ang), cy + r_y * 0.88 * math.sin(ang - w_ang)),
            (cx + r_x * r_len * math.cos(ang), cy + r_y * r_len * math.sin(ang)),
            (cx + r_x * 0.88 * math.cos(ang + w_ang), cy + r_y * 0.88 * math.sin(ang + w_ang)),
        ]
        ax.add_patch(patches.Polygon(tri, closed=True, facecolor="#e8be74", edgecolor="#8c6223", linewidth=0.9, zorder=3))
    disc = patches.Ellipse((cx, cy), width=r_x * 1.9, height=r_y * 1.9, facecolor="#f7dfb2", edgecolor="#8c6223", linewidth=1.3, zorder=4)
    ax.add_patch(disc)
    for side in (-1, 1):
        ex = cx + side * r_x * 0.34
        ey = cy + r_y * 0.16
        ax.add_patch(patches.Ellipse((ex, ey), width=r_x * 0.22, height=r_y * 0.14, facecolor="#6e4b16", edgecolor="none", zorder=5))
    smile = patches.Arc((cx, cy - r_y * 0.22), r_x * 0.42, r_y * 0.22, angle=0, theta1=200, theta2=340, color="#6e4b16", linewidth=1.1, zorder=5)
    ax.add_patch(smile)


def _draw_celestial_moon_header(ax, cx: float, cy: float, r_x: float, r_y: float) -> None:
    outer = patches.Ellipse((cx, cy), width=r_x * 2.1, height=r_y * 2.1, facecolor="#8c82b0", edgecolor="#3f375c", linewidth=1.3, zorder=3)
    ax.add_patch(outer)
    cutout = patches.Ellipse((cx - r_x * 0.56, cy + r_y * 0.14), width=r_x * 1.75, height=r_y * 1.85, facecolor=POSTER_BG, edgecolor="none", zorder=4)
    ax.add_patch(cutout)


def _draw_cloud(ax, cx: float, cy: float, w: float, h: float, z: float = 4) -> None:
    """Draw a fluffy comic/pop-art white cloud with black outline and inner contour arcs."""
    puffs = [
        (cx - w * 0.28, cy - h * 0.08, w * 0.46, h * 0.68),
        (cx + w * 0.26, cy - h * 0.08, w * 0.46, h * 0.68),
        (cx - w * 0.06, cy + h * 0.14, w * 0.54, h * 0.80),
        (cx + w * 0.08, cy - h * 0.14, w * 0.62, h * 0.64),
    ]
    for px, py, pw, ph in puffs:
        e_out = patches.Ellipse((px, py), width=pw * 1.09, height=ph * 1.11, facecolor=INK, edgecolor="none", zorder=z)
        ax.add_patch(e_out)
    for px, py, pw, ph in puffs:
        e_in = patches.Ellipse((px, py), width=pw, height=ph, facecolor="#ffffff", edgecolor="none", zorder=z + 0.1)
        ax.add_patch(e_in)
    # Subtle inner cloud puff line (matching reference!)
    arc = patches.Arc((cx - w * 0.05, cy - h * 0.02), w * 0.35, h * 0.40, angle=0, theta1=200, theta2=330, color=INK, linewidth=1.0, zorder=z + 0.2)
    ax.add_patch(arc)


def _draw_sparkle_card(ax, cx: float, cy: float, rx: float, ry: float, z: float = 5) -> None:
    """Draw a 4-pointed yellow star with black outline and vertical shine lines (matching reference!)."""
    pts = [
        (cx, cy + ry),
        (cx + rx * 0.28, cy + ry * 0.28),
        (cx + rx, cy),
        (cx + rx * 0.28, cy - ry * 0.28),
        (cx, cy - ry),
        (cx - rx * 0.28, cy - ry * 0.28),
        (cx - rx, cy),
        (cx - rx * 0.28, cy + ry * 0.28),
    ]
    star = patches.Polygon(pts, closed=True, facecolor="#ffea00", edgecolor=INK, linewidth=1.15, zorder=z)
    ax.add_patch(star)
    ax.plot([cx, cx], [cy - ry * 1.38, cy + ry * 1.38], color=INK, linewidth=0.95, zorder=z - 0.1)


def _draw_sun_corner(ax, sx: float, sy: float, rx: float, ry: float, z: float = 4) -> None:
    """Draw the bright yellow radiating sun in top-left of card with inner contour arcs (matching reference!)."""
    num_rays = 14
    for i in range(num_rays):
        ang = math.radians(i * (360.0 / num_rays))
        r_len = 1.85 if i % 2 == 0 else 1.45
        ang_w = 0.13
        tri = [
            (sx + rx * 0.82 * math.cos(ang - ang_w), sy + ry * 0.82 * math.sin(ang - ang_w)),
            (sx + rx * r_len * math.cos(ang), sy + ry * r_len * math.sin(ang)),
            (sx + rx * 0.82 * math.cos(ang + ang_w), sy + ry * 0.82 * math.sin(ang + ang_w)),
        ]
        ray = patches.Polygon(tri, closed=True, facecolor="#ffea00", edgecolor=INK, linewidth=1.15, zorder=z)
        ax.add_patch(ray)
    disc = patches.Ellipse((sx, sy), width=rx * 1.95, height=ry * 1.95, facecolor="#ffea00", edgecolor=INK, linewidth=1.5, zorder=z + 0.2)
    ax.add_patch(disc)
    inner_arc1 = patches.Arc((sx, sy), rx * 1.45, ry * 1.45, angle=0, theta1=200, theta2=350, color=INK, linewidth=1.1, zorder=z + 0.3)
    inner_arc2 = patches.Arc((sx, sy), rx * 1.35, ry * 1.35, angle=0, theta1=45, theta2=145, color=INK, linewidth=1.0, zorder=z + 0.3)
    ax.add_patch(inner_arc1)
    ax.add_patch(inner_arc2)


def _draw_saguaro_cactus(ax, px: float, y_base: float, w: float, h: float, arm_side: int = 1, z: float = 4.6) -> None:
    """Draw a classic multi-armed green desert saguaro cactus with black outline (matching reference!)."""
    trunk = patches.FancyBboxPatch(
        (px - w * 0.026, y_base),
        w * 0.052,
        h,
        boxstyle="round,pad=0.002,rounding_size=0.015",
        facecolor="#6ab845",
        edgecolor=INK,
        linewidth=1.3,
        zorder=z,
    )
    ax.add_patch(trunk)
    # Left & right arms
    arm_1 = patches.FancyBboxPatch(
        (px - (w * 0.082 if arm_side > 0 else -w * 0.015), y_base + h * 0.38),
        w * 0.068,
        h * 0.42,
        boxstyle="round,pad=0.002,rounding_size=0.012",
        facecolor="#6ab845",
        edgecolor=INK,
        linewidth=1.25,
        zorder=z - 0.05,
    )
    ax.add_patch(arm_1)
    arm_2 = patches.FancyBboxPatch(
        (px + (w * 0.015 if arm_side > 0 else -w * 0.075), y_base + h * 0.25),
        w * 0.062,
        h * 0.36,
        boxstyle="round,pad=0.002,rounding_size=0.012",
        facecolor="#6ab845",
        edgecolor=INK,
        linewidth=1.2,
        zorder=z - 0.05,
    )
    ax.add_patch(arm_2)


def _draw_skull_crow_rose(ax, cx: float, y_base: float, w: float, h: float, z: float = 5.4) -> None:
    """Draw the iconic vintage skull at the bottom center with a black crow on top and red rose beside it."""
    # Skull cranium & jaw
    sk_y = y_base + h * 0.075
    cranium = patches.Ellipse((cx, sk_y + h * 0.03), width=w * 0.25, height=h * 0.14, facecolor="#d6d5d2", edgecolor=INK, linewidth=1.4, zorder=z)
    ax.add_patch(cranium)
    jaw = patches.FancyBboxPatch((cx - w * 0.075, y_base + h * 0.005), w * 0.15, h * 0.055, boxstyle="round,pad=0.002,rounding_size=0.008", facecolor="#d6d5d2", edgecolor=INK, linewidth=1.35, zorder=z)
    ax.add_patch(jaw)
    # Eye sockets & nasal cavity
    for side in (-1, 1):
        eye_s = patches.Ellipse((cx + side * w * 0.052, sk_y + h * 0.015), width=w * 0.062, height=h * 0.042, facecolor="#8c8b88", edgecolor=INK, linewidth=1.15, zorder=z + 0.1)
        ax.add_patch(eye_s)
    nose_tri = [(cx, sk_y + h * 0.005), (cx - w * 0.024, sk_y - h * 0.030), (cx + w * 0.024, sk_y - h * 0.030)]
    ax.add_patch(patches.Polygon(nose_tri, closed=True, facecolor="#8c8b88", edgecolor=INK, linewidth=1.1, zorder=z + 0.1))

    # Black Crow perched atop the skull
    crow_y = sk_y + h * 0.105
    crow_body = [
        (cx - w * 0.08, crow_y + h * 0.035),
        (cx - w * 0.03, crow_y + h * 0.050),
        (cx + w * 0.06, crow_y + h * 0.005),
        (cx + w * 0.12, crow_y - h * 0.025),
        (cx + w * 0.02, crow_y - h * 0.010),
        (cx - w * 0.05, crow_y + h * 0.010),
    ]
    ax.add_patch(patches.Polygon(crow_body, closed=True, facecolor="#2b2b2b", edgecolor=INK, linewidth=1.2, zorder=z + 0.3))
    beak = [(cx - w * 0.08, crow_y + h * 0.035), (cx - w * 0.12, crow_y + h * 0.030), (cx - w * 0.08, crow_y + h * 0.022)]
    ax.add_patch(patches.Polygon(beak, closed=True, facecolor="#2b2b2b", edgecolor=INK, linewidth=1.0, zorder=z + 0.3))

    # Layered Red Rose at bottom-right of skull
    rx, ry = cx + w * 0.155, y_base + h * 0.032
    rose_out = patches.Ellipse((rx, ry), width=w * 0.105, height=h * 0.062, facecolor="#c92a2a", edgecolor=INK, linewidth=1.3, zorder=z + 0.4)
    ax.add_patch(rose_out)
    rose_in = patches.Ellipse((rx, ry), width=w * 0.055, height=h * 0.032, facecolor="#e03131", edgecolor=INK, linewidth=1.0, zorder=z + 0.5)
    ax.add_patch(rose_in)


def _draw_central_illustration(ax, cx: float, y_bot: float, w: float, h: float, card: Dict, z: float = 5) -> None:
    """
    Draw the desert floor, 4 saguaro cacti, skull+crow+rose base, and central suit/arcana emblem.
    """
    suit = card.get("suit") or "Major"
    ground_h = h * 0.055

    # Desert sand/green ground strip at bottom of art frame
    ground = patches.Rectangle(
        (cx - w / 2.0, y_bot),
        w,
        ground_h,
        facecolor="#d8e89b",
        edgecolor=INK,
        linewidth=1.4,
        zorder=z - 0.5,
    )
    ax.add_patch(ground)

    # Four desert saguaro cacti (2 on left, 2 on right — matching reference!)
    _draw_saguaro_cactus(ax, cx - w * 0.38, y_bot + ground_h * 0.3, w, h * 0.38, arm_side=1, z=z)
    _draw_saguaro_cactus(ax, cx - w * 0.24, y_bot + ground_h * 0.3, w, h * 0.27, arm_side=-1, z=z)
    _draw_saguaro_cactus(ax, cx + w * 0.25, y_bot + ground_h * 0.3, w, h * 0.29, arm_side=1, z=z)
    _draw_saguaro_cactus(ax, cx + w * 0.38, y_bot + ground_h * 0.3, w, h * 0.36, arm_side=-1, z=z)

    # Draw the vintage skull + black crow + red rose at the base
    _draw_skull_crow_rose(ax, cx, y_bot + ground_h * 0.4, w, h, z=z + 0.5)

    mid_y = y_bot + h * 0.50
    base_top = y_bot + h * 0.20

    if suit == "Cups" or (suit == "Major" and card["number"] % 4 == 0):
        # Iconic Coral-Red Goblet / Margarita Glass with lime slice & salted rim (1:1 homage to reference!)
        stem = patches.Rectangle((cx - w * 0.026, base_top), w * 0.052, h * 0.24, facecolor="#e8f6fa", edgecolor=INK, linewidth=1.4, zorder=z + 0.1)
        ax.add_patch(stem)
        foot = patches.Ellipse((cx, base_top), width=w * 0.30, height=h * 0.032, facecolor="#e8f6fa", edgecolor=INK, linewidth=1.35, zorder=z + 0.1)
        ax.add_patch(foot)
        # Lime wheel on top-right of rim with segments
        lx, ly = cx + w * 0.24, mid_y + h * 0.17
        lime_outer = patches.Ellipse((lx, ly), width=w * 0.24, height=h * 0.15, facecolor="#8ac947", edgecolor=INK, linewidth=1.45, zorder=z + 0.15)
        ax.add_patch(lime_outer)
        lime_inner = patches.Ellipse((lx, ly), width=w * 0.19, height=h * 0.12, facecolor="#b8e067", edgecolor=INK, linewidth=1.1, zorder=z + 0.16)
        ax.add_patch(lime_inner)
        for seg_a in range(0, 360, 60):
            rad_s = math.radians(seg_a)
            ax.plot([lx, lx + w * 0.09 * math.cos(rad_s)], [ly, ly + h * 0.055 * math.sin(rad_s)], color=INK, linewidth=0.9, zorder=z + 0.18)
        # Coral-red coupe bowl
        bowl_pts = [
            (cx - w * 0.33, mid_y + h * 0.15),
            (cx + w * 0.33, mid_y + h * 0.15),
            (cx + w * 0.25, mid_y + h * 0.02),
            (cx + w * 0.10, mid_y - h * 0.10),
            (cx - w * 0.10, mid_y - h * 0.10),
            (cx - w * 0.25, mid_y + h * 0.02),
        ]
        ax.add_patch(patches.Polygon(bowl_pts, closed=True, facecolor="#f2665e", edgecolor=INK, linewidth=1.6, zorder=z + 0.2))
        # White foamy/salted rim
        rim = patches.FancyBboxPatch((cx - w * 0.33, mid_y + h * 0.13), w * 0.66, h * 0.032, boxstyle="round,pad=0.002,rounding_size=0.008", facecolor="#ffffff", edgecolor=INK, linewidth=1.35, zorder=z + 0.3)
        ax.add_patch(rim)

    elif suit == "Swords" or (suit == "Major" and card["number"] % 4 == 1):
        # Silver Sword piercing a Golden Royal Crown above the skull & crow
        blade_pts = [
            (cx, mid_y + h * 0.29),
            (cx + w * 0.048, base_top + h * 0.06),
            (cx - w * 0.048, base_top + h * 0.06),
        ]
        ax.add_patch(patches.Polygon(blade_pts, closed=True, facecolor="#e3edf7", edgecolor=INK, linewidth=1.6, zorder=z + 0.2))
        ax.plot([cx, cx], [base_top + h * 0.08, mid_y + h * 0.25], color=INK, linewidth=0.9, zorder=z + 0.25)
        hilt = patches.FancyBboxPatch((cx - w * 0.19, base_top + h * 0.04), w * 0.38, h * 0.032, boxstyle="round,pad=0.003", facecolor="#ffd43b", edgecolor=INK, linewidth=1.45, zorder=z + 0.3)
        ax.add_patch(hilt)
        # Golden Crown around middle of blade
        crown_pts = [
            (cx - w * 0.18, mid_y + h * 0.04),
            (cx - w * 0.22, mid_y + h * 0.15),
            (cx - w * 0.09, mid_y + h * 0.09),
            (cx, mid_y + h * 0.18),
            (cx + w * 0.09, mid_y + h * 0.09),
            (cx + w * 0.22, mid_y + h * 0.15),
            (cx + w * 0.18, mid_y + h * 0.04),
        ]
        ax.add_patch(patches.Polygon(crown_pts, closed=True, facecolor="#ffea00", edgecolor=INK, linewidth=1.45, zorder=z + 0.35))

    elif suit == "Wands" or (suit == "Major" and card["number"] % 4 == 2):
        # Blossoming Royal Desert Wand with layered Flame & Golden Eye above skull
        staff = patches.FancyBboxPatch((cx - w * 0.034, base_top), w * 0.068, h * 0.38, boxstyle="round,pad=0.003", facecolor="#c27438", edgecolor=INK, linewidth=1.6, zorder=z + 0.2)
        ax.add_patch(staff)
        flame_outer = [
            (cx, mid_y + h * 0.31),
            (cx + w * 0.18, mid_y + h * 0.13),
            (cx + w * 0.10, mid_y + h * 0.02),
            (cx - w * 0.10, mid_y + h * 0.02),
            (cx - w * 0.18, mid_y + h * 0.13),
        ]
        ax.add_patch(patches.Polygon(flame_outer, closed=True, facecolor="#ff6b35", edgecolor=INK, linewidth=1.55, zorder=z + 0.3))
        flame_inner = [
            (cx, mid_y + h * 0.24),
            (cx + w * 0.09, mid_y + h * 0.11),
            (cx - w * 0.09, mid_y + h * 0.11),
        ]
        ax.add_patch(patches.Polygon(flame_inner, closed=True, facecolor="#ffea00", edgecolor=INK, linewidth=1.25, zorder=z + 0.4))

    else:
        # Golden Pentacle / Mystic Sun-Wheel with 5-pointed Star floating above the skull & crow
        stem = patches.Rectangle((cx - w * 0.024, base_top), w * 0.048, h * 0.20, facecolor="#e8f6fa", edgecolor=INK, linewidth=1.35, zorder=z + 0.1)
        ax.add_patch(stem)
        disc = patches.Ellipse((cx, mid_y + h * 0.08), width=w * 0.48, height=h * 0.29, facecolor="#ffea00", edgecolor=INK, linewidth=1.7, zorder=z + 0.2)
        ax.add_patch(disc)
        star_pts = []
        for k in range(10):
            r_k = 0.20 if k % 2 == 0 else 0.082
            ang = math.radians(90 + k * 36)
            star_pts.append((cx + w * r_k * math.cos(ang), mid_y + h * 0.08 + h * (r_k * 0.60) * math.sin(ang)))
        ax.add_patch(patches.Polygon(star_pts, closed=True, facecolor="#fff9db", edgecolor=INK, linewidth=1.35, zorder=z + 0.3))


def draw_single_card_on_axes(
    ax,
    cx: float,
    cy: float,
    card_w: float,
    card_h: float,
    card: Dict,
    badge_label: str = "",
) -> None:
    el = card.get("element", "Вода")
    sky_col = SKY_PALETTE.get(el, "#d4eef7")
    is_rev = bool(card.get("is_reversed"))

    x0 = cx - card_w / 2.0
    y0 = 1.0 - cy - card_h / 2.0

    # Soft drop shadow
    shadow = patches.FancyBboxPatch(
        (x0 + 0.006, y0 - 0.008),
        card_w,
        card_h,
        boxstyle="round,pad=0.008,rounding_size=0.022",
        facecolor="#c9bda6",
        edgecolor="none",
        alpha=0.55,
        zorder=2,
    )
    ax.add_patch(shadow)

    # Outer cream rounded card border
    outer_card = patches.FancyBboxPatch(
        (x0, y0),
        card_w,
        card_h,
        boxstyle="round,pad=0.008,rounding_size=0.022",
        facecolor=CREAM_CARD,
        edgecolor=INK,
        linewidth=2.2,
        zorder=3,
    )
    ax.add_patch(outer_card)

    pad_x = card_w * 0.052
    pad_y = card_h * 0.034
    in_x = x0 + pad_x
    in_y = y0 + pad_y
    in_w = card_w - 2 * pad_x
    in_h = card_h - 2 * pad_y

    banner_h = in_h * 0.162
    art_h = in_h - banner_h
    art_y = in_y + banner_h

    # Sky background box
    sky_box = patches.Rectangle(
        (in_x, art_y),
        in_w,
        art_h,
        facecolor=sky_col,
        edgecolor=INK,
        linewidth=1.7,
        zorder=3.5,
    )
    ax.add_patch(sky_box)

    # Bottom white title banner
    banner_box = patches.Rectangle(
        (in_x, in_y),
        in_w,
        banner_h,
        facecolor="#ffffff",
        edgecolor=INK,
        linewidth=1.7,
        zorder=6.5,
    )
    ax.add_patch(banner_box)

    # Sun in top-left of art box
    _draw_sun_corner(
        ax,
        sx=in_x + in_w * 0.18,
        sy=art_y + art_h * 0.83,
        rx=in_w * 0.115,
        ry=art_h * 0.076,
        z=4,
    )

    # Fluffy white clouds on left and right
    _draw_cloud(ax, in_x + in_w * 0.77, art_y + art_h * 0.77, in_w * 0.24, art_h * 0.10, z=4)
    _draw_cloud(ax, in_x + in_w * 0.21, art_y + art_h * 0.54, in_w * 0.22, art_h * 0.095, z=4)
    _draw_cloud(ax, in_x + in_w * 0.79, art_y + art_h * 0.52, in_w * 0.20, art_h * 0.088, z=4)

    # 4-pointed sparkles
    _draw_sparkle_card(ax, in_x + in_w * 0.78, art_y + art_h * 0.90, in_w * 0.036, art_h * 0.046, z=5)
    _draw_sparkle_card(ax, in_x + in_w * 0.22, art_y + art_h * 0.39, in_w * 0.032, art_h * 0.042, z=5)

    # Central illustration (cacti, skull+crow+rose, goblet/sword/wand/star)
    _draw_central_illustration(ax, cx, art_y, in_w, art_h, card, z=5)

    # Top Roman Numeral with classic serif overline & underline bars
    roman_str = str(card["roman"])
    num_y = art_y + art_h * 0.91
    bar_half_w = max(0.022, len(roman_str) * 0.0085) * (card_w / 0.22)
    ax.plot([cx - bar_half_w, cx + bar_half_w], [num_y + 0.015, num_y + 0.015], color=INK, linewidth=1.5, zorder=7)
    ax.plot([cx - bar_half_w, cx + bar_half_w], [num_y - 0.015, num_y - 0.015], color=INK, linewidth=1.5, zorder=7)
    ax.text(
        cx,
        num_y,
        roman_str,
        color=INK,
        fontsize=9.5,
        fontweight="bold",
        family="serif",
        ha="center",
        va="center",
        zorder=7,
    )

    # Bottom Banner Title in uppercase with trailing period (like "THE MARGARITA.")
    title_up = card["name_ru"].split("(")[0].strip().upper() + "."
    if is_rev:
        title_up += " ⟲"
    font_sz = 8.0 if len(title_up) <= 12 else (6.8 if len(title_up) <= 15 else 5.8)
    ax.text(
        cx,
        in_y + banner_h * 0.50,
        title_up,
        color="#b02a2a" if is_rev else INK,
        fontsize=font_sz,
        fontweight="bold",
        family="serif",
        ha="center",
        va="center",
        zorder=7,
    )

    # Position badge above card
    if badge_label:
        ax.text(
            cx,
            y0 + card_h + 0.020,
            badge_label,
            color="#2b261f",
            fontsize=8.0,
            fontweight="bold",
            family="serif",
            ha="center",
            va="bottom",
            zorder=8,
            bbox=dict(boxstyle="round,pad=0.22", facecolor="#f5efe2", edgecolor="#8c7f65", lw=1.0),
        )


def render_spread_image(spread: Dict, output_path: Path) -> Path:
    """
    Render the complete Tarot spread in a cohesive Vintage Cream Poster layout with
    pop-art illustrated Tarot cards on the left and vintage poster boxes on the right.
    """
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial Unicode MS", "Helvetica", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    fig = plt.figure(figsize=(16.5, 11.2), dpi=160, facecolor=POSTER_BG)

    ax_bg = fig.add_axes([0.0, 0.0, 1.0, 1.0], facecolor=POSTER_BG)
    ax_bg.set_xlim(0.0, 1.0)
    ax_bg.set_ylim(0.0, 1.0)
    ax_bg.axis("off")

    # Outer vintage poster border
    poster_frame = patches.FancyBboxPatch(
        (0.012, 0.014),
        0.976,
        0.972,
        boxstyle="round,pad=0.004,rounding_size=0.012",
        facecolor=POSTER_BG,
        edgecolor=BORDER_TAN,
        linewidth=2.0,
        zorder=0,
    )
    ax_bg.add_patch(poster_frame)

    # =========================================================================
    # 1. TOP VINTAGE HEADER (Celestial Sun, Title, Crescent Moon)
    # =========================================================================
    _draw_celestial_sun_header(ax_bg, 0.065, 0.925, 0.024, 0.034)
    _draw_celestial_moon_header(ax_bg, 0.935, 0.925, 0.024, 0.034)

    short_spread_title = spread["spread_title"].split("(")[0].strip().upper()
    ax_bg.text(
        0.50,
        0.948,
        f"РАСКЛАД ТАРО • {short_spread_title}",
        color=INK,
        fontsize=18.5,
        fontweight="bold",
        family="serif",
        ha="center",
        va="center",
    )
    _draw_sparkle_poster(ax_bg, 0.16, 0.910, 0.005, 0.007, GOLD_ACCENT, z=4)
    _draw_sparkle_poster(ax_bg, 0.84, 0.910, 0.005, 0.007, GOLD_ACCENT, z=4)
    ax_bg.text(
        0.50,
        0.910,
        f"Аркана • Запрос ({spread['subject_name'][:28]}): {spread['question'][:64]}",
        color=GOLD_ACCENT,
        fontsize=10.8,
        style="italic",
        family="serif",
        ha="center",
        va="center",
    )

    # =========================================================================
    # 2. LEFT PANEL: Illustrated Tarot Cards on Vintage Cream Table
    # =========================================================================
    _draw_poster_box(ax_bg, 0.024, 0.032, 0.485, 0.840, "ВЫПАВШИЕ КАРТЫ И АРКАНЫ")

    ax_cards = fig.add_axes([0.028, 0.036, 0.477, 0.785], facecolor=CARD_BOX_BG)
    ax_cards.set_xlim(0.0, 1.0)
    ax_cards.set_ylim(0.0, 1.0)
    ax_cards.axis("off")

    cards = spread["cards"]
    n = len(cards)
    bot_card = spread["bottom_of_deck"]
    q_card = spread["quintessence"]["card"]

    draw_single_card_on_axes(ax_cards, cx=0.28, cy=0.23, card_w=0.23, card_h=0.35, card=bot_card, badge_label="Дно колоды (Скрытый мотив)")
    draw_single_card_on_axes(ax_cards, cx=0.72, cy=0.23, card_w=0.23, card_h=0.35, card=q_card, badge_label="Квинтэссенция (Совет)")

    if n == 1:
        draw_single_card_on_axes(ax_cards, cx=0.50, cy=0.73, card_w=0.26, card_h=0.41, card=cards[0], badge_label="1. Карта вопроса")
    elif n == 3:
        xs = [0.19, 0.50, 0.81]
        for idx, c in enumerate(cards):
            raw_pos = c["position_title"]
            short_pos = raw_pos[:22] + (".." if len(raw_pos) > 22 else "")
            lbl_str = short_pos if raw_pos[:2].strip().endswith(".") else f"{idx + 1}. {short_pos}"
            draw_single_card_on_axes(ax_cards, cx=xs[idx], cy=0.73, card_w=0.24, card_h=0.38, card=c, badge_label=lbl_str)
    elif n == 5:
        coords = [(0.19, 0.59), (0.50, 0.59), (0.81, 0.59), (0.34, 0.85), (0.66, 0.85)]
        for idx, c in enumerate(cards):
            cx_i, cy_i = coords[idx]
            draw_single_card_on_axes(ax_cards, cx=cx_i, cy=cy_i, card_w=0.19, card_h=0.24, card=c, badge_label=f"Поз. {idx + 1}")
    elif n == 7:
        coords = [
            (0.16, 0.57), (0.39, 0.57), (0.62, 0.57), (0.85, 0.57),
            (0.25, 0.85), (0.50, 0.85), (0.75, 0.85),
        ]
        for idx, c in enumerate(cards):
            cx_i, cy_i = coords[idx]
            draw_single_card_on_axes(ax_cards, cx=cx_i, cy=cy_i, card_w=0.17, card_h=0.23, card=c, badge_label=f"Поз. {idx + 1}")
    else:
        cols = 5
        for idx, c in enumerate(cards[:10]):
            r_idx = idx // cols
            c_idx = idx % cols
            cx_i = 0.12 + c_idx * 0.19
            cy_i = 0.58 + r_idx * 0.27
            draw_single_card_on_axes(ax_cards, cx=cx_i, cy=cy_i, card_w=0.15, card_h=0.22, card=c, badge_label=f"#{idx + 1}")

    # =========================================================================
    # 3. RIGHT PANEL: Vintage Cream Poster Cards with Medallions
    # =========================================================================
    # Card 1: Spread Positions (RWS, Thoth, Marseille)
    _draw_poster_box(ax_bg, 0.522, 0.440, 0.454, 0.432, "1. АРКАНЫ ПО ПОЗИЦИЯМ (УЭЙТ • КРОУЛИ • МАРСЕЛЬ)")
    y = 0.815
    for idx, c in enumerate(cards[:6]):
        orient_mark = "⟲ Перев." if c["is_reversed"] else "↑ Прям."
        meaning = c["rws_reversed"] if c["is_reversed"] else c["rws_upright"]
        med_c = {"Огонь": "#f7d9c4", "Вода": "#d8e5f2", "Воздух": "#f9eec8", "Земля": "#dfead8"}.get(c["element"], "#f5dca8")

        med = patches.Ellipse((0.548, y - 0.015), width=0.032, height=0.042, facecolor=med_c, edgecolor=INK, linewidth=1.1, zorder=3)
        ax_bg.add_patch(med)
        ax_bg.text(0.548, y - 0.015, str(c["roman"]), color=INK, fontsize=8.0, fontweight="bold", family="serif", ha="center", va="center", zorder=4)

        pos_clean = c["position_title"]
        if not pos_clean[:2].strip().endswith("."):
            pos_clean = f"{c['position_index']}. {pos_clean}"
        header_line = f"{pos_clean[:30]} — [{c['roman']}] {c['name_ru']} ({orient_mark})"
        sub_line = f"Стихия: {c['element']} | Тот: {c['thoth_title'][:18]} ({c['astro']}) | {meaning[:36]}"

        ax_bg.text(0.572, y, header_line, color=INK, fontsize=8.3, fontweight="bold", family="serif", va="top")
        ax_bg.text(0.572, y - 0.020, sub_line, color=INK_MUTED, fontsize=7.4, va="top")
        y -= 0.060

    # Card 2: Bottom of Deck & Quintessence
    _draw_poster_box(ax_bg, 0.522, 0.215, 0.454, 0.210, "2. ДНО КОЛОДЫ (ПОДОПЛЁКА) И КВИНТЭССЕНЦИЯ (СОВЕТ)")
    bot_m = bot_card["rws_reversed"] if bot_card["is_reversed"] else bot_card["rws_upright"]
    q_info = spread["quintessence"]
    inner_str = f" (внутр. корень: {q_info['inner_card']['roman']} {q_info['inner_card']['name_ru']})" if q_info.get("inner_card") else ""

    med_b = patches.Ellipse((0.548, 0.340), width=0.032, height=0.042, facecolor="#dcd6eb", edgecolor=INK, linewidth=1.1, zorder=3)
    ax_bg.add_patch(med_b)
    ax_bg.text(0.548, 0.340, str(bot_card["roman"]), color=INK, fontsize=8.0, fontweight="bold", family="serif", ha="center", va="center", zorder=4)
    ax_bg.text(0.572, 0.356, f"Дно колоды: [{bot_card['roman']}] {bot_card['name_ru']} ({bot_card['orientation_ru']})", color=INK, fontsize=8.5, fontweight="bold", family="serif", va="top")
    ax_bg.text(0.572, 0.334, f"Скрытый мотив и атмосфера: {bot_m[:68]}", color=INK_MUTED, fontsize=7.8, va="top")

    med_q = patches.Ellipse((0.548, 0.265), width=0.032, height=0.042, facecolor="#f7dfb2", edgecolor=INK, linewidth=1.1, zorder=3)
    ax_bg.add_patch(med_q)
    ax_bg.text(0.548, 0.265, str(q_card["roman"]), color=INK, fontsize=8.0, fontweight="bold", family="serif", ha="center", va="center", zorder=4)
    ax_bg.text(0.572, 0.282, f"Квинтэссенция (Совет): [{q_card['roman']}] {q_card['name_ru']}{inner_str}", color=INK, fontsize=8.5, fontweight="bold", family="serif", va="top")
    ax_bg.text(0.572, 0.260, f"Ключ к решению: {q_card['rws_upright'][:68]}", color=INK_MUTED, fontsize=7.8, va="top")

    # Card 3: Elemental Dignities (Golden Dawn)
    _draw_poster_box(ax_bg, 0.522, 0.032, 0.454, 0.168, "3. БАЛАНС СТИХИЙ (ОРДЕН ЗОЛОТОЙ ЗАРИ)")
    el = spread["elemental_stats"]
    counts = el["counts"]

    el_pills = [
        ("ОГОНЬ", counts["Огонь"], "#f7d9c4", 0.585),
        ("ВОДА", counts["Вода"], "#d8e5f2", 0.695),
        ("ВОЗДУХ", counts["Воздух"], "#f9eec8", 0.805),
        ("ЗЕМЛЯ", counts["Земля"], "#dfead8", 0.915),
    ]
    for el_name, el_cnt, el_col, ex in el_pills:
        pill = patches.FancyBboxPatch((ex - 0.045, 0.105), 0.090, 0.042, boxstyle="round,pad=0.003,rounding_size=0.010", facecolor=el_col, edgecolor=INK, linewidth=1.0, zorder=3)
        ax_bg.add_patch(pill)
        ax_bg.text(ex, 0.126, f"{el_name}: {el_cnt}", color=INK, fontsize=7.8, fontweight="bold", family="serif", ha="center", va="center", zorder=4)

    ax_bg.text(
        0.749,
        0.082,
        f"Доминанта расклада: {el['dominant_element']}  •  Дефицит стихии: {', '.join(el['missing_elements']) if el['missing_elements'] else 'нет (гармония)'}\n"
        f"Старших Арканов (судьбоносность): {el['majors_count']} из {n}  •  Перевёрнутых карт: {el['reversed_count']} из {n}",
        color=INK_MUTED,
        fontsize=7.7,
        ha="center",
        va="top",
        linespacing=1.3,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160, bbox_inches="tight", facecolor=POSTER_BG)
    plt.close(fig)
    return output_path
