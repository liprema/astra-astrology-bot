"""
Illustrated Vintage Rider-Waite / Pop-Art Tarot Card & Spread Renderer for ARCANA ("Аркана").
Matches the user's reference style:
- Cream/ivory rounded outer card border (`#f8f5e6`) with crisp black ink outlines (`#1e1e1e`)
- Pastel sky-blue / elemental scenic interior (`#d9f0f7`)
- Top Roman numeral with classic serif overline & underline bars
- Rich illustrated vector artwork inside every card:
  * Radiant golden Sun with rays, fluffy white clouds, 4-pointed stars, landscape/desert hills,
    and detailed suit/archetype illustrations (Chalices/Goblets, Swords, Blossoming Wands, Golden Pentacles,
    Crowns, Scales, Chariots, Moons, Towers, Stars, etc.)
- Bottom white title banner (`#ffffff`) with bold uppercase typography and period (`THE MAGICIAN.`)
"""
from __future__ import annotations

import math
import textwrap
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np


SKY_PALETTE = {
    "Огонь": "#fcebd5",   # Warm sunny pastel sky
    "Вода": "#d8f0f8",    # Crisp pastel aqua-blue sky (exact match to reference)
    "Воздух": "#e6effa",  # Soft airy periwinkle sky
    "Земля": "#e5f5e0",   # Soft sage-mint sky
    "Дух": "#f2e6fa",     # Soft lavender sky
}

INK = "#1f1d1a"
CREAM_CARD = "#f9f6ea"


def _draw_cloud(ax, cx: float, cy: float, scale_x: float, scale_y: float, z: int = 4) -> None:
    """Draw a cute black-outlined fluffy white cloud."""
    offsets = [
        (0.0, 0.0, 0.42),
        (-0.32, -0.05, 0.30),
        (0.32, -0.05, 0.30),
        (-0.15, 0.14, 0.28),
        (0.16, 0.12, 0.27),
    ]
    for dx, dy, r in offsets:
        el = patches.Ellipse(
            (cx + dx * scale_x, cy + dy * scale_y),
            width=r * 2 * scale_x,
            height=r * 2 * scale_y,
            facecolor="#ffffff",
            edgecolor=INK,
            linewidth=1.5,
            zorder=z,
        )
        ax.add_patch(el)
    # Inner white cover so internal lines merge into a single fluffy cloud
    for dx, dy, r in offsets:
        el_in = patches.Ellipse(
            (cx + dx * scale_x, cy + dy * scale_y),
            width=r * 1.75 * scale_x,
            height=r * 1.75 * scale_y,
            facecolor="#ffffff",
            edgecolor="none",
            zorder=z + 0.1,
        )
        ax.add_patch(el_in)


def _draw_sparkle(ax, cx: float, cy: float, rx: float, ry: float, col: str = "#fff380", z: int = 6) -> None:
    """Draw a 4-pointed vintage tarot star sparkle."""
    pts = [
        (cx, cy + ry),
        (cx + rx * 0.22, cy + ry * 0.22),
        (cx + rx, cy),
        (cx + rx * 0.22, cy - ry * 0.22),
        (cx, cy - ry),
        (cx - rx * 0.22, cy - ry * 0.22),
        (cx - rx, cy),
        (cx - rx * 0.22, cy + ry * 0.22),
    ]
    poly = patches.Polygon(pts, closed=True, facecolor=col, edgecolor=INK, linewidth=1.1, zorder=z)
    ax.add_patch(poly)


def _draw_sun_corner(ax, sx: float, sy: float, rx: float, ry: float, z: int = 5) -> None:
    """Draw the bright yellow sun with triangular rays like in the reference card."""
    n_rays = 12
    for i in range(n_rays):
        ang = math.radians(i * (360.0 / n_rays))
        ang_l = ang - 0.12
        ang_r = ang + 0.12
        tri = [
            (sx + rx * 0.95 * math.cos(ang_l), sy + ry * 0.95 * math.sin(ang_l)),
            (sx + rx * 1.55 * math.cos(ang), sy + ry * 1.55 * math.sin(ang)),
            (sx + rx * 0.95 * math.cos(ang_r), sy + ry * 0.95 * math.sin(ang_r)),
        ]
        ax.add_patch(patches.Polygon(tri, closed=True, facecolor="#ffea00", edgecolor=INK, linewidth=1.0, zorder=z))

    sun_disc = patches.Ellipse((sx, sy), width=rx * 2.0, height=ry * 2.0, facecolor="#ffea00", edgecolor=INK, linewidth=1.6, zorder=z + 0.2)
    ax.add_patch(sun_disc)


def _draw_central_illustration(ax, cx: float, y_bot: float, w: float, h: float, card: Dict, z: int = 6) -> None:
    """Draw bold, colorful comic/vintage vector art tailored to the card's suit and archetype."""
    suit = card.get("suit", "Major")
    num = int(card.get("number", 1))
    mid_y = y_bot + h * 0.48

    # Desert / meadow ground hills at bottom of art frame
    ground_h = h * 0.10
    ground = patches.Rectangle((cx - w * 0.48, y_bot), w * 0.96, ground_h, facecolor="#e9f2a7", edgecolor=INK, linewidth=1.2, zorder=z - 1)
    ax.add_patch(ground)

    # Cacti / cypress pillars on left and right (like reference!)
    for side in (-1, 1):
        px = cx + side * w * 0.34
        trunk = patches.FancyBboxPatch(
            (px - w * 0.03, y_bot + ground_h * 0.5),
            w * 0.06,
            h * 0.32,
            boxstyle="round,pad=0.002,rounding_size=0.015",
            facecolor="#5bb344",
            edgecolor=INK,
            linewidth=1.3,
            zorder=z,
        )
        ax.add_patch(trunk)
        arm = patches.FancyBboxPatch(
            (px - (w * 0.09 if side > 0 else -w * 0.01), y_bot + h * 0.18),
            w * 0.08,
            h * 0.12,
            boxstyle="round,pad=0.002,rounding_size=0.012",
            facecolor="#5bb344",
            edgecolor=INK,
            linewidth=1.2,
            zorder=z,
        )
        ax.add_patch(arm)

    if suit == "Cups" or (suit == "Major" and card["number"] % 3 == 0):
        # Ornate Coral-Red Goblet / Chalice with lime/sun wheel on rim (exact homage to reference image!)
        stem = patches.Rectangle((cx - w * 0.025, y_bot + ground_h), w * 0.05, h * 0.28, facecolor="#e8f4f8", edgecolor=INK, linewidth=1.4, zorder=z)
        ax.add_patch(stem)
        base = patches.Ellipse((cx, y_bot + ground_h), width=w * 0.28, height=h * 0.04, facecolor="#e8f4f8", edgecolor=INK, linewidth=1.4, zorder=z)
        ax.add_patch(base)
        # Lime wheel on top-right of rim
        lime = patches.Ellipse((cx + w * 0.22, mid_y + h * 0.16), width=w * 0.22, height=h * 0.14, facecolor="#99d955", edgecolor=INK, linewidth=1.4, zorder=z)
        ax.add_patch(lime)
        # Goblet bowl
        bowl_pts = [
            (cx - w * 0.30, mid_y + h * 0.14),
            (cx + w * 0.30, mid_y + h * 0.14),
            (cx + w * 0.22, mid_y - h * 0.02),
            (cx + w * 0.07, mid_y - h * 0.12),
            (cx - w * 0.07, mid_y - h * 0.12),
            (cx - w * 0.22, mid_y - h * 0.02),
        ]
        ax.add_patch(patches.Polygon(bowl_pts, closed=True, facecolor="#f05a5b", edgecolor=INK, linewidth=1.6, zorder=z + 0.2))
        rim = patches.Rectangle((cx - w * 0.30, mid_y + h * 0.12), w * 0.60, h * 0.035, facecolor="#ffffff", edgecolor=INK, linewidth=1.3, zorder=z + 0.3)
        ax.add_patch(rim)

    elif suit == "Swords" or (suit == "Major" and card["number"] % 3 == 1):
        # Radiant Silver Sword piercing a Golden Crown & Rose
        blade_pts = [
            (cx, mid_y + h * 0.28),
            (cx + w * 0.045, mid_y - h * 0.12),
            (cx - w * 0.045, mid_y - h * 0.12),
        ]
        ax.add_patch(patches.Polygon(blade_pts, closed=True, facecolor="#dce6f2", edgecolor=INK, linewidth=1.6, zorder=z + 0.2))
        hilt = patches.FancyBboxPatch((cx - w * 0.18, mid_y - h * 0.15), w * 0.36, h * 0.035, boxstyle="round,pad=0.003", facecolor="#f5b82e", edgecolor=INK, linewidth=1.4, zorder=z + 0.3)
        ax.add_patch(hilt)
        grip = patches.Rectangle((cx - w * 0.025, y_bot + ground_h + h * 0.04), w * 0.05, h * 0.14, facecolor="#8c4a27", edgecolor=INK, linewidth=1.4, zorder=z + 0.2)
        ax.add_patch(grip)
        pommel = patches.Ellipse((cx, y_bot + ground_h + h * 0.03), width=w * 0.09, height=h * 0.05, facecolor="#f5b82e", edgecolor=INK, linewidth=1.4, zorder=z + 0.3)
        ax.add_patch(pommel)
        # Crown around blade tip
        crown_pts = [
            (cx - w * 0.16, mid_y + h * 0.08),
            (cx - w * 0.19, mid_y + h * 0.17),
            (cx - w * 0.08, mid_y + h * 0.12),
            (cx, mid_y + h * 0.19),
            (cx + w * 0.08, mid_y + h * 0.12),
            (cx + w * 0.19, mid_y + h * 0.17),
            (cx + w * 0.16, mid_y + h * 0.08),
        ]
        ax.add_patch(patches.Polygon(crown_pts, closed=True, facecolor="#ffd43b", edgecolor=INK, linewidth=1.4, zorder=z + 0.4))

    elif suit == "Wands":
        # Blossoming Royal Wand with Flame & Leaves
        staff = patches.FancyBboxPatch((cx - w * 0.035, y_bot + ground_h), w * 0.07, h * 0.56, boxstyle="round,pad=0.003", facecolor="#b86b35", edgecolor=INK, linewidth=1.6, zorder=z + 0.2)
        ax.add_patch(staff)
        # Flame crown at top of wand
        flame_outer = [
            (cx, mid_y + h * 0.31),
            (cx + w * 0.15, mid_y + h * 0.14),
            (cx + w * 0.08, mid_y + h * 0.04),
            (cx - w * 0.08, mid_y + h * 0.04),
            (cx - w * 0.15, mid_y + h * 0.14),
        ]
        ax.add_patch(patches.Polygon(flame_outer, closed=True, facecolor="#ff6b35", edgecolor=INK, linewidth=1.5, zorder=z + 0.3))
        flame_inner = [
            (cx, mid_y + h * 0.25),
            (cx + w * 0.08, mid_y + h * 0.12),
            (cx - w * 0.08, mid_y + h * 0.12),
        ]
        ax.add_patch(patches.Polygon(flame_inner, closed=True, facecolor="#ffea00", edgecolor=INK, linewidth=1.2, zorder=z + 0.4))

    else:
        # Golden Pentacle / Major Arcana Mystic Wheel with 5-pointed Star & Red Rose
        pedestal = patches.Polygon(
            [(cx - w * 0.16, y_bot + ground_h), (cx + w * 0.16, y_bot + ground_h), (cx + w * 0.10, mid_y - h * 0.08), (cx - w * 0.10, mid_y - h * 0.08)],
            closed=True,
            facecolor="#d0d4dc",
            edgecolor=INK,
            linewidth=1.5,
            zorder=z + 0.1,
        )
        ax.add_patch(pedestal)
        disc = patches.Ellipse((cx, mid_y + h * 0.06), width=w * 0.48, height=h * 0.30, facecolor="#ffd43b", edgecolor=INK, linewidth=1.8, zorder=z + 0.2)
        ax.add_patch(disc)
        # 5-pointed star inside disc
        star_pts = []
        for k in range(10):
            r_k = (0.20 if k % 2 == 0 else 0.08)
            ang = math.radians(90 + k * 36)
            star_pts.append((cx + w * r_k * math.cos(ang), mid_y + h * 0.06 + h * (r_k * 0.62) * math.sin(ang)))
        ax.add_patch(patches.Polygon(star_pts, closed=True, facecolor="#fff5b8", edgecolor=INK, linewidth=1.4, zorder=z + 0.3))

    # Red rose accent at the bottom-right of the pedestal (just like reference!)
    rose = patches.Ellipse((cx + w * 0.14, y_bot + ground_h * 0.9), width=w * 0.09, height=h * 0.055, facecolor="#d9383a", edgecolor=INK, linewidth=1.3, zorder=z + 0.5)
    ax.add_patch(rose)


def draw_single_card_on_axes(
    ax,
    cx: float,
    cy: float,
    card_w: float,
    card_h: float,
    card: Dict,
    badge_label: str = "",
) -> None:
    """
    Draw an illustrated Tarot card in the exact aesthetic of the user's reference:
    - Rounded cream card body with black ink outline
    - Inner sky-colored framed illustration box with Sun, fluffy Clouds, Sparkles, Cacti, and Suit/Arcana art
    - Top Roman Numeral with horizontal overline & underline bars
    - Bottom white banner with bold uppercase title and period
    """
    el = card.get("element", "Вода")
    sky_col = SKY_PALETTE.get(el, "#d8f0f8")
    is_rev = bool(card.get("is_reversed"))

    x0 = cx - card_w / 2.0
    y0 = 1.0 - cy - card_h / 2.0

    # Soft drop shadow
    shadow = patches.FancyBboxPatch(
        (x0 + 0.007, y0 - 0.009),
        card_w,
        card_h,
        boxstyle="round,pad=0.008,rounding_size=0.022",
        facecolor="#b8b09c",
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

    # Inner black-bordered rectangle split into:
    # 1) Upper illustrated scene (80% height)
    # 2) Bottom white title banner (20% height)
    pad_x = card_w * 0.055
    pad_y = card_h * 0.035
    in_x = x0 + pad_x
    in_y = y0 + pad_y
    in_w = card_w - 2 * pad_x
    in_h = card_h - 2 * pad_y

    banner_h = in_h * 0.165
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
        sy=art_y + art_h * 0.82,
        rx=in_w * 0.11,
        ry=art_h * 0.075,
        z=4,
    )

    # Fluffy white clouds on left and right
    _draw_cloud(ax, in_x + in_w * 0.78, art_y + art_h * 0.76, in_w * 0.22, art_h * 0.10, z=4)
    _draw_cloud(ax, in_x + in_w * 0.22, art_y + art_h * 0.52, in_w * 0.20, art_h * 0.09, z=4)
    _draw_cloud(ax, in_x + in_w * 0.80, art_y + art_h * 0.50, in_w * 0.18, art_h * 0.08, z=4)

    # 4-pointed sparkles
    _draw_sparkle(ax, in_x + in_w * 0.78, art_y + art_h * 0.90, in_w * 0.035, art_h * 0.045, z=5)
    _draw_sparkle(ax, in_x + in_w * 0.20, art_y + art_h * 0.36, in_w * 0.032, art_h * 0.040, z=5)

    # Central illustration
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
    font_sz = 8.0 if len(title_up) <= 12 else (6.8 if len(title_up) <= 15 else 5.9)
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
            y0 + card_h + 0.022,
            badge_label,
            color="#2b261f",
            fontsize=8.2,
            fontweight="bold",
            ha="center",
            va="bottom",
            bbox=dict(boxstyle="round,pad=0.20", facecolor="#f4efe1", edgecolor="#8c7a5b", lw=1.0),
            zorder=8,
        )


def render_spread_image(spread: Dict, output_path: Path) -> Path:
    """
    Render the Tarot spread layout and esoteric summary on a warm vintage parchment canvas.
    """
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial Unicode MS", "Helvetica", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    bg_parchment = "#f5efe2"
    fig = plt.figure(figsize=(15.8, 10.2), dpi=160, facecolor=bg_parchment)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.25, 1.0], wspace=0.05)

    # Left panel: Spread Table
    ax = fig.add_subplot(gs[0])
    ax.set_facecolor("#efe7d6")
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.axis("off")

    altar_border = patches.FancyBboxPatch(
        (0.015, 0.015),
        0.97,
        0.97,
        boxstyle="round,pad=0.008,rounding_size=0.02",
        facecolor="#efe7d6",
        edgecolor="#8c7a5b",
        linewidth=1.8,
        zorder=1,
    )
    ax.add_patch(altar_border)

    cards = spread["cards"]
    n_cards = len(cards)
    if n_cards <= 1:
        cw, ch = 0.26, 0.38
    elif n_cards <= 3:
        cw, ch = 0.23, 0.36
    elif n_cards <= 5:
        cw, ch = 0.18, 0.26
    elif n_cards <= 7:
        cw, ch = 0.17, 0.23
    else:
        cw, ch = 0.14, 0.20

    if n_cards <= 3:
        bot_card_vis = dict(spread["bottom_of_deck"])
        quint_card_vis = dict(spread["quintessence"]["card"])
        quint_card_vis["is_reversed"] = False
        draw_single_card_on_axes(
            ax=ax,
            cx=0.31,
            cy=0.23,
            card_w=0.20,
            card_h=0.30,
            card=bot_card_vis,
            badge_label="Дно колоды (Скрытый фон)",
        )
        draw_single_card_on_axes(
            ax=ax,
            cx=0.69,
            cy=0.23,
            card_w=0.20,
            card_h=0.30,
            card=quint_card_vis,
            badge_label="Квинтэссенция (Совет)",
        )

    for c in cards:
        short_pos = c["position_title"]
        if len(short_pos) > 26:
            short_pos = short_pos[:24] + ".."
        cy_adj = 0.70 if n_cards <= 3 else float(c["y"])
        draw_single_card_on_axes(
            ax=ax,
            cx=float(c["x"]),
            cy=cy_adj,
            card_w=cw,
            card_h=ch,
            card=c,
            badge_label=short_pos,
        )

    # Right panel: Detailed Esoteric Summary on Warm Parchment Cards
    ax_info = fig.add_subplot(gs[1])
    ax_info.set_facecolor(bg_parchment)
    ax_info.axis("off")

    title_text = f"АРКАНА • {spread['spread_title'].split('(')[0].strip().upper()}"
    ax_info.text(0.0, 0.97, title_text, color="#1f1d1a", fontsize=13.5, fontweight="bold", family="serif", va="top")

    q_clean = spread["question"].replace("\n", " ").strip()
    if len(q_clean) > 74:
        q_clean = q_clean[:71] + "..."
    ax_info.text(0.0, 0.935, f"Запрос ({spread['subject_name']}): {q_clean}", color="#5c5346", fontsize=8.8, va="top")

    y_cursor = 0.895
    ax_info.text(
        0.0,
        y_cursor,
        "ВЫПАВШИЕ АРКАНЫ ПО ПОЗИЦИЯМ (УЭЙТ RWS / КРОУЛИ ТОТ / ЗОЛОТАЯ ЗАРЯ)",
        color="#8b4513",
        fontsize=9.2,
        fontweight="bold",
        va="top",
    )
    y_cursor -= 0.030

    step_y = 0.052 if len(cards) <= 5 else 0.040
    for c in cards:
        rev_tag = "⟲ Перев." if c["is_reversed"] else "↑ Прям."
        line1 = f"{c['position_title']}  —  [{c['roman']}] {c['name_ru']} ({rev_tag})"
        meaning = c["rws_reversed"] if c["is_reversed"] else c["rws_upright"]
        short_meaning = meaning.split(",")[0] + (", " + meaning.split(",")[1] if "," in meaning else "")
        line2 = f"   Стихия: {c['element']} | Тот/Астро: {c['thoth_title'][:30]} | RWS: {short_meaning[:42]}"
        ax_info.text(0.0, y_cursor, line1[:70], color="#1f1d1a", fontsize=8.4, fontweight="bold", va="top")
        ax_info.text(0.0, y_cursor - 0.020, line2, color="#4a4238", fontsize=7.6, va="top")
        y_cursor -= step_y

    y_cursor -= 0.012
    ax_info.text(
        0.0,
        y_cursor,
        "ДНО КОЛОДЫ (СКРЫТЫЙ ФОН) И КВИНТЭССЕНЦИЯ (ИТОГОВЫЙ СОВЕТ)",
        color="#8b4513",
        fontsize=9.2,
        fontweight="bold",
        va="top",
    )
    y_cursor -= 0.028

    bot = spread["bottom_of_deck"]
    bot_meaning = bot["rws_reversed"] if bot["is_reversed"] else bot["rws_upright"]
    bot_short = ", ".join(bot_meaning.split(",")[:3])
    q = spread["quintessence"]
    q_card = q["card"]
    q_short = ", ".join(q_card["rws_upright"].split(",")[:4])
    inner_note = f" (корень: {q['inner_card']['roman']} {q['inner_card']['name_ru']})" if q.get("inner_card") else ""

    special_rows = [
        f"• Дно колоды: [{bot['roman']}] {bot['name_ru']} ({bot['orientation_ru']})",
        f"  Скрытый мотив: {bot_short}",
        f"• Квинтэссенция (Совет): [{q_card['roman']}] {q_card['name_ru']}{inner_note}",
        f"  Рекомендация: {q_short}",
    ]
    for sr in special_rows:
        ax_info.text(0.0, y_cursor, sr, color="#2b261f", fontsize=8.0, va="top")
        y_cursor -= 0.023

    y_cursor -= 0.010
    ax_info.text(
        0.0,
        y_cursor,
        "БАЛАНС СТИХИЙ И ЭЛЕМЕНТАЛЬНЫЕ ДОСТОИНСТВА",
        color="#2b6cb0",
        fontsize=9.2,
        fontweight="bold",
        va="top",
    )
    y_cursor -= 0.026

    el = spread["elemental_stats"]
    counts_str = " | ".join(f"{k}: {v}" for k, v in el["counts"].items())
    missing_str = ", ".join(el["missing_elements"]) if el["missing_elements"] else "все стихии в балансе"
    stat_rows = [
        f"• Стихии в раскладе: {counts_str}",
        f"• Доминанта: {el['dominant_element']}  |  Дефицит стихии: {missing_str}",
        f"• Старших Арканов: {el['majors_count']} из {len(cards)}  |  Перевёрнутых карт: {el['reversed_count']} из {len(cards)}",
    ]
    for str_row in stat_rows:
        ax_info.text(0.0, y_cursor, str_row, color="#2b261f", fontsize=8.0, va="top")
        y_cursor -= 0.023

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160, bbox_inches="tight", facecolor=bg_parchment)
    plt.close(fig)
    return output_path
