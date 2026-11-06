"""
High-resolution Natal / Horary / Mundane / Synastry Chart Renderer.
Produces a crisp PNG image ready to be sent as a Telegram photo.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

from bot.astro_engine import ZODIAC_GLYPHS, ZODIAC_SIGNS_RU

# Element colors for the 12 signs (Fire, Earth, Air, Water)
ELEMENT_COLORS = [
    "#ff6b6b",  # Fire (Aries, Leo, Sagittarius)
    "#51cf66",  # Earth (Taurus, Virgo, Capricorn)
    "#ffd43b",  # Air (Gemini, Libra, Aquarius)
    "#4dabf7",  # Water (Cancer, Scorpio, Pisces)
]

PLANET_COLORS = {
    "Солнце": "#ffd43b",
    "Луна": "#e9ecef",
    "Меркурий": "#74c0fc",
    "Венера": "#f783ac",
    "Марс": "#ff6b6b",
    "Юпитер": "#ffa94d",
    "Сатурн": "#ced4da",
    "Уран": "#3bc9db",
    "Нептун": "#748ffc",
    "Плутон": "#da77f2",
    "Сев. Узел (Раху)": "#63e6be",
    "Южн. Узел (Кету)": "#63e6be",
    "Лилит (Чёрная Луна)": "#b197fc",
}

ASPECT_STYLES = {
    "Соединение": ("#ffd43b", "-", 1.6),
    "Оппозиция": ("#ff6b6b", "-", 1.5),
    "Квадратура": ("#ff8787", "-", 1.3),
    "Трин": ("#51cf66", "-", 1.4),
    "Секстиль": ("#4dabf7", "--", 1.1),
    "Квиконс": ("#da77f2", ":", 0.9),
}


def ecl_to_polar_angle(lon: float, asc_lon: float) -> float:
    """
    Convert ecliptic longitude (0..360) to standard polar angle in radians
    such that the Ascendant (asc_lon) is fixed at 180° (left / 9 o'clock),
    and the zodiac progresses counter-clockwise (IC at bottom, DSC at right, MC near top).
    """
    deg = (180.0 + (lon - asc_lon)) % 360.0
    return math.radians(deg)


def spread_overlapping_planets(planets: List[Dict], min_gap_deg: float = 5.5) -> Dict[str, float]:
    """Adjust visual longitudes slightly so close conjunctions don't overlap on the wheel."""
    items = sorted([(p["name"], float(p["lon"])) for p in planets], key=lambda x: x[1])
    n = len(items)
    adjusted = [lon for _, lon in items]

    for _ in range(6):
        for i in range(n):
            j = (i + 1) % n
            diff = (adjusted[j] - adjusted[i]) % 360.0
            if diff < min_gap_deg:
                shift = (min_gap_deg - diff) / 2.0
                adjusted[i] = (adjusted[i] - shift) % 360.0
                adjusted[j] = (adjusted[j] + shift) % 360.0

    return {items[i][0]: adjusted[i] for i in range(n)}


def render_chart_image(chart: Dict, output_path: Path) -> Path:
    """
    Render the astrological chart wheel and sidebar summary table into a PNG file.
    """
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial Unicode MS", "Helvetica", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    fig = plt.figure(figsize=(15, 10), dpi=160, facecolor="#0d1117")
    gs = fig.add_gridspec(1, 2, width_ratios=[1.25, 1.0], wspace=0.05)

    # Left panel: Chart Wheel
    ax = fig.add_subplot(gs[0], aspect="equal")
    ax.set_facecolor("#0d1117")
    ax.set_xlim(-1.22, 1.22)
    ax.set_ylim(-1.22, 1.22)
    ax.axis("off")

    asc_lon = float(chart["asc"]["lon"])

    # Radii for concentric rings
    r_outer = 1.05
    r_sign_inner = 0.88
    r_house_inner = 0.42
    r_planet = 0.72
    r_aspect = 0.41

    # Draw outer background circles
    for rad, lw, col in [
        (r_outer, 2.0, "#8b949e"),
        (r_sign_inner, 1.5, "#8b949e"),
        (r_house_inner, 1.2, "#484f58"),
    ]:
        circle = patches.Circle((0, 0), rad, fill=False, edgecolor=col, linewidth=lw, zorder=3)
        ax.add_patch(circle)

    inner_fill = patches.Circle((0, 0), r_house_inner, facecolor="#161b22", edgecolor="none", zorder=1)
    ax.add_patch(inner_fill)

    # 1. Draw 12 Zodiac Sign Sectors
    for s_idx in range(12):
        start_lon = s_idx * 30.0
        end_lon = (s_idx + 1) * 30.0
        theta1 = math.degrees(ecl_to_polar_angle(start_lon, asc_lon))
        theta2 = math.degrees(ecl_to_polar_angle(end_lon, asc_lon))

        el_color = ELEMENT_COLORS[s_idx % 4]
        wedge = patches.Wedge(
            (0, 0),
            r_outer,
            theta1,
            theta2,
            width=r_outer - r_sign_inner,
            facecolor=el_color,
            alpha=0.18,
            edgecolor="#30363d",
            linewidth=1.0,
            zorder=2,
        )
        ax.add_patch(wedge)

        # Degree ticks every 5 degrees
        for d in range(0, 30, 5):
            tick_angle = ecl_to_polar_angle(start_lon + d, asc_lon)
            t_in = r_sign_inner
            t_out = r_sign_inner + (0.035 if d % 10 == 0 else 0.018)
            ax.plot(
                [t_in * math.cos(tick_angle), t_out * math.cos(tick_angle)],
                [t_in * math.sin(tick_angle), t_out * math.sin(tick_angle)],
                color="#8b949e",
                linewidth=0.7,
                zorder=4,
            )

        # Sign glyph + Russian short label in middle of sector
        mid_angle = ecl_to_polar_angle(start_lon + 15.0, asc_lon)
        r_mid = (r_outer + r_sign_inner) / 2.0
        gx, gy = r_mid * math.cos(mid_angle), r_mid * math.sin(mid_angle)
        ax.text(
            gx,
            gy,
            f"{ZODIAC_GLYPHS[s_idx]}",
            color=el_color,
            fontsize=16,
            fontweight="bold",
            ha="center",
            va="center",
            zorder=5,
        )

    # 2. Draw 12 House Cusps & Numbers
    cusps = chart["cusps"]
    for i in range(12):
        c_lon = cusps[i]
        c_next = cusps[(i + 1) % 12]
        ang = ecl_to_polar_angle(c_lon, asc_lon)

        is_angle = i in (0, 3, 6, 9)
        line_col = "#f0883e" if i in (0, 6) else ("#58a6ff" if i in (3, 9) else "#484f58")
        lw = 2.2 if is_angle else 1.0

        r_end = r_outer + 0.06 if is_angle else r_sign_inner
        ax.plot(
            [r_house_inner * math.cos(ang), r_end * math.cos(ang)],
            [r_house_inner * math.sin(ang), r_end * math.sin(ang)],
            color=line_col,
            linewidth=lw,
            zorder=4,
        )

        # Angle Labels (ASC, IC, DSC, MC)
        if i == 0:
            lbl = "ASC"
        elif i == 3:
            lbl = "IC"
        elif i == 6:
            lbl = "DSC"
        elif i == 9:
            lbl = "MC"
        else:
            lbl = None

        if lbl:
            lx = (r_outer + 0.11) * math.cos(ang)
            ly = (r_outer + 0.11) * math.sin(ang)
            ax.text(
                lx,
                ly,
                lbl,
                color=line_col,
                fontsize=11,
                fontweight="bold",
                ha="center",
                va="center",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#161b22", edgecolor=line_col, lw=1),
                zorder=7,
            )

        # House number at midpoint of house sector
        span = (c_next - c_lon) % 360.0
        mid_lon = (c_lon + span / 2.0) % 360.0
        mid_ang = ecl_to_polar_angle(mid_lon, asc_lon)
        r_hnum = r_house_inner + 0.06
        ax.text(
            r_hnum * math.cos(mid_ang),
            r_hnum * math.sin(mid_ang),
            str(i + 1),
            color="#8b949e",
            fontsize=9,
            fontweight="bold",
            ha="center",
            va="center",
            zorder=5,
        )

    # 3. Draw Planets and Lot of Fortune
    planets = chart["planets"]
    visual_lons = spread_overlapping_planets(planets, min_gap_deg=6.0)

    for p in planets:
        true_ang = ecl_to_polar_angle(p["lon"], asc_lon)
        vis_ang = ecl_to_polar_angle(visual_lons[p["name"]], asc_lon)
        p_col = PLANET_COLORS.get(p["name"], "#ffffff")

        # Tick on the sign inner border at exact position
        ax.plot(
            [r_sign_inner * math.cos(true_ang), (r_sign_inner - 0.03) * math.cos(true_ang)],
            [r_sign_inner * math.sin(true_ang), (r_sign_inner - 0.03) * math.sin(true_ang)],
            color=p_col,
            linewidth=1.3,
            zorder=5,
        )
        # Connector to visual glyph position
        ax.plot(
            [(r_sign_inner - 0.03) * math.cos(true_ang), (r_planet + 0.05) * math.cos(vis_ang)],
            [(r_sign_inner - 0.03) * math.sin(true_ang), (r_planet + 0.05) * math.sin(vis_ang)],
            color=p_col,
            linewidth=0.6,
            alpha=0.6,
            zorder=4,
        )

        px = r_planet * math.cos(vis_ang)
        py = r_planet * math.sin(vis_ang)
        ax.text(
            px,
            py,
            p["glyph"],
            color=p_col,
            fontsize=14,
            fontweight="bold",
            ha="center",
            va="center",
            bbox=dict(boxstyle="circle,pad=0.18", facecolor="#0d1117", edgecolor=p_col, lw=0.9),
            zorder=8,
        )

        # Degree label slightly inward
        r_deg = r_planet - 0.11
        dx = r_deg * math.cos(vis_ang)
        dy = r_deg * math.sin(vis_ang)
        retro_mark = "R" if p["retro"] else ""
        ax.text(
            dx,
            dy,
            f"{p['deg']}°{retro_mark}",
            color="#c9d1d9",
            fontsize=7.5,
            ha="center",
            va="center",
            zorder=8,
        )

    # 4. Draw Aspect chords inside inner circle
    for asp in chart["aspects"]:
        if asp["aspect"] not in ASPECT_STYLES:
            continue
        col, ls, lw = ASPECT_STYLES[asp["aspect"]]
        a1 = ecl_to_polar_angle(asp["p1_lon"], asc_lon)
        a2 = ecl_to_polar_angle(asp["p2_lon"], asc_lon)
        ax.plot(
            [r_aspect * math.cos(a1), r_aspect * math.cos(a2)],
            [r_aspect * math.sin(a1), r_aspect * math.sin(a2)],
            color=col,
            linestyle=ls,
            linewidth=lw,
            alpha=0.75,
            zorder=3,
        )

    # Right panel: Detailed Information Table
    ax_info = fig.add_subplot(gs[1])
    ax_info.set_facecolor("#0d1117")
    ax_info.axis("off")

    title_text = f"АСТРА • {chart['subject_name'].upper()}"
    ax_info.text(0.0, 0.97, title_text, color="#f0f6fc", fontsize=14, fontweight="bold", va="top")

    meta_lines = [
        f"Дата/время: {chart['dt_local_str']}  ({chart['dt_utc_str']})",
        f"Место: {chart['place_label'][:52]} ({chart['lat']:.2f}°, {chart['lon']:.2f}°)",
        f"Дома: {chart['house_system']}  |  {chart['hellenistic_medieval']['sect']}",
        f"ASC: {chart['asc']['formatted']}   |   MC: {chart['mc']['formatted']}",
    ]
    y_cursor = 0.925
    for ml in meta_lines:
        ax_info.text(0.0, y_cursor, ml, color="#8b949e", fontsize=9, va="top")
        y_cursor -= 0.028

    # Planets block
    y_cursor -= 0.015
    ax_info.text(0.0, y_cursor, "ПЛАНЕТЫ, ДОМА И ДОСТОИНСТВА (КЛАССИКА / МОДЕРН)", color="#58a6ff", fontsize=9.5, fontweight="bold", va="top")
    y_cursor -= 0.028

    for p in chart["planets"]:
        p_col = PLANET_COLORS.get(p["name"], "#c9d1d9")
        short_name = p["name"].replace(" (Чёрная Луна)", "").replace(" (Раху)", "").replace(" (Кету)", "")
        col1 = f"{p['glyph']} {short_name}"
        col2 = f"{p['formatted']}"
        col3 = f"Д.{p['house_primary']} (ПЗ:{p['house_wholesign']})"
        col4 = f"Упр: {p['trad_dispositor'][:4]}./{p['mod_dispositor'][:4]}. | {p['dignity_traditional'][:22]}"
        ax_info.text(0.00, y_cursor, col1, color=p_col, fontsize=8.2, fontweight="bold", va="top")
        ax_info.text(0.24, y_cursor, col2, color=p_col, fontsize=8.2, va="top")
        ax_info.text(0.49, y_cursor, col3, color="#c9d1d9", fontsize=8.0, va="top")
        ax_info.text(0.67, y_cursor, col4, color="#8b949e", fontsize=7.8, va="top")
        y_cursor -= 0.025

    # Medieval / Hellenistic / Uranian block
    y_cursor -= 0.012
    ax_info.text(0.0, y_cursor, "ЭЛЛИНИСТИКА, СРЕДНЕВЕКОВЬЕ, ФОРМУЛА ДУШИ, ГАМБУРГСКАЯ ШКОЛА", color="#f0883e", fontsize=9.2, fontweight="bold", va="top")
    y_cursor -= 0.026

    hm = chart["hellenistic_medieval"]
    fos = chart["formula_of_soul"]
    ur = chart["uranian"]
    extra_rows = [
        f"• Жребий Фортуны: {hm['lot_of_fortune']['formatted']} (дом {hm['lot_of_fortune']['house']}) | Жребий Духа: {hm['lot_of_spirit']['formatted']} (дом {hm['lot_of_spirit']['house']})",
        f"• Годовая профекция ({hm['annual_profection']['current_age']} л.): {hm['annual_profection']['profected_house']} дом ({hm['annual_profection']['profected_sign']}), Хронократор: {hm['annual_profection']['lord_of_year_trad']} / {hm['annual_profection']['lord_of_year_mod']}",
        f"• Фирдар сейчас: Большой период — {hm['firdaria']['major_firdar']}, Подпериод — {hm['firdaria']['sub_firdar']}",
        f"• Формула Души (центры обители): Модерн [{', '.join(fos['modern_centers_domicile']) or 'взаимная рецепция'}] | Классика [{', '.join(fos['traditional_centers_domicile']) or 'взаимная рецепция'}]",
        f"• Мидпойнт Солнце/Луна (☉/☽): {ur['sun_moon_midpoint']}",
    ]
    if ur["transneptunians"]:
        tn_short = ", ".join(f"{t['name'].split()[0]} {t['formatted'][:9]}" for t in ur["transneptunians"][:4])
        tn_short2 = ", ".join(f"{t['name'].split()[0]} {t['formatted'][:9]}" for t in ur["transneptunians"][4:])
        extra_rows.append(f"• Транснептуны (Уранич.): {tn_short}")
        extra_rows.append(f"  {tn_short2}")

    for er in extra_rows:
        ax_info.text(0.0, y_cursor, er, color="#c9d1d9", fontsize=8.0, va="top")
        y_cursor -= 0.024

    # Major Aspects block
    y_cursor -= 0.010
    ax_info.text(0.0, y_cursor, "КЛЮЧЕВЫЕ АСПЕКТЫ (ТОЧНЫЕ ОРБИСЫ)", color="#51cf66", fontsize=9.2, fontweight="bold", va="top")
    y_cursor -= 0.025

    sorted_aspects = sorted(chart["aspects"], key=lambda a: a["orb"])[:12]
    col1_aspects = sorted_aspects[:6]
    col2_aspects = sorted_aspects[6:12]

    y_asp_start = y_cursor
    for a in col1_aspects:
        txt = f"{a['p1_glyph']} {a['p1'][:8]} {a['glyph']} {a['p2_glyph']} {a['p2'][:8]} ({a['orb']}° {a['motion'][:4]}.)"
        ax_info.text(0.0, y_cursor, txt, color="#c9d1d9", fontsize=7.8, va="top")
        y_cursor -= 0.022

    y_cursor = y_asp_start
    for a in col2_aspects:
        txt = f"{a['p1_glyph']} {a['p1'][:8]} {a['glyph']} {a['p2_glyph']} {a['p2'][:8]} ({a['orb']}° {a['motion'][:4]}.)"
        ax_info.text(0.50, y_cursor, txt, color="#c9d1d9", fontsize=7.8, va="top")
        y_cursor -= 0.022

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160, bbox_inches="tight", facecolor="#0d1117")
    plt.close(fig)
    return output_path
