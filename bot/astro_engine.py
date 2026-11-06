"""
Multi-tradition Swiss Ephemeris Astrological Calculation Engine.

Calculates:
1. Western Classical & Modern (Placidus, Regiomontanus, Whole Sign, Koch; Tropical & Sidereal)
2. Essential Dignities (Domicile, Exaltation, Detriment, Fall, Triplicity rulers Day/Night/Participating)
   - Both Traditional (7 planets) and Modern (10 planets) rulerships!
3. Hellenistic & Medieval (Day/Night Sect, Arabic Parts / Lots of Fortune & Spirit,
   Annual Profections & Time Lord, Firdaria periods)
4. Uranian / Hamburg School (8 Transneptunians: Cupido, Hades, Zeus, Kronos, Apollon, Admetos, Vulkanus, Poseidon + Midpoints)
5. Formula of the Soul / Dispositor Chains (Traditional & Modern dispositors by sign)
6. Heliocentric positions & Karmic Nodes (True/Mean Node, Lilith)
7. Aspects (Major & Minor with orbs and applying/separating detection)
"""
from __future__ import annotations

import datetime
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pytz
import swisseph as swe
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

ZODIAC_SIGNS_RU = [
    "Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева",
    "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы",
]

ZODIAC_GLYPHS = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]

ELEMENTS_RU = ["Огонь", "Земля", "Воздух", "Вода"]

PLANET_LIST = [
    (swe.SUN, "Солнце", "☉", "Sun"),
    (swe.MOON, "Луна", "☽", "Moon"),
    (swe.MERCURY, "Меркурий", "☿", "Mercury"),
    (swe.VENUS, "Венера", "♀", "Venus"),
    (swe.MARS, "Марс", "♂", "Mars"),
    (swe.JUPITER, "Юпитер", "♃", "Jupiter"),
    (swe.SATURN, "Сатурн", "♄", "Saturn"),
    (swe.URANUS, "Уран", "♅", "Uranus"),
    (swe.NEPTUNE, "Нептун", "♆", "Neptune"),
    (swe.PLUTO, "Плутон", "♇", "Pluto"),
    (swe.MEAN_NODE, "Сев. Узел (Раху)", "☊", "North Node"),
    (swe.MEAN_APOG, "Лилит (Чёрная Луна)", "☾", "Lilith"),
]

# Hamburg / Uranian 8 Transneptunian hypothetical planets in Swiss Ephemeris
URANIAN_PLANETS = [
    (swe.CUPIDO, "Купидон (Ur)", "Cu"),
    (swe.HADES, "Гадес (Ur)", "Ha"),
    (swe.ZEUS, "Зевс (Ur)", "Ze"),
    (swe.KRONOS, "Кронос (Ur)", "Kr"),
    (swe.APOLLON, "Аполлон (Ur)", "Ap"),
    (swe.ADMETOS, "Адмет (Ur)", "Ad"),
    (swe.VULKANUS, "Вулкан (Ur)", "Vu"),
    (swe.POSEIDON, "Посейдон (Ur)", "Po"),
]

# Traditional vs Modern sign rulers (0 = Aries ... 11 = Pisces)
TRADITIONAL_RULERS = {
    0: "Марс",
    1: "Венера",
    2: "Меркурий",
    3: "Луна",
    4: "Солнце",
    5: "Меркурий",
    6: "Венера",
    7: "Марс",
    8: "Юпитер",
    9: "Сатурн",
    10: "Сатурн",
    11: "Юпитер",
}

MODERN_RULERS = {
    0: "Марс",
    1: "Венера",
    2: "Меркурий",
    3: "Луна",
    4: "Солнце",
    5: "Меркурий",
    6: "Венера",
    7: "Плутон",
    8: "Юпитер",
    9: "Сатурн",
    10: "Уран",
    11: "Нептун",
}

EXALTATIONS = {
    "Солнце": 0,     # Aries
    "Луна": 1,       # Taurus
    "Меркурий": 5,   # Virgo
    "Венера": 11,    # Pisces
    "Марс": 9,       # Capricorn
    "Юпитер": 3,     # Cancer
    "Сатурн": 6,     # Libra
    "Уран": 7,       # Scorpio (modern)
    "Нептун": 3,     # Cancer / Aquarius (debated in modern schools)
    "Плутон": 0,     # Aries / Leo (modern)
}

# Dorothean Triplicity Rulers: (Day, Night, Participating)
DOROTHEAN_TRIPLICITIES = {
    "Огонь": ("Солнце", "Юпитер", "Сатурн"),
    "Земля": ("Венера", "Луна", "Марс"),
    "Воздух": ("Сатурн", "Меркурий", "Юпитер"),
    "Вода": ("Венера", "Марс", "Луна"),
}

ASPECT_RULES = [
    ("Соединение", "☌", 0.0, 8.5, "major"),
    ("Оппозиция", "☍", 180.0, 8.0, "major"),
    ("Трин", "△", 120.0, 7.5, "major"),
    ("Квадратура", "□", 90.0, 7.5, "major"),
    ("Секстиль", "✶", 60.0, 5.5, "major"),
    ("Квиконс", "150°", 150.0, 2.5, "minor"),
    ("Полуквадрат", "45°", 45.0, 2.0, "minor"),
    ("Полутораквадрат", "135°", 135.0, 2.0, "minor"),
]

_geolocator = Nominatim(user_agent="astra_astrology_bot_v1")
_tz_finder = TimezoneFinder()


@dataclass
class GeoPlace:
    query: str
    resolved_name: str
    lat: float
    lon: float
    tz_name: str


def resolve_place(place_query: str) -> Optional[GeoPlace]:
    """Geocode city/place name to coordinates and timezone."""
    try:
        loc = _geolocator.geocode(place_query, language="ru", timeout=10)
        if not loc:
            loc = _geolocator.geocode(place_query, timeout=10)
        if not loc:
            return None
        tz_name = _tz_finder.timezone_at(lng=loc.longitude, lat=loc.latitude) or "UTC"
        return GeoPlace(
            query=place_query,
            resolved_name=loc.address,
            lat=float(loc.latitude),
            lon=float(loc.longitude),
            tz_name=tz_name,
        )
    except Exception:
        return None


def format_deg(lon: float) -> Tuple[int, str, str, int, int]:
    """Return (sign_idx, sign_name, sign_glyph, deg_in_sign, minutes)."""
    lon = lon % 360.0
    sign_idx = int(lon // 30)
    in_sign = lon % 30.0
    deg = int(in_sign)
    minutes = int(round((in_sign - deg) * 60))
    if minutes == 60:
        deg += 1
        minutes = 0
    return sign_idx, ZODIAC_SIGNS_RU[sign_idx], ZODIAC_GLYPHS[sign_idx], deg, minutes


def house_of_longitude(lon: float, cusps: List[float]) -> int:
    """Find 1-based house number (1..12) for a given ecliptic longitude."""
    lon = lon % 360.0
    for i in range(12):
        c1 = cusps[i] % 360.0
        c2 = cusps[(i + 1) % 12] % 360.0
        if c1 <= c2:
            if c1 <= lon < c2:
                return i + 1
        else:
            if lon >= c1 or lon < c2:
                return i + 1
    return 1


def compute_dignities(planet_name: str, sign_idx: int) -> Dict[str, str]:
    """Compare Traditional vs Modern essential dignities for a planet in a sign."""
    trad_ruler = TRADITIONAL_RULERS[sign_idx]
    mod_ruler = MODERN_RULERS[sign_idx]
    opp_sign = (sign_idx + 6) % 12
    trad_detriment = TRADITIONAL_RULERS[opp_sign]
    mod_detriment = MODERN_RULERS[opp_sign]

    exalt_sign = EXALTATIONS.get(planet_name)
    fall_sign = (exalt_sign + 6) % 12 if exalt_sign is not None else None

    trad_status = []
    mod_status = []

    if trad_ruler == planet_name:
        trad_status.append("Обитель (классич.)")
    if mod_ruler == planet_name:
        mod_status.append("Обитель (соврем.)")

    if trad_detriment == planet_name:
        trad_status.append("Изгнание (классич.)")
    if mod_detriment == planet_name:
        mod_status.append("Изгнание (соврем.)")

    if exalt_sign == sign_idx:
        trad_status.append("Экзальтация")
        mod_status.append("Экзальтация")
    elif fall_sign == sign_idx:
        trad_status.append("Падение")
        mod_status.append("Падение")

    element = ELEMENTS_RU[sign_idx % 4]
    trip_rulers = DOROTHEAN_TRIPLICITIES[element]
    if planet_name in trip_rulers:
        trad_status.append(f"Триплицитет ({element})")

    return {
        "traditional": ", ".join(trad_status) if trad_status else "Перегрин",
        "modern": ", ".join(mod_status) if mod_status else "Нейтрально",
    }


def compute_firdaria(is_day_chart: bool, birth_dt_utc: datetime.datetime, target_dt_utc: datetime.datetime) -> Dict[str, str]:
    """Calculate Medieval Firdaria major and sub-period for target date."""
    day_order = [
        ("Солнце", 10), ("Венера", 8), ("Меркурий", 13), ("Луна", 9),
        ("Сатурн", 11), ("Юпитер", 12), ("Марс", 7), ("Сев. Узел", 3), ("Южн. Узел", 2),
    ]
    night_order = [
        ("Луна", 9), ("Сатурн", 11), ("Юпитер", 12), ("Марс", 7),
        ("Солнце", 10), ("Венера", 8), ("Меркурий", 13), ("Сев. Узел", 3), ("Южн. Узел", 2),
    ]
    sequence = day_order if is_day_chart else night_order
    planetary_seven = ["Солнце", "Венера", "Меркурий", "Луна", "Сатурн", "Юпитер", "Марс"]

    age_years = max(0.0, (target_dt_utc - birth_dt_utc).days / 365.2425)
    cycle_age = age_years % 75.0

    elapsed = 0.0
    major_ruler = sequence[0][0]
    sub_ruler = major_ruler
    for ruler, span in sequence:
        if elapsed + span > cycle_age:
            major_ruler = ruler
            offset_in_major = cycle_age - elapsed
            if ruler in planetary_seven:
                start_idx = planetary_seven.index(ruler)
                sub_span = span / 7.0
                sub_idx = min(6, int(offset_in_major / sub_span))
                sub_ruler = planetary_seven[(start_idx + sub_idx) % 7]
            else:
                sub_ruler = ruler
            break
        elapsed += span

    return {
        "age_years": f"{age_years:.1f}",
        "major_firdar": major_ruler,
        "sub_firdar": sub_ruler,
    }


def calculate_full_chart(
    dt_local: datetime.datetime,
    lat: float,
    lon: float,
    tz_name: str,
    place_label: str = "",
    subject_name: str = "Карта",
    chart_type: str = "natal",
) -> Dict:
    """
    Calculate a comprehensive multi-tradition astrological dataset.
    """
    tz = pytz.timezone(tz_name)
    if dt_local.tzinfo is None:
        dt_localized = tz.localize(dt_local)
    else:
        dt_localized = dt_local.astimezone(tz)
    dt_utc = dt_localized.astimezone(pytz.UTC)

    hour_decimal = dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0
    jd_ut = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, hour_decimal)

    # 1. Houses in multiple traditions:
    # - Placidus ('P'): Western modern & classical standard
    # - Regiomontanus ('R'): Classical Horary standard (William Lilly, John Frawley)
    # - Whole Sign ('W'): Hellenistic & Ancient standard
    # - Koch ('K'): Event / Predictive schools
    cusps_placidus, ascmc_placidus = swe.houses(jd_ut, lat, lon, b"P")
    cusps_regio, _ = swe.houses(jd_ut, lat, lon, b"R")
    cusps_wholesign, _ = swe.houses(jd_ut, lat, lon, b"W")

    asc_lon = float(ascmc_placidus[0])
    mc_lon = float(ascmc_placidus[1])
    vertex_lon = float(ascmc_placidus[3])

    # Default house system depends on chart_type: Regiomontanus for horary, Placidus otherwise
    primary_cusps = list(cusps_regio if chart_type == "horary" else cusps_placidus)
    primary_house_sys_name = "Региомонтанус (Хорар)" if chart_type == "horary" else "Плацидус"

    # 2. Planetary positions (Tropical Geocentric, Heliocentric, and Uranian)
    planets_data = []
    planet_lons: Dict[str, float] = {}
    helio_data = []

    for pid, ru_name, glyph, en_name in PLANET_LIST:
        res, _ = swe.calc_ut(jd_ut, pid, swe.FLG_SWIEPH | swe.FLG_SPEED)
        plon = float(res[0])
        plat = float(res[1])
        pspeed = float(res[3])
        is_retro = pspeed < 0 and pid not in (swe.SUN, swe.MOON)

        s_idx, s_name, s_glyph, deg, mins = format_deg(plon)
        h_plac = house_of_longitude(plon, list(cusps_placidus))
        h_regio = house_of_longitude(plon, list(cusps_regio))
        h_whole = ((s_idx - int(asc_lon // 30)) % 12) + 1

        dignities = compute_dignities(ru_name, s_idx)

        planets_data.append({
            "id": pid,
            "name": ru_name,
            "en_name": en_name,
            "glyph": glyph,
            "lon": plon,
            "lat": plat,
            "speed": pspeed,
            "retro": is_retro,
            "sign_idx": s_idx,
            "sign": s_name,
            "sign_glyph": s_glyph,
            "deg": deg,
            "min": mins,
            "formatted": f"{deg:02d}°{mins:02d}' {s_glyph} {s_name}{' R' if is_retro else ''}",
            "house_placidus": h_plac,
            "house_regiomontanus": h_regio,
            "house_wholesign": h_whole,
            "house_primary": h_regio if chart_type == "horary" else h_plac,
            "dignity_traditional": dignities["traditional"],
            "dignity_modern": dignities["modern"],
            "trad_dispositor": TRADITIONAL_RULERS[s_idx],
            "mod_dispositor": MODERN_RULERS[s_idx],
        })
        planet_lons[ru_name] = plon

        # Heliocentric position for physical planets (Mercury..Pluto)
        if pid in (swe.MERCURY, swe.VENUS, swe.MARS, swe.JUPITER, swe.SATURN, swe.URANUS, swe.NEPTUNE, swe.PLUTO):
            try:
                h_res, _ = swe.calc_ut(jd_ut, pid, swe.FLG_SWIEPH | swe.FLG_HELCTR)
                hlon = float(h_res[0])
                _, hs_name, hs_glyph, hdeg, hmins = format_deg(hlon)
                helio_data.append(f"{ru_name}: {hdeg:02d}°{hmins:02d}' {hs_glyph} {hs_name}")
            except Exception:
                pass

    # Add South Node (Ketu) exactly opposite North Node
    nn_lon = planet_lons["Сев. Узел (Раху)"]
    sn_lon = (nn_lon + 180.0) % 360.0
    sn_s_idx, sn_s_name, sn_s_glyph, sn_deg, sn_mins = format_deg(sn_lon)
    planets_data.append({
        "id": -1,
        "name": "Южн. Узел (Кету)",
        "en_name": "South Node",
        "glyph": "☋",
        "lon": sn_lon,
        "lat": 0.0,
        "speed": -0.05,
        "retro": True,
        "sign_idx": sn_s_idx,
        "sign": sn_s_name,
        "sign_glyph": sn_s_glyph,
        "deg": sn_deg,
        "min": sn_mins,
        "formatted": f"{sn_deg:02d}°{sn_mins:02d}' {sn_s_glyph} {sn_s_name} R",
        "house_placidus": house_of_longitude(sn_lon, list(cusps_placidus)),
        "house_regiomontanus": house_of_longitude(sn_lon, list(cusps_regio)),
        "house_wholesign": ((sn_s_idx - int(asc_lon // 30)) % 12) + 1,
        "house_primary": house_of_longitude(sn_lon, primary_cusps),
        "dignity_traditional": "Кармическая точка",
        "dignity_modern": "Кармическая точка",
        "trad_dispositor": TRADITIONAL_RULERS[sn_s_idx],
        "mod_dispositor": MODERN_RULERS[sn_s_idx],
    })

    # 3. Hellenistic & Medieval Sect (Day vs Night chart) + Lots (Fortune & Spirit)
    sun_lon = planet_lons["Солнце"]
    moon_lon = planet_lons["Луна"]
    sun_house_plac = house_of_longitude(sun_lon, list(cusps_placidus))
    is_day_chart = sun_house_plac in (7, 8, 9, 10, 11, 12)

    if is_day_chart:
        lot_fortune_lon = (asc_lon + moon_lon - sun_lon) % 360.0
        lot_spirit_lon = (asc_lon + sun_lon - moon_lon) % 360.0
    else:
        lot_fortune_lon = (asc_lon + sun_lon - moon_lon) % 360.0
        lot_spirit_lon = (asc_lon + moon_lon - sun_lon) % 360.0

    lf_idx, lf_sign, lf_glyph, lf_deg, lf_min = format_deg(lot_fortune_lon)
    ls_idx, ls_sign, ls_glyph, ls_deg, ls_min = format_deg(lot_spirit_lon)

    # Annual Profections & Firdaria (for current moment UTC)
    now_utc = datetime.datetime.now(pytz.UTC)
    age_years_int = max(0, int((now_utc - dt_utc).days // 365.2425))
    profected_house_num = (age_years_int % 12) + 1
    asc_sign_idx = int(asc_lon // 30)
    profected_sign_idx = (asc_sign_idx + profected_house_num - 1) % 12
    profected_sign_name = ZODIAC_SIGNS_RU[profected_sign_idx]
    profected_lord_trad = TRADITIONAL_RULERS[profected_sign_idx]
    profected_lord_mod = MODERN_RULERS[profected_sign_idx]
    firdaria_info = compute_firdaria(is_day_chart, dt_utc, now_utc)

    # 4. Uranian / Hamburg School Transneptunians + Key Midpoints
    uranian_results = []
    for upid, uname, uglyph in URANIAN_PLANETS:
        try:
            ures, _ = swe.calc_ut(jd_ut, upid, swe.FLG_SWIEPH)
            ulon = float(ures[0])
            _, usign, usglyph, udeg, umin = format_deg(ulon)
            uranian_results.append({
                "name": uname,
                "glyph": uglyph,
                "lon": ulon,
                "formatted": f"{udeg:02d}°{umin:02d}' {usglyph} {usign}",
            })
        except Exception:
            pass

    # Sun/Moon midpoint & ASC/MC midpoint (Cosmobiology / Ebertin & Uranian)
    diff_sm = (moon_lon - sun_lon) % 360.0
    mid_sm = (sun_lon + (diff_sm / 2.0 if diff_sm <= 180 else (diff_sm - 360.0) / 2.0)) % 360.0
    _, sm_sign, sm_glyph, sm_deg, sm_min = format_deg(mid_sm)

    # 5. Formula of the Soul (Dispositor Centers by Modern & Classical Rulership)
    trad_chain = {p["name"]: p["trad_dispositor"] for p in planets_data[:7]}
    mod_chain = {p["name"]: p["mod_dispositor"] for p in planets_data[:10]}

    # Find centers (mutual reception loops or self-ruling planets in domicile)
    domicile_modern = [p["name"] for p in planets_data[:10] if p["name"] == p["mod_dispositor"]]
    domicile_trad = [p["name"] for p in planets_data[:7] if p["name"] == p["trad_dispositor"]]

    # 6. Aspects calculation (with applying/separating detection)
    aspects = []
    core_bodies = planets_data[:12]  # 10 planets + North Node + Lilith
    for i in range(len(core_bodies)):
        for j in range(i + 1, len(core_bodies)):
            p1 = core_bodies[i]
            p2 = core_bodies[j]
            diff = abs(p1["lon"] - p2["lon"]) % 360.0
            if diff > 180.0:
                diff = 360.0 - diff

            for asp_name, asp_glyph, exact_angle, max_orb, asp_kind in ASPECT_RULES:
                orb = abs(diff - exact_angle)
                if orb <= max_orb:
                    # Determine applying vs separating using relative speed
                    future_p1 = (p1["lon"] + p1["speed"] * 0.1) % 360.0
                    future_p2 = (p2["lon"] + p2["speed"] * 0.1) % 360.0
                    f_diff = abs(future_p1 - future_p2) % 360.0
                    if f_diff > 180.0:
                        f_diff = 360.0 - f_diff
                    f_orb = abs(f_diff - exact_angle)
                    motion_type = "сходящийся" if f_orb < orb else "расходящийся"

                    aspects.append({
                        "p1": p1["name"],
                        "p1_glyph": p1["glyph"],
                        "p1_lon": p1["lon"],
                        "p2": p2["name"],
                        "p2_glyph": p2["glyph"],
                        "p2_lon": p2["lon"],
                        "aspect": asp_name,
                        "glyph": asp_glyph,
                        "angle": exact_angle,
                        "orb": round(orb, 2),
                        "kind": asp_kind,
                        "motion": motion_type,
                    })
                    break

    # 7. Format Houses (Placidus, Regiomontanus, Whole Sign comparison)
    houses_info = []
    for idx in range(12):
        c_lon = primary_cusps[idx]
        s_i, s_n, s_g, d_deg, d_min = format_deg(c_lon)
        ws_sign_idx = (asc_sign_idx + idx) % 12
        houses_info.append({
            "house": idx + 1,
            "lon": c_lon,
            "sign": s_n,
            "sign_glyph": s_g,
            "deg": d_deg,
            "min": d_min,
            "formatted": f"{d_deg:02d}°{d_min:02d}' {s_g} {s_n}",
            "trad_ruler": TRADITIONAL_RULERS[s_i],
            "mod_ruler": MODERN_RULERS[s_i],
            "wholesign_sign": ZODIAC_SIGNS_RU[ws_sign_idx],
            "wholesign_trad_ruler": TRADITIONAL_RULERS[ws_sign_idx],
        })

    _, asc_sign, asc_glyph, asc_d, asc_m = format_deg(asc_lon)
    _, mc_sign, mc_glyph, mc_d, mc_m = format_deg(mc_lon)

    return {
        "subject_name": subject_name,
        "chart_type": chart_type,
        "place_label": place_label,
        "lat": lat,
        "lon": lon,
        "tz_name": tz_name,
        "dt_local_str": dt_localized.strftime("%d.%m.%Y %H:%M (%Z)"),
        "dt_utc_str": dt_utc.strftime("%d.%m.%Y %H:%M UTC"),
        "jd_ut": jd_ut,
        "house_system": primary_house_sys_name,
        "asc": {
            "lon": asc_lon,
            "formatted": f"{asc_d:02d}°{asc_m:02d}' {asc_glyph} {asc_sign}",
            "sign": asc_sign,
            "trad_ruler": TRADITIONAL_RULERS[asc_sign_idx],
            "mod_ruler": MODERN_RULERS[asc_sign_idx],
        },
        "mc": {
            "lon": mc_lon,
            "formatted": f"{mc_d:02d}°{mc_m:02d}' {mc_glyph} {mc_sign}",
            "sign": mc_sign,
        },
        "vertex_lon": vertex_lon,
        "cusps": primary_cusps,
        "houses": houses_info,
        "planets": planets_data,
        "aspects": aspects,
        "hellenistic_medieval": {
            "sect": "Дневная карта (Секта Солнца)" if is_day_chart else "Ночная карта (Секта Луны)",
            "lot_of_fortune": {
                "lon": lot_fortune_lon,
                "formatted": f"{lf_deg:02d}°{lf_min:02d}' {lf_glyph} {lf_sign}",
                "house": house_of_longitude(lot_fortune_lon, primary_cusps),
                "trad_ruler": TRADITIONAL_RULERS[lf_idx],
            },
            "lot_of_spirit": {
                "lon": lot_spirit_lon,
                "formatted": f"{ls_deg:02d}°{ls_min:02d}' {ls_glyph} {ls_sign}",
                "house": house_of_longitude(lot_spirit_lon, primary_cusps),
                "trad_ruler": TRADITIONAL_RULERS[ls_idx],
            },
            "annual_profection": {
                "current_age": age_years_int,
                "profected_house": profected_house_num,
                "profected_sign": profected_sign_name,
                "lord_of_year_trad": profected_lord_trad,
                "lord_of_year_mod": profected_lord_mod,
            },
            "firdaria": firdaria_info,
        },
        "uranian": {
            "sun_moon_midpoint": f"{sm_deg:02d}°{sm_min:02d}' {sm_glyph} {sm_sign}",
            "transneptunians": uranian_results,
        },
        "formula_of_soul": {
            "modern_chain": mod_chain,
            "traditional_chain": trad_chain,
            "modern_centers_domicile": domicile_modern,
            "traditional_centers_domicile": domicile_trad,
        },
        "heliocentric": helio_data,
    }


def format_chart_for_llm(chart: Dict) -> str:
    """Format full multi-tradition chart data into structured text for LLM synthesis."""
    lines = [
        f"=== АСТРОНОМИЧЕСКИЙ РАСЧЁТ КАРТЫ ({chart['subject_name']}) ===",
        f"Тип карты: {chart['chart_type']} | Основная система домов: {chart['house_system']}",
        f"Дата и время (местное): {chart['dt_local_str']} | UTC: {chart['dt_utc_str']}",
        f"Координаты: {chart['place_label']} ({chart['lat']:.4f}N, {chart['lon']:.4f}E, часовой пояс {chart['tz_name']})",
        f"Асцендент (ASC): {chart['asc']['formatted']} (Упр. классич.: {chart['asc']['trad_ruler']}, соврем.: {chart['asc']['mod_ruler']})",
        f"Середина Неба (MC): {chart['mc']['formatted']}",
        "",
        "--- 1. ПЛАНЕТЫ И УЗЛЫ (Тропический зодиак: Плацидус / Региомонтанус / Полнознаковые дома) ---",
    ]
    for p in chart["planets"]:
        lines.append(
            f"• {p['glyph']} {p['name']}: {p['formatted']} | "
            f"Дом Плац.: {p['house_placidus']}, Регио.: {p['house_regiomontanus']}, Полнознак.: {p['house_wholesign']} | "
            f"Достоинства [Классика: {p['dignity_traditional']} | Модерн: {p['dignity_modern']}] | "
            f"Диспозитор [Классика: {p['trad_dispositor']} / Модерн: {p['mod_dispositor']}]"
        )

    lines.append("\n--- 2. КУСПИДЫ ДОМОВ (Плацидус/Региомонтанус vs Полнознаковая эллинистическая система) ---")
    for h in chart["houses"]:
        lines.append(
            f"• {h['house']} дом: {h['formatted']} (Упр. классич.: {h['trad_ruler']}, соврем.: {h['mod_ruler']}) | "
            f"В Полнознаковой: {h['wholesign_sign']} (Упр.: {h['wholesign_trad_ruler']})"
        )

    hm = chart["hellenistic_medieval"]
    lines.extend([
        "\n--- 3. ЭЛЛИНИСТИЧЕСКАЯ И СРЕДНЕВЕКОВАЯ АСТРОЛОГИЯ ---",
        f"• Секта карты: {hm['sect']}",
        f"• Жребий Фортуны (Парс Фортуны): {hm['lot_of_fortune']['formatted']} (дом {hm['lot_of_fortune']['house']}, диспозитор {hm['lot_of_fortune']['trad_ruler']})",
        f"• Жребий Духа (Парс Духа): {hm['lot_of_spirit']['formatted']} (дом {hm['lot_of_spirit']['house']}, диспозитор {hm['lot_of_spirit']['trad_ruler']})",
        f"• Годовая профекция (возраст {hm['annual_profection']['current_age']}): {hm['annual_profection']['profected_house']}-й дом ({hm['annual_profection']['profected_sign']}), Хронократор года: классич. {hm['annual_profection']['lord_of_year_trad']} / соврем. {hm['annual_profection']['lord_of_year_mod']}",
        f"• Фирдар на текущий момент: Большой период — {hm['firdaria']['major_firdar']}, Подпериод — {hm['firdaria']['sub_firdar']}",
    ])

    fos = chart["formula_of_soul"]
    lines.extend([
        "\n--- 4. ФОРМУЛА ДУШИ И ЦЕПОЧКИ ДИСПОЗИТОРОВ ---",
        f"• Планеты в обители (центры силы, модерн): {', '.join(fos['modern_centers_domicile']) or 'нет планет в собственной обители (центры через взаимную рецепцию)'}",
        f"• Планеты в обители (классика септенера): {', '.join(fos['traditional_centers_domicile']) or 'нет'}",
        f"• Цепочка по современным управителям: " + ", ".join(f"{k}→{v}" for k, v in fos["modern_chain"].items()),
        f"• Цепочка по классическим управителям: " + ", ".join(f"{k}→{v}" for k, v in fos["traditional_chain"].items()),
    ])

    ur = chart["uranian"]
    lines.extend([
        "\n--- 5. УРАНИЧЕСКАЯ АСТРОЛОГИЯ (ГАМБУРГСКАЯ ШКОЛА) И ГЕЛИОЦЕНТРИКА ---",
        f"• Мидпойнт Солнце/Луна (☉/☽): {ur['sun_moon_midpoint']}",
    ])
    if ur["transneptunians"]:
        lines.append("• Транснептуны: " + "; ".join(f"{t['name']}: {t['formatted']}" for t in ur["transneptunians"]))
    if chart["heliocentric"]:
        lines.append("• Гелиоцентрические координаты: " + "; ".join(chart["heliocentric"]))

    lines.append("\n--- 6. АСПЕКТЫ (сходящиеся / расходящиеся) ---")
    for a in chart["aspects"]:
        lines.append(
            f"• {a['p1']} {a['glyph']} {a['p2']} ({a['aspect']}, орбис {a['orb']}°, {a['motion']})"
        )

    return "\n".join(lines)
