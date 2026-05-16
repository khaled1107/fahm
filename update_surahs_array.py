#!/usr/bin/env python3
"""
update_surahs_array.py
Replaces the SURAHS array in fahm_reader_v2.html with the full 114-surah version.
Run from your Fahm folder.
"""

from pathlib import Path

TEMPLATE = Path("fahm_reader_v2.html")

NEW_SURAHS = """const SURAHS = [
  { number: 1,   name: "Al-Fatihah",     arabic: "الفاتحة",      meaning: "The Opening",              verses: 7,   type: "Makki" },
  { number: 2,   name: "Al-Baqarah",     arabic: "البقرة",       meaning: "The Cow",                  verses: 286, type: "Madani" },
  { number: 3,   name: "Ali 'Imran",     arabic: "آل عمران",     meaning: "Family of Imran",          verses: 200, type: "Madani" },
  { number: 4,   name: "An-Nisa",        arabic: "النساء",       meaning: "The Women",                verses: 176, type: "Madani" },
  { number: 5,   name: "Al-Ma'idah",     arabic: "المائدة",      meaning: "The Table Spread",         verses: 120, type: "Madani" },
  { number: 6,   name: "Al-An'am",       arabic: "الأنعام",      meaning: "The Cattle",               verses: 165, type: "Makki" },
  { number: 7,   name: "Al-A'raf",       arabic: "الأعراف",      meaning: "The Heights",              verses: 206, type: "Makki" },
  { number: 8,   name: "Al-Anfal",       arabic: "الأنفال",      meaning: "The Spoils of War",        verses: 75,  type: "Madani" },
  { number: 9,   name: "At-Tawbah",      arabic: "التوبة",       meaning: "The Repentance",           verses: 129, type: "Madani" },
  { number: 10,  name: "Yunus",          arabic: "يونس",         meaning: "Jonah",                    verses: 109, type: "Makki" },
  { number: 11,  name: "Hud",            arabic: "هود",          meaning: "Hud",                      verses: 123, type: "Makki" },
  { number: 12,  name: "Yusuf",          arabic: "يوسف",         meaning: "Joseph",                   verses: 111, type: "Makki" },
  { number: 13,  name: "Ar-Ra'd",        arabic: "الرعد",        meaning: "The Thunder",              verses: 43,  type: "Madani" },
  { number: 14,  name: "Ibrahim",        arabic: "إبراهيم",      meaning: "Abraham",                  verses: 52,  type: "Makki" },
  { number: 15,  name: "Al-Hijr",        arabic: "الحجر",        meaning: "The Rocky Tract",          verses: 99,  type: "Makki" },
  { number: 16,  name: "An-Nahl",        arabic: "النحل",        meaning: "The Bee",                  verses: 128, type: "Makki" },
  { number: 17,  name: "Al-Isra",        arabic: "الإسراء",      meaning: "The Night Journey",        verses: 111, type: "Makki" },
  { number: 18,  name: "Al-Kahf",        arabic: "الكهف",        meaning: "The Cave",                 verses: 110, type: "Makki" },
  { number: 19,  name: "Maryam",         arabic: "مريم",         meaning: "Mary",                     verses: 98,  type: "Makki" },
  { number: 20,  name: "Taha",           arabic: "طه",           meaning: "Ta-Ha",                    verses: 135, type: "Makki" },
  { number: 21,  name: "Al-Anbya",       arabic: "الأنبياء",     meaning: "The Prophets",             verses: 112, type: "Makki" },
  { number: 22,  name: "Al-Hajj",        arabic: "الحج",         meaning: "The Pilgrimage",           verses: 78,  type: "Madani" },
  { number: 23,  name: "Al-Mu'minun",    arabic: "المؤمنون",     meaning: "The Believers",            verses: 118, type: "Makki" },
  { number: 24,  name: "An-Nur",         arabic: "النور",        meaning: "The Light",                verses: 64,  type: "Madani" },
  { number: 25,  name: "Al-Furqan",      arabic: "الفرقان",      meaning: "The Criterion",            verses: 77,  type: "Makki" },
  { number: 26,  name: "Ash-Shu'ara",    arabic: "الشعراء",      meaning: "The Poets",                verses: 227, type: "Makki" },
  { number: 27,  name: "An-Naml",        arabic: "النمل",        meaning: "The Ant",                  verses: 93,  type: "Makki" },
  { number: 28,  name: "Al-Qasas",       arabic: "القصص",        meaning: "The Stories",              verses: 88,  type: "Makki" },
  { number: 29,  name: "Al-'Ankabut",    arabic: "العنكبوت",     meaning: "The Spider",               verses: 69,  type: "Makki" },
  { number: 30,  name: "Ar-Rum",         arabic: "الروم",        meaning: "The Romans",               verses: 60,  type: "Makki" },
  { number: 31,  name: "Luqman",         arabic: "لقمان",        meaning: "Luqman",                   verses: 34,  type: "Makki" },
  { number: 32,  name: "As-Sajdah",      arabic: "السجدة",       meaning: "The Prostration",          verses: 30,  type: "Makki" },
  { number: 33,  name: "Al-Ahzab",       arabic: "الأحزاب",      meaning: "The Combined Forces",      verses: 73,  type: "Madani" },
  { number: 34,  name: "Saba",           arabic: "سبأ",          meaning: "Sheba",                    verses: 54,  type: "Makki" },
  { number: 35,  name: "Fatir",          arabic: "فاطر",         meaning: "Originator",               verses: 45,  type: "Makki" },
  { number: 36,  name: "Ya-Sin",         arabic: "يس",           meaning: "Ya-Sin",                   verses: 83,  type: "Makki" },
  { number: 37,  name: "As-Saffat",      arabic: "الصافات",      meaning: "Those Ranged in Ranks",    verses: 182, type: "Makki" },
  { number: 38,  name: "Sad",            arabic: "ص",            meaning: "Sad",                      verses: 88,  type: "Makki" },
  { number: 39,  name: "Az-Zumar",       arabic: "الزمر",        meaning: "The Groups",               verses: 75,  type: "Makki" },
  { number: 40,  name: "Ghafir",         arabic: "غافر",         meaning: "The Forgiver",             verses: 85,  type: "Makki" },
  { number: 41,  name: "Fussilat",       arabic: "فصلت",         meaning: "Explained in Detail",      verses: 54,  type: "Makki" },
  { number: 42,  name: "Ash-Shuraa",     arabic: "الشورى",       meaning: "The Consultation",         verses: 53,  type: "Makki" },
  { number: 43,  name: "Az-Zukhruf",     arabic: "الزخرف",       meaning: "The Ornaments of Gold",    verses: 89,  type: "Makki" },
  { number: 44,  name: "Ad-Dukhan",      arabic: "الدخان",       meaning: "The Smoke",                verses: 59,  type: "Makki" },
  { number: 45,  name: "Al-Jathiyah",    arabic: "الجاثية",      meaning: "The Crouching",            verses: 37,  type: "Makki" },
  { number: 46,  name: "Al-Ahqaf",       arabic: "الأحقاف",      meaning: "The Wind-Curved Sandhills",verses: 35,  type: "Makki" },
  { number: 47,  name: "Muhammad",       arabic: "محمد",         meaning: "Muhammad",                 verses: 38,  type: "Madani" },
  { number: 48,  name: "Al-Fath",        arabic: "الفتح",        meaning: "The Victory",              verses: 29,  type: "Madani" },
  { number: 49,  name: "Al-Hujurat",     arabic: "الحجرات",      meaning: "The Rooms",                verses: 18,  type: "Madani" },
  { number: 50,  name: "Qaf",            arabic: "ق",            meaning: "Qaf",                      verses: 45,  type: "Makki" },
  { number: 51,  name: "Adh-Dhariyat",   arabic: "الذاريات",     meaning: "The Winnowing Winds",      verses: 60,  type: "Makki" },
  { number: 52,  name: "At-Tur",         arabic: "الطور",        meaning: "The Mount",                verses: 49,  type: "Makki" },
  { number: 53,  name: "An-Najm",        arabic: "النجم",        meaning: "The Star",                 verses: 62,  type: "Makki" },
  { number: 54,  name: "Al-Qamar",       arabic: "القمر",        meaning: "The Moon",                 verses: 55,  type: "Makki" },
  { number: 55,  name: "Ar-Rahman",      arabic: "الرحمن",       meaning: "The Beneficent",           verses: 78,  type: "Madani" },
  { number: 56,  name: "Al-Waqi'ah",     arabic: "الواقعة",      meaning: "The Inevitable",           verses: 96,  type: "Makki" },
  { number: 57,  name: "Al-Hadid",       arabic: "الحديد",       meaning: "The Iron",                 verses: 29,  type: "Madani" },
  { number: 58,  name: "Al-Mujadila",    arabic: "المجادلة",     meaning: "The Pleading Woman",       verses: 22,  type: "Madani" },
  { number: 59,  name: "Al-Hashr",       arabic: "الحشر",        meaning: "The Exile",                verses: 24,  type: "Madani" },
  { number: 60,  name: "Al-Mumtahanah",  arabic: "الممتحنة",     meaning: "She That is to be Examined",verses: 13, type: "Madani" },
  { number: 61,  name: "As-Saf",         arabic: "الصف",         meaning: "The Ranks",                verses: 14,  type: "Madani" },
  { number: 62,  name: "Al-Jumu'ah",     arabic: "الجمعة",       meaning: "Friday",                   verses: 11,  type: "Madani" },
  { number: 63,  name: "Al-Munafiqun",   arabic: "المنافقون",    meaning: "The Hypocrites",           verses: 11,  type: "Madani" },
  { number: 64,  name: "At-Taghabun",    arabic: "التغابن",      meaning: "Mutual Disillusion",       verses: 18,  type: "Madani" },
  { number: 65,  name: "At-Talaq",       arabic: "الطلاق",       meaning: "Divorce",                  verses: 12,  type: "Madani" },
  { number: 66,  name: "At-Tahrim",      arabic: "التحريم",      meaning: "The Prohibition",          verses: 12,  type: "Madani" },
  { number: 67,  name: "Al-Mulk",        arabic: "الملك",        meaning: "The Sovereignty",          verses: 30,  type: "Makki" },
  { number: 68,  name: "Al-Qalam",       arabic: "القلم",        meaning: "The Pen",                  verses: 52,  type: "Makki" },
  { number: 69,  name: "Al-Haqqah",      arabic: "الحاقة",       meaning: "The Inevitable",           verses: 52,  type: "Makki" },
  { number: 70,  name: "Al-Ma'arij",     arabic: "المعارج",      meaning: "The Ascending Stairways",  verses: 44,  type: "Makki" },
  { number: 71,  name: "Nuh",            arabic: "نوح",          meaning: "Noah",                     verses: 28,  type: "Makki" },
  { number: 72,  name: "Al-Jinn",        arabic: "الجن",         meaning: "The Jinn",                 verses: 28,  type: "Makki" },
  { number: 73,  name: "Al-Muzzammil",   arabic: "المزمل",       meaning: "The Enshrouded One",       verses: 20,  type: "Makki" },
  { number: 74,  name: "Al-Muddaththir", arabic: "المدثر",       meaning: "The Cloaked One",          verses: 56,  type: "Makki" },
  { number: 75,  name: "Al-Qiyamah",     arabic: "القيامة",      meaning: "The Resurrection",         verses: 40,  type: "Makki" },
  { number: 76,  name: "Al-Insan",       arabic: "الإنسان",      meaning: "The Man",                  verses: 31,  type: "Madani" },
  { number: 77,  name: "Al-Mursalat",    arabic: "المرسلات",     meaning: "The Emissaries",           verses: 50,  type: "Makki" },
  { number: 78,  name: "An-Naba",        arabic: "النبأ",        meaning: "The Announcement",         verses: 40,  type: "Makki" },
  { number: 79,  name: "An-Nazi'at",     arabic: "النازعات",     meaning: "Those Who Pull Out",       verses: 46,  type: "Makki" },
  { number: 80,  name: "'Abasa",         arabic: "عبس",          meaning: "He Frowned",               verses: 42,  type: "Makki" },
  { number: 81,  name: "At-Takwir",      arabic: "التكوير",      meaning: "The Folding Up",           verses: 29,  type: "Makki" },
  { number: 82,  name: "Al-Infitar",     arabic: "الإنفطار",     meaning: "The Cleaving",             verses: 19,  type: "Makki" },
  { number: 83,  name: "Al-Mutaffifin",  arabic: "المطففين",     meaning: "The Defrauders",           verses: 36,  type: "Makki" },
  { number: 84,  name: "Al-Inshiqaq",    arabic: "الانشقاق",     meaning: "The Splitting Open",       verses: 25,  type: "Makki" },
  { number: 85,  name: "Al-Buruj",       arabic: "البروج",       meaning: "The Constellations",       verses: 22,  type: "Makki" },
  { number: 86,  name: "At-Tariq",       arabic: "الطارق",       meaning: "The Nightcomer",           verses: 17,  type: "Makki" },
  { number: 87,  name: "Al-A'la",        arabic: "الأعلى",       meaning: "The Most High",            verses: 19,  type: "Makki" },
  { number: 88,  name: "Al-Ghashiyah",   arabic: "الغاشية",      meaning: "The Overwhelming",         verses: 26,  type: "Makki" },
  { number: 89,  name: "Al-Fajr",        arabic: "الفجر",        meaning: "The Dawn",                 verses: 30,  type: "Makki" },
  { number: 90,  name: "Al-Balad",       arabic: "البلد",        meaning: "The City",                 verses: 20,  type: "Makki" },
  { number: 91,  name: "Ash-Shams",      arabic: "الشمس",        meaning: "The Sun",                  verses: 15,  type: "Makki" },
  { number: 92,  name: "Al-Layl",        arabic: "الليل",        meaning: "The Night",                verses: 21,  type: "Makki" },
  { number: 93,  name: "Ad-Duhaa",       arabic: "الضحى",        meaning: "The Morning Brightness",   verses: 11,  type: "Makki" },
  { number: 94,  name: "Ash-Sharh",      arabic: "الشرح",        meaning: "The Relief",               verses: 8,   type: "Makki" },
  { number: 95,  name: "At-Tin",         arabic: "التين",        meaning: "The Fig",                  verses: 8,   type: "Makki" },
  { number: 96,  name: "Al-'Alaq",       arabic: "العلق",        meaning: "The Clot",                 verses: 19,  type: "Makki" },
  { number: 97,  name: "Al-Qadr",        arabic: "القدر",        meaning: "The Power",                verses: 5,   type: "Makki" },
  { number: 98,  name: "Al-Bayyinah",    arabic: "البينة",       meaning: "The Clear Proof",          verses: 8,   type: "Madani" },
  { number: 99,  name: "Az-Zalzalah",    arabic: "الزلزلة",      meaning: "The Earthquake",           verses: 8,   type: "Madani" },
  { number: 100, name: "Al-'Adiyat",     arabic: "العاديات",     meaning: "The Chargers",             verses: 11,  type: "Makki" },
  { number: 101, name: "Al-Qari'ah",     arabic: "القارعة",      meaning: "The Striking Hour",        verses: 11,  type: "Makki" },
  { number: 102, name: "At-Takathur",    arabic: "التكاثر",      meaning: "The Rivalry in World Increase", verses: 8, type: "Makki" },
  { number: 103, name: "Al-'Asr",        arabic: "العصر",        meaning: "The Declining Day",        verses: 3,   type: "Makki" },
  { number: 104, name: "Al-Humazah",     arabic: "الهمزة",       meaning: "The Slanderer",            verses: 9,   type: "Makki" },
  { number: 105, name: "Al-Fil",         arabic: "الفيل",        meaning: "The Elephant",             verses: 5,   type: "Makki" },
  { number: 106, name: "Quraysh",        arabic: "قريش",         meaning: "Quraysh",                  verses: 4,   type: "Makki" },
  { number: 107, name: "Al-Ma'un",       arabic: "الماعون",      meaning: "The Small Kindnesses",     verses: 7,   type: "Makki" },
  { number: 108, name: "Al-Kawthar",     arabic: "الكوثر",       meaning: "The Abundance",            verses: 3,   type: "Makki" },
  { number: 109, name: "Al-Kafirun",     arabic: "الكافرون",     meaning: "The Disbelievers",         verses: 6,   type: "Makki" },
  { number: 110, name: "An-Nasr",        arabic: "النصر",        meaning: "The Divine Support",       verses: 3,   type: "Madani" },
  { number: 111, name: "Al-Masad",       arabic: "المسد",        meaning: "The Palm Fibre",           verses: 5,   type: "Makki" },
  { number: 112, name: "Al-Ikhlas",      arabic: "الإخلاص",      meaning: "The Sincerity",            verses: 4,   type: "Makki" },
  { number: 113, name: "Al-Falaq",       arabic: "الفلق",        meaning: "The Daybreak",             verses: 5,   type: "Makki" },
  { number: 114, name: "An-Nas",         arabic: "الناس",        meaning: "Mankind",                  verses: 6,   type: "Makki" },
];"""

with open(TEMPLATE, 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the SURAHS array
lines = content.split('\n')
start = None
end = None
for i, line in enumerate(lines):
    if line.strip().startswith('const SURAHS = ['):
        start = i
    if start is not None and line.strip() == '];' and i > start:
        end = i
        break

if start is None or end is None:
    print("ERROR: Could not find SURAHS array boundaries")
    exit(1)

new_lines = lines[:start] + [NEW_SURAHS] + lines[end+1:]
with open(TEMPLATE, 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines))

print(f"Updated SURAHS array: replaced lines {start+1}-{end+1} with 114 surahs")
