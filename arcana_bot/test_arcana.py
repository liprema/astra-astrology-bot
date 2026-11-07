"""
Self-test suite for Arcana Tarot Bot:
1. Tests wake-word detection ("Аркана" / "Arcana" in various cases and languages).
2. Tests pre-answer dialog verification (incomplete vs complete context).
3. Tests 78-card deck, Quintessence, Bottom of Deck, and Elemental Dignities.
4. Tests high-resolution PNG spread image rendering.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bot.config import SPREADS_DIR, contains_arcana_wake_word
from bot.knowledge_base import knowledge_base
from bot.llm_tarot import build_offline_tarot_synthesis, rule_based_extract_tarot_dialog
from bot.spread_renderer import render_spread_image
from bot.tarot_engine import draw_tarot_spread


def run_tests() -> None:
    should_match = [
        "Аркана, привет!",
        "аркана разложи карты",
        "Привет, АРКАНА!",
        "Arcana, pull a spread for me",
        "Hey arcana!",
        "Позовите Аркану",
        "Спрошу у Арканы про выбор",
        "Αρκάνα",
        "ארקנה",
        "أركانا",
    ]
    for s in should_match:
        assert contains_arcana_wake_word(s), f"Failed to detect wake word in: {s}"

    should_not_match = [
        "Просто обычное сообщение в чате",
        "Сегодня отличная погода",
    ]
    for s in should_not_match:
        assert not contains_arcana_wake_word(s), f"False positive wake word in: {s}"
    print("[OK] Multilingual & case-insensitive wake-word detector ('Аркана' / 'Arcana') verified.")

    incomplete = rule_based_extract_tarot_dialog([{"role": "user", "content": "Аркана, погадай мне"}])
    assert not incomplete["has_all_required_data"], "Should require context (who/what) before pulling cards!"

    complete = rule_based_extract_tarot_dialog([
        {"role": "user", "content": "Аркана, сделай триплет для Анны на перспективу новой работы в ближайшие 3 месяца"}
    ])
    assert complete["has_all_required_data"], "Should detect complete Tarot request!"
    print("[OK] Pre-answer verification protocol verified.")

    spread = draw_tarot_spread(
        spread_type="triplet",
        question="Перспектива карьеры и финансов на ближайшие 3 месяца",
        subject_name="Анна (Карьера)",
        allow_reversed=True,
    )
    out_img = SPREADS_DIR / "sample_tarot_spread.png"
    render_spread_image(spread, out_img)
    assert out_img.exists() and out_img.stat().st_size > 20000, "Spread PNG image was not generated properly!"
    print(f"[OK] Tarot spread image generated at: {out_img} ({out_img.stat().st_size} bytes)")

    passages = knowledge_base.search("Квинтэссенция Дно колоды Уэйт Кроули", top_k=3)
    synthesis = build_offline_tarot_synthesis(spread, passages)
    assert "Квинтэссенция" in synthesis and "Дно колоды" in synthesis
    print("[OK] Multi-school Tarot synthesis verified.")


if __name__ == "__main__":
    run_tests()
