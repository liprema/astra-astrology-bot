"""
Tarot Book Library Loader, Cloud Downloader (Yandex.Disk),
Authority Ranker, and Hybrid BM25 Retriever for ARCANA ("Аркана").

Prioritizes canonical works when traditions conflict:
- Tier 10: Arthur Edward Waite (Pictorial Key to the Tarot), Aleister Crowley (The Book of Thoth),
  Golden Dawn (Mathers, Regardie), Paul Foster Case (B.O.T.A.), Papus (Tarot of the Bohemians),
  Alejandro Jodorowsky (Way of Tarot — Marseille), Rachel Pollack (78 Degrees of Wisdom).
- Tier 9: Mary K. Greer, Hajo Banzhaf, Theresa Reed, Jungian / Archetypal Tarot (Sallie Nichols).
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
        ["уэйт", "waite", "кроули", "crowley", "книга тота", "book of thoth",
         "золотая заря", "golden dawn", "регарди", "regardie", "мазерс", "mathers",
         "папюс", "papus", "цыганское таро", "ходоровски", "jodorowsky", "марсельск",
         "рэйчел поллак", "pollack", "78 степеней", "пол фостер кейс", "b.o.t.a"],
        10,
        "Первоисточники и Высший Канон Таро (Английская школа Уэйта, Таро Тота Кроули, Золотая Заря, Марсельская и Французская традиция)",
    ),
    (
        ["банцхаф", "banzhaf", "мэри грир", "greer", "котельникова", "колесов",
         "хшановская", "юнгианск", "архетип", "салли николс", "алексей лобанов",
         "феликс эльдемуров", "нина фролова", "константин лаво"],
        9,
        "Академическая и практическая школа современного Таро и психологического анализа",
    ),
]


def detect_authority_and_school(filename: str, text_sample: str) -> Tuple[int, str]:
    combined = (filename + " " + text_sample[:2500]).lower()
    for keywords, score, school_label in AUTHORITY_RULES:
        for kw in keywords:
            if kw in combined:
                return score, school_label
    return 7, "Общая литература по Таро"


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
                fname = meta.get("name", "yandex_tarot_book.pdf")
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


BUILTIN_CANONICAL_TAROT_CHUNKS = [
    {
        "book": "Канонический свод Таро: Сравнение Школы Уэйта (RWS), Системы Тота Кроули и Марсельского/Французского Таро",
        "school": "Сравнительный канон: Английская школа (Уэйт / Золотая Заря), Телемитская школа (Кроули) и Марсельская/Французская традиция (Папюс / Ходоровски)",
        "authority": 10,
        "text": (
            "КЛЮЧЕВЫЕ РАЗЛИЧИЯ ШКОЛ ТАРО (ОБЯЗАТЕЛЬНО УКАЗЫВАТЬ ПРИ ТРАКТОВКЕ):\n"
            "1. НУМЕРАЦИЯ И СООТВЕТСТВИЯ: В школе Артура Эдварда Уэйта (RWS) VIII аркан — Сила (Лев), а XI аркан — Справедливость (Весы). "
            "В Марсельском Таро, Французской школе (Папюс, Элифас Леви) и в Таро Тота Алистера Кроули сохранена традиционная нумерация: "
            "VIII аркан — Правосудие/Регулирование, а XI аркан — Сила/Вожделение. Кроме того, во Французской школе Папюса Шут (0/21) "
            "располагается между Судом (XX) и Миром (XXI) и соотносится с буквой Шин.\n"
            "2. МЛАДШИЕ АРКАНЫ: У Уэйта все номерные карты (2–10) снабжены сюжетными рисунками Памелы Колман Смит. "
            "В Таро Тота Кроули каждая номерная карта имеет строгое каббалистическое имя по сефире и астрологическому декану (например, "
            "6 Мечей — «Наука», Меркурий в Водолее; 2 Кубков — «Любовь», Венера в Раке). В Марсельском Таро номерные карты не имеют бытовых сцен "
            "и трактуются через сакральную геометрию чисел Пифагора и динамику стихии.\n"
            "3. ПРИДВОРНЫЕ КАРТЫ (ДВОР): У Уэйта — Паж, Рыцарь, Королева, Король. В Таро Тота Кроули — Принцесса (Земля масти), "
            "Принц на колеснице (Воздух масти, соответствует Рыцарю Уэйта), Королева (Вода масти) и Рыцарь на коне (Огонь масти, соответствует Королю Уэйта)."
        ),
    },
    {
        "book": "Канонический свод Таро: Прямые и Перевёрнутые карты, Квинтэссенция, Дно колоды и Элементальные достоинства",
        "school": "Методология чтения раскладов (Орден Золотой Зари, Мэри Грир, Хайо Банцхаф)",
        "authority": 10,
        "text": (
            "ТЕХНИКИ ГЛУБИННОГО ЧТЕНИЯ РАСКЛАДА:\n"
            "1. ПЕРЕВЁРНУТЫЕ КАРТЫ: В классической школе Уэйта и Мэри Грир перевёрнутая позиция читается как: "
            "а) блокированная, задержанная или ослабленная энергия прямой карты; б) теневая гиперкомпенсация (избыток качества); "
            "в) внутренний, скрытый или неосознаваемый процесс; г) возврат к уроку предыдущего аркана. "
            "Альтернативное мнение (Таро Тота Кроули и ряд мастеров Золотой Зари): перевёрнутые карты не используются механически, "
            "а теневое или ослабленное проявление карты определяется через Элементальные достоинства (соседние карты враждебных стихий: Огонь гасит Воду, Воздух конфликтует с Землёй).\n"
            "2. ДНО КОЛОДЫ (Теневая карта под срезом): Показывает бессознательную мотивацию кверента, истинную подоплёку вопроса или невысказанный страх, "
            "который влияет на весь расклад изнутри.\n"
            "3. КВИНТЭССЕНЦИЯ РАСКЛАДА (по Хайо Банцхафу и пифагорейской традиции): Теософская сумма всех выпавших арканов, сведённая к числу Старшего Аркана (от 1 до 21). "
            "Даёт высший синтез и практический совет: какую архетипическую позицию нужно занять кверенту, чтобы наилучшим образом пройти через ситуацию."
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
        self.chunks = list(BUILTIN_CANONICAL_TAROT_CHUNKS)
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
        if not self.chunks or not self.bm25:
            return BUILTIN_CANONICAL_TAROT_CHUNKS[:top_k]

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
        for canon in BUILTIN_CANONICAL_TAROT_CHUNKS:
            if canon["book"] not in seen_books:
                results.append(canon)
        return results


knowledge_base = KnowledgeBase()
