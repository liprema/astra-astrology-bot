"""
Numerology Book Library Loader, Cloud Downloader (Yandex.Disk),
Authority Ranker, and Hybrid BM25 Retriever for MATRIX ("Матрица").

Prioritizes canonical works when traditions conflict:
- Tier 10: А. Ф. Александров (Классическая Психоматрица / Квадрат Пифагора), Н. Сидорова (Система Идеал),
  Наталия Ладини (Матрица Судьбы — Диагностика предназначения, 22 энергии), Хейро / Cheiro (Халдейская нумерология),
  Мэтью Гудвин / Х. Деко (Западная Пифагорейская школа), Хариш Джохари (Ведическая Санкхья-шастра).
- Tier 9: Джулия По (Кармическая нумерология и Хроноток), Дэвид Филлипс, Клаудия Уэлш, Ло-Шу / У-Син.
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from docx import Document
from pypdf import PdfReader
from rank_bm25 import BM25Okapi

from bot.config import BOOKS_DIR, KNOWLEDGE_INDEX_PATH

AUTHORITY_RULES: List[Tuple[List[str], int, str]] = [
    (
        ["александров", "психоматриц", "квадрат пифагора", "сидорова", "система идеал",
         "ладини", "матрица судьбы", "22 энергии", "хейро", "cheiro", "халдейск",
         "гудвин", "goodwin", "джохари", "johari", "санкхья", "ведическ"],
        10,
        "Первоисточники и Высший Канон Нумерологии (Психоматрица Александрова, Матрица Судьбы Ладини, Западная Пифагорейская, Халдейская и Ведическая Санкхья-шастра)",
    ),
    (
        ["джулия по", "кармическая нумерология", "хроноток", "филлипс", "ло-шу", "у-син"],
        9,
        "Признанная школа Кармической, Прогностической и Восточной нумерологии",
    ),
]


def detect_authority_and_school(filename: str, text_sample: str) -> Tuple[int, str]:
    combined = (filename + " " + text_sample[:2500]).lower()
    for keywords, score, school_label in AUTHORITY_RULES:
        for kw in keywords:
            if kw in combined:
                return score, school_label
    return 7, "Общая литература по Нумерологии"


def extract_text_from_file(filepath: Path) -> Tuple[str, Optional[str]]:
    ext = filepath.suffix.lower()
    try:
        if ext in (".txt", ".md"):
            for enc in ("utf-8", "cp1251", "utf-16", "latin-1"):
                try:
                    txt = filepath.read_text(encoding=enc)
                    if len(txt.strip()) > 50:
                        return txt, None
                except Exception:
                    continue
            return "", "Не удалось определить кодировку текстового файла или файл пуст."

        elif ext == ".pdf":
            reader = PdfReader(str(filepath))
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:
                    return "", "PDF-файл защищён паролем."
            pages_text = []
            for page in reader.pages:
                try:
                    t = page.extract_text() or ""
                    if t.strip():
                        pages_text.append(t)
                except Exception:
                    continue
            full_text = "\n\n".join(pages_text).strip()
            if len(full_text) < 100:
                return "", "PDF состоит из отсканированных картинок без текстового слоя (нужен OCR) или пуст."
            return full_text, None

        elif ext == ".docx":
            doc = Document(str(filepath))
            full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            if len(full_text) < 50:
                return "", "DOCX-файл не содержит читаемого текста."
            return full_text, None

        elif ext == ".fb2":
            raw = filepath.read_bytes()
            soup = BeautifulSoup(raw, "xml")
            body = soup.find("body")
            full_text = body.get_text(separator="\n") if body else soup.get_text(separator="\n")
            if len(full_text.strip()) < 50:
                return "", "FB2-файл повреждён или не содержит текста."
            return full_text, None

        elif ext == ".epub":
            texts = []
            with zipfile.ZipFile(filepath, "r") as zf:
                for name in zf.namelist():
                    if name.endswith((".xhtml", ".html", ".htm")):
                        raw_html = zf.read(name)
                        soup = BeautifulSoup(raw_html, "html.parser")
                        texts.append(soup.get_text(separator="\n"))
            full_text = "\n\n".join(texts).strip()
            if len(full_text) < 50:
                return "", "EPUB-файл не содержит текстовых глав."
            return full_text, None

        else:
            return "", f"Неподдерживаемый формат файла ({ext})."
    except Exception as exc:
        return "", f"Ошибка чтения файла: {exc}"


def download_from_yandex_disk(public_url: str, target_dir: Path = BOOKS_DIR) -> Tuple[List[Path], List[str]]:
    downloaded: List[Path] = []
    errors: List[str] = []
    api_url = "https://cloud-api.yandex.net/v1/disk/public/resources"

    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            resp = client.get(api_url, params={"public_key": public_url, "limit": 200})
            if resp.status_code != 200:
                return [], [f"Яндекс.Диск вернул код {resp.status_code} для ссылки {public_url}"]
            meta = resp.json()

            if meta.get("type") == "file":
                dl_resp = client.get(f"{api_url}/download", params={"public_key": public_url})
                href = dl_resp.json().get("href")
                fname = meta.get("name", "yandex_numerology_book.pdf")
                if href:
                    file_path = target_dir / fname
                    with client.stream("GET", href) as stream:
                        with open(file_path, "wb") as f:
                            for chunk in stream.iter_bytes():
                                f.write(chunk)
                    downloaded.append(file_path)
            elif meta.get("type") == "dir":
                items = meta.get("_embedded", {}).get("items", [])
                for item in items:
                    if item.get("type") == "file":
                        fname = item.get("name")
                        item_path = item.get("path")
                        dl_resp = client.get(
                            f"{api_url}/download",
                            params={"public_key": public_url, "path": item_path},
                        )
                        if dl_resp.status_code == 200 and dl_resp.json().get("href"):
                            href = dl_resp.json()["href"]
                            out_file = target_dir / fname
                            with client.stream("GET", href) as stream:
                                with open(out_file, "wb") as f:
                                    for chunk in stream.iter_bytes():
                                        f.write(chunk)
                            downloaded.append(out_file)
                        else:
                            errors.append(f"Не удалось скачать файл {fname} с Яндекс.Диска.")
    except Exception as exc:
        errors.append(f"Ошибка при скачивании с Яндекс.Диска ({public_url}): {exc}")

    return downloaded, errors


def tokenize_ru_en(text: str) -> List[str]:
    words = re.findall(r"[а-яёa-z0-9]{3,}", text.lower())
    return [w[:6] if len(w) > 6 else w for w in words]


BUILTIN_CANONICAL_NUMEROLOGY_CHUNKS = [
    {
        "book": "Канонический свод Нумерологии: Сравнение Школы Александрова, Системы Идеал (Сидоровой), Западной Пифагорейской и Халдейской школ",
        "school": "Сравнительный канон: Психоматрица А. Ф. Александрова, Система «Идеал» Н. Сидоровой, Западная Пифагорейская и Халдейская традиции",
        "authority": 10,
        "text": (
            "КЛЮЧЕВЫЕ РАЗЛИЧИЯ ШКОЛ НУМЕРОЛОГИИ (ОБЯЗАТЕЛЬНО УКАЗЫВАТЬ ПРИ РАЗБОРЕ):\n"
            "1. РАСЧЁТ КВАДРАТА ПИФАГОРА ДЛЯ РОЖДЁННЫХ ПОСЛЕ 2000 ГОДА: В классической школе А. Ф. Александрова 3-е рабочее число "
            "всегда находится вычитанием удвоенной первой цифры дня рождения (`W1 - 2*d1`). В современной школе («Идеал» Н. Сидоровой и др.) "
            "для людей, рождённых в 2000 году и позже, вместо вычитания `-2` прибавляется константа `+19`, которая также заносится в ячейки `1` и `9`. "
            "При анализе даты после 2000 года необходимо указывать оба варианта!\n"
            "2. НОРМА ЯЧЕЕК ПСИХОМАТРИЦЫ (Александров vs Сидорова «Идеал»): У Александрова сильными считаются ячейки от 3 и более одинаковых цифр, "
            "а переходы возможны между `11↔8`, `22↔4`, `5↔9`, `6↔7`. В системе «Идеал» Н. Сидоровой установлена эталонная матрица нормы "
            "(`11`, `22`, `3`, `4`, `5`, `6`, `7`, `8`, `99`), где оценивается избыток или дефицит каждого качества относительно нормы.\n"
            "3. ЗАПАДНАЯ ПИФАГОРЕЙСКАЯ vs ХАЛДЕЙСКАЯ ШКОЛА ИМЕНИ: В Пифагорейской нумерологии буквы алфавита идут строго по порядку от 1 до 9. "
            "В древней Халдейской школе (Cheiro) буквы распределены по звуковой вибрации от 1 до 8 (число 9 считается священным и не присваивается буквам), "
            "а решающую роль играет двузначное составное число имени."
        ),
    },
    {
        "book": "Канонический свод: Матрица Судьбы (22 Аркана Н. Ладини), Кармическая нумерология (Джулия По) и Ведическая Санкхья-шастра",
        "school": "Матрица Судьбы (Н. Ладини), Кармическая школа (Джулия По) и Ведическая нумерология (Х. Джохари)",
        "authority": 10,
        "text": (
            "МАТРИЦА СУДЬБЫ И ВЕДИЧЕСКАЯ САНКХЬЯ-ШАСТРА:\n"
            "1. ПРАВИЛО 22 ЭНЕРГИЙ: Любое число больше 22 складывается по цифрам (например, 27 → 2+7 = 9 Отшельник). Каждая энергия проживается "
            "либо «в плюсе» (ресурсное состояние), либо «в минусе» (блокировка или гиперкомпенсация). Кармический хвост (3 нижние энергии) всегда "
            "начинается в минусе и требует осознанной проработки.\n"
            "2. ВЕДИЧЕСКАЯ САНКХЬЯ-ШАСТРА: Делит карту на Число Души (Джива/Муланк — день рождения, определяет внутренний характер и отношения до 35–40 лет) "
            "и Число Дхармы/Судьбы (Бхагьянк — сумма всей даты, включается в полную силу после 35–40 лет и показывает событийный коридор кармы). "
            "Каждому числу от 1 до 9 соответствует планета Джйотиш: 1 — Солнце, 2 — Луна, 3 — Юпитер, 4 — Раху, 5 — Меркурий, 6 — Венера, 7 — Кету, 8 — Сатурн, 9 — Марс."
        ),
    },
]


class KnowledgeBase:
    def __init__(self) -> None:
        self.chunks: List[Dict] = []
        self.bm25: Optional[BM25Okapi] = None
        self.unreadable_files: List[Dict[str, str]] = []
        self.indexed_books: List[Dict] = []
        self.load_or_build_index()

    def load_or_build_index(self) -> Dict:
        self.chunks = list(BUILTIN_CANONICAL_NUMEROLOGY_CHUNKS)
        self.unreadable_files = []
        self.indexed_books = []

        if BOOKS_DIR.exists():
            for path in sorted(BOOKS_DIR.rglob("*")):
                if path.is_dir() or path.name.startswith("."):
                    continue
                text, err = extract_text_from_file(path)
                if err or not text:
                    self.unreadable_files.append({
                        "file": path.name,
                        "path": str(path),
                        "reason": err or "Пустой файл",
                    })
                    continue

                auth_score, school_name = detect_authority_and_school(path.name, text)
                book_chunks = self._split_into_chunks(text, chunk_size=1400, overlap=200)
                for ch in book_chunks:
                    self.chunks.append({
                        "book": path.name,
                        "school": school_name,
                        "authority": auth_score,
                        "text": ch,
                    })
                self.indexed_books.append({
                    "file": path.name,
                    "school": school_name,
                    "authority": auth_score,
                    "chunks_count": len(book_chunks),
                })

        tokenized_corpus = [tokenize_ru_en(c["text"] + " " + c["book"] + " " + c["school"]) for c in self.chunks]
        if tokenized_corpus:
            self.bm25 = BM25Okapi(tokenized_corpus)

        summary = {
            "indexed_books_count": len(self.indexed_books),
            "total_chunks": len(self.chunks),
            "indexed_books": self.indexed_books,
            "unreadable_files": self.unreadable_files,
        }
        try:
            KNOWLEDGE_INDEX_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return summary

    @staticmethod
    def _split_into_chunks(text: str, chunk_size: int = 1400, overlap: int = 200) -> List[str]:
        clean = re.sub(r"\n{3,}", "\n\n", text).strip()
        if len(clean) <= chunk_size:
            return [clean]
        chunks = []
        start = 0
        while start < len(clean):
            end = min(len(clean), start + chunk_size)
            chunks.append(clean[start:end])
            if end == len(clean):
                break
            start = max(start + 1, end - overlap)
        return chunks

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        if not self.chunks or not self.bm25:
            return BUILTIN_CANONICAL_NUMEROLOGY_CHUNKS[:top_k]

        q_tokens = tokenize_ru_en(query)
        if not q_tokens:
            return self.chunks[:top_k]

        scores = self.bm25.get_scores(q_tokens)
        weighted = []
        for idx, base_score in enumerate(scores):
            auth = self.chunks[idx].get("authority", 7)
            combined_score = (base_score + 0.1) * (1.0 + (auth / 20.0))
            weighted.append((combined_score, idx))

        weighted.sort(key=lambda x: x[0], reverse=True)
        results = [self.chunks[idx] for _, idx in weighted[:top_k]]

        seen_books = {r["book"] for r in results}
        for canon in BUILTIN_CANONICAL_NUMEROLOGY_CHUNKS:
            if canon["book"] not in seen_books:
                results.append(canon)
        return results


knowledge_base = KnowledgeBase()
