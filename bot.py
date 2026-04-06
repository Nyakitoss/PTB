import os
import json
import asyncio
import random
import requests
from pathlib import Path
from telethon import TelegramClient, events, functions, types
from groq import Groq
from dotenv import load_dotenv
import sys

load_dotenv()

# ================== FILES ==================

BASE_DIR = Path(__file__).parent
CHAT_CONFIG_FILE = BASE_DIR / "chats.json"
CHAT_SETTINGS_FILE = BASE_DIR / "chat_settings.json"

# ================== RUNTIME ==================

PRIVATE_BLACKLIST = set()

# ================== CONST ==================

MOM_ID = 538973139
AI_SIGN = "(ai)"

DEFAULT_PROMPT = (
    "Ты просто помошник, твоя задача до смена промта помочь пользователям сделать свои настройки чата. Вот настройки: /set_reply (1-n) частота ответа /set_sticker (0-100) частота стикера /set_prompt текст нового промпта /chat_config текущие настройки чата. Пиши кратко, но доходчиво, предлагай перенастроить промпт пользователям и помогай с этим. Если спросят что-то, отвечай."
)

DEFAULT_STICKERS = [
    "nagieveryhotmen_by_fStikBot",
    "FemboyBaseStiks_by_fStikBot",
    "goydadimkamalinka_by_fStikBot",
    "nyaaatox",
    "shydevry_fikbooka",
    "autismbylidreron",
    "Veibae_by_MoiStikiBot",
    "xelivet_by_fStikBot",
    "shlrona",
    "MurderDronesTelegram_vol1",
    "GVWNVudmkSBshtk_by_stickers_stealer_bot",
    "Dark245",
    "diseasedthoughts_furry_by_fStikBot",
    "feelbtw_by_fStikBot",
    "ssluhansk_by_fStikBot",
    "destroy77707_by_fStikBot",
    "diseasedthoughts808_by_fStikBot",
    "Kururu2",
    "traxodrom52_by_fStikBot",
    "findiexxx_by_fStikBot",
    "Sobn791_by_fStikBot",
    "sobnfghty_by_fStikBot",
]

DEFAULT_CHAT_SETTINGS = {
    "reply_every": 5,
    "sticker_chance": 0.5,
    "prompt": DEFAULT_PROMPT,
    "sticker_packs": DEFAULT_STICKERS
}

chat_settings = {}
chat_counters = {}

# ================== LOADERS ==================

def load_runtime_config():
    global PRIVATE_BLACKLIST

    if CHAT_CONFIG_FILE.exists():
        data = json.loads(CHAT_CONFIG_FILE.read_text(encoding="utf-8"))
        PRIVATE_BLACKLIST = set(data.get("private_blacklist", []))
    else:
        PRIVATE_BLACKLIST = set()

def load_chat_settings():
    global chat_settings
    if CHAT_SETTINGS_FILE.exists():
        chat_settings = json.loads(CHAT_SETTINGS_FILE.read_text(encoding="utf-8"))
    else:
        chat_settings = {}

def save_chat_settings():
    CHAT_SETTINGS_FILE.write_text(
        json.dumps(chat_settings, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

def get_chat_settings(chat_id: int) -> dict:
    key = str(chat_id)
    if key not in chat_settings:
        chat_settings[key] = {
            "reply_every": DEFAULT_CHAT_SETTINGS["reply_every"],
            "sticker_chance": DEFAULT_CHAT_SETTINGS["sticker_chance"],
            "prompt": DEFAULT_CHAT_SETTINGS["prompt"],
            "sticker_packs": list(DEFAULT_CHAT_SETTINGS["sticker_packs"]),
        }
        save_chat_settings()
    return chat_settings[key]

# ================== HELPERS ==================

def normalize_sticker_pack(value: str) -> str | None:
    value = value.strip()
    if value.startswith("https://t.me/addstickers/"):
        value = value.replace("https://t.me/addstickers/", "")
    return value if value else None

def parse_int(v):
    try:
        return int(v)
    except:
        return None

def parse_percent(v):
    try:
        n = int(v)
        if 0 <= n <= 100:
            return n / 100
    except:
        pass
    return None

# ================== INIT ==================

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
OR_API_KEY = os.getenv("OPENROUTER_API_KEY")

client = TelegramClient(
    "bot",
    int(os.getenv("API_ID")),
    os.getenv("API_HASH")
).start(
    bot_token=os.getenv("BOT_TOKEN")
)

# ================== AI ==================

async def ask_ai(prompt, history):
    full = f"роль:\n{prompt}\n\nистория:\n{history}\n\nответ:"
    try:
        r = await asyncio.to_thread(
            groq_client.chat.completions.create,
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": full}]
        )
        return r.choices[0].message.content
    except Exception as e:
        if "429" in str(e):
            r = await asyncio.to_thread(
                requests.post,
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OR_API_KEY}"},
                json={
                    "model": "google/gemini-2.0-flash-lite-preview-05-05:free",
                    "messages": [{"role": "user", "content": full}],
                },
                timeout=10,
            )
            return r.json()["choices"][0]["message"]["content"]
        raise

# ================== HANDLER ==================

@client.on(events.NewMessage)
async def handler(event):
    sender = event.sender_id
    text = (event.message.text or "").strip()

    if sender == MOM_ID or AI_SIGN in text:
        return

    # ----- access -----
    if event.is_private:
        if sender in PRIVATE_BLACKLIST:
            return

    settings = get_chat_settings(event.chat_id)

    # ===== admin only (из избранного) =====

    if text == "/reload_config":
        me = await client.get_me()
        if event.is_private and event.chat_id == me.id:
            load_runtime_config()
            await event.reply("🔄 конфиг перезагружен")
        return

    if text == "/restart_bot":
        me = await client.get_me()
        if event.is_private and event.chat_id == me.id:
            await event.reply("🔁 перезапуск…")
            await client.disconnect()
            os.execv(sys.executable, [sys.executable] + sys.argv)
        return

    # ===== sticker management =====

    if text == "/stickers":
        packs = settings["sticker_packs"]
        if not packs:
            await event.reply("📭 стикерпаков пока нет")
        else:
            msg = "🎴 стикерпаки чата:\n\n"
            for p in packs:
                msg += f"https://t.me/addstickers/{p}\n"
            await event.reply(msg)
        return

    if text.startswith("/add_sticker"):
        if len(text.split(maxsplit=1)) < 2:
            await event.reply("пример: /add_sticker https://t.me/addstickers/packname")
            return

        pack = normalize_sticker_pack(text.split(maxsplit=1)[1])
        if not pack:
            await event.reply("❌ не понял стикерпак")
            return

        if pack in settings["sticker_packs"]:
            await event.reply("⚠️ этот стикерпак уже добавлен")
            return

        settings["sticker_packs"].append(pack)
        save_chat_settings()
        await event.reply(f"✅ добавлен:\nhttps://t.me/addstickers/{pack}")
        return

    if text.startswith("/del_sticker"):
        if len(text.split(maxsplit=1)) < 2:
            await event.reply("пример: /del_sticker packname")
            return

        pack = normalize_sticker_pack(text.split(maxsplit=1)[1])
        if pack not in settings["sticker_packs"]:
            await event.reply("❌ такого стикерпака нет")
            return

        settings["sticker_packs"].remove(pack)
        save_chat_settings()
        await event.reply(f"🗑 удалён:\n{pack}")
        return

        # ----- help -----
    if text == "/help":
        await event.reply(
            "`/set_reply` N - 💌частота ответов, раз в n сообщений💌\n"
            "`/set_sticker` P - 💟шанс стикера в %💟\n"
            "`/set_prompt` текст - 📝задать промпт боту📝\n"
            "`/chat_config` - 🛠текущие настройки🛠\n"
            "`/stickers` - 🌠стикерпаки чата🌠\n"
            "`/add_sticker` - 📈добавить стикерпак в чат📈\n"
            "`/del_sticker` - 📉удалить стикер пак из чата📉\n"
            "`/reload_config` - ❌admin only(перезагрузка конфига)❌\n"
            "`/restart_bot` - ❌admin only(перезагрузка бота)❌"
        )
        return

        # ----- settings commands (for all) -----
    if text.startswith("/set_reply"):
        v = parse_int(text.split(maxsplit=1)[1]) if len(text.split()) > 1 else None
        if not v or v < 1:
            await event.reply("пример: /set_reply 3")
            return
        settings["reply_every"] = v
        save_chat_settings()
        await event.reply(f"✅ теперь раз в {v} сообщений")
        return

    if text.startswith("/set_sticker"):
        p = parse_percent(text.split(maxsplit=1)[1]) if len(text.split()) > 1 else None
        if p is None:
            await event.reply("пример: /set_sticker 40")
            return
        settings["sticker_chance"] = p
        save_chat_settings()
        await event.reply(f"🎲 шанс {int(p*100)}%")
        return

    if text.startswith("/set_prompt"):
        if len(text.split(maxsplit=1)) < 2:
            await event.reply("пример: /set_prompt новый стиль")
            return
        settings["prompt"] = text.split(maxsplit=1)[1]
        save_chat_settings()
        await event.reply("🧠 промпт обновлён")
        return

    if text == "/chat_config":
        await event.reply(
            f"reply: {settings['reply_every']}\n"
            f"sticker: {int(settings['sticker_chance']*100)}%\n"
            f"sticker_packs: для просмотра стикерпаков введите команду /stickers\n"
            f"prompt:\n{settings['prompt'][:300]}"
            
        )
        return
    
    # ===== ignore own =====
    if event.out:
        return

    # ===== reply logic =====

    forced = event.mentioned
    if event.is_reply:
        r = await event.get_reply_message()
        if r and r.out:
            forced = True

    if not forced:
        cid = event.chat_id
        chat_counters[cid] = chat_counters.get(cid, 0) + 1
        if chat_counters[cid] % settings["reply_every"] != 0:
            return

    async with client.action(event.chat_id, "typing"):
        hist = []
        async for m in client.iter_messages(event.chat_id, limit=6):
            if m.out:
                continue
            t = (m.text or "").replace(AI_SIGN, "").strip()
            if t:
                hist.append(t)
        hist.reverse()

        resp = await ask_ai(settings["prompt"], "\n".join(hist))
        resp = resp.strip().lower()

        if resp:
            await event.reply(f"{resp} {AI_SIGN}")

            packs = settings["sticker_packs"]
            if packs and random.random() < settings["sticker_chance"]:
                try:
                    pack = random.choice(packs)
                    s = await client(functions.messages.GetStickerSetRequest(
                        stickerset=types.InputStickerSetShortName(pack),
                        hash=0
                    ))
                    await client.send_file(
                        event.chat_id,
                        random.choice(s.documents),
                        reply_to=event.id
                    )
                except Exception as e:
                    print("[STICKER ERROR]", e)

# ================== START ==================

client = TelegramClient(
    "bot",
    int(os.getenv("API_ID")),
    os.getenv("API_HASH")
)

async def main():
    load_runtime_config()
    load_chat_settings()

    await client.start(
        bot_token=os.getenv("BOT_TOKEN")
    )

    print("бот запущен")

    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
