"""
High-Resolution Vintage Cream Infographic Natal Chart Renderer for ASTRA ("Астра")
modeled directly on the "THE BIRTH CHART in Astrology" vintage poster aesthetic:
- Warm parchment/cream background (#faf6ee) with delicate tan borders (#c9b99a)
- Illustrated Celestial Sun (with face & rays) in top-left and Crescent Moon (with face & stars) in top-right
- Hand-drawn vector icons for Birth Date (calendar), Birth Time (clock), Birth Location (map pin)
- Left column: "ИСХОДНЫЕ ДАННЫЕ" + "БОЛЬШАЯ ТРОЙКА" (Sun, Moon, Rising/ASC medallions)
- Center: Pastel 12-sign Zodiac Wheel + "КАК ВСЁ РАБОТАЕТ ВМЕСТЕ" card with 4 circular medallions (Планеты + Знаки + Дома + Аспекты) & curly bracket
- Right column: "ЧТО РАСКРЫВАЕТ ВАША КАРТА" with 5 large colored circular medallions (1. Знаки, 2. Планеты, 3. Дома, 4. Аспекты, 5. Асцендент)
- Bottom full-width strip: "ПЛАНЕТЫ И ИХ ЗНАЧЕНИЯ" (all 10 planets in a horizontal row with glyphs, degrees, houses, and meanings)
- Footer: 2 summary cards flanking a central starry-night cosmos medallion + bottom motto
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

from bot.astro_engine import ZODIAC_GLYPHS


BG_CREAM = "#faf6ee"
CARD_CREAM = "#f5efe2"
BORDER_TAN = "#cbbba0"
INK_DARK = "#232533"
INK_MUTED = "#5a534a"
GOLD_ACCENT = "#b58338"

PASTEL_ELEMENT_FILLS = [
    "#f7d9c4",  # Огонь (Fire - soft peach/coral)
    "#dfead8",  # Земля (Earth - soft sage green)
    "#f9eec8",  # Воздух (Air - warm buttercream yellow)
    "#d8e5f2",  # Вода (Water - soft powder blue/lavender)
]

SIGN_INK_COLORS = [
    "#b84a39",  # Огонь
    "#3b6e4c",  # Земля
    "#9c711c",  # Воздух
    "#385a8c",  # Вода
]

PLANET_INK_COLORS = {
    "Солнце": "#c77d18",
    "Луна": "#5c527f",
    "Меркурий": "#2e6f5e",
    "Венера": "#b84b6b",
    "Марс": "#c0392b",
    "Юпитер": "#6c4699",
    "Сатурн": "#3d3d4e",
    "Уран": "#256d85",
    "Нептун": "#2c548e",
    "Плутон": "#5a2a47",
    "Сев. Узел (Раху)": "#7d5a2b",
    "Южн. Узел (Кету)": "#7d5a2b",
    "Лилит (Чёрная Луна)": "#3b2c47",
}

ASPECT_POSTER_STYLES = {
    "Соединение": ("#c77d18", "-", 1.4),
    "Оппозиция": ("#c0392b", "-", 1.3),
    "Квадратура": ("#c0392b", "-", 1.15),
    "Трин": ("#385a8c", "-", 1.25),
    "Секстиль": ("#385a8c", "--", 1.0),
    "Квиконс": ("#8c7a6b", ":", 0.9),
}

PLANET_ROLES_RU = {
    "Солнце": ("СОЛНЦЕ", "Личность\nСознание\nЭнергия жизни"),
    "Луна": ("ЛУНА", "Эмоции\nВнутренний мир\nИнтуиция"),
    "Меркурий": ("МЕРКУРИЙ", "Общение\nМышление\nОбучение"),
    "Венера": ("ВЕНЕРА", "Любовь\nКрасота\nЦенности"),
    "Марс": ("МАРС", "Действие\nСтрасть\nИмпульс"),
    "Юпитер": ("ЮПИТЕР", "Рост\nУдача\nМасштаб"),
    "Сатурн": ("САТУРН", "Дисциплина\nОтветственность\nУроки"),
    "Уран": ("УРАН", "Перемены\nСвобода\nОригинальность"),
    "Нептун": ("НЕПТУН", "Мечты\nИнтуиция\nДуховность"),
    "Плутон": ("ПЛУТОН", "Трансформация\nСила\nВозрождение"),
}


def ecl_to_polar_angle(ecl_lon: float, asc_lon: float) -> float:
    return math.radians((180.0 + (ecl_lon - asc_lon)) % 360.0)


def spread_overlapping_planets(planets: List[Dict], min_gap_deg: float = 6.5) -> Dict[str, float]:
    sorted_p = sorted(planets, key=lambda x: x["lon"])
    lons = [p["lon"] for p in sorted_p]
    names = [p["name"] for p in sorted_p]

    for _ in range(12):
        for i in range(len(lons)):
            j = (i + 1) % len(lons)
            diff = (lons[j] - lons[i]) % 360.0
            if diff < min_gap_deg:
                push = (min_gap_deg - diff) / 2.0
                lons[i] = (lons[i] - push) % 360.0
                lons[j] = (lons[j] + push) % 360.0

    return {names[i]: lons[i] for i in range(len(names))}


def _draw_sparkle(ax, cx: float, cy: float, rx: float, ry: float, col: str = GOLD_ACCENT, z: float = 4) -> None:
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


def _draw_poster_box(ax, x: float, y: float, w: float, h: float, title: str = "", title_sparkles: bool = True) -> None:
    box = patches.FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.006,rounding_size=0.014",
        facecolor=CARD_CREAM,
        edgecolor=BORDER_TAN,
        linewidth=1.35,
        zorder=1,
    )
    ax.add_patch(box)
    if title:
        ax.text(
            x + w / 2.0,
            y + h - 0.015,
            title,
            color=INK_DARK,
            fontsize=9.2,
            fontweight="bold",
            family="serif",
            ha="center",
            va="top",
            zorder=3,
        )
        if title_sparkles:
            half_span = min(w * 0.44, len(title) * 0.0046 + 0.025)
            _draw_sparkle(ax, x + w / 2.0 - half_span, y + h - 0.021, 0.0045, 0.0055, GOLD_ACCENT, z=4)
            _draw_sparkle(ax, x + w / 2.0 + half_span, y + h - 0.021, 0.0045, 0.0055, GOLD_ACCENT, z=4)
        ax.plot(
            [x + 0.016, x + w - 0.016],
            [y + h - 0.034, y + h - 0.034],
            color=BORDER_TAN,
            linewidth=0.9,
            zorder=2,
        )


def _draw_celestial_sun(ax, cx: float, cy: float, r_x: float, r_y: float) -> None:
    """Draw vintage Sun with classic face and alternating rays + sparkles."""
    for i in range(16):
        ang = math.radians(i * 22.5)
        r_len = 1.75 if i % 2 == 0 else 1.38
        w_ang = 0.11 if i % 2 == 0 else 0.08
        tri = [
            (cx + r_x * 0.88 * math.cos(ang - w_ang), cy + r_y * 0.88 * math.sin(ang - w_ang)),
            (cx + r_x * r_len * math.cos(ang), cy + r_y * r_len * math.sin(ang)),
            (cx + r_x * 0.88 * math.cos(ang + w_ang), cy + r_y * 0.88 * math.sin(ang + w_ang)),
        ]
        ax.add_patch(patches.Polygon(tri, closed=True, facecolor="#e8be74", edgecolor="#8c6223", linewidth=0.9, zorder=3))
    disc = patches.Ellipse((cx, cy), width=r_x * 1.9, height=r_y * 1.9, facecolor="#f7dfb2", edgecolor="#8c6223", linewidth=1.35, zorder=4)
    ax.add_patch(disc)
    # Drawn face inside sun
    for side in (-1, 1):
        ex = cx + side * r_x * 0.34
        ey = cy + r_y * 0.16
        eye = patches.Ellipse((ex, ey), width=r_x * 0.22, height=r_y * 0.14, facecolor="#6e4b16", edgecolor="none", zorder=5)
        ax.add_patch(eye)
        brow = patches.Arc((ex, ey + r_y * 0.10), r_x * 0.36, r_y * 0.22, angle=0, theta1=20, theta2=160, color="#6e4b16", linewidth=1.0, zorder=5)
        ax.add_patch(brow)
    # Nose & serene smile
    ax.plot([cx, cx - r_x * 0.08, cx + r_x * 0.04], [cy + r_y * 0.14, cy - r_y * 0.10, cy - r_y * 0.12], color="#6e4b16", linewidth=1.0, zorder=5)
    smile = patches.Arc((cx, cy - r_y * 0.24), r_x * 0.42, r_y * 0.22, angle=0, theta1=200, theta2=340, color="#6e4b16", linewidth=1.1, zorder=5)
    ax.add_patch(smile)
    # Sparkles around sun
    _draw_sparkle(ax, cx + r_x * 2.1, cy + r_y * 1.1, 0.005, 0.006, GOLD_ACCENT, z=4)
    _draw_sparkle(ax, cx + r_x * 1.9, cy - r_y * 1.2, 0.004, 0.005, GOLD_ACCENT, z=4)
    _draw_sparkle(ax, cx - r_x * 1.9, cy - r_y * 1.3, 0.004, 0.005, GOLD_ACCENT, z=4)


def _draw_celestial_moon(ax, cx: float, cy: float, r_x: float, r_y: float) -> None:
    """Draw vintage Crescent Moon with profile face and surrounding stars."""
    outer = patches.Ellipse((cx, cy), width=r_x * 2.15, height=r_y * 2.15, facecolor="#8c82b0", edgecolor="#3f375c", linewidth=1.35, zorder=3)
    ax.add_patch(outer)
    cutout = patches.Ellipse((cx - r_x * 0.56, cy + r_y * 0.14), width=r_x * 1.75, height=r_y * 1.85, facecolor=BG_CREAM, edgecolor="none", zorder=4)
    ax.add_patch(cutout)
    # Subtle inner crescent contour & eye/smile on moon crescent
    eye_m = patches.Arc((cx + r_x * 0.42, cy + r_y * 0.18), r_x * 0.26, r_y * 0.16, angle=0, theta1=190, theta2=350, color="#2e2747", linewidth=1.1, zorder=5)
    ax.add_patch(eye_m)
    smile_m = patches.Arc((cx + r_x * 0.34, cy - r_y * 0.22), r_x * 0.28, r_y * 0.18, angle=0, theta1=200, theta2=330, color="#2e2747", linewidth=1.0, zorder=5)
    ax.add_patch(smile_m)
    # Surrounding stars
    _draw_sparkle(ax, cx - r_x * 1.5, cy + r_y * 0.9, 0.005, 0.006, GOLD_ACCENT, z=5)
    _draw_sparkle(ax, cx - r_x * 1.8, cy - r_y * 0.6, 0.004, 0.005, GOLD_ACCENT, z=5)
    _draw_sparkle(ax, cx + r_x * 1.4, cy + r_y * 1.1, 0.004, 0.005, GOLD_ACCENT, z=5)
    _draw_sparkle(ax, cx + r_x * 1.3, cy - r_y * 1.1, 0.0045, 0.0055, GOLD_ACCENT, z=5)


def _draw_line_icon(ax, kind: str, cx: float, cy: float, w: float, h: float) -> None:
    """Draw crisp vintage line-art icons (calendar, clock, pin, house) in the left card."""
    if kind == "calendar":
        rect = patches.FancyBboxPatch((cx - w * 0.45, cy - h * 0.45), w * 0.9, h * 0.85, boxstyle="round,pad=0.001,rounding_size=0.003", facecolor="#ffffff", edgecolor=INK_DARK, linewidth=1.1, zorder=4)
        ax.add_patch(rect)
        ax.plot([cx - w * 0.45, cx + w * 0.45], [cy + h * 0.15, cy + h * 0.15], color=INK_DARK, linewidth=1.0, zorder=5)
        ax.plot([cx - w * 0.22, cx - w * 0.22], [cy + h * 0.30, cy + h * 0.50], color=INK_DARK, linewidth=1.2, zorder=5)
        ax.plot([cx + w * 0.22, cx + w * 0.22], [cy + h * 0.30, cy + h * 0.50], color=INK_DARK, linewidth=1.2, zorder=5)
        for gx in (-0.22, 0.0, 0.22):
            for gy in (-0.05, -0.25):
                dot = patches.Ellipse((cx + w * gx, cy + h * gy), width=w * 0.10, height=h * 0.10, facecolor=GOLD_ACCENT, edgecolor="none", zorder=5)
                ax.add_patch(dot)
    elif kind == "clock":
        circ = patches.Ellipse((cx, cy), width=w * 0.95, height=h * 0.95, facecolor="#ffffff", edgecolor=INK_DARK, linewidth=1.1, zorder=4)
        ax.add_patch(circ)
        ax.plot([cx, cx], [cy, cy + h * 0.30], color=INK_DARK, linewidth=1.1, zorder=5)
        ax.plot([cx, cx + w * 0.26], [cy, cy - h * 0.10], color=GOLD_ACCENT, linewidth=1.1, zorder=5)
    elif kind == "pin":
        circ = patches.Ellipse((cx, cy + h * 0.12), width=w * 0.72, height=h * 0.68, facecolor="#ffffff", edgecolor=INK_DARK, linewidth=1.1, zorder=4)
        ax.add_patch(circ)
        tri = [(cx - w * 0.30, cy - h * 0.02), (cx + w * 0.30, cy - h * 0.02), (cx, cy - h * 0.48)]
        ax.add_patch(patches.Polygon(tri, closed=True, facecolor="#ffffff", edgecolor=INK_DARK, linewidth=1.1, zorder=4))
        inner = patches.Ellipse((cx, cy + h * 0.12), width=w * 0.28, height=h * 0.28, facecolor=GOLD_ACCENT, edgecolor=INK_DARK, linewidth=0.8, zorder=5)
        ax.add_patch(inner)
    elif kind == "house":
        roof = [(cx - w * 0.48, cy + h * 0.05), (cx, cy + h * 0.48), (cx + w * 0.48, cy + h * 0.05)]
        ax.add_patch(patches.Polygon(roof, closed=True, facecolor="#dfead8", edgecolor=INK_DARK, linewidth=1.0, zorder=4))
        body = patches.Rectangle((cx - w * 0.34, cy - h * 0.42), w * 0.68, h * 0.47, facecolor="#ffffff", edgecolor=INK_DARK, linewidth=1.0, zorder=4)
        ax.add_patch(body)


def render_chart_image(chart: Dict, output_path: Path) -> Path:
    """
    Render the astrological chart in the exact Vintage Cream Infographic Poster layout.
    """
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial Unicode MS", "Helvetica", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    fig = plt.figure(figsize=(15.0, 18.2), dpi=150, facecolor=BG_CREAM)

    ax_bg = fig.add_axes([0.0, 0.0, 1.0, 1.0], facecolor=BG_CREAM)
    ax_bg.set_xlim(0.0, 1.0)
    ax_bg.set_ylim(0.0, 1.0)
    ax_bg.axis("off")

    # Outer poster frame
    poster_frame = patches.FancyBboxPatch(
        (0.014, 0.012),
        0.972,
        0.976,
        boxstyle="round,pad=0.004,rounding_size=0.012",
        facecolor=BG_CREAM,
        edgecolor=BORDER_TAN,
        linewidth=2.0,
        zorder=0,
    )
    ax_bg.add_patch(poster_frame)

    # =========================================================================
    # 1. TOP HEADER (Sun with face on left, Title in center, Crescent Moon on right)
    # =========================================================================
    _draw_celestial_sun(ax_bg, 0.088, 0.936, 0.030, 0.025)
    _draw_celestial_moon(ax_bg, 0.912, 0.936, 0.030, 0.025)

    ax_bg.text(
        0.50,
        0.956,
        "НАТАЛЬНАЯ КАРТА",
        color=INK_DARK,
        fontsize=26,
        fontweight="bold",
        family="serif",
        ha="center",
        va="center",
    )
    # Decorative lines & sparkles around subtitle (matching "in Astrology")
    ax_bg.plot([0.26, 0.34], [0.923, 0.923], color=BORDER_TAN, linewidth=1.1)
    ax_bg.plot([0.66, 0.74], [0.923, 0.923], color=BORDER_TAN, linewidth=1.1)
    _draw_sparkle(ax_bg, 0.352, 0.923, 0.005, 0.006, GOLD_ACCENT, z=4)
    _draw_sparkle(ax_bg, 0.648, 0.923, 0.005, 0.006, GOLD_ACCENT, z=4)
    ax_bg.text(
        0.50,
        0.923,
        f"Астра • {chart['subject_name'][:28]}",
        color=INK_DARK,
        fontsize=14.0,
        style="italic",
        family="serif",
        ha="center",
        va="center",
    )
    ax_bg.text(
        0.50,
        0.896,
        f"Натальная карта — это точный астрономический срез неба в момент и месте рождения ({chart['dt_local_str']} • {chart['place_label'][:42]})",
        color=INK_MUTED,
        fontsize=8.9,
        ha="center",
        va="center",
    )

    # =========================================================================
    # 2. LEFT COLUMN CARDS: Birth Data & "THE BIG THREE" (Sun, Moon, Ascendant)
    # =========================================================================
    _draw_poster_box(ax_bg, 0.026, 0.645, 0.215, 0.228, "ИСХОДНЫЕ ДАННЫЕ")
    dt_parts = chart["dt_local_str"].split()
    d_only = dt_parts[0] if dt_parts else chart["dt_local_str"]
    t_only = " ".join(dt_parts[1:]) if len(dt_parts) > 1 else ""

    left_items = [
        ("calendar", "Дата рождения", d_only),
        ("clock", "Точное время", f"{t_only} (расчёт ASC и домов)"),
        ("pin", "Место и координаты", f"{chart['place_label'][:22]} ({chart['lat']:.1f}°N, {chart['lon']:.1f}°E)"),
        ("house", "Дома и секта", f"{chart['house_system']} • {chart['hellenistic_medieval']['sect'].split('(')[0].strip()}"),
    ]
    dy = 0.812
    for icon_k, lbl, val in left_items:
        _draw_line_icon(ax_bg, icon_k, 0.050, dy - 0.008, 0.026, 0.022)
        ax_bg.text(0.072, dy, lbl, color=INK_DARK, fontsize=8.3, fontweight="bold", va="top")
        ax_bg.text(0.072, dy - 0.015, val, color=INK_MUTED, fontsize=7.6, va="top")
        dy -= 0.039

    ax_bg.text(
        0.038,
        0.665,
        "Точное время рождения задаёт ваш Восходящий знак (ASC)\nи расклад сетки 12 астрологических домов.",
        color=INK_MUTED,
        fontsize=6.6,
        style="italic",
        va="top",
        linespacing=1.18,
    )

    # "THE BIG THREE" Card (Sun, Moon, Rising/ASC)
    _draw_poster_box(ax_bg, 0.026, 0.302, 0.215, 0.330, "БОЛЬШАЯ ТРОЙКА")
    planets_by_name = {p["name"]: p for p in chart["planets"]}
    sun_p = planets_by_name["Солнце"]
    moon_p = planets_by_name["Луна"]
    asc_info = chart["asc"]

    big_three = [
        ("☉", "#f7dfb2", "СОЛНЕЧНЫЙ ЗНАК", f"{sun_p['sign']} ({sun_p['deg']}°{sun_p['min']:02d}')", f"{sun_p['house_primary']} дом • Упр.: {sun_p['trad_dispositor']}/{sun_p['mod_dispositor']}", "Сознание, ядро личности и жизненная сила."),
        ("☽", "#dcd6eb", "ЛУННЫЙ ЗНАК", f"{moon_p['sign']} ({moon_p['deg']}°{moon_p['min']:02d}')", f"{moon_p['house_primary']} дом • Упр.: {moon_p['trad_dispositor']}/{moon_p['mod_dispositor']}", "Эмоции, внутренний мир и базовые потребности."),
        ("ASC", "#dfead8", "ВОСХОДЯЩИЙ (ASC)", f"{asc_info['sign']} ({asc_info['formatted'].split()[0]})", f"Упр. классич.: {asc_info['trad_ruler']} | модр.: {asc_info['mod_ruler']}", "Первое впечатление, стиль действия и старт."),
    ]
    by = 0.576
    for sym, badge_col, head_t, sign_t, sub_t, desc_t in big_three:
        circ = patches.Ellipse((0.058, by - 0.020), width=0.042, height=0.035, facecolor=badge_col, edgecolor=BORDER_TAN, linewidth=1.3, zorder=3)
        ax_bg.add_patch(circ)
        ax_bg.text(0.058, by - 0.020, sym, color=INK_DARK, fontsize=9.5, fontweight="bold", ha="center", va="center", zorder=4)

        ax_bg.text(0.086, by, head_t, color=GOLD_ACCENT, fontsize=8.0, fontweight="bold", va="top")
        ax_bg.text(0.086, by - 0.015, sign_t, color=INK_DARK, fontsize=8.8, fontweight="bold", va="top")
        ax_bg.text(0.086, by - 0.030, sub_t, color=INK_MUTED, fontsize=7.3, va="top")
        ax_bg.text(0.086, by - 0.044, desc_t, color=INK_MUTED, fontsize=7.0, style="italic", va="top")
        by -= 0.092

    # =========================================================================
    # 3. CENTER PANEL: Vintage Pastel Natal Wheel + "КАК ВСЁ РАБОТАЕТ ВМЕСТЕ"
    # =========================================================================
    ax_wheel = fig.add_axes([0.243, 0.460, 0.442, 0.420], aspect="equal", facecolor=BG_CREAM)
    ax_wheel.set_xlim(-1.22, 1.22)
    ax_wheel.set_ylim(-1.22, 1.22)
    ax_wheel.axis("off")

    asc_lon = float(chart["asc"]["lon"])
    r_outer = 1.04
    r_sign_in = 0.84
    r_house_in = 0.72
    r_planet = 0.57
    r_aspect = 0.44

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

    house_ring = patches.Wedge((0, 0), r_sign_in, 0, 360, width=r_sign_in - r_house_in, facecolor="#faf6ee", edgecolor=INK_DARK, linewidth=1.0, zorder=2)
    ax_wheel.add_patch(house_ring)
    planet_ring = patches.Wedge((0, 0), r_house_in, 0, 360, width=r_house_in - r_aspect, facecolor="#ffffff", edgecolor=INK_DARK, linewidth=0.9, zorder=2)
    ax_wheel.add_patch(planet_ring)
    center_circle = patches.Circle((0, 0), r_aspect, facecolor="#faf8f2", edgecolor=INK_DARK, linewidth=1.0, zorder=2)
    ax_wheel.add_patch(center_circle)

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
            alpha=0.82,
            zorder=3,
        )

    # Center-Bottom Card: "КАК ВСЁ РАБОТАЕТ ВМЕСТЕ" (matching "HOW IT ALL WORKS TOGETHER" with 4 medallions + bracket)
    _draw_poster_box(ax_bg, 0.254, 0.302, 0.422, 0.155, "КАК ВСЁ РАБОТАЕТ ВМЕСТЕ")
    hm = chart["hellenistic_medieval"]
    fos = chart["formula_of_soul"]

    ax_bg.text(
        0.465,
        0.415,
        f"Жребий Фортуны: {hm['lot_of_fortune']['formatted']} ({hm['lot_of_fortune']['house']} д.) • Профекция ({hm['annual_profection']['current_age']} л.): {hm['annual_profection']['profected_house']} дом ({hm['annual_profection']['lord_of_year_trad']})\n"
        f"Фирдар: {hm['firdaria']['major_firdar']}/{hm['firdaria']['sub_firdar']} • Центры ФД: {', '.join(fos['modern_centers_domicile'][:3]) or 'взаимная рецепция'}",
        color=INK_MUTED,
        fontsize=7.3,
        ha="center",
        va="top",
    )

    four_pills = [
        ("🪐", "ПЛАНЕТЫ", "Какая грань\nличности", "#dcd6eb", 0.305),
        (ZODIAC_GLYPHS[sun_p["sign_idx"]], "ЗНАКИ", "Как течёт\nэнергия", "#d8e5f2", 0.412),
        ("⌂", "ДОМА", "В какой сфере\nжизни", "#dfead8", 0.518),
        ("△", "АСПЕКТЫ", "Как всё\nсвязано", "#f7d9c4", 0.625),
    ]
    for idx_m, (g_sym, m_title, m_sub, m_col, mx) in enumerate(four_pills):
        my = 0.365
        c_med = patches.Ellipse((mx, my), width=0.044, height=0.036, facecolor=m_col, edgecolor=INK_DARK, linewidth=1.0, zorder=3)
        ax_bg.add_patch(c_med)
        ax_bg.text(mx, my, g_sym if idx_m > 0 else "☉", color=INK_DARK, fontsize=11, fontweight="bold", ha="center", va="center", zorder=4)
        ax_bg.text(mx, my - 0.023, m_title, color=INK_DARK, fontsize=7.4, fontweight="bold", family="serif", ha="center", va="top")
        ax_bg.text(mx, my - 0.035, m_sub, color=INK_MUTED, fontsize=6.4, ha="center", va="top")
        if idx_m < 3:
            ax_bg.text(mx + 0.053, my, "+", color=GOLD_ACCENT, fontsize=11, fontweight="bold", ha="center", va="center")

    # Curly bracket line pointing to star and motto
    ax_bg.plot([0.305, 0.305, 0.465, 0.625, 0.625], [0.320, 0.315, 0.315, 0.315, 0.320], color=BORDER_TAN, linewidth=1.0, zorder=3)
    _draw_sparkle(ax_bg, 0.465, 0.315, 0.005, 0.006, GOLD_ACCENT, z=4)
    ax_bg.text(0.465, 0.305, "ВЫ — уникальная история вашей карты и судьбы", color=INK_DARK, fontsize=7.8, fontweight="bold", family="serif", ha="center", va="bottom")

    # =========================================================================
    # 4. RIGHT COLUMN CARD: 5 Medallion Sections (matching "WHAT A BIRTH CHART INCLUDES")
    # =========================================================================
    _draw_poster_box(ax_bg, 0.690, 0.302, 0.284, 0.571, "ЧТО РАСКРЫВАЕТ ВАША КАРТА")

    # Prepare concise data for the 5 sections
    p_lines_1 = [f"{p['glyph']} {p['name'][:8]}: {p['formatted']} (Д.{p['house_primary']}/ПЗ:{p['house_wholesign']})" for p in chart["planets"][:5]]
    p_lines_2 = [f"{p['glyph']} {p['name'].split()[0][:8]}: {p['formatted']} (Д.{p['house_primary']}/ПЗ:{p['house_wholesign']})" for p in chart["planets"][5:10]]
    top_asps = [f"• {a['p1_glyph']} {a['p1'][:7]} {a['glyph']} {a['p2_glyph']} {a['p2'][:7]} — {a['aspect']} ({a['orb']}°)" for a in sorted(chart["aspects"], key=lambda x: x["orb"])[:4]]

    right_sections = [
        (
            "#9b8ec4",
            "♈♉",
            "1. СВЕТИЛА И ЛИЧНЫЕ ПЛАНЕТЫ",
            "\n".join(p_lines_1),
        ),
        (
            "#6b9ac4",
            "♃♄",
            "2. СОЦИАЛЬНЫЕ И ВЫСШИЕ ПЛАНЕТЫ",
            "\n".join(p_lines_2),
        ),
        (
            "#6ba38b",
            "12",
            "3. ДОМА (ПЛАЦИДУС vs ПОЛНОЗНАК)",
            f"I (ASC): {asc_info['formatted']} | X (MC): {chart['mc']['formatted']}\n"
            f"Узлы: Раху {planets_by_name['Сев. Узел (Раху)']['formatted']} (Д.{planets_by_name['Сев. Узел (Раху)']['house_primary']})\n"
            f"Лилит: {planets_by_name['Лилит (Чёрная Луна)']['formatted']} (Д.{planets_by_name['Лилит (Чёрная Луна)']['house_primary']})",
        ),
        (
            "#d98a8c",
            "△□",
            "4. ТОЧНЫЕ АСПЕКТЫ (ОРБИСЫ)",
            "\n".join(top_asps),
        ),
        (
            "#e6c88a",
            "ASC",
            "5. ВОСХОДЯЩИЙ ЗНАК И УПРАВИТЕЛИ",
            f"Асцендент в знаке {asc_info['sign']} ({asc_info['formatted'].split()[0]}).\n"
            f"Управитель по классике: {asc_info['trad_ruler']} | Модерн: {asc_info['mod_ruler']}.\n"
            f"Мидпойнт ☉/☽ (Гамбургская шк.): {chart['uranian']['sun_moon_midpoint']}",
        ),
    ]

    ry = 0.822
    for idx_s, (med_col, med_sym, sec_title, sec_body) in enumerate(right_sections):
        mc_x = 0.724
        mc_y = ry - 0.032
        outer_m = patches.Ellipse((mc_x, mc_y), width=0.048, height=0.040, facecolor=med_col, edgecolor=INK_DARK, linewidth=1.1, zorder=3)
        ax_bg.add_patch(outer_m)
        inner_m = patches.Ellipse((mc_x, mc_y), width=0.038, height=0.031, facecolor="none", edgecolor="#ffffff", linewidth=0.8, linestyle=":", zorder=4)
        ax_bg.add_patch(inner_m)
        ax_bg.text(mc_x, mc_y, med_sym, color="#ffffff" if idx_s < 4 else INK_DARK, fontsize=9.0, fontweight="bold", ha="center", va="center", zorder=5)

        ax_bg.text(0.756, ry, sec_title, color= SIGN_INK_COLORS[idx_s % 4], fontsize=7.9, fontweight="bold", family="serif", va="top")
        ax_bg.text(0.756, ry - 0.015, sec_body, color=INK_DARK, fontsize=7.0, va="top", linespacing=1.25)

        if idx_s < 4:
            ax_bg.plot([0.704, 0.960], [ry - 0.095, ry - 0.095], color=BORDER_TAN, linewidth=0.75, zorder=2)
        ry -= 0.105

    # =========================================================================
    # 5. BOTTOM FULL-WIDTH STRIP: "ПЛАНЕТЫ И ИХ ЗНАЧЕНИЯ" (10 Planets)
    # =========================================================================
    _draw_poster_box(ax_bg, 0.026, 0.122, 0.948, 0.166, "ПЛАНЕТЫ И ИХ ЗНАЧЕНИЯ В ВАШЕЙ КАРТЕ")

    ten_planets = chart["planets"][:10]
    for idx, p in enumerate(ten_planets):
        px = 0.075 + idx * 0.0945
        py_circ = 0.226
        p_col = PLANET_INK_COLORS.get(p["name"], INK_DARK)
        fill_c = PASTEL_ELEMENT_FILLS[p["sign_idx"] % 4]

        med = patches.Ellipse((px, py_circ), width=0.038, height=0.031, facecolor=fill_c, edgecolor=p_col, linewidth=1.3, zorder=3)
        ax_bg.add_patch(med)
        ax_bg.text(px, py_circ, p["glyph"], color=p_col, fontsize=13, fontweight="bold", ha="center", va="center", zorder=4)

        p_title, p_role = PLANET_ROLES_RU.get(p["name"], (p["name"].upper(), ""))
        ax_bg.text(px, 0.199, p_title, color=INK_DARK, fontsize=7.6, fontweight="bold", family="serif", ha="center", va="top")
        ax_bg.text(px, 0.183, f"{p['deg']}° {p['sign'][:6]}. ({p['house_primary']} д.)", color=p_col, fontsize=7.1, fontweight="bold", ha="center", va="top")
        ax_bg.text(px, 0.166, p_role, color=INK_MUTED, fontsize=6.5, ha="center", va="top", linespacing=1.18)

        if idx < 9:
            ax_bg.plot([px + 0.047, px + 0.047], [0.132, 0.245], color=BORDER_TAN, linewidth=0.75, zorder=2)

    # =========================================================================
    # 6. FOOTER: 2 Side Cards + Central Starry Night Medallion + Motto
    # =========================================================================
    _draw_poster_box(ax_bg, 0.026, 0.028, 0.375, 0.082, "ЧЕМ ПОЛЕЗНА НАТАЛЬНАЯ КАРТА")
    left_footer_cols = [
        (0.038, 0.076, "• Понимание своей природы и силы"),
        (0.038, 0.058, "• Осознание эмоциональных потребностей"),
        (0.038, 0.040, "• Гармония в любви и партнёрстве"),
        (0.215, 0.076, "• Поиск призвания и финансового роста"),
        (0.215, 0.058, "• Проживание кризисов и циклов"),
        (0.215, 0.040, "• Точный выбор времени для решений"),
    ]
    for fx, fy, ftxt in left_footer_cols:
        ax_bg.text(fx, fy, ftxt, color=INK_MUTED, fontsize=7.0, va="top")

    # Central Starry Cosmos Medallion (homage to reference bottom-center circle!)
    cosmos_cx, cosmos_cy = 0.50, 0.068
    cosmos_outer = patches.Ellipse((cosmos_cx, cosmos_cy), width=0.145, height=0.092, facecolor="#1f2847", edgecolor=GOLD_ACCENT, linewidth=1.8, zorder=4)
    ax_bg.add_patch(cosmos_outer)
    # Horizon glow & stars inside medallion
    glow = patches.Ellipse((cosmos_cx, cosmos_cy - 0.018), width=0.125, height=0.042, facecolor="#3b4d7a", edgecolor="none", alpha=0.6, zorder=4.2)
    ax_bg.add_patch(glow)
    # Constellation lines & glowing orbs
    const_pts = [(0.455, 0.082), (0.478, 0.095), (0.505, 0.088), (0.532, 0.096), (0.548, 0.078)]
    ax_bg.plot([p[0] for p in const_pts], [p[1] for p in const_pts], color="#e8be74", linewidth=0.7, alpha=0.8, zorder=4.5)
    for spx, spy in const_pts:
        orb = patches.Ellipse((spx, spy), width=0.006, height=0.005, facecolor="#f7dfb2", edgecolor="none", zorder=5)
        ax_bg.add_patch(orb)
    _draw_sparkle(ax_bg, 0.485, 0.074, 0.004, 0.005, "#f7dfb2", z=5)
    _draw_sparkle(ax_bg, 0.522, 0.072, 0.004, 0.005, "#f7dfb2", z=5)
    # Silhouette of stargazer at bottom of circle
    head_s = patches.Ellipse((cosmos_cx, cosmos_cy - 0.016), width=0.018, height=0.015, facecolor="#0f1324", edgecolor="none", zorder=5)
    ax_bg.add_patch(head_s)
    shoulders = patches.Wedge((cosmos_cx, cosmos_cy - 0.044), 0.028, 25, 155, facecolor="#0f1324", edgecolor="none", zorder=5)
    ax_bg.add_patch(shoulders)

    _draw_poster_box(ax_bg, 0.599, 0.028, 0.375, 0.082, "ГЛАВНЫЙ СИНТЕЗ ШКОЛ")
    ax_bg.text(
        0.612,
        0.076,
        f"Классическая школа ({asc_info['trad_ruler']}) показывает внешние события и структуру судьбы,\n"
        f"а современная школа ({asc_info['mod_ruler']}) — глубинные мотивы души.\n"
        f"Вы — больше, чем просто Солнечный знак: вся карта рассказывает вашу историю.",
        color=INK_MUTED,
        fontsize=7.0,
        va="top",
        linespacing=1.25,
    )

    # Bottom motto
    _draw_sparkle(ax_bg, 0.31, 0.016, 0.004, 0.005, GOLD_ACCENT, z=4)
    _draw_sparkle(ax_bg, 0.69, 0.016, 0.004, 0.005, GOLD_ACCENT, z=4)
    ax_bg.text(
        0.50,
        0.016,
        "Звёзды не принуждают вас — они раскрывают вашу природу",
        color=INK_DARK,
        fontsize=8.5,
        style="italic",
        family="serif",
        ha="center",
        va="center",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=BG_CREAM)
    plt.close(fig)
    return output_path
