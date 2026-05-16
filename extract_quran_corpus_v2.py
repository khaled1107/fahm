"""
Fahm Corpus Extractor v2
========================
Extracts Quran translations, Arabic text, chapter info, and tafsir
from the Quran Foundation API (v4).

Usage:
    1. Set environment variables:
        export QF_CLIENT_ID="your_client_id"
        export QF_CLIENT_SECRET="your_client_secret"
        export QF_ENV="production"

    2. Run:
        python3 extract_quran_corpus.py

    3. Output will be saved to ./corpus/ directory as JSON files.
"""

import os
import re
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timezone

import requests
from requests.auth import HTTPBasicAuth

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ABDEL_HALEEM_ID = 85
SAHIH_INTL_ID = 20
TRANSLATION_IDS = [ABDEL_HALEEM_ID, SAHIH_INTL_ID]
TRANSLATION_NAMES = {85: "abdel_haleem", 20: "sahih_international"}

TOTAL_SURAHS = 114
PER_PAGE = 50
REQUEST_DELAY = 0.5
OUTPUT_DIR = Path("./corpus")

ENV_CONFIG = {
    "prelive": {
        "auth_url": "https://prelive-oauth2.quran.foundation",
        "api_url": "https://apis-prelive.quran.foundation",
    },
    "production": {
        "auth_url": "https://oauth2.quran.foundation",
        "api_url": "https://apis.quran.foundation",
    },
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fahm")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def get_access_token(client_id: str, client_secret: str, auth_url: str) -> str:
    log.info("Requesting access token from %s ...", auth_url)
    resp = requests.post(
        f"{auth_url}/oauth2/token",
        auth=HTTPBasicAuth(client_id, client_secret),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials", "scope": "content"},
        timeout=30,
    )
    resp.raise_for_status()
    token_data = resp.json()
    log.info("Access token acquired (expires in %s seconds)", token_data.get("expires_in", "unknown"))
    return token_data["access_token"]


# ---------------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------------

class QuranAPI:
    def __init__(self, api_url: str, access_token: str, client_id: str):
        self.base = f"{api_url}/content/api/v4"
        self.session = requests.Session()
        self.session.headers.update({
            "x-auth-token": access_token,
            "x-client-id": client_id,
        })

    def _get(self, path: str, params: dict = None) -> dict:
        url = f"{self.base}{path}"
        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=30)
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 5))
                    log.warning("Rate limited. Waiting %d seconds...", wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                time.sleep(REQUEST_DELAY)
                return resp.json()
            except requests.exceptions.RequestException as e:
                if attempt < 2:
                    log.warning("Request failed (%s), retrying in %ds...", e, 2 ** attempt)
                    time.sleep(2 ** attempt)
                else:
                    raise
        return {}

    def list_chapters(self) -> list:
        return self._get("/chapters").get("chapters", [])

    def get_chapter_info(self, chapter_number: int) -> dict:
        return self._get(f"/chapters/{chapter_number}/info").get("chapter_info", {})

    def list_translations(self) -> list:
        return self._get("/resources/translations").get("translations", [])

    def list_tafsirs(self) -> list:
        return self._get("/resources/tafsirs").get("tafsirs", [])

    def get_verses_with_translations(self, chapter_number: int, translation_ids: list) -> list:
        """Fetch verses with inline translations — single call per page."""
        trans_param = ",".join(str(tid) for tid in translation_ids)
        all_verses = []
        page = 1
        while True:
            data = self._get(
                f"/verses/by_chapter/{chapter_number}",
                params={
                    "translations": trans_param,
                    "per_page": PER_PAGE,
                    "page": page,
                },
            )
            verses = data.get("verses", [])
            all_verses.extend(verses)
            pagination = data.get("pagination", {})
            next_page = pagination.get("next_page")
            if next_page and next_page > page:
                page = next_page
            else:
                break
        return all_verses

    def get_arabic_text(self, chapter_number: int) -> list:
        """Fetch Arabic Uthmani script."""
        all_verses = []
        page = 1
        while True:
            data = self._get(
                "/quran/verses/uthmani",
                params={"chapter_number": chapter_number, "page": page},
            )
            verses = data.get("verses", [])
            all_verses.extend(verses)
            pagination = data.get("pagination", {})
            next_page = pagination.get("next_page")
            if next_page and next_page > page:
                page = next_page
            else:
                break
        return all_verses

    def get_tafsir_for_chapter(self, tafsir_id: int, chapter_number: int) -> list:
        """Try multiple endpoint patterns for tafsir."""
        for pattern in [
            f"/tafsirs/{tafsir_id}/by_chapter/{chapter_number}",
            f"/tafsirs/{tafsir_id}/{chapter_number}",
        ]:
            try:
                data = self._get(pattern, params={"per_page": PER_PAGE})
                tafsirs = data.get("tafsirs", [])
                if tafsirs:
                    return tafsirs
            except Exception:
                continue
        return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def save_json(data, filepath: Path):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info("  Saved: %s", filepath)


def strip_html(text: str) -> str:
    """Remove HTML tags like <sup foot_note=...>1</sup> from translation text."""
    if not text:
        return ""
    text = re.sub(r'<sup[^>]*>\d+</sup>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


# ---------------------------------------------------------------------------
# Extraction Pipeline
# ---------------------------------------------------------------------------

def extract_corpus(api: QuranAPI):
    timestamp = datetime.now(timezone.utc).isoformat()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Step 1: Discover resources
    # ------------------------------------------------------------------
    log.info("=" * 60)
    log.info("STEP 1: Discovering available resources")
    log.info("=" * 60)

    translations = api.list_translations()
    save_json(translations, OUTPUT_DIR / "meta" / "available_translations.json")
    log.info("Found %d translations", len(translations))

    tafsirs_list = api.list_tafsirs()
    save_json(tafsirs_list, OUTPUT_DIR / "meta" / "available_tafsirs.json")
    log.info("Found %d tafsirs", len(tafsirs_list))

    english_tafsir_ids = {}
    for t in tafsirs_list:
        if (t.get("language_name", "") or "").lower() == "english":
            english_tafsir_ids[t["id"]] = t.get("name", f"tafsir_{t['id']}")
            log.info("  English tafsir: id=%d, name='%s'", t["id"], t.get("name", ""))

    # Use first English tafsir (usually Ibn Kathir)
    tafsir_ids = dict(list(english_tafsir_ids.items())[:1])

    # ------------------------------------------------------------------
    # Step 2: Extract chapter metadata
    # ------------------------------------------------------------------
    log.info("=" * 60)
    log.info("STEP 2: Extracting chapter metadata")
    log.info("=" * 60)

    chapters = api.list_chapters()
    save_json(chapters, OUTPUT_DIR / "meta" / "chapters.json")
    log.info("Extracted metadata for %d chapters", len(chapters))

    chapter_infos = {}
    for ch in chapters:
        ch_num = ch["id"]
        log.info("  Chapter %d: %s", ch_num, ch.get("name_simple", ""))
        info = api.get_chapter_info(ch_num)
        chapter_infos[ch_num] = info
    save_json(chapter_infos, OUTPUT_DIR / "meta" / "chapter_infos.json")

    # ------------------------------------------------------------------
    # Step 3: Extract verse-by-verse corpus
    # ------------------------------------------------------------------
    log.info("=" * 60)
    log.info("STEP 3: Extracting verse-by-verse corpus")
    log.info("=" * 60)

    full_corpus = []
    tafsir_available = None

    for ch in chapters:
        ch_num = ch["id"]
        ch_name = ch.get("name_simple", f"Chapter {ch_num}")
        ch_name_arabic = ch.get("name_arabic", "")
        revelation_place = ch.get("revelation_place", "")
        verses_count = ch.get("verses_count", 0)

        log.info("-" * 40)
        log.info("Chapter %d/%d: %s (%s) - %d verses",
                 ch_num, TOTAL_SURAHS, ch_name, revelation_place, verses_count)

        # 3a. Arabic text
        log.info("  Fetching Arabic text...")
        arabic_verses = api.get_arabic_text(ch_num)
        arabic_map = {}
        for v in arabic_verses:
            arabic_map[v.get("verse_key", "")] = v.get("text_uthmani", "")

        # 3b. Verses with both translations in one call
        log.info("  Fetching translations (Abdel Haleem + Sahih International)...")
        verses_data = api.get_verses_with_translations(ch_num, TRANSLATION_IDS)

        # 3c. Tafsir
        tafsir_map = {}
        if tafsir_ids and tafsir_available is not False:
            for tafsir_id, tafsir_name in tafsir_ids.items():
                log.info("  Fetching tafsir: %s (id=%d)...", tafsir_name, tafsir_id)
                try:
                    tafsir_verses = api.get_tafsir_for_chapter(tafsir_id, ch_num)
                    if tafsir_verses:
                        tafsir_available = True
                        for tv in tafsir_verses:
                            key = tv.get("verse_key", "")
                            if key:
                                tafsir_map[key] = tv.get("text", "")
                    elif tafsir_available is None:
                        log.warning("  Tafsir endpoint not available, skipping for remaining chapters")
                        tafsir_available = False
                except Exception as e:
                    log.warning("  Tafsir fetch failed: %s", e)
                    if tafsir_available is None:
                        tafsir_available = False

        # 3d. Assemble records
        chapter_verses = []
        for v in verses_data:
            verse_key = v.get("verse_key", "")
            verse_number = v.get("verse_number", 0)

            # Extract translations by resource_id
            trans_haleem = ""
            trans_sahih = ""
            for t in v.get("translations", []):
                rid = t.get("resource_id")
                clean_text = strip_html(t.get("text", ""))
                if rid == ABDEL_HALEEM_ID:
                    trans_haleem = clean_text
                elif rid == SAHIH_INTL_ID:
                    trans_sahih = clean_text

            record = {
                "verse_key": verse_key,
                "surah_number": ch_num,
                "surah_name": ch_name,
                "surah_name_arabic": ch_name_arabic,
                "verse_number": verse_number,
                "revelation_type": revelation_place,
                "juz_number": v.get("juz_number"),
                "hizb_number": v.get("hizb_number"),
                "page_number": v.get("page_number"),
                "arabic_uthmani": arabic_map.get(verse_key, ""),
                "translation_abdel_haleem": trans_haleem,
                "translation_sahih_international": trans_sahih,
                "tafsir": tafsir_map.get(verse_key, ""),
            }

            chapter_verses.append(record)
            full_corpus.append(record)

        log.info("  Assembled %d verse records", len(chapter_verses))

        # Save per-chapter file
        safe_name = ch_name.lower().replace("'", "").replace("-", "_").replace(" ", "_")
        save_json(
            {
                "chapter": ch_num,
                "name": ch_name,
                "name_arabic": ch_name_arabic,
                "revelation_place": revelation_place,
                "verses_count": verses_count,
                "verses": chapter_verses,
            },
            OUTPUT_DIR / "chapters" / f"chapter_{ch_num:03d}_{safe_name}.json",
        )

    # ------------------------------------------------------------------
    # Step 4: Save complete corpus
    # ------------------------------------------------------------------
    log.info("=" * 60)
    log.info("STEP 4: Saving complete corpus")
    log.info("=" * 60)

    corpus_metadata = {
        "project": "Fahm",
        "extracted_at": timestamp,
        "total_verses": len(full_corpus),
        "total_chapters": TOTAL_SURAHS,
        "translations": {
            str(ABDEL_HALEEM_ID): "M.A.S. Abdel Haleem",
            str(SAHIH_INTL_ID): "Sahih International",
        },
        "tafsirs": {str(k): v for k, v in tafsir_ids.items()},
        "source": "Quran Foundation API v4",
    }

    save_json(corpus_metadata, OUTPUT_DIR / "corpus_metadata.json")
    save_json(full_corpus, OUTPUT_DIR / "full_corpus.json")

    log.info("=" * 60)
    log.info("EXTRACTION COMPLETE")
    log.info("  Total verses extracted: %d", len(full_corpus))
    log.info("  Output directory: %s", OUTPUT_DIR.resolve())
    log.info("=" * 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    client_id = os.environ.get("QF_CLIENT_ID")
    client_secret = os.environ.get("QF_CLIENT_SECRET")
    env = os.environ.get("QF_ENV", "prelive")

    if not client_id or not client_secret:
        log.error(
            "Missing credentials. Set QF_CLIENT_ID and QF_CLIENT_SECRET.\n"
            "  export QF_CLIENT_ID=\"your_client_id\"\n"
            "  export QF_CLIENT_SECRET=\"your_client_secret\"\n"
            "  export QF_ENV=\"production\"\n"
        )
        sys.exit(1)

    if env not in ENV_CONFIG:
        log.error("QF_ENV must be 'prelive' or 'production', got '%s'", env)
        sys.exit(1)

    config = ENV_CONFIG[env]
    log.info("Environment: %s", env)
    log.info("API base: %s", config["api_url"])

    access_token = get_access_token(client_id, client_secret, config["auth_url"])
    api = QuranAPI(config["api_url"], access_token, client_id)

    log.info("Testing connection...")
    chapters = api.list_chapters()
    if chapters:
        log.info("Connected! Found %d chapters.", len(chapters))
    else:
        log.error("Connection failed. Check credentials.")
        sys.exit(1)

    extract_corpus(api)


if __name__ == "__main__":
    main()
