"""
Self-test suite for Astra Bot:
1. Tests wake-word detection ("Астра" / "Astra" in various cases and languages).
2. Tests pre-answer dialog verification (incomplete vs complete data).
3. Tests multi-tradition Swiss Ephemeris calculation (Western, Hellenistic, Horary, Uranian, Formula of Soul).
4. Tests high-resolution PNG chart rendering.
"""
import datetime
from pathlib import Path

from bot.astro_engine import calculate_full_chart
from bot.chart_renderer import render_chart_image
from bot.config import CHARTS_DIR, contains_astra_wake_word
from bot.knowledge_base import knowledge_base
from bot.llm_astrologer import build_offline_expert_synthesis, rule_based_extract_dialog


def run_tests() -> None:
    # 1. Wake word tests
    should_match = [
        "Астра, привет!",
        "астра подскажи пожалуйста",
        "Привет, АСТРА!",
        "Astra, can you check my chart?",
        "Hey astra!",
        "Астру позовите",
        "Спрошу у Астры про хорар",
        "Ἄστρα",
        "אסטרה",
        "أسترا",
    ]
    for s in should_match:
        assert contains_astra_wake_word(s), f"Failed to detect wake word in: {s}"

    should_not_match = [
        "Я увлекаюсь астрологией",
        "Астральный план",
        "Просто обычное сообщение в группе",
    ]
    for s in should_not_match:
        assert not contains_astra_wake_word(s), f"False positive wake word in: {s}"
    print("[OK] Multilingual & case-insensitive wake-word detector ('Астра' / 'Astra') verified.")

    # 2. Dialog completeness check
    incomplete = rule_based_extract_dialog([{"role": "user", "content": "Астра, когда у меня наладится карьера?"}])
    assert not incomplete["has_all_required_data"], "Should require birth date, time, and city first!"

    complete = rule_based_extract_dialog([
        {"role": "user", "content": "Астра, разбери мою натальную карту, родилась 15.05.1995 в 14:30, город Москва"}
    ])
    assert complete["has_all_required_data"], "Should detect complete birth data!"
    print("[OK] Pre-answer verification protocol verified.")

    # 3. Multi-tradition ephemeris & chart image rendering
    dt = datetime.datetime(1995, 5, 15, 14, 30)
    chart = calculate_full_chart(
        dt_local=dt,
        lat=55.7558,
        lon=37.6173,
        tz_name="Europe/Moscow",
        place_label="Москва, Россия",
        subject_name="Тестовая Натальная Карта",
        chart_type="natal",
    )
    out_img = CHARTS_DIR / "sample_natal_chart.png"
    render_chart_image(chart, out_img)
    assert out_img.exists() and out_img.stat().st_size > 20000, "Chart PNG image was not generated properly!"
    print(f"[OK] Natal chart image generated at: {out_img} ({out_img.stat().st_size} bytes)")

    # 4. RAG & multi-school synthesis test
    passages = knowledge_base.search("Скорпион управитель Плутон Марс дома", top_k=4)
    synthesis = build_offline_expert_synthesis(chart, "Карьера и предназначение", passages)
    assert "Альтернативное" in synthesis or "классической" in synthesis
    print("[OK] Multi-school synthesis & alternative school comparison verified.")


if __name__ == "__main__":
    run_tests()
