"""
Multi-Tradition Numerology Calculation Engine for MATRIX ("Матрица"):
Calculates with 100% mathematical precision across all major numerology schools:
1. Classical Psychomatrix (Pythagorean Square / А. Ф. Александров + Идеал Н. Сидоровой):
   - 4 Working Numbers (with both the classical `-2` rule and the post-2000 `+19` rule so differences are explicitly shown!)
   - 3×3 Grid (1..9 cells), Rows (Purpose, Family, Stability), Columns (Self-esteem, Finance, Talent), Diagonals (Temperament, Spirituality)
2. Matrix of Destiny (Матрица Судьбы — 22 Energies / Н. Ладини + Джулия По):
   - Personal Square (Corners A, B, C, D) + Ancestral/Diagonal Square (E, F, G, H)
   - Central Comfort Zone Energy (Center = reduce_22(A+B+C+D))
   - Karmic Tail (3 energies at bottom)
   - Money Channel (Entry, Profession, Block/Anchor) & Love/Relationship Channel
   - Destinies: Personal (Sky + Earth, up to 40 yrs), Social (Male + Female lineage, 40–60 yrs), Spiritual (General synthesis)
3. Western Pythagorean & Chaldean Numerology:
   - Life Path Number (ЧЖП) with Master Numbers (11, 22, 33) and Karmic Debt Numbers (13/4, 14/5, 16/7, 19/1)
   - Expression/Destiny Number (by full name), Soul Urge (by vowels), Personality (by consonants) — in both Pythagorean & Chaldean tables!
   - Financial Code of Abundance (4-digit personal wealth code)
4. Vedic Numerology (Sankhya Shastra):
   - Psychic / Soul Number (Chislo Dushi / Mulank — Day of birth 1..9 & its ruling Graha/Planet)
   - Destiny / Dharma Number (Bhagyank — Full date sum 1..9 & its ruling Graha/Planet)
5. Predictive & Karmic Numerology (Pinnacles, Challenges, Personal Year / Month / Day) & Chinese Lo Shu Elements.
"""
from __future__ import annotations

import datetime
import re
from typing import Dict, List, Optional, Tuple

ARCANA_22_NAMES = {
    1: "1 — Маг (Чудотворец, Инициатива)",
    2: "2 — Верховная Жрица (Интуиция, Гармония, Тайна)",
    3: "3 — Императрица (Плодородие, Изобилие, Хозяйка)",
    4: "4 — Император (Власть, Структура, Ответственность)",
    5: "5 — Иерофант (Учитель, Традиция, Закон и Семья)",
    6: "6 — Влюблённые (Любовь, Выбор, Отношения, Красота)",
    7: "7 — Колесница (Победитель, Движение к цели, Лидер)",
    8: "8 — Справедливость (Кармический баланс, Закон причины и следствия)",
    9: "9 — Отшельник (Мудрец, Глубина, Самодостаточность)",
    10: "10 — Колесо Фортуны (Поток, Удача, Цикличность)",
    11: "11 — Сила (Потенциал, Трудолюбие, Энергетическая мощь)",
    12: "12 — Повешенный (Служение, Иное видение, Творчество, Благотворительность)",
    13: "13 — Смерть (Трансформация, Обновление, Смелость перемен)",
    14: "14 — Умеренность (Зрелая Душа, Искусство, Исцеление, Баланс)",
    15: "15 — Дьявол (Проявление, Искушение, Харизма, Большие деньги и тень)",
    16: "16 — Башня (Духовное пробуждение, Созидание нового, Реконструкция)",
    17: "17 — Звезда (Талант, Яркость, Небожитель, Признание)",
    18: "18 — Луна (Магия подсознания, Воображение, Материализация мысли)",
    19: "19 — Солнце (Процветание, Щедрость, Общественный масштаб, Радость)",
    20: "20 — Суд (Связь с Родом, Яснознание, Пробуждение системы)",
    21: "21 — Мир (Глобальность, Миротворец, Выход за рамки и границы)",
    22: "22 — Шут (Высшая духовная свобода, Обнуление, Творческий полёт)",
}

VEDIC_PLANETS = {
    1: ("Солнце (Сурья)", "Лидерство, воля, независимость, авторитет"),
    2: ("Луна (Чандра)", "Дипломатия, чувствительность, эмпатия, адаптивность"),
    3: ("Юпитер (Гуру)", "Мудрость, наставничество, оптимизм, расширение, закон"),
    4: ("Раху (Сев. Узел)", "Реформаторство, нестандартность, бунт, материальный прорыв"),
    5: ("Меркурий (Будха)", "Интеллект, бизнес, коммуникация, скорость, торговля"),
    6: ("Венера (Шукра)", "Любовь, искусство, комфорт, магнетизм, изобилие"),
    7: ("Кету (Южн. Узел)", "Интуиция, мистика, аналитика, духовный поиск, отстранённость"),
    8: ("Сатурн (Шани)", "Карма, дисциплина, масштабный труд, справедливость, выдержка"),
    9: ("Марс (Мангала)", "Энергия, смелость, защита, действие, преодоление преград"),
}

# Russian & Latin letter tables for Western Pythagorean vs Chaldean Name Numerology
PYTHAGOREAN_RU = {
    "а": 1, "и": 1, "с": 1, "ъ": 1,
    "б": 2, "й": 2, "т": 2, "ы": 2,
    "в": 3, "к": 3, "у": 3, "ь": 3,
    "г": 4, "л": 4, "ф": 4, "э": 4,
    "д": 5, "м": 5, "х": 5, "ю": 5,
    "е": 6, "н": 6, "ц": 6, "я": 6,
    "ё": 7, "о": 7, "ч": 7,
    "ж": 8, "п": 8, "ш": 8,
    "з": 9, "р": 9, "щ": 9,
}

PYTHAGOREAN_EN = {
    "a": 1, "j": 1, "s": 1,
    "b": 2, "k": 2, "t": 2,
    "c": 3, "l": 3, "u": 3,
    "d": 4, "m": 4, "v": 4,
    "e": 5, "n": 5, "w": 5,
    "f": 6, "o": 6, "x": 6,
    "g": 7, "p": 7, "y": 7,
    "h": 8, "q": 8, "z": 8,
    "i": 9, "r": 9,
}

# Chaldean vibration system (numbers 1..8, 9 is sacred)
CHALDEAN_MAP = {
    "a": 1, "i": 1, "j": 1, "q": 1, "y": 1, "а": 1, "и": 1, "й": 1, "я": 1,
    "b": 2, "k": 2, "r": 2, "б": 2, "к": 2, "р": 2,
    "c": 3, "g": 3, "l": 3, "s": 3, "г": 3, "л": 3, "с": 3, "ц": 3, "ч": 3, "ш": 3, "щ": 3,
    "d": 4, "m": 4, "t": 4, "д": 4, "м": 4, "т": 4,
    "e": 5, "h": 5, "n": 5, "x": 5, "е": 5, "ё": 5, "н": 5, "х": 5, "э": 5,
    "u": 6, "v": 6, "w": 6, "в": 6, "у": 6, "ю": 6,
    "o": 7, "z": 7, "з": 7, "о": 7, "ж": 7,
    "f": 8, "p": 8, "п": 8, "ф": 8, "ъ": 8, "ы": 8, "ь": 8,
}

VOWELS = set("аеёиоуыэюяaeiouy")


def sum_digits(n: int) -> int:
    return sum(int(d) for d in str(abs(n)))


def reduce_to_single_or_master(n: int) -> Tuple[int, Optional[int], Optional[int]]:
    """
    Reduce number to 1..9 while preserving Master Numbers (11, 22, 33)
    and detecting Karmic Debt intermediate numbers (13, 14, 16, 19).
    Returns (base_single_1_to_9, master_number_if_any, karmic_debt_if_any).
    """
    karmic = n if n in (13, 14, 16, 19) else None
    master = n if n in (11, 22, 33) else None

    curr = n
    while curr > 9:
        if curr in (13, 14, 16, 19) and karmic is None:
            karmic = curr
        if curr in (11, 22, 33) and master is None:
            master = curr
        curr = sum_digits(curr)
    return curr, master, karmic


def reduce_22(n: int) -> int:
    """Reduce any positive integer to the 1..22 Major Arcana range (Matrix of Destiny rule)."""
    n = abs(int(n))
    if n == 0:
        return 22
    while n > 22:
        n = sum_digits(n)
    return n if n > 0 else 22


def compute_pythagorean_square(day: int, month: int, year: int) -> Dict:
    """
    Compute Classical Psychomatrix (Квадрат Пифагора / А. Ф. Александров)
    plus the alternative post-2000 calculation (`+19` vs `-2`) and Ideal School comparison.
    """
    date_digits_str = f"{day}{month}{year}"
    w1 = sum(int(d) for d in date_digits_str)
    w2 = sum_digits(w1)

    # First non-zero digit of day
    first_day_digit = int(str(day)[0]) if day >= 10 else day

    # Classical Aleksandrov rule: subtract 2 * first_day_digit
    w3_classic = abs(w1 - 2 * first_day_digit)
    w4_classic = sum_digits(w3_classic)

    # Post-2000 modern school rule: add 19 for 2000+ births
    w3_modern2000 = w1 + 19
    w4_modern2000 = sum_digits(w3_modern2000)

    # Use classical for <2000, and for >=2000 provide both!
    primary_w3 = w3_modern2000 if year >= 2000 else w3_classic
    primary_w4 = w4_modern2000 if year >= 2000 else w4_classic

    all_digits_str = f"{day}{month}{year}{w1}{w2}{primary_w3}{primary_w4}"
    if year >= 2000:
        all_digits_str += "19"

    cells: Dict[int, str] = {}
    counts: Dict[int, int] = {}
    for digit in range(1, 10):
        cnt = all_digits_str.count(str(digit))
        counts[digit] = cnt
        cells[digit] = (str(digit) * cnt) if cnt > 0 else "—"

    # Also compute classical -2 counts if year >= 2000 for school comparison
    alt_str_classic = f"{day}{month}{year}{w1}{w2}{w3_classic}{w4_classic}"
    alt_cells_classic = {
        d: (str(d) * alt_str_classic.count(str(d)) or "—") for d in range(1, 10)
    }

    rows = {
        "purpose_row1": counts[1] + counts[4] + counts[7],     # Целеустремлённость (1-4-7)
        "family_row2": counts[2] + counts[5] + counts[8],      # Семья (2-5-8)
        "stability_row3": counts[3] + counts[6] + counts[9],   # Стабильность / Привычки (3-6-9)
    }
    cols = {
        "self_esteem_col1": counts[1] + counts[2] + counts[3], # Самооценка (1-2-3)
        "finance_col2": counts[4] + counts[5] + counts[6],     # Быт / Финансы (4-5-6)
        "talent_col3": counts[7] + counts[8] + counts[9],      # Талант (7-8-9)
    }
    diagonals = {
        "temperament_up": counts[3] + counts[5] + counts[7],   # Темперамент / Плотская диагональ (3-5-7)
        "spirituality_down": counts[1] + counts[5] + counts[9],# Духовность (1-5-9)
    }

    return {
        "w1": w1,
        "w2": w2,
        "w3": primary_w3,
        "w4": primary_w4,
        "w3_classic_minus2": w3_classic,
        "w4_classic_minus2": w4_classic,
        "w3_modern_plus19": w3_modern2000,
        "w4_modern_plus19": w4_modern2000,
        "cells": cells,
        "counts": counts,
        "alt_cells_classic": alt_cells_classic,
        "rows": rows,
        "cols": cols,
        "diagonals": diagonals,
    }


def compute_destiny_matrix_22(day: int, month: int, year: int) -> Dict:
    """
    Calculate the 22-Arcana Matrix of Destiny (Матрица Судьбы — Наталия Ладини / Джулия По).
    """
    # Four main corners of Personal Square (Diagonal Square):
    # A (Left — Portrait / Visit Card): Day reduced to 22
    # B (Top — Guardian Angel / Spiritual Connection): Month (1..12)
    # C (Right — Material Karma & Health / Financial threshold): Year reduced to 22
    # D (Bottom — Past Life Karma point): reduce_22(A + B + C)
    A = reduce_22(day)
    B = reduce_22(month)
    C = reduce_22(sum_digits(year))
    D = reduce_22(A + B + C)

    # Central Comfort Zone (Core of the Matrix):
    center = reduce_22(A + B + C + D)

    # Four corners of the Ancestral Square (Direct Square — Родовой квадрат):
    # E (Top-Left — Father's Spiritual Lineage): reduce_22(A + B)
    # F (Top-Right — Mother's Spiritual Lineage): reduce_22(B + C)
    # G (Bottom-Right — Father's Material Lineage): reduce_22(C + D)
    # H (Bottom-Left — Mother's Material Lineage): reduce_22(D + A)
    E = reduce_22(A + B)
    F = reduce_22(B + C)
    G = reduce_22(C + D)
    H = reduce_22(D + A)

    # Ancestral power node:
    ancestral_sum = reduce_22(E + F + G + H)

    # Karmic Tail (Кармический хвост — 3 нижние энергии):
    k_mid = reduce_22(center + D)
    k_inner = reduce_22(k_mid + D)
    karmic_tail = f"{k_mid}–{k_inner}–{D}"

    # Money & Relationship Channels (между правой точкой C и нижней D):
    c_mid = reduce_22(center + C)
    money_entry = reduce_22(k_mid + c_mid)
    money_prof = reduce_22(money_entry + c_mid)
    love_entry = reduce_22(k_mid + money_entry)
    money_channel = f"{c_mid}–{money_prof}–{money_entry}"
    love_channel = f"{D}–{k_mid}–{love_entry}"

    # Three Destinies (Предназначения):
    sky = reduce_22(B + D)
    earth = reduce_22(A + C)
    personal_destiny = reduce_22(sky + earth)  # До 40 лет (Личное предназначение)

    male_line = reduce_22(E + G)
    female_line = reduce_22(F + H)
    social_destiny = reduce_22(male_line + female_line)  # 40–60 лет (Социальное предназначение)

    spiritual_destiny = reduce_22(personal_destiny + social_destiny)  # Общее духовное предназначение

    return {
        "A_left_portrait": A,
        "B_top_spirit": B,
        "C_right_finance_karma": C,
        "D_bottom_past_karma": D,
        "center_comfort_zone": center,
        "E_father_spirit": E,
        "F_mother_spirit": F,
        "G_father_matter": G,
        "H_mother_matter": H,
        "ancestral_power": ancestral_sum,
        "karmic_tail": karmic_tail,
        "karmic_tail_tuple": (k_mid, k_inner, D),
        "money_channel": money_channel,
        "money_nodes": (c_mid, money_prof, money_entry),
        "love_channel": love_channel,
        "love_nodes": (D, k_mid, love_entry),
        "sky": sky,
        "earth": earth,
        "personal_destiny_20_40": personal_destiny,
        "male_lineage": male_line,
        "female_lineage": female_line,
        "social_destiny_40_60": social_destiny,
        "spiritual_destiny_60plus": spiritual_destiny,
    }


def compute_name_numbers(full_name: str) -> Dict:
    """
    Calculate Expression (Судьба/Имя), Soul Urge (Душевное побуждение по гласным),
    and Personality (Личность по согласным) in BOTH Western Pythagorean and Chaldean systems!
    """
    letters = [ch.lower() for ch in full_name if ch.isalpha()]
    if not letters:
        return {
            "has_name": False,
            "pythagorean": {"expression": None, "soul_urge": None, "personality": None},
            "chaldean": {"expression": None, "soul_urge": None, "personality": None},
        }

    pyth_all, pyth_vow, pyth_con = 0, 0, 0
    chald_all, chald_vow, chald_con = 0, 0, 0

    for ch in letters:
        pv = PYTHAGOREAN_RU.get(ch) or PYTHAGOREAN_EN.get(ch, 0)
        cv = CHALDEAN_MAP.get(ch, 0)
        pyth_all += pv
        chald_all += cv
        if ch in VOWELS:
            pyth_vow += pv
            chald_vow += cv
        else:
            pyth_con += pv
            chald_con += cv

    p_exp, p_exp_m, p_exp_k = reduce_to_single_or_master(pyth_all)
    p_soul, p_soul_m, _ = reduce_to_single_or_master(pyth_vow)
    p_pers, p_pers_m, _ = reduce_to_single_or_master(pyth_con)

    c_exp, c_exp_m, c_exp_k = reduce_to_single_or_master(chald_all)
    c_soul, _, _ = reduce_to_single_or_master(chald_vow)
    c_pers, _, _ = reduce_to_single_or_master(chald_con)

    return {
        "has_name": True,
        "clean_name": full_name.strip(),
        "pythagorean": {
            "raw_sum": pyth_all,
            "expression": f"{p_exp_m}/{p_exp}" if p_exp_m else str(p_exp),
            "soul_urge": f"{p_soul_m}/{p_soul}" if p_soul_m else str(p_soul),
            "personality": f"{p_pers_m}/{p_pers}" if p_pers_m else str(p_pers),
            "karmic_debt": p_exp_k,
        },
        "chaldean": {
            "compound_number": chald_all,
            "expression": str(c_exp),
            "soul_urge": str(c_soul),
            "personality": str(c_pers),
            "karmic_debt": c_exp_k,
        },
    }


def calculate_full_numerology(
    day: int,
    month: int,
    year: int,
    full_name: str = "",
    subject_label: str = "Разбор Матрицы",
    partner_date: Optional[Tuple[int, int, int]] = None,
) -> Dict:
    """
    Calculate the complete multi-tradition numerological profile.
    """
    # 1. Western Life Path (ЧЖП) — two methods (Direct sum vs Period reduction Day+Month+Year)
    raw_all_sum = sum_digits(day) + sum_digits(month) + sum_digits(year)
    lp_base, lp_master, lp_karmic = reduce_to_single_or_master(raw_all_sum)

    d_red, d_m, d_k = reduce_to_single_or_master(day)
    m_red, m_m, _ = reduce_to_single_or_master(month)
    y_red, y_m, _ = reduce_to_single_or_master(sum_digits(year))
    period_sum = (d_m or d_red) + (m_m or m_red) + (y_m or y_red)
    _, lp_master_period, lp_karmic_period = reduce_to_single_or_master(period_sum)

    final_master = lp_master or lp_master_period
    final_karmic = lp_karmic or lp_karmic_period or (day if day in (13, 14, 16, 19) else None)
    lp_formatted = f"{final_master}/{lp_base}" if final_master else str(lp_base)

    # Financial Code (4 digits: Day reduced, Month reduced, Year reduced, Sum reduced)
    fin_d1 = reduce_to_single_or_master(day)[0]
    fin_d2 = reduce_to_single_or_master(month)[0]
    fin_d3 = reduce_to_single_or_master(year)[0]
    fin_d4 = reduce_to_single_or_master(fin_d1 + fin_d2 + fin_d3)[0]
    financial_code = f"{fin_d1}{fin_d2}{fin_d3}{fin_d4}"

    # 2. Vedic Numerology (Sankhya Shastra)
    vedic_soul = d_red  # Число Души (Джива / Муланк)
    vedic_destiny = lp_base  # Число Судьбы / Дхармы (Бхагьянк)
    soul_planet, soul_desc = VEDIC_PLANETS[vedic_soul]
    dest_planet, dest_desc = VEDIC_PLANETS[vedic_destiny]

    # 3. Classical Psychomatrix (Pythagorean Square)
    psychomatrix = compute_pythagorean_square(day, month, year)

    # 4. Matrix of Destiny (22 Arcana)
    destiny_22 = compute_destiny_matrix_22(day, month, year)

    # 5. Name Numerology (Pythagorean vs Chaldean)
    name_data = compute_name_numbers(full_name)

    # 6. Predictive Cycles (Personal Year, Month, Day, 4 Pinnacles & 4 Challenges)
    now = datetime.date.today()
    py_base, py_m, _ = reduce_to_single_or_master(d_red + m_red + reduce_to_single_or_master(now.year)[0])
    pm_base, _, _ = reduce_to_single_or_master(py_base + reduce_to_single_or_master(now.month)[0])
    pd_base, _, _ = reduce_to_single_or_master(pm_base + reduce_to_single_or_master(now.day)[0])

    # 4 Life Pinnacles (Пики жизни) & 4 Challenges (Вызовы)
    pin1 = reduce_to_single_or_master(d_red + m_red)[0]
    pin2 = reduce_to_single_or_master(d_red + y_red)[0]
    pin3 = reduce_to_single_or_master(pin1 + pin2)[0]
    pin4 = reduce_to_single_or_master(m_red + y_red)[0]
    first_pin_end_age = 36 - lp_base

    chal1 = abs(d_red - m_red)
    chal2 = abs(d_red - y_red)
    chal3 = abs(chal1 - chal2)
    chal4 = abs(m_red - y_red)

    # Partner compatibility if partner_date is provided
    compatibility = None
    if partner_date:
        pd, pm, py = partner_date
        p_m22 = compute_destiny_matrix_22(pd, pm, py)
        p_lp = reduce_to_single_or_master(sum_digits(pd) + sum_digits(pm) + sum_digits(py))[0]
        compatibility = {
            "partner_date_str": f"{pd:02d}.{pm:02d}.{py:04d}",
            "partner_lp": p_lp,
            "combined_lp": reduce_to_single_or_master(lp_base + p_lp)[0],
            "combined_center_22": reduce_22(destiny_22["center_comfort_zone"] + p_m22["center_comfort_zone"]),
            "combined_sky_22": reduce_22(destiny_22["B_top_spirit"] + p_m22["B_top_spirit"]),
            "combined_finance_22": reduce_22(destiny_22["C_right_finance_karma"] + p_m22["C_right_finance_karma"]),
        }

    return {
        "subject_label": subject_label,
        "full_name": full_name.strip(),
        "date_str": f"{day:02d}.{month:02d}.{year:04d}",
        "day": day,
        "month": month,
        "year": year,
        "western": {
            "life_path": lp_formatted,
            "life_path_base": lp_base,
            "master_number": final_master,
            "karmic_debt": final_karmic,
            "birthday_number": day,
            "financial_code": financial_code,
        },
        "vedic": {
            "soul_number": vedic_soul,
            "soul_planet": soul_planet,
            "soul_traits": soul_desc,
            "destiny_number": vedic_destiny,
            "destiny_planet": dest_planet,
            "destiny_traits": dest_desc,
        },
        "psychomatrix": psychomatrix,
        "destiny_matrix_22": destiny_22,
        "name_numerology": name_data,
        "forecast": {
            "current_year": now.year,
            "personal_year": f"{py_m}/{py_base}" if py_m else str(py_base),
            "personal_month": pm_base,
            "personal_day": pd_base,
            "pinnacles": [
                (f"0–{first_pin_end_age} лет", pin1),
                (f"{first_pin_end_age + 1}–{first_pin_end_age + 9} лет", pin2),
                (f"{first_pin_end_age + 10}–{first_pin_end_age + 18} лет", pin3),
                (f"После {first_pin_end_age + 19} лет", pin4),
            ],
            "challenges": [chal1, chal2, chal3, chal4],
        },
        "compatibility": compatibility,
    }


def format_numerology_for_llm(data: Dict) -> str:
    """Format full multi-tradition numerological profile into structured text for LLM synthesis."""
    w = data["western"]
    v = data["vedic"]
    pm = data["psychomatrix"]
    dm = data["destiny_matrix_22"]
    nm = data["name_numerology"]
    fc = data["forecast"]

    lines = [
        f"=== ПОЛНЫЙ НУМЕРОЛОГИЧЕСКИЙ РАСЧЁТ: {data['subject_label']} ({data['date_str']}) ===",
        f"Имя / ФИО: {data['full_name'] or 'не указано (расчёт по дате рождения)'}",
        "",
        "--- 1. КЛАССИЧЕСКИЙ ПСИХОМАТРИКС (КВАДРАТ ПИФАГОРА / ШКОЛА А. Ф. АЛЕКСАНДРОВА vs Н. СИДОРОВОЙ) ---",
        f"• Доп. рабочие числа: 1-е = {pm['w1']}, 2-е = {pm['w2']}, 3-е = {pm['w3']}, 4-е = {pm['w4']} "
        f"(Сравнение школ для 2000+ годов: по правилу -2: {pm['w3_classic_minus2']}/{pm['w4_classic_minus2']}; по правилу +19: {pm['w3_modern_plus19']}/{pm['w4_modern_plus19']})",
        f"• Ячейки матрицы: [1 Характер: {pm['cells'][1]}] | [4 Здоровье: {pm['cells'][4]}] | [7 Удача: {pm['cells'][7]}]",
        f"                  [2 Энергия:  {pm['cells'][2]}] | [5 Логика:   {pm['cells'][5]}] | [8 Долг:  {pm['cells'][8]}]",
        f"                  [3 Интерес:  {pm['cells'][3]}] | [6 Труд:     {pm['cells'][6]}] | [9 Память:{pm['cells'][9]}]",
        f"• Строки: Целеустремлённость (1-4-7) = {pm['rows']['purpose_row1']}, Семья (2-5-8) = {pm['rows']['family_row2']}, Стабильность (3-6-9) = {pm['rows']['stability_row3']}",
        f"• Столбцы: Самооценка (1-2-3) = {pm['cols']['self_esteem_col1']}, Быт/Финансы (4-5-6) = {pm['cols']['finance_col2']}, Талант (7-8-9) = {pm['cols']['talent_col3']}",
        f"• Диагонали: Темперамент (3-5-7) = {pm['diagonals']['temperament_up']}, Духовность (1-5-9) = {pm['diagonals']['spirituality_down']}",
        "",
        "--- 2. МАТРИЦА СУДЬБЫ (МЕТОД 22 ЭНЕРГИЙ Н. ЛАДИНИ / КАРМИЧЕСКАЯ НУМЕРОЛОГИЯ ДЖУЛИИ ПО) ---",
        f"• Личный квадрат: Визитка (левый угол) = {ARCANA_22_NAMES[dm['A_left_portrait']]} | Высшая связь (верх) = {ARCANA_22_NAMES[dm['B_top_spirit']]}",
        f"• Финансово-здоровенный узел (правый угол) = {ARCANA_22_NAMES[dm['C_right_finance_karma']]} | Кармическая точка (низ) = {ARCANA_22_NAMES[dm['D_bottom_past_karma']]}",
        f"• ЦЕНТР МАТРИЦЫ (Зона комфорта Души): {ARCANA_22_NAMES[dm['center_comfort_zone']]}",
        f"• КАРМИЧЕСКИЙ ХВОСТ (3 нижние энергии): {dm['karmic_tail']}",
        f"• ДЕНЕЖНЫЙ КАНАЛ (вход, профессия, блок): {dm['money_channel']}",
        f"• КАНАЛ ОТНОШЕНИЙ (партнёрство и баланс): {dm['love_channel']}",
        f"• Родовой квадрат: Род отца ({dm['E_father_spirit']} и {dm['G_father_matter']}), Род матери ({dm['F_mother_spirit']} и {dm['H_mother_matter']}), Сила Рода = {dm['ancestral_power']}",
        f"• 3 Предназначения: Личное (до 40 лет) = {dm['personal_destiny_20_40']} (Небо {dm['sky']} + Земля {dm['earth']}), Социальное (40–60 лет) = {dm['social_destiny_40_60']}, Духовное общее = {dm['spiritual_destiny_60plus']}",
        "",
        "--- 3. ЗАПАДНАЯ ПИФАГОРЕЙСКАЯ И ХАЛДЕЙСКАЯ НУМЕРОЛОГИЯ ---",
        f"• Число Жизненного Пути (ЧЖП): {w['life_path']} | Управляющее Мастер-число: {w['master_number'] or 'нет'} | Кармический долг: {w['karmic_debt'] or 'нет'}",
        f"• Личный Финансовый Код Изобилия: {w['financial_code']}",
    ]
    if nm.get("has_name"):
        lines.append(
            f"• Имя «{nm['clean_name']}» [Западная Пифагорейская школа]: Число Имени (Экспрессии) = {nm['pythagorean']['expression']} (сумма {nm['pythagorean']['raw_sum']}), "
            f"Душевное Побуждение (гласные) = {nm['pythagorean']['soul_urge']}, Личность (согласные) = {nm['pythagorean']['personality']}"
        )
        lines.append(
            f"• Альтернативное мнение [Древняя Халдейская школа вибраций]: составное число имени = {nm['chaldean']['compound_number']} → {nm['chaldean']['expression']}, "
            f"гласные = {nm['chaldean']['soul_urge']}, согласные = {nm['chaldean']['personality']}"
        )

    lines.extend([
        "",
        "--- 4. ВЕДИЧЕСКАЯ НУМЕРОЛОГИЯ (САНКХЬЯ-ШАСТРА) ---",
        f"• Число Души (Муланк / Джива): {v['soul_number']} — Планета-управитель: {v['soul_planet']} ({v['soul_traits']})",
        f"• Число Дхармы/Судьбы (Бхагьянк): {v['destiny_number']} — Планета-управитель: {v['destiny_planet']} ({v['destiny_traits']})",
        "",
        "--- 5. ПРОГНОСТИКА (ПИКИ ЖИЗНИ, ВЫЗОВЫ И ПЕРСОНАЛЬНЫЙ ГОД) ---",
        f"• Персональный Год ({fc['current_year']}): {fc['personal_year']} | Персональный Месяц: {fc['personal_month']} | Персональный День: {fc['personal_day']}",
        "• 4 Жизненных Пика: " + ", ".join(f"{lbl}: число {val}" for lbl, val in fc["pinnacles"]),
        f"• 4 Кармических Вызова: {fc['challenges']}",
    ])

    if data.get("compatibility"):
        comp = data["compatibility"]
        lines.extend([
            "",
            f"--- 6. СОВМЕСТИМОСТЬ С ПАРТНЁРОМ ({comp['partner_date_str']}) ---",
            f"• ЧЖП партнёра: {comp['partner_lp']} | Общее число пары: {comp['combined_lp']}",
            f"• Матрица Совместимости (22 аркана): Центр пары = {comp['combined_center_22']}, Духовный союз = {comp['combined_sky_22']}, Финансы пары = {comp['combined_finance_22']}",
        ])

    return "\n".join(lines)
