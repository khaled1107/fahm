# Fahm Corpus Extractor

Extracts the Quran corpus from the Quran Foundation API for the Fahm project.

## What it extracts

For each of the 6,236 verses in the Quran:
- **Arabic text** (Uthmani script)
- **The Clear Quran** translation (Dr. Mustafa Khattab) — primary translation
- **Sahih International** translation — secondary reference
- **Tafsir** (English, e.g. Ibn Kathir) — contextual commentary
- **Chapter metadata** — name, revelation type (Makki/Madani), verse count, chapter introductions

## Output structure

```
corpus/
├── corpus_metadata.json          # Extraction metadata
├── full_corpus.json              # All 6,236 verses in one file
├── meta/
│   ├── chapters.json             # Chapter list with metadata
│   ├── chapter_infos.json        # Chapter introductions/background
│   ├── available_translations.json
│   └── available_tafsirs.json
└── chapters/
    ├── chapter_001_al_fatihah.json
    ├── chapter_002_al_baqarah.json
    └── ... (114 files)
```

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your Quran Foundation API credentials
#    IMPORTANT: Regenerate these if you've ever shared them.
export QF_CLIENT_ID="your_client_id_here"
export QF_CLIENT_SECRET="your_client_secret_here"

# 3. Choose environment
#    Use "prelive" for testing (limited data, all features)
#    Use "production" for full extraction (all 114 surahs)
export QF_ENV="prelive"
```

## Usage

```bash
# Test with prelive first
export QF_ENV="prelive"
python extract_quran_corpus.py

# Once verified, run full extraction
export QF_ENV="production"
python extract_quran_corpus.py
```

## Per-verse record format

Each verse record looks like this:

```json
{
  "verse_key": "2:255",
  "surah_number": 2,
  "surah_name": "Al-Baqarah",
  "surah_name_arabic": "البقرة",
  "verse_number": 255,
  "revelation_type": "madinah",
  "arabic_uthmani": "ٱللَّهُ لَآ إِلَٰهَ إِلَّا هُوَ ٱلْحَىُّ ٱلْقَيُّومُ ...",
  "translation_clear_quran": "Allah! There is no god ˹worthy of worship˺ except Him, the Ever-Living ...",
  "translation_sahih_international": "Allah - there is no deity except Him, the Ever-Living ...",
  "tafsir_ibn_kathir": "..."
}
```

## Rate limiting

The script includes a 0.5 second delay between API calls and handles
429 (rate limit) responses with automatic retry. Full extraction of all
114 surahs with two translations + tafsir takes approximately 15-25 minutes.

## Next steps after extraction

1. Review the output in `corpus/` to verify data quality
2. Check `meta/available_translations.json` and `meta/available_tafsirs.json`
   to see what other resources you might want to include
3. Use `full_corpus.json` as input for your vector database embedding pipeline
