"""
High-Resolution Numerological Chart & Matrix Renderer for MATRIX ("Матрица").
Produces a crisp 3-panel PNG image ready to be sent as a Telegram photo:
1. Top-Left: Classical Pythagorean Square (3×3 Psychomatrix) with cells, row/column/diagonal totals.
2. Bottom-Left: 22-Arcana Matrix of Destiny Octagram (Personal & Ancestral squares, Central Comfort Zone,
   Karmic Tail, Money Channel, and Relationship Channel).
3. Right Panel: Full Comparative Multi-School Table (Western Pythagorean & Chaldean, Vedic Sankhya Shastra,
   Matrix of Destiny Destinies, Financial Code, and Predictive Cycles).
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


CELL_LABELS = {
    1: "1 • Характер / Воля",
    2: "2 • Энергия / Биополе",
    3: "3 • Интерес / Наука",
    4: "4 • Здоровье / Тело",
    5: "5 • Логика / Интуиция",
    6: "6 • Труд / Мастерство",
    7: "7 • Удача / Ангел",
    8: "8 • Долг / Правда",
    9: "9 • Память / Ум",
}


def draw_octagram_node(ax, x: float, y: float, val: int, r: float, fill: str, edge: str, label: str = "") -> None:
    c = patches.Circle((x, y), radius=r, facecolor=fill, edgecolor=edge, linewidth=1.8, zorder=6)
    ax.add_patch(c)
    ax.text(x, y, str(val), color="#f0f6fc", fontsize=9.5, fontweight="bold", ha="center", va="center", zorder=7)
    if label:
        ax.text(x, y - r - 0.045, label, color="#8b949e", fontsize=6.8, ha="center", va="top", zorder=7)


def render_numerology_image(data: Dict, output_path: Path) -> Path:
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial Unicode MS", "Helvetica", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    fig = plt.figure(figsize=(15.5, 10.2), dpi=160, facecolor="#0b0e14")
    gs = fig.add_gridspec(2, 2, width_ratios=[1.15, 1.15], height_ratios=[0.95, 1.15], wspace=0.06, hspace=0.14)

    # =========================================================================
    # PANEL 1 (Top-Left): Classical Pythagorean Square (3x3 Psychomatrix)
    # =========================================================================
    ax_sq = fig.add_subplot(gs[0, 0])
    ax_sq.set_facecolor("#0f131c")
    ax_sq.set_xlim(0.0, 1.0)
    ax_sq.set_ylim(0.0, 1.0)
    ax_sq.axis("off")

    pm = data["psychomatrix"]
    ax_sq.text(
        0.02,
        0.96,
        f"КВАДРАТ ПИФАГОРА (ПСИХОМАТРИЦА) • Доп. числа: {pm['w1']}.{pm['w2']}  {pm['w3']}.{pm['w4']}",
        color="#58a6ff",
        fontsize=9.8,
        fontweight="bold",
        va="top",
    )

    # 3x3 grid coordinates: columns (1-2-3, 4-5-6, 7-8-9), rows top-to-bottom
    grid_layout = [
        (1, 0, 0), (4, 1, 0), (7, 2, 0),
        (2, 0, 1), (5, 1, 1), (8, 2, 1),
        (3, 0, 2), (6, 1, 2), (9, 2, 2),
    ]
    cw, ch = 0.23, 0.22
    gx0, gy0 = 0.03, 0.66

    for cell_num, col_idx, row_idx in grid_layout:
        x = gx0 + col_idx * (cw + 0.015)
        y = gy0 - row_idx * (ch + 0.020)
        val_str = pm["cells"][cell_num]
        has_digits = val_str != "—"
        edge_col = "#3bc9db" if has_digits else "#30363d"
        fill_col = "#16202c" if has_digits else "#11161f"

        rect = patches.FancyBboxPatch(
            (x, y),
            cw,
            ch,
            boxstyle="round,pad=0.008,rounding_size=0.018",
            facecolor=fill_col,
            edgecolor=edge_col,
            linewidth=1.4,
            zorder=2,
        )
        ax_sq.add_patch(rect)
        ax_sq.text(
            x + cw / 2.0,
            y + ch * 0.74,
            CELL_LABELS[cell_num],
            color="#8b949e",
            fontsize=7.2,
            ha="center",
            va="center",
            zorder=3,
        )
        ax_sq.text(
            x + cw / 2.0,
            y + ch * 0.34,
            val_str,
            color="#ffd43b" if has_digits else "#484f58",
            fontsize=13.5,
            fontweight="bold",
            ha="center",
            va="center",
            zorder=4,
        )

    # Right column of grid: Row totals & Diagonals
    rx = gx0 + 3 * (cw + 0.015) + 0.01
    row_items = [
        (f"Темп.: {pm['diagonals']['temperament_up']}", gy0 + ch * 0.85, "#f783ac"),
        (f"Цель: {pm['rows']['purpose_row1']}", gy0 + ch * 0.42, "#c9d1d9"),
        (f"Семья: {pm['rows']['family_row2']}", gy0 - (ch + 0.020) + ch * 0.50, "#c9d1d9"),
        (f"Быт/Ст.: {pm['rows']['stability_row3']}", gy0 - 2 * (ch + 0.020) + ch * 0.50, "#c9d1d9"),
        (f"Дух.: {pm['diagonals']['spirituality_down']}", gy0 - 2 * (ch + 0.020) + ch * 0.05, "#da77f2"),
    ]
    for r_txt, ry, r_col in row_items:
        ax_sq.text(
            rx,
            ry,
            r_txt,
            color=r_col,
            fontsize=8.0,
            fontweight="bold",
            va="center",
            bbox=dict(boxstyle="round,pad=0.22", facecolor="#161b22", edgecolor="#30363d", lw=0.8),
        )

    # Bottom row of grid: Column totals
    col_items = [
        (f"Самооценка: {pm['cols']['self_esteem_col1']}", gx0 + cw * 0.5),
        (f"Финансы: {pm['cols']['finance_col2']}", gx0 + (cw + 0.015) + cw * 0.5),
        (f"Талант: {pm['cols']['talent_col3']}", gx0 + 2 * (cw + 0.015) + cw * 0.5),
    ]
    for c_txt, cx in col_items:
        ax_sq.text(
            cx,
            0.08,
            c_txt,
            color="#51cf66",
            fontsize=8.0,
            fontweight="bold",
            ha="center",
            va="center",
        )

    # =========================================================================
    # PANEL 2 (Bottom-Left): Matrix of Destiny Octagram (22 Energies)
    # =========================================================================
    ax_oct = fig.add_subplot(gs[1, 0], aspect="equal")
    ax_oct.set_facecolor("#0b0e14")
    ax_oct.set_xlim(-1.18, 1.18)
    ax_oct.set_ylim(-1.18, 1.18)
    ax_oct.axis("off")

    dm = data["destiny_matrix_22"]
    ax_oct.text(
        0.0,
        1.14,
        "МАТРИЦА СУДЬБЫ (22 АРКАНА • ОКТАГРАММА)",
        color="#f0883e",
        fontsize=10.0,
        fontweight="bold",
        ha="center",
        va="top",
    )

    R = 0.86
    s = R * math.cos(math.pi / 4.0)

    # Personal Square (Diamond: Left, Top, Right, Bottom)
    diamond_pts = [(-R, 0), (0, R), (R, 0), (0, -R), (-R, 0)]
    ax_oct.plot([p[0] for p in diamond_pts], [p[1] for p in diamond_pts], color="#da77f2", linewidth=1.8, zorder=2)

    # Ancestral Square (Direct Square: Top-Left, Top-Right, Bottom-Right, Bottom-Left)
    square_pts = [(-s, s), (s, s), (s, -s), (-s, -s), (-s, s)]
    ax_oct.plot([p[0] for p in square_pts], [p[1] for p in square_pts], color="#4dabf7", linewidth=1.5, linestyle="--", zorder=2)

    # Sky-Earth & Ancestral axes
    ax_oct.plot([-R, R], [0, 0], color="#484f58", linewidth=1.2, zorder=1)
    ax_oct.plot([0, 0], [-R, R], color="#484f58", linewidth=1.2, zorder=1)
    ax_oct.plot([-s, s], [s, -s], color="#30363d", linewidth=0.9, zorder=1)
    ax_oct.plot([-s, s], [-s, s], color="#30363d", linewidth=0.9, zorder=1)

    # Money & Love line between (0, -0.46) and (0.46, 0)
    ax_oct.plot([0, 0.46], [-0.46, 0], color="#51cf66", linewidth=1.6, zorder=3)

    # Draw Main Personal Corners
    draw_octagram_node(ax_oct, -R, 0.0, dm["A_left_portrait"], 0.115, "#2b193d", "#da77f2", "Визитка")
    draw_octagram_node(ax_oct, 0.0, R, dm["B_top_spirit"], 0.115, "#2b193d", "#da77f2", "Ангел")
    draw_octagram_node(ax_oct, R, 0.0, dm["C_right_finance_karma"], 0.115, "#2b1216", "#ff6b6b", "Деньги/Тело")
    draw_octagram_node(ax_oct, 0.0, -R, dm["D_bottom_past_karma"], 0.115, "#2b1216", "#ff6b6b", "Карма")

    # Draw Ancestral Corners
    draw_octagram_node(ax_oct, -s, s, dm["E_father_spirit"], 0.095, "#112136", "#4dabf7", "Род отца (Д)")
    draw_octagram_node(ax_oct, s, s, dm["F_mother_spirit"], 0.095, "#112136", "#4dabf7", "Род мат. (Д)")
    draw_octagram_node(ax_oct, s, -s, dm["G_father_matter"], 0.095, "#112136", "#4dabf7", "Род отца (М)")
    draw_octagram_node(ax_oct, -s, -s, dm["H_mother_matter"], 0.095, "#112136", "#4dabf7", "Род мат. (М)")

    # Center Comfort Zone
    draw_octagram_node(ax_oct, 0.0, 0.0, dm["center_comfort_zone"], 0.135, "#3b2f0b", "#ffd43b", "Центр")

    # Karmic Tail & Money/Love Inner Nodes
    k_mid, k_inner, _ = dm["karmic_tail_tuple"]
    c_mid, money_prof, money_entry = dm["money_nodes"]
    draw_octagram_node(ax_oct, 0.0, -0.46, k_mid, 0.075, "#1f1626", "#f783ac")
    draw_octagram_node(ax_oct, 0.0, -0.66, k_inner, 0.070, "#1f1626", "#f783ac")
    draw_octagram_node(ax_oct, 0.46, 0.0, c_mid, 0.075, "#12291a", "#51cf66")
    draw_octagram_node(ax_oct, 0.23, -0.23, money_entry, 0.075, "#12291a", "#51cf66", "$/❤")

    # =========================================================================
    # PANEL 3 (Right Side, full height): Multi-Tradition Summary Table
    # =========================================================================
    ax_info = fig.add_subplot(gs[:, 1])
    ax_info.set_facecolor("#0b0e14")
    ax_info.axis("off")

    w = data["western"]
    v = data["vedic"]
    nm = data["name_numerology"]
    fc = data["forecast"]

    title_str = f"МАТРИЦА • {data['subject_label'].upper()} ({data['date_str']})"
    ax_info.text(0.0, 0.98, title_str[:54], color="#ffd43b", fontsize=13.0, fontweight="bold", va="top")
    if data["full_name"]:
        ax_info.text(0.0, 0.95, f"Имя / ФИО: {data['full_name']}", color="#8b949e", fontsize=9.0, va="top")

    y = 0.915
    ax_info.text(0.0, y, "1. ЗАПАДНАЯ ПИФАГОРЕЙСКАЯ И ХАЛДЕЙСКАЯ НУМЕРОЛОГИЯ", color="#58a6ff", fontsize=9.5, fontweight="bold", va="top")
    y -= 0.028

    west_rows = [
        f"• Число Жизненного Пути (ЧЖП): {w['life_path']}   |   Мастер-число: {w['master_number'] or '—'}   |   Кармический долг: {w['karmic_debt'] or '—'}",
        f"• Личный Финансовый Код Изобилия: {w['financial_code']}   |   Число Дня Рождения: {w['birthday_number']}",
    ]
    if nm.get("has_name"):
        west_rows.append(
            f"• Пифагорейский код имени: Экспрессия = {nm['pythagorean']['expression']} | Душа (гласные) = {nm['pythagorean']['soul_urge']} | Личность = {nm['pythagorean']['personality']}"
        )
        west_rows.append(
            f"• Халдейский код имени (альт. школа): Составное число = {nm['chaldean']['compound_number']} → {nm['chaldean']['expression']} (Душа: {nm['chaldean']['soul_urge']})"
        )

    for r in west_rows:
        ax_info.text(0.0, y, r, color="#e6edf3", fontsize=8.2, va="top")
        y -= 0.025

    y -= 0.012
    ax_info.text(0.0, y, "2. МАТРИЦА СУДЬБЫ (22 ЭНЕРГИИ / Н. ЛАДИНИ И ДЖУЛИЯ ПО)", color="#f0883e", fontsize=9.5, fontweight="bold", va="top")
    y -= 0.028

    m22_rows = [
        f"• Центр (Зона комфорта): {ARCANA_22_NAMES[dm['center_comfort_zone']]}",
        f"• Визитка (Портрет): {ARCANA_22_NAMES[dm['A_left_portrait']]}",
        f"• Высшая духовная связь: {ARCANA_22_NAMES[dm['B_top_spirit']]}",
        f"• Кармический хвост (из прошлых воплощений): {dm['karmic_tail']}",
        f"• Денежный канал (вход–профессия–блок): {dm['money_channel']}   |   Канал отношений: {dm['love_channel']}",
        f"• Личное предназначение (до 40 лет): {dm['personal_destiny_20_40']} (Небо {dm['sky']} + Земля {dm['earth']})",
        f"• Социальное предназначение (40–60 лет): {dm['social_destiny_40_60']} (Муж. род {dm['male_lineage']} + Жен. род {dm['female_lineage']})",
        f"• Духовное предназначение (60+ и общий синтез): {dm['spiritual_destiny_60plus']}   |   Сила Рода: {dm['ancestral_power']}",
    ]
    for r in m22_rows:
        ax_info.text(0.0, y, r, color="#c9d1d9", fontsize=8.1, va="top")
        y -= 0.024

    y -= 0.012
    ax_info.text(0.0, y, "3. ВЕДИЧЕСКАЯ НУМЕРОЛОГИЯ (САНКХЬЯ-ШАСТРА)", color="#da77f2", fontsize=9.5, fontweight="bold", va="top")
    y -= 0.028

    ved_rows = [
        f"• Число Души (Муланк / Джива): {v['soul_number']} — Планета: {v['soul_planet']}",
        f"  Качества: {v['soul_traits']}",
        f"• Число Дхармы/Судьбы (Бхагьянк): {v['destiny_number']} — Планета: {v['destiny_planet']}",
        f"  Качества: {v['destiny_traits']}",
    ]
    for r in ved_rows:
        ax_info.text(0.0, y, r, color="#c9d1d9", fontsize=8.1, va="top")
        y -= 0.024

    y -= 0.012
    ax_info.text(0.0, y, "4. ПРОГНОСТИКА, ПИКИ ЖИЗНИ И КАРМИЧЕСКИЕ ВЫЗОВЫ", color="#51cf66", fontsize=9.5, fontweight="bold", va="top")
    y -= 0.028

    pins_str = " | ".join(f"{lbl}: {val}" for lbl, val in fc["pinnacles"])
    chals_str = ", ".join(str(x) for x in fc["challenges"])
    prog_rows = [
        f"• Персональный Год ({fc['current_year']}): {fc['personal_year']}   |   Персональный Месяц: {fc['personal_month']}   |   Персональный День: {fc['personal_day']}",
        f"• 4 Жизненных Пика: {pins_str}",
        f"• 4 Кармических Вызова (уроки преодоления): {chals_str}",
    ]
    if data.get("compatibility"):
        comp = data["compatibility"]
        prog_rows.append(
            f"• Совместимость с {comp['partner_date_str']}: Центр пары = {comp['combined_center_22']}, Духовный союз = {comp['combined_sky_22']}, Финансы пары = {comp['combined_finance_22']}"
        )

    for r in prog_rows:
        ax_info.text(0.0, y, r, color="#c9d1d9", fontsize=8.0, va="top")
        y -= 0.024

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160, bbox_inches="tight", facecolor="#0b0e14")
    plt.close(fig)
    return output_path
