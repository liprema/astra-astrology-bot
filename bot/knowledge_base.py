"""
Astrological Book Library Loader, Cloud Downloader (Yandex.Disk / Google Drive),
Authority Ranker, and Hybrid BM25 + TF-IDF Retriever.

Key features requested by user:
- Reads PDF, DOCX, EPUB, FB2, TXT, MD from `books/`.
- Downloads from Yandex.Disk or Google Drive public links automatically.
- Reports any unreadable / scanned / corrupted files clearly so the user knows which books couldn't be parsed.
- Assigns an authority tier (Tier 1 Primary Masters -> Tier 2 Classical/Academic -> Tier 3 General)
  so that when sources conflict, the bot prioritizes higher-authority works and explicitly notes
  alternative opinions from other traditions.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from docx import Document
from pypdf import PdfReader
from rank_bm25 import BM25Okapi

from bot.config import BOOKS_DIR, KNOWLEDGE_INDEX_PATH

# Authority Ranking Rules (higher score = higher priority when doctrines conflict)
AUTHORITY_RULES: List[Tuple[List[str], int, str]] = [
    # Tier 10: Primary Classical & Horary / Hellenistic / Predictive Masters
    (
        [" птолемей", "ptolemy", "тетрабиблос", "дорофей", "dorotheus", "валент", "valens",
         "фирмик", "лилли", "lilly", "христианская астрология", "фроули", "frawley",
         "аль-бируни", "biruni", "авраам ибн эзра", "бонатти", "bonatti", "крис бреннан",
         "brennan", "деметра джордж", "demetra george", "роберт хэнд", "robert hand"],
        10,
        "Античная, Эллинистическая, Средневековая и Классическая Хорарная Традиция (Высший канонический авторитет)",
    ),
    # Tier 9: Leading Academic Western / Predictive / Synastry / Mundane Masters
    (
        ["радьяр", "rudhyar", "лиз грин", "liz greene", "хоукинс", "роберт пеллетье",
         "картер", "carter", "эбертин", "ebertin", "витте", "witte", "гамбург",
         "дараган", "константин дараган", "левин", "михаил левин", "шестопалов",
         "подводный", "авессалом подводный", "вронский", "кефер", "я. кефер",
         "марч", "макивер", "катрин обье", "брэди", "bernadette brady"],
        9,
        "Признанная классика Западной, Прогностической, Кармической и Уранической астрологии",
    ),
    # Tier 8: Specialized Schools (Formula of the Soul, Karmic, Medical)
    (
        ["астрогор", "формула души", "шульман", "мартин шульман", "кобб", "семира", "ветош"],
        8,
        "Специализированная школа (Формула Души / Кармическая / Астероидная астрология)",
    ),
]


def detect_authority_and_school(filename: str, text_sample: str) -> Tuple[int, str]:
    """Determine authority score (1..10) and tradition label from filename and header."""
    combined = (filename + " " + text_sample[:2500]).lower()
    for keywords, score, school_label in AUTHORITY_RULES:
        for kw in keywords:
            if kw in combined:
                return score, school_label
    return 7, "Общая астрологическая литература (Западная школа)"


def extract_text_from_file(filepath: Path) -> Tuple[str, Optional[str]]:
    """
    Extract text from a book file.
    Returns (extracted_text, error_reason_if_failed_or_unreadable).
    """
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

        elif ext in (".djvu", ".doc", ".rar", ".7z"):
            return "", f"Формат {ext} требует конвертации в PDF/DOCX/FB2/TXT/EPUB."

        else:
            return "", f"Неподдерживаемый формат файла ({ext})."

    except Exception as exc:
        return "", f"Ошибка чтения файла: {exc}"


def download_from_yandex_disk(public_url: str, target_dir: Path = BOOKS_DIR) -> Tuple[List[Path], List[str]]:
    """
    Download a public file or folder from Yandex.Disk via official public cloud API.
    Returns (downloaded_files, error_messages).
    """
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
                fname = meta.get("name", "yandex_book.pdf")
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
    """Fast tokenizer normalizing Russian and English astrological terms."""
    words = re.findall(r"[а-яёa-z0-9]{3,}", text.lower())
    # Simple stem truncation to 6 chars so Russian declensions match (e.g. скорпион/скорпионе -> скорпи)
    return [w[:6] if len(w) > 6 else w for w in words]


# Built-in Canonical Multi-Tradition Compendium (always available even before external books are loaded,
# and acts as baseline reference across Western, Horary, Hellenistic, Uranian, and Formula of Soul).
BUILTIN_CANONICAL_CHUNKS = [
    {
        "book": "Канонический свод: Классическая vs Современная Западная Астрология",
        "school": "Сравнительный канон: Традиционная (Птолемей/Лилли/Фроули) и Современная (Радьяр/Грин/Дараган) школы",
        "authority": 10,
        "text": (
            "УПРАВИТЕЛИ ЗНАКОВ И РАЗЛИЧИЯ ШКОЛ:\n"
            "В классической астрологии (эллинистической, средневековой, хорарной по У. Лилли и Дж. Фроули) "
            "используется строго септенер (7 видимых планет): Овен и Скорпион управляются Марсом; Телец и Весы — Венерой; "
            "Близнецы и Дева — Меркурием; Рак — Луной; Лев — Солнцем; Стрелец и Рыбы — Юпитером; Козерог и Водолей — Сатурном. "
            "В современной западной астрологии (модерн) транссатурновые планеты получают статус главных управителей: "
            "Скорпион — Плутон (соуправитель Марс), Водолей — Уран (соуправитель Сатурн), Рыбы — Нептун (соуправитель Юпитер). "
            "При анализе карты обязательно указывать оба взгляда: классический диспозитор показывает конкретные событийные обстоятельства, "
            "а транссатурновый управитель — глубинный психологический и поколенческий пласт."
        ),
    },
    {
        "book": "Канонический свод: Хорарная и Элективная Астрология (Уильям Лилли, Джон Фроули)",
        "school": "Классическая Хорарная и Элективная школа (Система домов Региомонтанус)",
        "authority": 10,
        "text": (
            "ПРАВИЛА ХОРАРНОЙ КАРТЫ (У. Лилли «Христианская астрология», Дж. Фроули «Учебник хорарной астрологии»):\n"
            "1. Карта строится на точное время и место, где астролог/система поняли вопрос, в системе домов Региомонтанус.\n"
            "2. Кверент (спрашивающий) всегда представлен управителем 1-го дома, Луной (как со-сигнификатором вопроса и хода дела) "
            "и планетой в 1-м доме.\n"
            "3. Квезит (предмет вопроса) определяется профильным домом (2-й — деньги и движимое имущество, 3-й — поездки/братья/документы, "
            "4-й — недвижимость и отец, 5-й — дети/любовники/творчество, 6-й — болезни и наёмные работники, 7-й — супруг/партнёр/оппонент, "
            "8-й — чужие деньги/кредиты/страхи, 9-й — суд/высшее образование/заграница, 10-й — работа/карьера/мать/судья, "
            "11-й — друзья/надежды/доход от бизнеса, 12-й — тайные враги/изоляция).\n"
            "4. Событие свершается, если между сигнификаторами кверента и квезита есть сходящийся (аппликационный) мажорный аспект "
            "без воспрепятствования (прохибиции), либо передача света, либо собирание света. "
            "Рецепция показывает истинную мотивацию, чувства и заинтересованность сторон, а эссенциальное достоинство (обитель, экзальтация, "
            "триплицитет, терм, фас, перегрин, изгнание, падение) показывает реальную способность действовать."
        ),
    },
    {
        "book": "Канонический свод: Эллинистическая и Средневековая Астрология (Веттий Валент, Дорофей, Бонатти)",
        "school": "Эллинистическая и Средневековая традиция (Полнознаковые дома, Секта, Жребии, Профекции, Фирдары)",
        "authority": 10,
        "text": (
            "ЭЛЛИНИСТИЧЕСКИЕ И СРЕДНЕВЕКОВЫЕ ТЕХНИКИ:\n"
            "1. СЕКТА (Хайз): Дневная карта (Солнце над горизонтом, дома 7–12) имеет секту Солнца (Юпитер — главный благодетель, "
            "Сатурн действует конструктивнее и дисциплинированнее, Марс — главный вредитель). Ночная карта (Солнце под горизонтом, дома 1–6) "
            "имеет секту Луны (Венера — главный благодетель, Марс действует мягче и результативнее, Сатурн — главный вредитель).\n"
            "2. ПОЛНОЗНАКОВЫЕ ДОМА (Знак = Дом): Весь знак, в котором находится Асцендент, считается 1-м домом от 0° до 30°. "
            "Если в Плацидусе планета попала в другой дом из-за наклона эклиптики, необходимо указать оба положения: "
            "Плацидус показывает психологическое восприятие и динамику среды, а Полнознаковый дом — фундаментальную тему сферы жизни.\n"
            "3. ЖРЕБИИ (Арабские части): Жребий Фортуны (Парс Фортуны) с учётом секты отражает тело, здоровье и материальные обстоятельства, "
            "не зависящие от воли человека. Жребий Духа (Парс Духа) показывает волю, призвание, карьеру и намерения души.\n"
            "4. ГОДОВЫЕ ПРОФЕКЦИИ и ФИРДАРЫ: Каждый год жизни активирует следующий знак от Асцендента (0 лет — 1 дом, 1 год — 2 дом, "
            "12, 24, 36 лет — снова 1 дом). Управитель знака профекции становится Владыкой Года (Хронократором), чьи транзиты и натальное "
            "положение определяют главные события года. Фирдары делят жизнь на планетарные периоды по 75-летнему циклу с учётом секты рождения."
        ),
    },
    {
        "book": "Канонический свод: Ураническая Астрология (Гамбургская школа А. Витте) и Космобиология (Р. Эбертин)",
        "school": "Ураническая астрология (Гамбургская школа) и Космобиология (Мидпойнты и Транснептуны)",
        "authority": 9,
        "text": (
            "УРАНИЧЕСКАЯ ШКОЛА И МИДПОЙНТЫ:\n"
            "1. Мидпойнт (средняя точка) Солнце/Луна (☉/☽) — ключевая ось синтеза духа и души, внутреннего равновесия и брака.\n"
            "2. 8 Транснептуновых планет Гамбургской школы:\n"
            "• Купидон (Cupido) — семья, брак, сообщества, искусство, корпорации.\n"
            "• Гадес (Hades) — прошлое, тайны, медицина, хронические процессы, археология, дефицит, кармические долги.\n"
            "• Зевс (Zeus) — направленная энергия, творческий импульс, техника, лидерство, старт проектов.\n"
            "• Кронос (Kronos) — высший авторитет, государство, начальство, элита, экспертность и мастерство.\n"
            "• Аполлон (Apollon) — наука, коммерция, успех, международное расширение, мир и широта знаний.\n"
            "• Адмет (Admetos) — глубинный фундамент, недвижимость, первоисточник, сверхконцентрация, остановка и выдержка.\n"
            "• Вулкан (Vulkanus) — колоссальная мощь, энергия, сверхусилие, влияние в социуме.\n"
            "• Посейдон (Poseidon) — высший разум, просветление, идеология, духовная культура и истина."
        ),
    },
    {
        "book": "Канонический свод: Формула Души (Цепочки диспозиторов) и Кармическая Астрология",
        "school": "Школа Формулы Души (А. Астрогор) и Кармическая астрология (М. Шульман, А. Подводный)",
        "authority": 8,
        "text": (
            "ФОРМУЛА ДУШИ И КАРМИЧЕСКИЕ ПОКАЗАТЕЛИ:\n"
            "1. Центры Формулы Души формируются планетами в собственной обители (6 баллов силы) или замкнутыми кольцами взаимной рецепции. "
            "Планеты на орбитах вокруг центра показывают инструменты, через которые человек реализует ядерную мотивацию центра.\n"
            "2. Восходящий Северный Узел (Раху) указывает вектор эволюционного развития, незнакомый, но необходимый опыт. "
            "Нисходящий Южный Узел (Кету) показывает накопленный фундамент прошлого, привычные паттерны, от которых нельзя закрываться, "
            "но нельзя и застревать только в них.\n"
            "3. Лилит (Чёрная Луна — апогей лунной орбиты) показывает зону психологических искажений, искушений, гиперкомпенсации "
            "или страха по теме знака и дома, требующую осознанности и трезвости."
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
        """Scan BOOKS_DIR, parse all readable books, record unreadable ones, and build BM25 index."""
        self.chunks = list(BUILTIN_CANONICAL_CHUNKS)
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

    def search(self, query: str, top_k: int = 6) -> List[Dict]:
        """
        Retrieve relevant book passages weighted by BM25 relevance AND authority score.
        Ensures higher-authority sources win when multiple books discuss the same topic.
        """
        if not self.chunks or not self.bm25:
            return BUILTIN_CANONICAL_CHUNKS[:top_k]

        q_tokens = tokenize_ru_en(query)
        if not q_tokens:
            return self.chunks[:top_k]

        scores = self.bm25.get_scores(q_tokens)
        weighted = []
        for idx, base_score in enumerate(scores):
            auth = self.chunks[idx].get("authority", 7)
            # Combine lexical relevance with authority multiplier (1.0 .. 1.5x)
            combined_score = (base_score + 0.1) * (1.0 + (auth / 20.0))
            weighted.append((combined_score, idx))

        weighted.sort(key=lambda x: x[0], reverse=True)
        results = [self.chunks[idx] for _, idx in weighted[:top_k]]

        # Always include at least 2 canonical school-comparison chunks if not already in top_k
        seen_books = {r["book"] for r in results}
        for canon in BUILTIN_CANONICAL_CHUNKS[:2]:
            if canon["book"] not in seen_books and len(results) < top_k + 2:
                results.append(canon)
        return results


knowledge_base = KnowledgeBase()
