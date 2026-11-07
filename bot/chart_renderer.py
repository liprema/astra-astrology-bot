"""
Vintage Cream Poster Natal / Horary Chart Renderer for ASTRA ("Астра").
Matches the user's "THE BIRTH CHART in Astrology" reference poster aesthetic:
- Warm cream/ivory parchment poster background (`#faf6ee`) with fine vintage borders (`#cbbba0`)
- Top Header with Celestial Golden Sun (left) and Indigo Crescent Moon (right), stars, and bold serif title
- Central Natal Wheel with soft pastel zodiac sectors, crisp black ink lines, house ring, and colored planet glyphs
- Left Cards:
  1. "ДАННЫЕ РОЖДЕНИЯ" (Date, Time, Location, House System, Sect)
  2. "БОЛЬШАЯ ТРОЙКА (THE BIG THREE)" — Sun Sign, Moon Sign, and Rising Sign (Ascendant) with circular emblems
- Right Cards:
  "ПЛАНЕТЫ, ДОМА И ШКОЛЫ" — Detailed positions, rulers (Classical vs Modern), Hellenistic Lots, Profections, Firdaria & Formula of Soul
- Bottom Full-Width Strip:
  "ПЛАНЕТЫ И ИХ ЗНАЧЕНИЯ В КАРТЕ" — 10 Planets arranged horizontally with glyphs, sign, degree, house, and role!
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

from bot.astro_engine import ZODIAC_GLYPHS, ZODIAC_SIGNS_RU

BG_CREAM = "#faf6ee"
CARD_BG = "#f5efe2"
BORDER_TAN = "#cbbba0"
INK_DARK = "#1f2430"
INK_MUTED = "#5a5347"
GOLD_ACCENT = "#c8963e"

# Pastel Zodiac Wheel fills matching the reference poster
PASTEL_ELEMENT_FILLS = [
    "#f9dcd4",  # Fire (soft coral-peach)
    "#dfead8",  # Earth (soft sage-green)
    "#faeccf",  # Air (soft warm cream-gold)
    "#d8e6f2",  # Water (soft powder-blue)
]

SIGN_INK_COLORS = [
    "#c94a38",  # Fire
    "#3b7a47",  # Earth
    "#b87a1e",  # Air
    "#2c5e8a",  # Water
]

PLANET_INK_COLORS = {
    "Солнце": "#d48817",
    "Луна": "#4a5568",
    "Меркурий": "#2f855a",
    "Венера": "#c53060",
    "Марс": "#c53030",
    "Юпитер": "#6b46c1",
    "Сатурн": "#2d3748",
    "Уран": "#2b6cb0",
    "Нептун": "#3182ce",
    "Плутон": "#553c9a",
    "Сев. Узел (Раху)": "#744210",
    "Южн. Узел (Кету)": "#744210",
    "Лилит (Чёрная Луна)": "#4a5568",
}

PLANET_ROLES_RU = {
    "Солнце": ("СОЛНЦЕ", "Личность • Дух\nСознание • Цель"),
    "Луна": ("ЛУНА", "Эмоции • Душа\nПотребности • Быт"),
    "Меркурий": ("МЕРКУРИЙ", "Мышление • Речь\nОбучение • Связи"),
    "Венера": ("ВЕНЕРА", "Любовь • Ценности\nКрасота • Деньги"),
    "Марс": ("МАРС", "Действие • Воля\nСтрасть • Импульс"),
    "Юпитер": ("ЮПИТЕР", "Рост • Удача\nМасштаб • Мудрость"),
    "Сатурн": ("САТУРН", "Дисциплина • Закон\nОпыт • Карма"),
    "Уран": ("УРАН", "Свобода • Озарение\nРеформы • Будущее"),
    "Нептун": ("НЕПТУН", "Интуиция • Мечты\nТворчество • Тайна"),
    "Плутон": ("ПЛУТОН", "Трансформация\nВласть • Ресурс"),
}

ASPECT_POSTER_STYLES = {
    "Соединение": ("#c8963e", "-", 1.4),
    "Оппозиция": ("#c94a38", "-", 1.3),
    "Квадратура": ("#d9534f", "-", 1.2),
    "Трин": ("#3b6e9c", "-", 1.3),
    "Секстиль": ("#4a89bd", "--", 1.1),
    "Квиконс": ("#8c6bb1", ":", 0.9),
}


def ecl_to_polar_angle(lon: float, asc_lon: float) -> float:
    deg = (180.0 + (lon - asc_lon)) % 360.0
    return math.radians(deg)


def spread_overlapping_planets(planets: List[Dict], min_gap_deg: float = 6.2) -> Dict[str, float]:
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


def _draw_poster_box(ax, x: float, y: float, w: float, h: float, title: str = "") -> None:
    box = patches.FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.006,rounding_size=0.015",
        facecolor=CARD_BG,
        edgecolor=BORDER_TAN,
        linewidth=1.4,
        zorder=1,
    )
    ax.add_patch(box)
    if title:
        ax.text(
            x + w / 2.0,
            y + h - 0.018,
            f"—  {title}  —",
            color=INK_DARK,
            fontsize=9.5,
            fontweight="bold",
            family="serif",
            ha="center",
            va="top",
            zorder=3,
        )
        ax.plot(
            [x + 0.02, x + w - 0.02],
            [y + h - 0.038, y + h - 0.038],
            color=BORDER_TAN,
            linewidth=0.9,
            zorder=2,
        )


def _draw_celestial_sun(ax, cx: float, cy: float, r_x: float, r_y: float) -> None:
    for i in range(16):
        ang = math.radians(i * 22.5)
        r_len = 1.65 if i % 2 == 0 else 1.32
        tri = [
            (cx + r_x * 0.85 * math.cos(ang - 0.11), cy + r_y * 0.85 * math.sin(ang - 0.11)),
            (cx + r_x * r_len * math.cos(ang), cy + r_y * r_len * math.sin(ang)),
            (cx + r_x * 0.85 * math.cos(ang + 0.11), cy + r_y * 0.85 * math.sin(ang + 0.11)),
        ]
        ax.add_patch(patches.Polygon(tri, closed=True, facecolor="#e3b464", edgecolor="#8c6223", linewidth=0.9, zorder=3))
    disc = patches.Ellipse((cx, cy), width=r_x * 1.9, height=r_y * 1.9, facecolor="#f5dca8", edgecolor="#8c6223", linewidth=1.3, zorder=4)
    ax.add_patch(disc)
    ax.text(cx, cy, "☉", color="#6e4b16", fontsize=16, ha="center", va="center", zorder=5)


def _draw_celestial_moon(ax, cx: float, cy: float, r_x: float, r_y: float) -> None:
    outer = patches.Ellipse((cx, cy), width=r_x * 2.1, height=r_y * 2.1, facecolor="#8278a8", edgecolor="#3f375c", linewidth=1.3, zorder=3)
    ax.add_patch(outer)
    cutout = patches.Ellipse((cx - r_x * 0.55, cy + r_y * 0.18), width=r_x * 1.75, height=r_y * 1.85, facecolor=BG_CREAM, edgecolor="none", zorder=4)
    ax.add_patch(cutout)


def render_chart_image(chart: Dict, output_path: Path) -> Path:
    """
    Render the astrological chart in the Vintage Cream Infographic Poster layout.
    """
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial Unicode MS", "Helvetica", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    fig = plt.figure(figsize=(15.0, 18.0), dpi=150, facecolor=BG_CREAM)

    # Full-figure background canvas for cards, headers, and bottom strip
    ax_bg = fig.add_axes([0.0, 0.0, 1.0, 1.0], facecolor=BG_CREAM)
    ax_bg.set_xlim(0.0, 1.0)
    ax_bg.set_ylim(0.0, 1.0)
    ax_bg.axis("off")

    # Outer poster frame
    poster_frame = patches.FancyBboxPatch(
        (0.015, 0.012),
        0.97,
        0.976,
        boxstyle="round,pad=0.004,rounding_size=0.012",
        facecolor=BG_CREAM,
        edgecolor=BORDER_TAN,
        linewidth=2.0,
        zorder=0,
    )
    ax_bg.add_patch(poster_frame)

    # =========================================================================
    # 1. TOP HEADER (Sun on left, Title in center, Crescent Moon on right)
    # =========================================================================
    _draw_celestial_sun(ax_bg, 0.085, 0.935, 0.028, 0.023)
    _draw_celestial_moon(ax_bg, 0.915, 0.935, 0.028, 0.023)

    ax_bg.text(
        0.50,
        0.955,
        "НАТАЛЬНАЯ КАРТА",
        color=INK_DARK,
        fontsize=25,
        fontweight="bold",
        family="serif",
        ha="center",
        va="center",
    )
    ax_bg.text(
        0.50,
        0.922,
        f"—   Астра • {chart['subject_name']}   —",
        color=GOLD_ACCENT,
        fontsize=13.5,
        style="italic",
        family="serif",
        ha="center",
        va="center",
    )
    ax_bg.text(
        0.50,
        0.896,
        f"Астрономический срез неба в точный момент и на координаты: {chart['dt_local_str']} • {chart['place_label'][:48]}",
        color=INK_MUTED,
        fontsize=9.2,
        ha="center",
        va="center",
    )

    # =========================================================================
    # 2. LEFT COLUMN CARDS: Birth Data & "THE BIG THREE" (Sun, Moon, Ascendant)
    # =========================================================================
    _draw_poster_box(ax_bg, 0.028, 0.655, 0.215, 0.215, "ИСХОДНЫЕ ДАННЫЕ")
    data_items = [
        ("• Дата и время:", chart["dt_local_str"]),
        ("• Координаты:", f"{chart['lat']:.2f}°N, {chart['lon']:.2f}°E"),
        ("• Место:", chart["place_label"][:26]),
        ("• Система домов:", chart["house_system"]),
        ("• Секта карты:", chart["hellenistic_medieval"]["sect"].split("(")[0].strip()),
    ]
    dy = 0.818
    for lbl, val in data_items:
        ax_bg.text(0.040, dy, lbl, color=INK_DARK, fontsize=8.3, fontweight="bold", va="top")
        ax_bg.text(0.040, dy - 0.014, val, color=INK_MUTED, fontsize=8.0, va="top")
        dy -= 0.032

    # "THE BIG THREE" Card (Sun, Moon, Rising/ASC)
    _draw_poster_box(ax_bg, 0.028, 0.305, 0.215, 0.335, "БОЛЬШАЯ ТРОЙКА")
    planets_by_name = {p["name"]: p for p in chart["planets"]}
    sun_p = planets_by_name["Солнце"]
    moon_p = planets_by_name["Луна"]
    asc_info = chart["asc"]

    big_three = [
        ("☉", "#f5dca8", "СОЛНЕЧНЫЙ ЗНАК", f"{sun_p['sign']} ({sun_p['deg']}°{sun_p['min']:02d}')", f"{sun_p['house_primary']} дом • Упр.: {sun_p['trad_dispositor']}/{sun_p['mod_dispositor']}", "Сознание, ядро личности и жизненная сила."),
        ("☽", "#dcd6eb", "ЛУННЫЙ ЗНАК", f"{moon_p['sign']} ({moon_p['deg']}°{moon_p['min']:02d}')", f"{moon_p['house_primary']} дом • Упр.: {moon_p['trad_dispositor']}/{moon_p['mod_dispositor']}", "Эмоции, подсознание, адаптация и душа."),
        ("ASC", "#dfead8", "АСЦЕНДЕНТ (ВОСХ.)", f"{asc_info['sign']} ({asc_info['formatted'].split()[0]})", f"Упр. классич.: {asc_info['trad_ruler']} | модр.: {asc_info['mod_ruler']}", "Внешнее проявление, старт и фильтр мира."),
    ]
    by = 0.578
    for sym, badge_col, head_t, sign_t, sub_t, desc_t in big_three:
        circ = patches.Ellipse((0.062, by - 0.018), width=0.042, height=0.035, facecolor=badge_col, edgecolor=BORDER_TAN, linewidth=1.2, zorder=3)
        ax_bg.add_patch(circ)
        ax_bg.text(0.062, by - 0.018, sym, color=INK_DARK, fontsize=9.5, fontweight="bold", ha="center", va="center", zorder=4)

        ax_bg.text(0.092, by, head_t, color=GOLD_ACCENT, fontsize=8.0, fontweight="bold", va="top")
        ax_bg.text(0.092, by - 0.016, sign_t, color=INK_DARK, fontsize=9.0, fontweight="bold", va="top")
        ax_bg.text(0.092, by - 0.032, sub_t, color=INK_MUTED, fontsize=7.5, va="top")
        ax_bg.text(0.040, by - 0.050, desc_t, color=INK_MUTED, fontsize=7.3, style="italic", va="top")
        by -= 0.095

    # =========================================================================
    # 3. CENTER PANEL: Vintage Pastel Natal Wheel + "СИНТЕЗ ШКОЛ" Card Below
    # =========================================================================
    ax_wheel = fig.add_axes([0.245, 0.455, 0.445, 0.425], aspect="equal", facecolor=BG_CREAM)
    ax_wheel.set_xlim(-1.22, 1.22)
    ax_wheel.set_ylim(-1.22, 1.22)
    ax_wheel.axis("off")

    asc_lon = float(chart["asc"]["lon"])
    r_outer = 1.04
    r_sign_in = 0.84
    r_house_in = 0.72
    r_planet = 0.57
    r_aspect = 0.44

    # Draw Zodiac Sign Ring (12 Pastel Sectors)
    for s_idx in range(12):
        start_lon = s_idx * 30.0
        end_lon = (s_idx + 1) * 30.0
        theta1 = math.degrees(ecl_to_polar_angle(start_lon, asc_lon))
        theta2 = math.degrees(ecl_to_polar_angle(end_lon, asc_lon))

        wedge = patches.Wedge(
            (0, 0),
            r_outer,
            theta1,
            theta2,
            width=r_outer - r_sign_in,
            facecolor=PASTEL_ELEMENT_FILLS[s_idx % 4],
            edgecolor=INK_DARK,
            linewidth=1.1,
            zorder=2,
        )
        ax_wheel.add_patch(wedge)

        mid_ang = ecl_to_polar_angle(start_lon + 15.0, asc_lon)
        r_mid = (r_outer + r_sign_in) / 2.0
        ax_wheel.text(
            r_mid * math.cos(mid_ang),
            r_mid * math.sin(mid_ang),
            ZODIAC_GLYPHS[s_idx],
            color=SIGN_INK_COLORS[s_idx % 4],
            fontsize=16,
            fontweight="bold",
            ha="center",
            va="center",
            zorder=5,
        )

    # House Number Ring & Inner Circles
    house_ring = patches.Wedge((0, 0), r_sign_in, 0, 360, width=r_sign_in - r_house_in, facecolor="#faf6ee", edgecolor=INK_DARK, linewidth=1.0, zorder=2)
    ax_wheel.add_patch(house_ring)
    planet_ring = patches.Wedge((0, 0), r_house_in, 0, 360, width=r_house_in - r_aspect, facecolor="#ffffff", edgecolor=INK_DARK, linewidth=0.9, zorder=2)
    ax_wheel.add_patch(planet_ring)
    center_circle = patches.Circle((0, 0), r_aspect, facecolor="#faf8f2", edgecolor=INK_DARK, linewidth=1.0, zorder=2)
    ax_wheel.add_patch(center_circle)

    # Draw 12 House Cusps & Angles (ASC, IC, DSC, MC)
    cusps = chart["cusps"]
    for i in range(12):
        c_lon = cusps[i]
        c_next = cusps[(i + 1) % 12]
        ang = ecl_to_polar_angle(c_lon, asc_lon)
        is_angle = i in (0, 3, 6, 9)
        lw = 2.0 if is_angle else 0.85

        r_start = 0.0 if is_angle else r_aspect
        r_end = (r_outer + 0.07) if is_angle else r_sign_in
        ax_wheel.plot(
            [r_start * math.cos(ang), r_end * math.cos(ang)],
            [r_start * math.sin(ang), r_end * math.sin(ang)],
            color=INK_DARK,
            linewidth=lw,
            zorder=4,
        )

        if i in (0, 3, 6, 9):
            lbl = {0: "ASC", 3: "IC", 6: "DSC", 9: "MC"}[i]
            lx = (r_outer + 0.13) * math.cos(ang)
            ly = (r_outer + 0.13) * math.sin(ang)
            ax_wheel.text(lx, ly, lbl, color=INK_DARK, fontsize=10.5, fontweight="bold", family="serif", ha="center", va="center", zorder=7)

        span = (c_next - c_lon) % 360.0
        mid_lon = (c_lon + span / 2.0) % 360.0
        mid_ang = ecl_to_polar_angle(mid_lon, asc_lon)
        r_hnum = (r_sign_in + r_house_in) / 2.0
        ax_wheel.text(
            r_hnum * math.cos(mid_ang),
            r_hnum * math.sin(mid_ang),
            str(i + 1),
            color=INK_DARK,
            fontsize=8.2,
            fontweight="bold",
            ha="center",
            va="center",
            zorder=5,
        )

    # Draw Planets inside the wheel
    planets = chart["planets"]
    visual_lons = spread_overlapping_planets(planets, min_gap_deg=6.5)
    for p in planets:
        vis_ang = ecl_to_polar_angle(visual_lons[p["name"]], asc_lon)
        p_col = PLANET_INK_COLORS.get(p["name"], INK_DARK)
        px = r_planet * math.cos(vis_ang)
        py = r_planet * math.sin(vis_ang)
        ax_wheel.text(
            px,
            py,
            p["glyph"],
            color=p_col,
            fontsize=14,
            fontweight="bold",
            ha="center",
            va="center",
            zorder=7,
        )

    # Draw Aspect lines inside center circle
    for asp in chart["aspects"]:
        if asp["aspect"] not in ASPECT_POSTER_STYLES:
            continue
        col, ls, lw = ASPECT_POSTER_STYLES[asp["aspect"]]
        a1 = ecl_to_polar_angle(asp["p1_lon"], asc_lon)
        a2 = ecl_to_polar_angle(asp["p2_lon"], asc_lon)
        ax_wheel.plot(
            [r_aspect * 0.96 * math.cos(a1), r_aspect * 0.96 * math.cos(a2)],
            [r_aspect * 0.96 * math.sin(a1), r_aspect * 0.96 * math.sin(a2)],
            color=col,
            linestyle=ls,
            linewidth=lw,
            alpha=0.80,
            zorder=3,
        )

    # Center-Bottom Card: "ЭЛЛИНИСТИКА, ФОРМУЛА ДУШИ И УРАНИЧЕСКАЯ ШКОЛА"
    _draw_poster_box(ax_bg, 0.258, 0.305, 0.420, 0.145, "СИНТЕЗ ТРАДИЦИЙ И ШКОЛ")
    hm = chart["hellenistic_medieval"]
    fos = chart["formula_of_soul"]
    ur = chart["uranian"]
    synth_lines = [
        f"• Жребий Фортуны: {hm['lot_of_fortune']['formatted']} (дом {hm['lot_of_fortune']['house']})  |  Жребий Духа: {hm['lot_of_spirit']['formatted']} (дом {hm['lot_of_spirit']['house']})",
        f"• Профекция ({hm['annual_profection']['current_age']} л.): {hm['annual_profection']['profected_house']} дом ({hm['annual_profection']['profected_sign']}), Хронократор: {hm['annual_profection']['lord_of_year_trad']} / {hm['annual_profection']['lord_of_year_mod']}",
        f"• Фирдар сейчас: Большой период — {hm['firdaria']['major_firdar']}, Подпериод — {hm['firdaria']['sub_firdar']}",
        f"• Центры Формулы Души: Модерн [{', '.join(fos['modern_centers_domicile']) or 'рецепция'}] | Классика [{', '.join(fos['traditional_centers_domicile']) or 'рецепция'}]",
        f"• Гамбургская школа: Мидпойнт ☉/☽ = {ur['sun_moon_midpoint']}",
    ]
    sy = 0.408
    for sl in synth_lines:
        ax_bg.text(0.270, sy, sl[:76], color=INK_DARK, fontsize=7.6, va="top")
        sy -= 0.020

    # =========================================================================
    # 4. RIGHT COLUMN CARD: Detailed Planetary & Aspect Breakdown
    # =========================================================================
    _draw_poster_box(ax_bg, 0.695, 0.305, 0.277, 0.565, "ПЛАНЕТЫ, ДОМА И АСПЕКТЫ")
    ry = 0.825
    ax_bg.text(0.708, ry, "1. КООРДИНАТЫ И ДОМА (КЛАССИКА / ПЗ)", color=GOLD_ACCENT, fontsize=8.3, fontweight="bold", va="top")
    ry -= 0.022

    for p in chart["planets"]:
        short_n = p["name"].replace(" (Чёрная Луна)", "").replace(" (Раху)", "").replace(" (Кету)", "")
        p_col = PLANET_INK_COLORS.get(p["name"], INK_DARK)
        row_t = f"{p['glyph']} {short_n:<9} {p['formatted']:<14} Д.{p['house_primary']} (ПЗ:{p['house_wholesign']})"
        ax_bg.text(0.708, ry, row_t, color=p_col, fontsize=7.6, fontweight="bold", va="top")
        ry -= 0.021

    ry -= 0.010
    ax_bg.text(0.708, ry, "2. ТОЧНЫЕ АСПЕКТЫ (ОРБИС И ДВИЖЕНИЕ)", color=GOLD_ACCENT, fontsize=8.3, fontweight="bold", va="top")
    ry -= 0.022

    for a in sorted(chart["aspects"], key=lambda x: x["orb"])[:10]:
        asp_t = f"• {a['p1_glyph']} {a['p1'][:8]} {a['glyph']} {a['p2_glyph']} {a['p2'][:8]} — {a['aspect']} ({a['orb']}°, {a['motion'][:4]}.)"
        ax_bg.text(0.708, ry, asp_t, color=INK_DARK, fontsize=7.3, va="top")
        ry -= 0.019

    # =========================================================================
    # 5. BOTTOM FULL-WIDTH STRIP: "THE PLANETS AND THEIR MEANINGS" (10 Planets)
    # =========================================================================
    _draw_poster_box(ax_bg, 0.028, 0.115, 0.944, 0.172, "ПЛАНЕТЫ И ИХ ЗНАЧЕНИЯ В ВАШЕЙ КАРТЕ")

    ten_planets = chart["planets"][:10]
    for idx, p in enumerate(ten_planets):
        px = 0.075 + idx * 0.094
        py_circ = 0.222
        p_col = PLANET_INK_COLORS.get(p["name"], INK_DARK)
        fill_c = PASTEL_ELEMENT_FILLS[p["sign_idx"] % 4]

        med = patches.Ellipse((px, py_circ), width=0.040, height=0.033, facecolor=fill_c, edgecolor=p_col, linewidth=1.3, zorder=3)
        ax_bg.add_patch(med)
        ax_bg.text(px, py_circ, p["glyph"], color=p_col, fontsize=13, fontweight="bold", ha="center", va="center", zorder=4)

        p_title, p_role = PLANET_ROLES_RU.get(p["name"], (p["name"].upper(), ""))
        ax_bg.text(px, 0.194, p_title, color=INK_DARK, fontsize=7.6, fontweight="bold", family="serif", ha="center", va="top")
        ax_bg.text(px, 0.177, f"{p['deg']}° {p['sign'][:6]}. ({p['house_primary']} д.)", color=p_col, fontsize=7.2, fontweight="bold", ha="center", va="top")
        ax_bg.text(px, 0.156, p_role, color=INK_MUTED, fontsize=6.6, ha="center", va="top")

        if idx < 9:
            ax_bg.plot([px + 0.047, px + 0.047], [0.128, 0.242], color=BORDER_TAN, linewidth=0.7, zorder=2)

    # =========================================================================
    # 6. FOOTER CARDS: Classical vs Modern Rulerships & Quick Summary
    # =========================================================================
    _draw_poster_box(ax_bg, 0.028, 0.024, 0.455, 0.078)
    ax_bg.text(0.042, 0.088, "— КЛАССИЧЕСКАЯ ТРАДИЦИЯ vs СОВРЕМЕННАЯ ШКОЛА —", color=INK_DARK, fontsize=8.4, fontweight="bold", family="serif", va="top")
    ax_bg.text(
        0.042,
        0.066,
        f"• Управитель ASC ({asc_info['sign']}): Классика — {asc_info['trad_ruler']} | Модерн — {asc_info['mod_ruler']}\n"
        f"• Дома: {chart['house_system']} (психология и события) + Полнознаковая система (эллинистика)",
        color=INK_MUTED,
        fontsize=7.5,
        va="top",
    )

    _draw_poster_box(ax_bg, 0.517, 0.024, 0.455, 0.078)
    ax_bg.text(0.531, 0.088, "— КАРМИЧЕСКИЕ УЗЛЫ И ЧЁРНАЯ ЛУНА (ЛИЛИТ) —", color=INK_DARK, fontsize=8.4, fontweight="bold", family="serif", va="top")
    rahu = planets_by_name["Сев. Узел (Раху)"]
    ketu = planets_by_name["Южн. Узел (Кету)"]
    lilith = planets_by_name["Лилит (Чёрная Луна)"]
    ax_bg.text(
        0.531,
        0.066,
        f"• Северный Узел (Раху): {rahu['formatted']} ({rahu['house_primary']} дом)  |  Южный (Кету): {ketu['formatted']} ({ketu['house_primary']} дом)\n"
        f"• Лилит (Чёрная Луна): {lilith['formatted']} ({lilith['house_primary']} дом)  •  Звёзды не принуждают, а направляют",
        color=INK_MUTED,
        fontsize=7.5,
        va="top",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=BG_CREAM)
    plt.close(fig)
    return output_path
