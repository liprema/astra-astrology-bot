"""
High-Resolution Tarot Spread Renderer for ARCANA ("Аркана").
Renders an atmospheric, crisp PNG image of the laid-out Tarot spread:
- Draws each Tarot card with ornamental golden/elemental borders, Roman numerals,
  card title, upright/reversed indicator (↑ / ⟲), suit/element emblem, and position title.
- Right-hand summary panel displaying:
  * All drawn positions (with RWS & Thoth/Golden Dawn correspondences)
  * Bottom of the Deck ("Дно колоды — скрытый мотив")
  * Quintessence ("Квинтэссенция — итоговый совет расклада")
  * Elemental Balance & Dignities
"""
from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

ELEMENT_PALETTE = {
    "Огонь": ("#ff6b6b", "#2b1216"),
    "Вода": ("#4dabf7", "#112136"),
    "Воздух": ("#ffd43b", "#2a2612"),
    "Земля": ("#51cf66", "#12291a"),
    "Дух": ("#da77f2", "#25142b"),
}

SUIT_SYMBOLS = {
    "Major": "✦",
    "Wands": "Ψ",
    "Cups": "∪",
    "Swords": "†",
    "Pentacles": "✪",
}


def draw_single_card_on_axes(
    ax,
    cx: float,
    cy: float,
    card_w: float,
    card_h: float,
    card: Dict,
    badge_label: str = "",
) -> None:
    """Draw a stylized esoteric Tarot card on the spread table."""
    el = card.get("element", "Воздух")
    border_col, fill_col = ELEMENT_PALETTE.get(el, ("#d4af37", "#161b22"))
    is_major = card["arcana_type"] == "Старший Аркан"
    outer_edge = "#f59f00" if is_major else border_col
    is_rev = bool(card.get("is_reversed"))

    x0 = cx - card_w / 2.0
    y0 = 1.0 - cy - card_h / 2.0  # Invert Y so 0.18 is near top and 0.85 is near bottom

    # Shadow
    shadow = patches.FancyBboxPatch(
        (x0 + 0.008, y0 - 0.010),
        card_w,
        card_h,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        facecolor="#05070a",
        edgecolor="none",
        alpha=0.75,
        zorder=2,
    )
    ax.add_patch(shadow)

    # Outer card body
    body = patches.FancyBboxPatch(
        (x0, y0),
        card_w,
        card_h,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        facecolor=fill_col,
        edgecolor=outer_edge,
        linewidth=2.2 if is_major else 1.6,
        zorder=3,
    )
    ax.add_patch(body)

    # Inner ornamental frame
    pad = 0.009
    inner = patches.FancyBboxPatch(
        (x0 + pad, y0 + pad),
        card_w - 2 * pad,
        card_h - 2 * pad,
        boxstyle="round,pad=0.006,rounding_size=0.012",
        facecolor="none",
        edgecolor="#f0883e" if is_rev else outer_edge,
        linestyle="--" if is_rev else "-",
        linewidth=0.9,
        alpha=0.8,
        zorder=4,
    )
    ax.add_patch(inner)

    # Position badge above card
    if badge_label:
        ax.text(
            cx,
            y0 + card_h + 0.024,
            badge_label,
            color="#c9d1d9",
            fontsize=8.2,
            fontweight="bold",
            ha="center",
            va="bottom",
            bbox=dict(boxstyle="round,pad=0.18", facecolor="#161b22", edgecolor="#30363d", lw=0.8),
            zorder=7,
        )

    # Top Roman numeral / Rank
    orient_tag = " ⟲ ПЕРЕВ." if is_rev else " ↑ ПРЯМАЯ"
    top_color = "#ff8787" if is_rev else "#ffd43b"
    ax.text(
        cx,
        y0 + card_h - 0.022,
        f"{card['roman']}{orient_tag}",
        color=top_color,
        fontsize=8.0,
        fontweight="bold",
        ha="center",
        va="top",
        zorder=6,
    )

    # Central esoteric medallion
    suit_sym = SUIT_SYMBOLS.get(card["suit"], "✦")
    medallion = patches.Circle(
        (cx, y0 + card_h * 0.56),
        radius=min(card_w, card_h) * 0.21,
        facecolor="#0d1117",
        edgecolor=outer_edge,
        linewidth=1.2,
        zorder=5,
    )
    ax.add_patch(medallion)
    ax.text(
        cx,
        y0 + card_h * 0.56,
        suit_sym,
        color=outer_edge,
        fontsize=18,
        fontweight="bold",
        ha="center",
        va="center",
        zorder=6,
    )

    # Card Name wrapped
    wrapped_name = "\n".join(textwrap.wrap(card["name_ru"], width=14))
    ax.text(
        cx,
        y0 + card_h * 0.24,
        wrapped_name,
        color="#f0f6fc",
        fontsize=8.5,
        fontweight="bold",
        ha="center",
        va="center",
        zorder=6,
    )

    # Astro / Element footer inside card
    short_astro = card["astro"].split("(")[0].strip()[:18]
    ax.text(
        cx,
        y0 + 0.012,
        f"{card['element']} • {short_astro}",
        color="#8b949e",
        fontsize=6.8,
        ha="center",
        va="bottom",
        zorder=6,
    )


def render_spread_image(spread: Dict, output_path: Path) -> Path:
    """
    Render the Tarot spread layout and esoteric summary into a high-resolution PNG file.
    """
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial Unicode MS", "Helvetica", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    fig = plt.figure(figsize=(15.5, 10), dpi=160, facecolor="#0b0e14")
    gs = fig.add_gridspec(1, 2, width_ratios=[1.22, 1.0], wspace=0.05)

    # Left panel: Tarot Cloth / Spread Table
    ax = fig.add_subplot(gs[0])
    ax.set_facecolor("#0f131c")
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.axis("off")

    # Subtle altar table border
    altar_border = patches.FancyBboxPatch(
        (0.02, 0.02),
        0.96,
        0.96,
        boxstyle="round,pad=0.01,rounding_size=0.02",
        facecolor="#0f131c",
        edgecolor="#30363d",
        linewidth=1.5,
        zorder=1,
    )
    ax.add_patch(altar_border)

    cards = spread["cards"]
    n_cards = len(cards)
    if n_cards <= 1:
        cw, ch = 0.25, 0.36
    elif n_cards <= 3:
        cw, ch = 0.22, 0.34
    elif n_cards <= 5:
        cw, ch = 0.18, 0.25
    elif n_cards <= 7:
        cw, ch = 0.17, 0.22
    else:
        cw, ch = 0.14, 0.19

    # For 1 or 3 card spreads, also draw the Bottom of the Deck and Quintessence cards at the top of the altar!
    if n_cards <= 3:
        bot_card_vis = dict(spread["bottom_of_deck"])
        quint_card_vis = dict(spread["quintessence"]["card"])
        quint_card_vis["is_reversed"] = False
        draw_single_card_on_axes(
            ax=ax,
            cx=0.31,
            cy=0.22,
            card_w=0.19,
            card_h=0.27,
            card=bot_card_vis,
            badge_label="Дно колоды (Скрытый фон)",
        )
        draw_single_card_on_axes(
            ax=ax,
            cx=0.69,
            cy=0.22,
            card_w=0.19,
            card_h=0.27,
            card=quint_card_vis,
            badge_label="Квинтэссенция (Совет)",
        )

    for c in cards:
        short_pos = c["position_title"]
        if len(short_pos) > 26:
            short_pos = short_pos[:24] + ".."
        cy_adj = 0.68 if n_cards <= 3 else float(c["y"])
        draw_single_card_on_axes(
            ax=ax,
            cx=float(c["x"]),
            cy=cy_adj,
            card_w=cw,
            card_h=ch,
            card=c,
            badge_label=short_pos,
        )

    # Right panel: Detailed Esoteric Table
    ax_info = fig.add_subplot(gs[1])
    ax_info.set_facecolor("#0b0e14")
    ax_info.axis("off")

    title_text = f"АРКАНА • {spread['spread_title'].split('(')[0].strip().upper()}"
    ax_info.text(0.0, 0.97, title_text, color="#ffd43b", fontsize=12.5, fontweight="bold", va="top")

    q_clean = spread["question"].replace("\n", " ").strip()
    if len(q_clean) > 74:
        q_clean = q_clean[:71] + "..."
    ax_info.text(0.0, 0.935, f"Запрос ({spread['subject_name']}): {q_clean}", color="#8b949e", fontsize=8.6, va="top")

    y_cursor = 0.895
    ax_info.text(
        0.0,
        y_cursor,
        "ВЫПАВШИЕ КАРТЫ ПО ПОЗИЦИЯМ (УЭЙТ RWS / КРОУЛИ ТОТ / ЗОЛОТАЯ ЗАРЯ)",
        color="#58a6ff",
        fontsize=9.0,
        fontweight="bold",
        va="top",
    )
    y_cursor -= 0.030

    step_y = 0.052 if len(cards) <= 5 else 0.040
    for c in cards:
        el_col = ELEMENT_PALETTE.get(c["element"], ("#ffd43b", ""))[0]
        rev_tag = "⟲ Перев." if c["is_reversed"] else "↑ Прям."
        line1 = f"{c['position_title']}  —  [{c['roman']}] {c['name_ru']} ({rev_tag})"
        meaning = c["rws_reversed"] if c["is_reversed"] else c["rws_upright"]
        short_meaning = meaning.split(",")[0] + (", " + meaning.split(",")[1] if "," in meaning else "")
        line2 = f"   Стихия: {c['element']} | Тот/Астро: {c['thoth_title'][:30]} | RWS: {short_meaning[:42]}"
        ax_info.text(0.0, y_cursor, line1[:70], color=el_col, fontsize=8.3, fontweight="bold", va="top")
        ax_info.text(0.0, y_cursor - 0.020, line2, color="#c9d1d9", fontsize=7.5, va="top")
        y_cursor -= step_y

    # Bottom of the deck & Quintessence section
    y_cursor -= 0.012
    ax_info.text(
        0.0,
        y_cursor,
        "ДНО КОЛОДЫ (СКРЫТЫЙ ФОН) И КВИНТЭССЕНЦИЯ (ИТОГОВЫЙ СОВЕТ)",
        color="#f0883e",
        fontsize=9.0,
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
        ax_info.text(0.0, y_cursor, sr, color="#e6edf3", fontsize=7.9, va="top")
        y_cursor -= 0.023

    # Elemental Dignities & Statistics
    y_cursor -= 0.010
    ax_info.text(
        0.0,
        y_cursor,
        "БАЛАНС СТИХИЙ И ЭЛЕМЕНТАЛЬНЫЕ ДОСТОИНСТВА",
        color="#51cf66",
        fontsize=9.0,
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
        ax_info.text(0.0, y_cursor, str_row, color="#c9d1d9", fontsize=7.9, va="top")
        y_cursor -= 0.023

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160, bbox_inches="tight", facecolor="#0b0e14")
    plt.close(fig)
    return output_path
