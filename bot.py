# ────────────────────────────────────────────────────────────
#  Qur'on Telegram-bot  |  3 til (arab, uz, eng)  |  Audio (bitta MP3)
#  • Surani nomi/raqami → qisqa (5 oyat, arab) ↔ Ko‘proq (3 til)
#  • “🔊 Audio” → qori tanlash, sura to‘liq audio (1 ta MP3)
#  • “⬅️ Ortga” bilan menyular orasida qaytish
#  • Sura + oyat so‘ralsa – faqat o‘sha oyat matn + audio
#  Python 3.8+, requests, pyTelegramBotAPI 4.27+
# ────────────────────────────────────────────────────────────

import os, re, textwrap, difflib, requests, telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

API_TOKEN = os.getenv("BOT_TOKEN", "8043572243:AAE5kFj3SSImlJ2F66XbJcCsnd2WWkf-SFs")
bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")

API_BASE = "https://api.alquran.cloud/v1"
AUDIO_BASE = "https://cdn.islamic.network/quran/audio-surah/128"  # 128kbps sura MP3

TEXT_EDITIONS = {
    "arabic":  "quran-uthmani",
    "uzbek":   "uz.sodik",
    "english": "en.asad",
}
RECITERS = {
    "Mishary Al‑Afasy": "ar.alafasy",
    "AbdulBasit":       "ar.abdulbasitmurattal",
    "Hudhaify":         "ar.hudhaify",
}
PREVIEW = 5
MAXLEN  = 4000

# ═════════ Surah lug'ati ════════════════════════════════════
print("📥 Surah ma'lumotlari yuklanmoqda …")
_meta = requests.get(f"{API_BASE}/meta", timeout=20).json()["data"]["surahs"]["references"]

def _key(s:str):
    return re.sub(r"[^a-z0-9]", "", s.lower())

SURAH_MAP = {}
for s in _meta:
    n = s["number"]
    SURAH_MAP[str(n)] = n
    SURAH_MAP[_key(s["englishName"])] = n
    SURAH_MAP[_key(s["name"])] = n
SURAH_KEYS = list(SURAH_MAP.keys())

# ═════════ Yordamchilar ═════════════════════════════════════

def api(url):
    r = requests.get(url, timeout=20)
    return r.json() if r.status_code==200 else None

def wrap(txt):
    return textwrap.wrap(txt, MAXLEN, break_long_words=False, break_on_hyphens=False)

# fuzzy match

def find_surah(q:str):
    norm=_key(q)
    if norm in SURAH_MAP:
        return SURAH_MAP[norm]
    m=difflib.get_close_matches(norm, SURAH_KEYS, n=1, cutoff=0.6)
    return SURAH_MAP[m[0]] if m else None

# ═════════ /start ═══════════════════════════════════════════
@bot.message_handler(commands=["start","help"])
def start(m):
    bot.reply_to(m,
        "<b>Qur'on bot</b>\nSurani nomi/raqami yuboring (mas: <code>Yasin</code>, <code>36</code>, <code>Baqarah 255</code>).")

# ═════════ Xabarlar ════════════════════════════════════════
@bot.message_handler(func=lambda m: True)
def on_msg(m):
    txt=m.text.strip()
    sura,ayah=parse_ref(txt)
    if not sura:
        return bot.reply_to(m,"❌ Surani topib bo'lmadi. Imloni tekshiring.")
    if ayah:
        send_ayah(m.chat.id,sura,ayah)
    else:
        send_preview(m.chat.id,sura)

def parse_ref(t:str):
    t=t.strip()
    if ":" in t:
        s,a=t.split(":",1); return find_surah(s), int(a) if a.isdigit() else None
    if " " in t:
        s,a=t.rsplit(" ",1); return (find_surah(s), int(a)) if a.isdigit() else (find_surah(t),None)
    return find_surah(t), None

# ═════════ Matn chiqarish ═════════════════════════════════

def header(n):
    s=_meta[n-1]; return f"<b>{s['englishName']} — {s['name']}</b>\n"

def send_preview(chat,s):
    parts=[]
    for lang,ed in TEXT_EDITIONS.items():
        js=api(f"{API_BASE}/surah/{s}/{ed}"); ay=js['data']['ayahs'][:PREVIEW]
        parts.append(f"<b>{lang.capitalize()}:</b>\n"+"\n".join(f"{a['numberInSurah']}. {a['text']}" for a in ay))
    msg=header(s)+"\n\n".join(parts)+"\n…"
    kb=InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("▶️ Ko‘proq",callback_data=f"more|{s}"),
           InlineKeyboardButton("🔊 Audio",callback_data=f"audio|{s}"))
    bot.send_message(chat,msg,reply_markup=kb)

def send_full(chat,s,cb=None):
    blocks=[]
    for lang,ed in TEXT_EDITIONS.items():
        js=api(f"{API_BASE}/surah/{s}/{ed}"); ay=js['data']['ayahs']
        blocks.append(f"<b>{lang.capitalize()}:</b>\n"+"\n".join(f"{a['numberInSurah']}. {a['text']}" for a in ay))
    full=header(s)+"\n\n".join(blocks)
    kb=InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬅️ Yopish",callback_data=f"less|{s}"),
           InlineKeyboardButton("🔊 Audio",callback_data=f"audio|{s}"))
    chunks=wrap(full)
    if cb:
        bot.edit_message_text(chunks[0],chat,cb.message.id,reply_markup=kb)
        for p in chunks[1:]: bot.send_message(chat,p)
    else:
        bot.send_message(chat,chunks[0],reply_markup=kb)
        for p in chunks[1:]: bot.send_message(chat,p)

# ═════════ Oyat ═══════════════════════════════════════════

def send_ayah(chat,s,a):
    js=api(f"{API_BASE}/ayah/{s}:{a}/quran-uthmani");
    if not js or js['status']!='OK':
        return bot.send_message(chat,"❌ Oyat topilmadi.")
    d=js['data']
    kb=InlineKeyboardMarkup(); kb.add(InlineKeyboardButton("🔊 Audio",callback_data=f"audayah|{s}|{a}"))
    bot.send_message(chat,f"<b>{d['surah']['englishName']} {a}</b>\n{d['text']}",reply_markup=kb)

# ═════════ Audio ══════════════════════════════════════════

def surah_audio_link(s,rec_id):
    return f"{AUDIO_BASE}/{rec_id}/{s}.mp3"

def send_surah_audio(chat,s,rec_id):
    link=surah_audio_link(s,rec_id)
    bot.send_audio(chat,link,title=f"Surah {s}")

def send_ayah_audio(chat,s,a,rec_id):
    js=api(f"{API_BASE}/ayah/{s}:{a}/{rec_id}")
    if js and js['status']=='OK':
        bot.send_audio(chat,js['data']['audio'],title=f"{s}:{a}")
    else:
        bot.send_message(chat,"❌ Audio topilmadi.")

# ═════════ Callback’lar ═══════════════════════════════════
@bot.callback_query_handler(func=lambda c: True)
def cb(c:CallbackQuery):
    act,*ar=c.data.split("|")
    if act=="more": send_full(c.message.chat.id,int(ar[0]),c)
    elif act=="less":
        bot.delete_message(c.message.chat.id,c.message.id)
        send_preview(c.message.chat.id,int(ar[0]))
    elif act=="audio":
        s=int(ar[0]); kb=InlineKeyboardMarkup(row_width=1)
        for n,id_ in RECITERS.items(): kb.add(InlineKeyboardButton(n,callback_data=f"qori|{s}|{id_}"))
        kb.add(InlineKeyboardButton("⬅️ Ortga",callback_data=f"less|{s}"))
        bot.edit_message_reply_markup(c.message.chat.id,c.message.id,reply_markup=kb)
    elif act=="qori": send_surah_audio(c.message.chat.id,int(ar[0]),ar[1])
    elif act=="audayah": send_ayah_audio(c.message.chat.id,int(ar[0]),int(ar[1]),list(RECITERS.values())[0])

# ═════════ Run ════════════════════════════════════════════
if __name__=='__main__':
    print("🚀 Bot ishga tushdi …")
    bot.infinity_polling(skip_pending=True)
