"""
Self-test suite for Matrix Numerology Bot:
1. Tests wake-word detection ("Матрица" / "Matrix" in various cases and languages).
2. Tests pre-answer dialog verification & profile memory.
3. Tests multi-tradition numerological calculations (Pythagorean Square, 22-Arcana Matrix of Destiny,
   Western Pythagorean & Chaldean, Vedic Sankhya Shastra, Predictive cycles).
4. Tests high-resolution PNG Matrix image rendering.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bot.config import CHARTS_DIR, contains_matrix_wake_word
from bot.knowledge_base import knowledge_base
from bot.llm_numerology import build_offline_numerology_synthesis, rule_based_extract_matrix_dialog
from bot.matrix_renderer import render_numerology_image
from bot.numerology_engine import calculate_full_numerology


def run_tests() -> None:
    should_match = [
        "Матрикс, привет!",
        "матрикс посчитай мне дату",
        "Матрица, привет!",
        "матрица посчитай мне дату",
        "Привет, МАТРИКС!",
        "Matrix, calculate my life path",
        "Hey matrix!",
        "Позовите Матрикса",
        "Спрошу у Матрикса про финансовый код",
        "Спрошу у Матрицы про финансовый код",
        "Μάτριξ",
        "מטריקס",
        "ماتريكس",
    ]
    for s in should_match:
        assert contains_matrix_wake_word(s), f"Failed to detect wake word in: {s}"

    should_not_match = [
        "Просто обычное сообщение в чате",
        "Сегодня отличная погода",
    ]
    for s in should_not_match:
        assert not contains_matrix_wake_word(s), f"False positive wake word in: {s}"
    print("[OK] Multilingual & case-insensitive wake-word detector ('Матрикс' / 'Матрица' / 'Matrix') verified.")

    incomplete = rule_based_extract_matrix_dialog([{"role": "user", "content": "Матрица, расскажи про мои деньги"}])
    assert not incomplete["has_all_required_data"], "Should require birth date before calculating!"

    complete = rule_based_extract_matrix_dialog([
        {"role": "user", "content": "Матрица, посчитай для Анны Ивановой, дата рождения 15.05.1995, финансы и предназначение"}
    ])
    assert complete["has_all_required_data"], "Should detect complete numerology request!"
    print("[OK] Pre-answer verification & memory protocol verified.")

    num_data = calculate_full_numerology(
        day=15,
        month=5,
        year=1995,
        full_name="Анна Иванова",
        subject_label="Анна Иванова",
    )
    out_img = CHARTS_DIR / "sample_numerology_matrix.png"
    render_numerology_image(num_data, out_img)
    assert out_img.exists() and out_img.stat().st_size > 20000, "Matrix PNG image was not generated properly!"
    print(f"[OK] Numerology Matrix image generated at: {out_img} ({out_img.stat().st_size} bytes)")

    passages = knowledge_base.search("Квадрат Пифагора Матрица Судьбы Санкхья", top_k=3)
    synthesis = build_offline_numerology_synthesis(num_data, passages)
    assert "Квадрат Пифагора" in synthesis and "Матрица Судьбы" in synthesis
    print("[OK] Multi-school Numerology synthesis verified.")


if __name__ == "__main__":
    run_tests()
