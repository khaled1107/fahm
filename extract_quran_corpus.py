"""
Fahm Corpus Extractor
=====================
Extracts Quran translations, Arabic text, chapter info, and tafsir
from the Quran Foundation API (v4).

Usage:
    1. Set environment variables:
        export QF_CLIENT_ID="your_client_id"
        export QF_CLIENT_SECRET="your_client_secret"
        export QF_ENV="production"  # or "prelive" for testing

    2. Run:
        python3 extract_quran_corpus.py

    3. Output will be saved to ./corpus/ directory as JSON files.
"""

import os
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

# Translation resource IDs
ABDEL_HALEEM_ID = 85        # M.A.S. Abdel Haleem
SAHIH_INTL_ID = 20          # Sahih International

TRANSLATION_IDS = {
    ABDEL_HALEEM_ID: "abdel_haleem",
    SAHIH_INTL_ID: "sahih_international",
}

TOTAL_SURAHS = 114

# Rate limiting: seconds between API calls
REQUEST_DELAY = 0.5

# Output directory
OUTPUT_DIR = Path("./corpus")

# Environment config
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

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

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
    """Exchange client credentials for an access token."""
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
    access_token = token_data["access_token"]
    expires_in = token_data.get("expires_in", "unknown")
    log.info("Access token acquired (expires in %s seconds)", expires_in)
    return access_token


# ---------------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------------


class QuranAPI:
    """Simple wrapper around Quran Foundation Content API v4."""

    def __init__(self, api_url: str, access_token: str, client_id: str):
        self.api_url = api_url
        self.session = requests.Session()
        self.session.headers.update(
            {
                "x-auth-token": access_token,
                "x-client-id": client_id,
            }
        )

    def _get(self, path: str, params: dict = None) -> dict:
        """Make a GET request with rate limiting and retry."""
        url = f"{self.api_url}/content/api/v4{path}"
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
                    log.warning("Request failed (%s), retrying...", e)
                    time.sleep(2 ** attempt)
                else:
                    raise
        return {}

    # --- Discovery endpoints ---

    def list_chapters(self) -> list:
        """Get all 114 chapter metadata."""
        data = self._get("/chapters")
        return data.get("chapters", [])

    def get_chapter_info(self, chapter_number: int) -> dict:
        """Get detailed info for a chapter (intro text, background, etc.)."""
        data = self._get(f"/chapters/{chapter_number}/info")
        return data.get("chapter_info", {})

    def list_translations(self) -> list:
        """Discover all available translation resources."""
        data = self._get("/resources/translations")
        return data.get("translations", [])

    def list_tafsirs(self) -> list:
        """Discover all available tafsir resources."""
        data = self._get("/resources/tafsirs")
        return data.get("tafsirs", [])

    # --- Content endpoints ---

    def get_translation(self, resource_id: int, chapter_number: int) -> list:
        """Get translation for all verses in a chapter."""
        all_translations = []
        page = 1
        while True:
            data = self._get(
                f"/translations/{resource_id}/{chapter_number}",
                params={"page": page},
            )
            translations = data.get("translations", [])
            all_translations.extend(translations)
            pagination = data.get("pagination", {})
            next_page = pagination.get("next_page")
            if next_page and next_page > page:
                page = next_page
            else:
                break
        return all_translations

    def get_tafsir(self, resource_id: int, chapter_number: int) -> list:
        """Get tafsir for all verses in a chapter."""
        all_tafsirs = []
        page = 1
        while True:
            data = self._get(
                f"/tafsirs/{resource_id}/{chapter_number}",
                params={"page": page},
            )
            tafsirs = data.get("tafsirs", [])
            all_tafsirs.extend(tafsirs)
            pagination = data.get("pagination", {})
            next_page = pagination.get("next_page")
            if next_page and next_page > page:
                page = next_page
            else:
                break
        return all_tafsirs

    def get_quran_text(self, chapter_number: int, script: str = "uthmani") -> list:
        """Get Arabic Quran text for a chapter."""
        all_verses = []
        page = 1
        while True:
            data = self._get(
                f"/quran/verses/{script}",
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


# ---------------------------------------------------------------------------
# Extraction Pipeline
# ---------------------------------------------------------------------------


def save_json(data, filepath: Path):
    """Save data as formatted JSON."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info("  Saved: %s", filepath)


def extract_corpus(api: QuranAPI):
    """Main extraction pipeline."""

    timestamp = datetime.now(timezone.utc).isoformat()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Step 1: Discover available resources
    # ------------------------------------------------------------------
    log.info("=" * 60)
    log.info("STEP 1: Discovering available resources")
    log.info("=" * 60)

    translations = api.list_translations()
    save_json(translations, OUTPUT_DIR / "meta" / "available_translations.json")
    log.info("Found %d translations", len(translations))

    # Find translation IDs by name
    sahih_id = None
    haleem_id = None
    for t in translations:
        name_lower = (t.get("name", "") or "").lower()
        slug_lower = (t.get("slug", "") or "").lower()
        if "haleem" in name_lower or "haleem" in slug_lower:
            haleem_id = t["id"]
            log.info("  Found Abdel Haleem: id=%d, name='%s'", t["id"], t["name"])
        if "sahih" in slug_lower or "saheeh" in name_lower:
            sahih_id = t["id"]
            log.info("  Found Sahih Intl: id=%d, name='%s'", t["id"], t["name"])

    if not haleem_id:
        log.warning("Could not find Abdel Haleem, using default ID %d", ABDEL_HALEEM_ID)
        haleem_id = ABDEL_HALEEM_ID
    if not sahih_id:
        log.warning("Could not find Sahih International, using default ID %d", SAHIH_INTL_ID)
        sahih_id = SAHIH_INTL_ID

    translation_map = {
        haleem_id: "abdel_haleem",
        sahih_id: "sahih_international",
    }

    tafsirs = api.list_tafsirs()
    save_json(tafsirs, OUTPUT_DIR / "meta" / "available_tafsirs.json")
    log.info("Found %d tafsirs", len(tafsirs))

    # Find English tafsirs
    english_tafsirs = {}
    for t in tafsirs:
        if (t.get("language_name", "") or "").lower() == "english":
            english_tafsirs[t["id"]] = t.get("name", t.get("slug", f"tafsir_{t['id']}"))
            log.info("  English tafsir: id=%d, name='%s'", t["id"], t.get("name", ""))

    # Pick the first 2 English tafsirs
    tafsir_ids = dict(list(english_tafsirs.items())[:2])

    # ------------------------------------------------------------------
    # Step 2: Extract chapter metadata
    # ------------------------------------------------------------------
    log.info("=" * 60)
    log.info("STEP 2: Extracting chapter metadata")
    log.info("=" * 60)

    chapters = api.list_chapters()
    save_json(chapters, OUTPUT_DIR / "meta" / "chapters.json")
    log.info("Extracted metadata for %d chapters", len(chapters))

    # Also get chapter info (introductions, background)
    chapter_infos = {}
    for ch in chapters:
        ch_num = ch["id"]
        log.info("  Getting info for chapter %d: %s", ch_num, ch.get("name_simple", ""))
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

    for ch in chapters:
        ch_num = ch["id"]
        ch_name = ch.get("name_simple", f"Chapter {ch_num}")
        ch_name_arabic = ch.get("name_arabic", "")
        revelation_place = ch.get("revelation_place", "")
        verses_count = ch.get("verses_count", 0)

        log.info("-" * 40)
        log.info("Chapter %d: %s (%s) - %d verses", ch_num, ch_name, revelation_place, verses_count)

        # 3a. Arabic text
        log.info("  Fetching Arabic text...")
        arabic_verses = api.get_quran_text(ch_num)
        arabic_map = {}
        for v in arabic_verses:
            key = v.get("verse_key", "")
            arabic_map[key] = v.get("text_uthmani", "")

        # 3b. Translations
        translations_data = {}
        for res_id, res_name in translation_map.items():
            log.info("  Fetching translation: %s (id=%d)...", res_name, res_id)
            trans = api.get_translation(res_id, ch_num)
            for t in trans:
                key = t.get("verse_key", "")
                if key not in translations_data:
                    translations_data[key] = {}
                translations_data[key][res_name] = t.get("text", "")

        # 3c. Tafsir (if available)
        tafsir_data = {}
        for res_id, res_name in tafsir_ids.items():
            log.info("  Fetching tafsir: %s (id=%d)...", res_name, res_id)
            try:
                tafs = api.get_tafsir(res_id, ch_num)
                for t in tafs:
                    key = t.get("verse_key", "")
                    if key not in tafsir_data:
                        tafsir_data[key] = {}
                    tafsir_data[key][res_name] = t.get("text", "")
            except Exception as e:
                log.warning("  Could not fetch tafsir %s for ch %d: %s", res_name, ch_num, e)

        # 3d. Assemble per-verse records
        chapter_verses = []
        for verse_num in range(1, verses_count + 1):
            verse_key = f"{ch_num}:{verse_num}"

            record = {
                "verse_key": verse_key,
                "surah_number": ch_num,
                "surah_name": ch_name,
                "surah_name_arabic": ch_name_arabic,
                "verse_number": verse_num,
                "revelation_type": revelation_place,
                "arabic_uthmani": arabic_map.get(verse_key, ""),
                "translation_abdel_haleem": translations_data.get(verse_key, {}).get("abdel_haleem", ""),
                "translation_sahih_international": translations_data.get(verse_key, {}).get("sahih_international", ""),
            }

            # Add tafsir fields
            for res_id, res_name in tafsir_ids.items():
                safe_key = res_name.lower().replace(" ", "_").replace("-", "_").replace("'", "")[:50]
                record[f"tafsir_{safe_key}"] = tafsir_data.get(verse_key, {}).get(res_name, "")

            chapter_verses.append(record)
            full_corpus.append(record)

        # Save per-chapter file
        save_json(
            {
                "chapter": ch_num,
                "name": ch_name,
                "name_arabic": ch_name_arabic,
                "revelation_place": revelation_place,
                "verses_count": verses_count,
                "verses": chapter_verses,
            },
            OUTPUT_DIR / "chapters" / f"chapter_{ch_num:03d}_{ch_name.lower().replace('-', '_').replace(' ', '_')}.json",
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
        "translations": {str(k): v for k, v in translation_map.items()},
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
    # Load credentials from environment
    client_id = os.environ.get("QF_CLIENT_ID")
    client_secret = os.environ.get("QF_CLIENT_SECRET")
    env = os.environ.get("QF_ENV", "prelive")

    if not client_id or not client_secret:
        log.error(
            "Missing credentials. Set QF_CLIENT_ID and QF_CLIENT_SECRET environment variables.\n"
            "Example:\n"
            '  export QF_CLIENT_ID="your_client_id"\n'
            '  export QF_CLIENT_SECRET="your_client_secret"\n'
            '  export QF_ENV="production"  # or "prelive"\n'
        )
        sys.exit(1)

    if env not in ENV_CONFIG:
        log.error("QF_ENV must be 'prelive' or 'production', got '%s'", env)
        sys.exit(1)

    config = ENV_CONFIG[env]
    log.info("Environment: %s", env)
    log.info("API base: %s", config["api_url"])

    # Authenticate
    access_token = get_access_token(client_id, client_secret, config["auth_url"])

    # Create API client
    api = QuranAPI(config["api_url"], access_token, client_id)

    # Test connection
    log.info("Testing connection with chapters endpoint...")
    chapters = api.list_chapters()
    if chapters:
        log.info("Connection successful! Found %d chapters.", len(chapters))
    else:
        log.error("Could not retrieve chapters. Check credentials and try again.")
        sys.exit(1)

    # Run extraction
    extract_corpus(api)


if __name__ == "__main__":
    main()
