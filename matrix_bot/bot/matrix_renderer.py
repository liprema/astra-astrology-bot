"""
High-Resolution Vintage Cream Infographic Numerology & Matrix Renderer for MATRIX ("Матрикс"):
Modeled in the exact same Vintage Cream Poster aesthetic (#faf6ee) as Astra's Birth Chart & Arcana's Spread:
1. Header: Celestial Sun (with face) on left, Serif Title "НУМЕРОЛОГИЧЕСКАЯ МАТРИЦА", Crescent Moon on right.
2. Top-Left Card: Classical Pythagorean Square (3x3 Psychomatrix) in warm vintage cream/gold/sage cells.
3. Bottom-Left Card: 22-Arcana Matrix of Destiny Octagram with pastel chakra medallions & sacred geometry lines.
4. Right Card: 4 Medallion Sections (1. Западная и Халдейская школы, 2. Матрица Судьбы 22 энергии,
   3. Ведическая Санкхья-шастра, 4. Прогностика, Пики и Вызовы).
5. Bottom Full-Width Strip: "9 БАЗОВЫХ ЭНЕРГИЙ И ПЛАНЕТ-УПРАВИТЕЛЕЙ В ВАШЕЙ КАРТЕ" (9 medallions in a row).
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Dict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

from bot.numerology_engine import ARCANA_22_NAMES


BG_CREAM = "#faf6ee"
CARD_CREAM = "#f5efe2"
BORDER_TAN = "#cbbba0"
INK_DARK = "#232533"
INK_MUTED = "#5a534a"
GOLD_ACCENT = "#b58338"

CELL_LABELS = {
    1: "1 • Характер / Воля",
    2: "2 • Энергия / Душа",
    3: "3 • Интерес / Наука",
    4: "4 • Здоровье / Тело",
    5: "5 • Логика / Интуиция",
    6: "6 • Труд / Мастерство",
    7: "7 • Удача / Ангел",
    8: "8 • Долг / Правда",
    9: "9 • Память / Ум",
}

NINE_NUMBERS_STRIP = [
    (1, "☉ Солнце", "ХАРАКТЕР", "Воля • Лидерство\nСамостоятельность", "#f7dfb2"),
    (2, "☽ Луна", "ЭНЕРГИЯ", "Дипломатия • Связь\nЭмоции • Биополе", "#dcd6eb"),
    (3, "♃ Юпитер", "ИНТЕРЕС", "Знания • Творчество\nОптимизм • Наука", "#f9eec8"),
    (4, "☊ Раху", "ЗДОРОВЬЕ", "Тело • Устойчивость\nПорядок • Опора", "#dfead8"),
    (5, "☿ Меркурий", "ЛОГИКА", "Интуиция • Анализ\nГибкость • Планы", "#d8e5f2"),
    (6, "♀ Венера", "МАСТЕРСТВО", "Труд • Красота\nФинансы • Уют", "#f7d9c4"),
    (7, "☋ Кету", "УДАЧА", "Талант • Духовность\nВезение • Мудрость", "#dcd6eb"),
    (8, "♄ Сатурн", "ДОЛГ", "Ответственность\nПравда • Карма", "#d8e5f2"),
    (9, "♂ Марс", "ПАМЯТЬ", "Ясновидение • Ум\nМасштаб • Цель", "#f7d9c4"),
]


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


def _draw_poster_box(ax, x: float, y: float, w: float, h: float, title: str = "") -> None:
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
        half_s = min(w * 0.44, len(title) * 0.0046 + 0.025)
        _draw_sparkle(ax, x + w / 2.0 - half_s, y + h - 0.021, 0.0045, 0.0055, GOLD_ACCENT, z=4)
        _draw_sparkle(ax, x + w / 2.0 + half_s, y + h - 0.021, 0.0045, 0.0055, GOLD_ACCENT, z=4)
        ax.plot([x + 0.016, x + w - 0.016], [y + h - 0.034, y + h - 0.034], color=BORDER_TAN, linewidth=0.9, zorder=2)


def _draw_celestial_sun(ax, cx: float, cy: float, r_x: float, r_y: float) -> None:
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
    disc = patches.Ellipse((cx, cy), width=r_x * 1.9, height=r_y * 1.9, facecolor="#f7dfb2", edgecolor="#8c6223", linewidth=1.35, zorder=4)
    ax.add_patch(disc)
    for side in (-1, 1):
        ex = cx + side * r_x * 0.34
        ey = cy + r_y * 0.16
        ax.add_patch(patches.Ellipse((ex, ey), width=r_x * 0.22, height=r_y * 0.14, facecolor="#6e4b16", edgecolor="none", zorder=5))
    smile = patches.Arc((cx, cy - r_y * 0.22), r_x * 0.42, r_y * 0.22, angle=0, theta1=200, theta2=340, color="#6e4b16", linewidth=1.1, zorder=5)
    ax.add_patch(smile)


def _draw_celestial_moon(ax, cx: float, cy: float, r_x: float, r_y: float) -> None:
    outer = patches.Ellipse((cx, cy), width=r_x * 2.1, height=r_y * 2.1, facecolor="#8c82b0", edgecolor="#3f375c", linewidth=1.35, zorder=3)
    ax.add_patch(outer)
    cutout = patches.Ellipse((cx - r_x * 0.56, cy + r_y * 0.14), width=r_x * 1.75, height=r_y * 1.85, facecolor=BG_CREAM, edgecolor="none", zorder=4)
    ax.add_patch(cutout)


def draw_octagram_node(ax, x: float, y: float, val: int, r: float, fill: str, edge: str, label: str = "") -> None:
    c = patches.Circle((x, y), radius=r, facecolor=fill, edgecolor=edge, linewidth=1.6, zorder=6)
    ax.add_patch(c)
    ax.text(x, y, str(val), color=INK_DARK, fontsize=9.5, fontweight="bold", family="serif", ha="center", va="center", zorder=7)
    if label:
        ax.text(x, y - r - 0.048, label, color=INK_MUTED, fontsize=6.9, fontweight="bold", ha="center", va="top", zorder=7)


def render_numerology_image(data: Dict, output_path: Path) -> Path:
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial Unicode MS", "Helvetica", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    fig = plt.figure(figsize=(15.5, 16.5), dpi=150, facecolor=BG_CREAM)

    ax_bg = fig.add_axes([0.0, 0.0, 1.0, 1.0], facecolor=BG_CREAM)
    ax_bg.set_xlim(0.0, 1.0)
    ax_bg.set_ylim(0.0, 1.0)
    ax_bg.axis("off")

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
    # 1. TOP VINTAGE HEADER (Celestial Sun, Title, Crescent Moon)
    # =========================================================================
    _draw_celestial_sun(ax_bg, 0.085, 0.935, 0.028, 0.026)
    _draw_celestial_moon(ax_bg, 0.915, 0.935, 0.028, 0.026)

    ax_bg.text(
        0.50,
        0.955,
        "НУМЕРОЛОГИЧЕСКАЯ МАТРИЦА",
        color=INK_DARK,
        fontsize=24,
        fontweight="bold",
        family="serif",
        ha="center",
        va="center",
    )
    _draw_sparkle(ax_bg, 0.30, 0.922, 0.005, 0.006, GOLD_ACCENT, z=4)
    _draw_sparkle(ax_bg, 0.70, 0.922, 0.005, 0.006, GOLD_ACCENT, z=4)
    ax_bg.text(
        0.50,
        0.922,
        f"Матрикс • {data['subject_label'][:28]} ({data['date_str']})",
        color=GOLD_ACCENT,
        fontsize=13.5,
        style="italic",
        family="serif",
        ha="center",
        va="center",
    )
    pm = data["psychomatrix"]
    w = data["western"]
    ax_bg.text(
        0.50,
        0.896,
        f"Квадрат Пифагора • Матрица Судьбы (22 аркана) • Западная, Халдейская и Ведическая школы • Доп. числа: {pm['w1']}.{pm['w2']} | {pm['w3']}.{pm['w4']}",
        color=INK_MUTED,
        fontsize=8.8,
        ha="center",
        va="center",
    )

    # =========================================================================
    # 2. TOP-LEFT CARD: Classical Pythagorean Square (3x3 Psychomatrix)
    # =========================================================================
    _draw_poster_box(ax_bg, 0.026, 0.565, 0.455, 0.310, "КВАДРАТ ПИФАГОРА (ПСИХОМАТРИЦА)")

    grid_layout = [
        (1, 0, 0), (4, 1, 0), (7, 2, 0),
        (2, 0, 1), (5, 1, 1), (8, 2, 1),
        (3, 0, 2), (6, 1, 2), (9, 2, 2),
    ]
    cw, ch = 0.102, 0.068
    gx0, gy0 = 0.042, 0.760

    for cell_num, col_idx, row_idx in grid_layout:
        x = gx0 + col_idx * (cw + 0.008)
        y = gy0 - row_idx * (ch + 0.008)
        val_str = pm["cells"][cell_num]
        has_digits = val_str != "—"
        fill_col = "#faf6ee" if has_digits else "#f0eadc"
        edge_col = GOLD_ACCENT if has_digits else BORDER_TAN

        rect = patches.FancyBboxPatch(
            (x, y),
            cw,
            ch,
            boxstyle="round,pad=0.003,rounding_size=0.008",
            facecolor=fill_col,
            edgecolor=edge_col,
            linewidth=1.35 if has_digits else 0.9,
            zorder=2,
        )
        ax_bg.add_patch(rect)
        ax_bg.text(
            x + cw / 2.0,
            y + ch * 0.75,
            CELL_LABELS[cell_num],
            color=INK_MUTED,
            fontsize=7.0,
            fontweight="bold",
            ha="center",
            va="center",
            zorder=3,
        )
        ax_bg.text(
            x + cw / 2.0,
            y + ch * 0.33,
            val_str,
            color="#9c6418" if has_digits else "#a89f91",
            fontsize=13.0,
            fontweight="bold",
            family="serif",
            ha="center",
            va="center",
            zorder=4,
        )

    # Right column of grid: Row totals & Diagonals
    rx = gx0 + 3 * (cw + 0.008) + 0.008
    row_items = [
        (f"Темперамент: {pm['diagonals']['temperament_up']}", gy0 + ch * 0.85, "#f7d9c4"),
        (f"Цель (1 стр.): {pm['rows']['purpose_row1']}", gy0 + ch * 0.42, "#f7dfb2"),
        (f"Семья (2 стр.): {pm['rows']['family_row2']}", gy0 - (ch + 0.008) + ch * 0.50, "#dfead8"),
        (f"Быт/Стаб.: {pm['rows']['stability_row3']}", gy0 - 2 * (ch + 0.008) + ch * 0.50, "#d8e5f2"),
        (f"Духовность: {pm['diagonals']['spirituality_down']}", gy0 - 2 * (ch + 0.008) + ch * 0.05, "#dcd6eb"),
    ]
    for r_txt, ry, r_fill in row_items:
        ax_bg.text(
            rx,
            ry,
            r_txt,
            color=INK_DARK,
            fontsize=7.4,
            fontweight="bold",
            va="center",
            bbox=dict(boxstyle="round,pad=0.22", facecolor=r_fill, edgecolor=BORDER_TAN, lw=0.9),
        )

    # Bottom row of grid: Column totals
    col_items = [
        (f"Самооценка: {pm['cols']['self_esteem_col1']}", gx0 + cw * 0.5),
        (f"Финансы: {pm['cols']['finance_col2']}", gx0 + (cw + 0.008) + cw * 0.5),
        (f"Талант: {pm['cols']['talent_col3']}", gx0 + 2 * (cw + 0.008) + cw * 0.5),
    ]
    for c_txt, cx in col_items:
        ax_bg.text(
            cx,
            0.582,
            c_txt,
            color="#3b6e4c",
            fontsize=7.8,
            fontweight="bold",
            family="serif",
            ha="center",
            va="center",
        )

    # =========================================================================
    # 3. BOTTOM-LEFT CARD: Matrix of Destiny Octagram (22 Energies)
    # =========================================================================
    _draw_poster_box(ax_bg, 0.026, 0.205, 0.455, 0.345, "МАТРИЦА СУДЬБЫ (22 АРКАНА • ОКТАГРАММА)")

    ax_oct = fig.add_axes([0.075, 0.212, 0.355, 0.295], aspect="equal", facecolor=CARD_CREAM)
    ax_oct.set_xlim(-1.18, 1.18)
    ax_oct.set_ylim(-1.18, 1.18)
    ax_oct.axis("off")

    dm = data["destiny_matrix_22"]
    R = 0.85
    s = R * math.cos(math.pi / 4.0)

    # Personal Square (Diamond)
    diamond_pts = [(-R, 0), (0, R), (R, 0), (0, -R), (-R, 0)]
    ax_oct.plot([p[0] for p in diamond_pts], [p[1] for p in diamond_pts], color="#7a5999", linewidth=1.8, zorder=2)

    # Ancestral Square (Direct Square)
    square_pts = [(-s, s), (s, s), (s, -s), (-s, -s), (-s, s)]
    ax_oct.plot([p[0] for p in square_pts], [p[1] for p in square_pts], color="#4a7c9b", linewidth=1.5, linestyle="--", zorder=2)

    # Axes
    ax_oct.plot([-R, R], [0, 0], color=BORDER_TAN, linewidth=1.2, zorder=1)
    ax_oct.plot([0, 0], [-R, R], color=BORDER_TAN, linewidth=1.2, zorder=1)
    ax_oct.plot([-s, s], [s, -s], color=BORDER_TAN, linewidth=0.9, zorder=1)
    ax_oct.plot([-s, s], [-s, s], color=BORDER_TAN, linewidth=0.9, zorder=1)

    # Money & Love line
    ax_oct.plot([0, 0.46], [-0.46, 0], color="#3b6e4c", linewidth=1.6, zorder=3)

    # Personal Corners
    draw_octagram_node(ax_oct, -R, 0.0, dm["A_left_portrait"], 0.12, "#dcd6eb", "#5c527f", "Визитка")
    draw_octagram_node(ax_oct, 0.0, R, dm["B_top_spirit"], 0.12, "#dcd6eb", "#5c527f", "Ангел")
    draw_octagram_node(ax_oct, R, 0.0, dm["C_right_finance_karma"], 0.12, "#f7d9c4", "#b84a39", "Деньги/Тело")
    draw_octagram_node(ax_oct, 0.0, -R, dm["D_bottom_past_karma"], 0.12, "#f7d9c4", "#b84a39", "Карма")

    # Ancestral Corners
    draw_octagram_node(ax_oct, -s, s, dm["E_father_spirit"], 0.10, "#d8e5f2", "#385a8c", "Род отца (Д)")
    draw_octagram_node(ax_oct, s, s, dm["F_mother_spirit"], 0.10, "#d8e5f2", "#385a8c", "Род мат. (Д)")
    draw_octagram_node(ax_oct, s, -s, dm["G_father_matter"], 0.10, "#d8e5f2", "#385a8c", "Род отца (М)")
    draw_octagram_node(ax_oct, -s, -s, dm["H_mother_matter"], 0.10, "#d8e5f2", "#385a8c", "Род мат. (М)")

    # Center Comfort Zone
    draw_octagram_node(ax_oct, 0.0, 0.0, dm["center_comfort_zone"], 0.14, "#f7dfb2", "#9c6418", "Центр")

    # Karmic Tail & Money/Love Inner Nodes
    k_mid, k_inner, _ = dm["karmic_tail_tuple"]
    c_mid, _, money_entry = dm["money_nodes"]
    draw_octagram_node(ax_oct, 0.0, -0.46, k_mid, 0.08, "#f7d9c4", "#b84b6b")
    draw_octagram_node(ax_oct, 0.0, -0.66, k_inner, 0.075, "#f7d9c4", "#b84b6b")
    draw_octagram_node(ax_oct, 0.46, 0.0, c_mid, 0.08, "#dfead8", "#3b6e4c")
    draw_octagram_node(ax_oct, 0.23, -0.23, money_entry, 0.08, "#dfead8", "#3b6e4c", "$/❤")

    # =========================================================================
    # 4. RIGHT COLUMN CARD: 4 Medallion Sections Across All Numerology Schools
    # =========================================================================
    _draw_poster_box(ax_bg, 0.495, 0.205, 0.479, 0.670, "ПОЛНЫЙ СИНТЕЗ ШКОЛ НУМЕРОЛОГИИ")

    v = data["vedic"]
    nm = data["name_numerology"]
    fc = data["forecast"]

    name_block = (
        f"Код имени «{nm['clean_name']}»: Пифагор (Экспрессия {nm['pythagorean']['expression']}, Душа {nm['pythagorean']['soul_urge']}) | "
        f"Халдейская шк.: {nm['chaldean']['compound_number']} → {nm['chaldean']['expression']}"
        if nm.get("has_name")
        else "Код имени: укажите ФИО для сравнения Пифагорейской и Халдейской вибраций"
    )

    pins_str = " | ".join(f"{lbl}: {val}" for lbl, val in fc["pinnacles"])
    chals_str = ", ".join(str(x) for x in fc["challenges"])
    comp_line = (
        f"Совместимость с {data['compatibility']['partner_date_str']}: Центр пары = {data['compatibility']['combined_center_22']}, Союз = {data['compatibility']['combined_sky_22']}"
        if data.get("compatibility")
        else f"Сравнение расчёта 2000+: по Александрову (-2) = {pm['w3_classic_minus2']}.{pm['w4_classic_minus2']} | современная шк. (+19) = {pm['w3_modern_plus19']}.{pm['w4_modern_plus19']}"
    )

    sections = [
        (
            "#9b8ec4",
            f"ЧЖП\n{w['life_path']}",
            "1. ЗАПАДНАЯ ПИФАГОРЕЙСКАЯ И ХАЛДЕЙСКАЯ ШКОЛЫ",
            f"• Число Жизненного Пути (ЧЖП): {w['life_path']}  |  Мастер-число: {w['master_number'] or '—'}  |  Кармический долг: {w['karmic_debt'] or '—'}\n"
            f"• Личный Финансовый Код Изобилия: {w['financial_code']}  |  Число Дня Рождения: {w['birthday_number']}\n"
            f"• {name_block}\n"
            f"• {comp_line}",
        ),
        (
            "#e6c88a",
            f"XXII\n[{dm['center_comfort_zone']}]",
            "2. МАТРИЦА СУДЬБЫ (22 ЭНЕРГИИ • Н. ЛАДИНИ И ДЖУЛИЯ ПО)",
            f"• Центр (Зона комфорта души): {ARCANA_22_NAMES[dm['center_comfort_zone']]}\n"
            f"• Визитка (Портрет личности): {ARCANA_22_NAMES[dm['A_left_portrait']]}\n"
            f"• Высшая духовная связь (Ангел-хранитель): {ARCANA_22_NAMES[dm['B_top_spirit']]}\n"
            f"• Кармический хвост: {dm['karmic_tail']}  |  Денежный канал: {dm['money_channel']}  |  Канал любви: {dm['love_channel']}\n"
            f"• Предназначения: Личное (до 40 л.) = {dm['personal_destiny_20_40']} | Социальное (40–60 л.) = {dm['social_destiny_40_60']} | Духовное = {dm['spiritual_destiny_60plus']}",
        ),
        (
            "#d98a8c",
            f"{v['soul_number']}/{v['destiny_number']}",
            "3. ВЕДИЧЕСКАЯ НУМЕРОЛОГИЯ (САНКХЬЯ-ШАСТРА И ДЖЙОТИШ)",
            f"• Число Души (Муланк / Джива): {v['soul_number']} — Планета-управитель: {v['soul_planet']}\n"
            f"  Качества характера: {v['soul_traits']}\n"
            f"• Число Дхармы и Судьбы (Бхагьянк): {v['destiny_number']} — Планета-управитель: {v['destiny_planet']}\n"
            f"  Задачи реализации (после 35–40 лет): {v['destiny_traits']}",
        ),
        (
            "#6ba38b",
            f"ГОД\n{fc['personal_year']}",
            "4. ПРОГНОСТИКА, ЖИЗНЕННЫЕ ПИКИ И КАРМИЧЕСКИЕ ВЫЗОВЫ",
            f"• Персональный Год ({fc['current_year']}): {fc['personal_year']}  |  Персональный Месяц: {fc['personal_month']}  |  Персональный День: {fc['personal_day']}\n"
            f"• 4 Жизненных Пика: {pins_str}\n"
            f"• 4 Кармических Вызова (уроки преодоления): {chals_str}",
        ),
    ]

    ry = 0.818
    for idx_s, (m_col, m_sym, s_title, s_body) in enumerate(sections):
        mc_x = 0.534
        mc_y = ry - 0.042
        med = patches.Ellipse((mc_x, mc_y), width=0.052, height=0.048, facecolor=m_col, edgecolor=INK_DARK, linewidth=1.15, zorder=3)
        ax_bg.add_patch(med)
        ax_bg.text(mc_x, mc_y, m_sym, color=INK_DARK if idx_s == 1 else "#ffffff", fontsize=8.5, fontweight="bold", family="serif", ha="center", va="center", zorder=4)

        ax_bg.text(0.570, ry, s_title, color=GOLD_ACCENT, fontsize=8.4, fontweight="bold", family="serif", va="top")
        ax_bg.text(0.570, ry - 0.018, s_body, color=INK_DARK, fontsize=7.5, va="top", linespacing=1.32)

        if idx_s < 3:
            ax_bg.plot([0.510, 0.958], [ry - 0.138, ry - 0.138], color=BORDER_TAN, linewidth=0.8, zorder=2)
        ry -= 0.152

    # =========================================================================
    # 5. BOTTOM FULL-WIDTH STRIP: "9 БАЗОВЫХ ЭНЕРГИЙ И ПЛАНЕТ В ВАШЕЙ МАТРИЦЕ"
    # =========================================================================
    _draw_poster_box(ax_bg, 0.026, 0.025, 0.948, 0.165, "9 БАЗОВЫХ ЧИСЕЛ, ИХ ПЛАНЕТЫ-УПРАВИТЕЛИ И ЗНАЧЕНИЯ В ВАШЕЙ КАРТЕ")

    for idx, (digit, planet_lbl, title_lbl, desc_lbl, fill_c) in enumerate(NINE_NUMBERS_STRIP):
        px = 0.078 + idx * 0.1055
        py_circ = 0.128
        cell_val = pm["cells"][digit]
        has_d = cell_val != "—"

        med = patches.Ellipse((px, py_circ), width=0.042, height=0.035, facecolor=fill_c, edgecolor=GOLD_ACCENT if has_d else BORDER_TAN, linewidth=1.4 if has_d else 1.0, zorder=3)
        ax_bg.add_patch(med)
        ax_bg.text(px, py_circ, str(digit), color=INK_DARK, fontsize=12.5, fontweight="bold", family="serif", ha="center", va="center", zorder=4)

        ax_bg.text(px, 0.100, f"{title_lbl} ({cell_val})", color=INK_DARK if has_d else INK_MUTED, fontsize=7.5, fontweight="bold", family="serif", ha="center", va="top")
        ax_bg.text(px, 0.083, planet_lbl, color=GOLD_ACCENT, fontsize=7.1, fontweight="bold", ha="center", va="top")
        ax_bg.text(px, 0.064, desc_lbl, color=INK_MUTED, fontsize=6.5, ha="center", va="top", linespacing=1.18)

        if idx < 8:
            ax_bg.plot([px + 0.0527, px + 0.0527], [0.036, 0.148], color=BORDER_TAN, linewidth=0.75, zorder=2)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=BG_CREAM)
    plt.close(fig)
    return output_path
