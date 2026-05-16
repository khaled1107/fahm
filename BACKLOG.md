# Fahm — Backlog & Known Issues
Last updated: Apr 17, 2026

## Current State
- All 114 surahs live at tryfahm.com/reader (English + Bangla)
- Landing page at tryfahm.com with EN/BN toggle
- Supabase backend, Netlify proxy (rate limiting, key hidden server-side)
- Google Auth working, progress sync working
- Feedback form working, stored in fahm_feedback table

---

## 🔴 Must Fix Before Public Launch

### Remaining UI issues from Apr 17 session (needs testing after latest deploy)
- Sidebar "THE QURAN · 114 SURAHS" label — verify fully removed
- Hamburger button position on desktop — needs more testing
- Feedback button on mobile — verify not overlapping after latest deploy
- Juz breadcrumb ("Juz 1 · Al-Fatihah") — verify working

---

## 🟡 Queued (Next Sprint)

### Email notification on feedback submission
- Send email to khaled1107@gmail.com when feedback is submitted
- Include: feedback text, surah, user email, timestamp
- Options: Supabase Edge Function + Resend, or Netlify Function
- Workaround: check Supabase fahm_feedback table manually

### Fix English content minor duplicates
- Surahs 2, 4, 46 have minor duplicate sections
- Run: python3 dedupe_comprehension.py --apply then re-migrate

---

## 🟢 Backlog (Future)

### Additional reciters
- Omar Hisham Al Arabi, Abu Bakr Shatri, Yasser Al Dosari, Fares Abbad, Mansour Al-Salimi

### Word-level Arabic exploration — high effort
### Tajweed highlighting — high effort
### Native mobile app — post-web-launch
### Per-surah URL routing (tryfahm.com/reader/2)
### Makki/Madani discoverability improvements

---

## ✅ Completed (Apr 17, 2026)

- All 114 surahs Bangla content generated, validated, migrated
- Landing page with EN/BN toggle, language persists to reader
- Reader at tryfahm.com/reader, landing at tryfahm.com
- Netlify proxy with rate limiting
- Feedback stored in Supabase
- GA: landing_page_view, bismillah_clicked, landing_lang_switch
- Juz breadcrumb, sidebar label removed, shimmer loading
- Feedback icon-only on mobile, Feedback link in footer
- Hamburger X/☰ toggle on desktop
- Single-line sidebar surah items

---

## Deploy workflow
```bash
python3 build_beta.py
cp fahm_beta.html dist/reader.html
cp landing.html dist/index.html
netlify deploy --dir=dist          # preview first
netlify deploy --prod --dir=dist   # then production
```

## Key files
- fahm_reader_v2.html — reader template
- landing.html — landing page
- netlify/functions/supabase-proxy.js — proxy
- netlify.toml — routing
- build_beta.py, migrate_to_supabase.py
- validate_bn.py, dedupe_comprehension_bn.py
