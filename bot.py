import os
from dotenv import load_dotenv
import sqlite3
import secrets
import json
import asyncio
import re
from datetime import datetime

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, Update, BotCommand,
    BotCommandScopeDefault, BotCommandScopeChat, MessageEntity
)
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes,
    MessageHandler, filters
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN belum diset di environment variable")

# Keamanan: daftar admin default. Owner pertama tidak boleh dihapus lewat panel.
DEFAULT_ADMIN_IDS = {1137740036, 1779151962, 1943239073, 7186342193}
OWNER_ID = 1137740036
CHANNEL_ID = -1001967813918
FREE_GROUP_ID = -1002228292417
MEMBERSHIP_GROUP_ID = -1002115664800

DEFAULT_CHANNEL_LINK = "https://t.me/Nakahoshi"
DEFAULT_FREE_GROUP_LINK = "https://t.me/+lYiuGXIVy1JkYWE9"
DEFAULT_PAYMENT_LINK = "https://t.me/nakanosqbot?start=NakaFileBOT"
DEFAULT_OWNER_LINK = "https://t.me/seiizn"
DB_NAME = "files.db"

DEFAULT_START_TEXT = """╭━━━━━━━━━━━━━━━━━━━━╮
       ✦ NAKAHOSHI ✦
      FILE SHARE BOT
╰━━━━━━━━━━━━━━━━━━━━╯

🤖 BOT KHUSUS FILE SHARE
   NON-MEMBERSHIP USER

Jika Anda sudah bergabung ke Membership Nakahoshi, silakan langsung menikmati konten Membership.

🎬 @Nakahoshi

━━━━━━━━━━━━━━━━━━━━

Belum menjadi member?

⭐ Membership Nakahoshi
💰 Rp15.000 / 30 Hari

Dapatkan akses Membership dan nikmati konten lengkap.

👇 Pilih akses Anda:"""

DEFAULT_FSUB_TEXT = "UNTUK FREE USER, SILAHKAN BERGABUNG TERLEBIH DAHULU KE GRUP DAN CHANNEL UTAMA KAMI UNTUK MENDAPATKAN FILE!!\n\nSETELAH BERGABUNG KE CHANNEL DAN GRUP, SILAHKAN TEKAN TOMBOL 🔄 CEK AKSES DI BAWAH UNTUK MENDAPATKAN FILE.\n\n━━━━━━━━━━━━━━━━━━━━\n\n💎 MEMBERSHIP NAKAHOSHI\n\nBosan menggunakan bot file?\nNggak perlu ribet cari file atau join sana-sini.\nLangsung saja tekan tombol ⭐ JOIN MEMBERSHIP di bawah!"

DEFAULT_BANNED_TEXT = "🚫 AKUN KAMU TELAH DI-BANNED.\n\nJika merasa ini kesalahan, silakan hubungi Customer Service."
DEFAULT_DENIED_TEXT = "🚫 COMMAND KHUSUS ADMIN.\n\nKamu tidak memiliki izin untuk menggunakan command ini."
DEFAULT_NOT_FOUND_TEXT = "❌ File tidak ditemukan atau sudah tidak tersedia."
DEFAULT_INVALID_LINK_TEXT = "❌ Link file tidak valid."
DEFAULT_ACCESS_OK_TEXT = "✅ AKSES OK\n\n📤 File sedang dikirim..."
DEFAULT_ACCESS_DENIED_CHANNEL_TEXT = "❌ Kamu belum bergabung ke Channel Nakahoshi."
DEFAULT_ACCESS_DENIED_GROUP_TEXT = "❌ Kamu belum bergabung ke Group Nakahoshi."
DEFAULT_ACCESS_DENIED_BOTH_TEXT = "❌ Kamu belum bergabung ke Channel dan Group Nakahoshi."
DEFAULT_DELETE_NOTICE = "⚠️ FILE INI AKAN DIHAPUS OTOMATIS DALAM {minutes} MENIT."
DEFAULT_CS_TEXT = "🛠️ CUSTOMER SERVICE NAKAHOSHI\n\nJika terdapat masalah pada file, akses, atau akun, silakan hubungi admin kami."
DEFAULT_UNBAN_TEXT = "🚫 Akun kamu sedang dibanned.\n\nSilakan ajukan permintaan unban kepada admin melalui tombol di bawah."
DEFAULT_MAINTENANCE_TEXT = "🔧 NAKAHOSHI SEDANG DALAM PEMELIHARAAN.\n\nSilakan coba kembali nanti."

pending_batches = {}
admin_sessions = {}


def db():
    conn = sqlite3.connect(DB_NAME, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn, table, column, definition):
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    conn = db(); cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS files (code TEXT PRIMARY KEY, file_id TEXT NOT NULL, file_type TEXT NOT NULL, caption TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS batches (code TEXT PRIMARY KEY, created_by INTEGER, created_at TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS batch_items (id INTEGER PRIMARY KEY AUTOINCREMENT, batch_code TEXT NOT NULL, file_id TEXT NOT NULL, file_type TEXT NOT NULL, caption TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, first_seen TEXT, last_seen TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, added_at TEXT, added_by INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS banned_users (user_id INTEGER PRIMARY KEY, reason TEXT, banned_at TEXT, banned_by INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS user_commands (command TEXT PRIMARY KEY, description TEXT, config TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1)")
    ensure_column(conn, "files", "caption_entities", "TEXT")
    ensure_column(conn, "batch_items", "caption_entities", "TEXT")
    defaults = {
        "start_text": DEFAULT_START_TEXT,
        "start_media": "",
        "start_media_type": "",
        "start_entities": "[]",
        "start_config": json.dumps({"text": DEFAULT_START_TEXT, "entities": [], "media_id": "", "media_type": "", "buttons": [["⭐ JOIN MEMBERSHIP", "url", DEFAULT_PAYMENT_LINK], ["📢 JOIN CHANNEL", "url", DEFAULT_CHANNEL_LINK], ["👥 JOIN GROUP", "url", DEFAULT_FREE_GROUP_LINK], ["👤 OWNER BOT", "url", DEFAULT_OWNER_LINK]]}, ensure_ascii=False),
        "fsub_config": json.dumps({"text": DEFAULT_FSUB_TEXT, "entities": [], "media_id": "", "media_type": "", "buttons": [["📢 JOIN CHANNEL", "url", DEFAULT_CHANNEL_LINK], ["👥 JOIN GROUP", "url", DEFAULT_FREE_GROUP_LINK], ["🔄 CEK AKSES", "check", ""], ["⭐ JOIN MEMBERSHIP", "url", DEFAULT_PAYMENT_LINK]]}, ensure_ascii=False),
        "membership_price": "Rp15.000 / 30 Hari",
        "channel_link": DEFAULT_CHANNEL_LINK,
        "free_group_link": DEFAULT_FREE_GROUP_LINK,
        "payment_link": DEFAULT_PAYMENT_LINK,
        "owner_link": DEFAULT_OWNER_LINK,
        "cs_link": DEFAULT_OWNER_LINK,
        "protect_content": "1",
        "auto_delete_enabled": "0",
        "auto_delete_minutes": "10",
        "auto_delete_notice": json.dumps({"text": DEFAULT_DELETE_NOTICE, "entities": [], "media_id": "", "media_type": "", "buttons": []}, ensure_ascii=False),
        "banned_message": json.dumps({"text": DEFAULT_BANNED_TEXT, "entities": [], "media_id": "", "media_type": "", "buttons": []}, ensure_ascii=False),
        "denied_message": json.dumps({"text": DEFAULT_DENIED_TEXT, "entities": [], "media_id": "", "media_type": "", "buttons": []}, ensure_ascii=False),
        "not_found_message": json.dumps({"text": DEFAULT_NOT_FOUND_TEXT, "entities": [], "media_id": "", "media_type": "", "buttons": []}, ensure_ascii=False),
        "invalid_link_message": json.dumps({"text": DEFAULT_INVALID_LINK_TEXT, "entities": [], "media_id": "", "media_type": "", "buttons": []}, ensure_ascii=False),
        "access_ok_message": json.dumps({"text": DEFAULT_ACCESS_OK_TEXT, "entities": [], "media_id": "", "media_type": "", "buttons": []}, ensure_ascii=False),
        "access_denied_channel": json.dumps({"text": DEFAULT_ACCESS_DENIED_CHANNEL_TEXT, "entities": [], "media_id": "", "media_type": "", "buttons": []}, ensure_ascii=False),
        "access_denied_group": json.dumps({"text": DEFAULT_ACCESS_DENIED_GROUP_TEXT, "entities": [], "media_id": "", "media_type": "", "buttons": []}, ensure_ascii=False),
        "access_denied_both": json.dumps({"text": DEFAULT_ACCESS_DENIED_BOTH_TEXT, "entities": [], "media_id": "", "media_type": "", "buttons": []}, ensure_ascii=False),
        "cs_config": json.dumps({"text": DEFAULT_CS_TEXT, "entities": [], "media_id": "", "media_type": "", "buttons": [["👤 HUBUNGI ADMIN", "url", DEFAULT_OWNER_LINK]]}, ensure_ascii=False),
        "unban_config": json.dumps({"text": DEFAULT_UNBAN_TEXT, "entities": [], "media_id": "", "media_type": "", "buttons": [["📝 AJUKAN UNBAN", "url", DEFAULT_OWNER_LINK]]}, ensure_ascii=False),
        "maintenance_config": json.dumps({"text": DEFAULT_MAINTENANCE_TEXT, "entities": [], "media_id": "", "media_type": "", "buttons": []}, ensure_ascii=False),
        "maintenance": "0",
    }
    for key, value in defaults.items():
        cur.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (key, value))
    for uid in DEFAULT_ADMIN_IDS:
        cur.execute("INSERT OR IGNORE INTO admins(user_id,added_at,added_by) VALUES(?,?,?)", (uid, datetime.now().isoformat(timespec="seconds"), OWNER_ID))
    default_commands = {
        "peraturan": ("Peraturan Nakahoshi", {"text": "📜 PERATURAN NAKAHOSHI\n\nSilakan isi peraturan Nakahoshi melalui Admin Panel.", "entities": [], "media_id": "", "media_type": "", "buttons": []}),
        "unbanned": ("Pengajuan unban akun", {"text": DEFAULT_UNBAN_TEXT, "entities": [], "media_id": "", "media_type": "", "buttons": [["📝 AJUKAN UNBAN", "url", DEFAULT_OWNER_LINK]]}),
        "joinvip": ("Membership Nakahoshi", {"text": "⭐ JOIN VIP\n\nCuma Rp15.000 / 30 Hari. Murah banget 😝", "entities": [], "media_id": "", "media_type": "", "buttons": [["⭐ JOIN MEMBERSHIP", "url", DEFAULT_PAYMENT_LINK]]}),
        "listchannel": ("List channel Nakahoshi", {"text": "📚 LIST CHANNEL NAKAHOSHI\n\nSilakan pilih channel/folder yang ingin kamu buka 👇", "entities": [], "media_id": "", "media_type": "", "buttons": []}),
        "customerservice": ("Hubungi Customer Service", {"text": DEFAULT_CS_TEXT, "entities": [], "media_id": "", "media_type": "", "buttons": [["👤 HUBUNGI ADMIN", "url", DEFAULT_OWNER_LINK]]}),
    }
    for command, (desc, config) in default_commands.items():
        cur.execute("INSERT OR IGNORE INTO user_commands(command,description,config,enabled) VALUES(?,?,?,1)", (command, desc, json.dumps(config, ensure_ascii=False)))
    conn.commit(); conn.close()


def get_setting(key):
    conn = db(); row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone(); conn.close()
    return row["value"] if row else ""


def set_setting(key, value):
    conn = db(); conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value)); conn.commit(); conn.close()


def get_admin_ids():
    conn = db(); rows = conn.execute("SELECT user_id FROM admins").fetchall(); conn.close()
    ids = {int(r["user_id"]) for r in rows}; ids.add(OWNER_ID); return ids


def is_admin(user_id): return user_id in get_admin_ids()


def is_banned(user_id):
    conn = db(); row = conn.execute("SELECT 1 FROM banned_users WHERE user_id=?", (user_id,)).fetchone(); conn.close()
    return row is not None and user_id not in get_admin_ids()


def save_user(user):
    if not user: return
    now = datetime.now().isoformat(timespec="seconds")
    conn = db(); conn.execute("""INSERT INTO users(user_id,username,first_name,first_seen,last_seen) VALUES(?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name, last_seen=excluded.last_seen""",
        (user.id, user.username or "", user.first_name or "", now, now)); conn.commit(); conn.close()


def serialize_entities(entities):
    result=[]
    for e in entities or []:
        d={"type":e.type,"offset":e.offset,"length":e.length}
        for name in ("url","language","custom_emoji_id"):
            value=getattr(e,name,None)
            if value is not None: d[name]=value
        user=getattr(e,"user",None)
        if user is not None:
            d["user"]={"id":user.id,"is_bot":user.is_bot,"first_name":user.first_name or "","username":user.username}
        result.append(d)
    return result


def deserialize_entities(raw):
    try: data=json.loads(raw or "[]")
    except Exception: return []
    out=[]
    for d in data:
        try:
            kwargs={k:d[k] for k in ("type","offset","length") if k in d}
            for k in ("url","language","custom_emoji_id"):
                if k in d: kwargs[k]=d[k]
            user_data=d.get("user")
            if user_data and isinstance(user_data, dict) and user_data.get("id") is not None:
                from telegram import User
                kwargs["user"]=User(
                    id=int(user_data["id"]),
                    first_name=str(user_data.get("first_name") or "User"),
                    is_bot=bool(user_data.get("is_bot", False)),
                    username=user_data.get("username")
                )
            out.append(MessageEntity(**kwargs))
        except Exception: pass
    return out


def cfg_json(text="", entities=None, media_id="", media_type="", buttons=None):
    return {"text": text or "", "entities": serialize_entities(entities) if entities is not None else [], "media_id": media_id or "", "media_type": media_type or "", "buttons": buttons or []}


def get_config(key):
    try: return json.loads(get_setting(key) or "{}")
    except Exception: return cfg_json()


def set_config(key, config): set_setting(key, json.dumps(config, ensure_ascii=False))


def user_command(command):
    conn=db(); row=conn.execute("SELECT * FROM user_commands WHERE command=?",(command,)).fetchone(); conn.close(); return row


def make_code(prefix): return f"{prefix}_{secrets.token_urlsafe(10)}"


def create_file_record(file_id, file_type, caption, entities):
    code=make_code("F"); conn=db(); conn.execute("INSERT INTO files(code,file_id,file_type,caption,caption_entities) VALUES(?,?,?,?,?)",(code,file_id,file_type,caption or "",json.dumps(serialize_entities(entities),ensure_ascii=False))); conn.commit(); conn.close(); return code


def create_batch(user_id, items):
    code=make_code("B"); conn=db(); conn.execute("INSERT INTO batches(code,created_by,created_at) VALUES(?,?,?)",(code,user_id,datetime.now().isoformat(timespec="seconds")))
    conn.executemany("INSERT INTO batch_items(batch_code,file_id,file_type,caption,caption_entities) VALUES(?,?,?,?,?)",[(code,x[0],x[1],x[2] or "",json.dumps(serialize_entities(x[3]),ensure_ascii=False)) for x in items]); conn.commit(); conn.close(); return code


def get_file(code):
    conn=db(); row=conn.execute("SELECT * FROM files WHERE code=?",(code,)).fetchone(); conn.close(); return row


def get_batch(code):
    conn=db(); rows=conn.execute("SELECT * FROM batch_items WHERE batch_code=? ORDER BY id",(code,)).fetchall(); conn.close(); return rows


def make_button(button, code=None):
    if not isinstance(button, (list, tuple)) or len(button) < 2:
        return None
    label = str(button[0] or "")
    kind = str(button[1] or "")
    value = str(button[2] or "") if len(button) > 2 else ""
    style = button[3] if len(button) > 3 else None
    icon = button[4] if len(button) > 4 else None
    kwargs = {}
    if kind == "check" and code:
        kwargs["callback_data"] = f"check:{code}"
    elif kind == "url" and value:
        kwargs["url"] = value
    else:
        return None
    if style in {"primary", "success", "danger"}:
        kwargs["style"] = style
    if icon:
        kwargs["icon_custom_emoji_id"] = str(icon)
    try:
        return InlineKeyboardButton(label, **kwargs)
    except TypeError:
        kwargs.pop("style", None)
        kwargs.pop("icon_custom_emoji_id", None)
        return InlineKeyboardButton(label, **kwargs)


def build_keyboard(buttons, code=None):
    rows = []
    for index, b in enumerate(buttons or []):
        btn = make_button(b, code)
        if not btn:
            continue
        row_id = b[6] if len(b) > 6 and isinstance(b[6], int) else None
        same = len(b) > 5 and b[5] == "same"
        if row_id is not None:
            while len(rows) <= row_id:
                rows.append([])
            rows[row_id].append(btn)
        elif same and rows:
            rows[-1].append(btn)
        else:
            rows.append([btn])
    rows = [row for row in rows if row]
    return InlineKeyboardMarkup(rows) if rows else None


def _fsub_buttons_with_rows(buttons):
    """Preserve saved labels/icons/styles while fixing legacy FSUB row layout."""
    items = [list(b) for b in (buttons or []) if isinstance(b, (list, tuple)) and len(b) >= 2]
    if not items:
        return []
    # New-format buttons already carry an explicit row id; never rewrite them.
    if any(len(b) > 6 and isinstance(b[6], int) for b in items):
        return items
    channel = get_setting("channel_link")
    group = get_setting("free_group_link")
    payment = get_setting("payment_link")
    channel_btn = next((b for b in items if len(b) > 2 and b[1] == "url" and b[2] == channel), None)
    group_btn = next((b for b in items if len(b) > 2 and b[1] == "url" and b[2] == group), None)
    check_btn = next((b for b in items if b[1] == "check"), None)
    membership_btn = next((b for b in items if len(b) > 2 and b[1] == "url" and b[2] == payment), None)
    known = {id(x) for x in (channel_btn, group_btn, check_btn, membership_btn) if x is not None}
    ordered = []
    if channel_btn: ordered.append(channel_btn)
    if group_btn: ordered.append(group_btn)
    if check_btn: ordered.append(check_btn)
    if membership_btn: ordered.append(membership_btn)
    ordered.extend(b for b in items if id(b) not in known)
    # Desired legacy FSUB layout: channel+group / check / membership.
    for i, b in enumerate(ordered):
        b = list(b)
        row = 0 if i < 2 else (1 if i == 2 else 2)
        while len(b) < 7:
            b.append(None)
        b[5] = "new"
        b[6] = row
        ordered[i] = b
    return ordered


def access_keyboard(code):
    cfg = get_config("fsub_config")
    buttons = _fsub_buttons_with_rows(cfg.get("buttons"))
    return build_keyboard(buttons, code) or InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 JOIN CHANNEL", url=get_setting("channel_link")), InlineKeyboardButton("👥 JOIN GROUP", url=get_setting("free_group_link"))],
        [InlineKeyboardButton("🔄 CEK AKSES", callback_data=f"check:{code}")],
        [InlineKeyboardButton("⭐ JOIN MEMBERSHIP", url=get_setting("payment_link"))]
    ])


def start_keyboard(): return build_keyboard(get_config("start_config").get("buttons"))


async def member_is_inside(bot, chat_id, user_id):
    try:
        member=await bot.get_chat_member(chat_id,user_id)
        return member.status in {"member","administrator","creator","restricted"}
    except Exception: return False


async def check_access(bot,user_id):
    if is_admin(user_id): return True
    if is_banned(user_id): return False
    if await member_is_inside(bot,MEMBERSHIP_GROUP_ID,user_id): return True
    return await member_is_inside(bot,CHANNEL_ID,user_id) and await member_is_inside(bot,FREE_GROUP_ID,user_id)


def protect(): return get_setting("protect_content") == "1"


def _entity_copy_with_offsets(entity, offset=None, length=None):
    kwargs={"type":entity.type,"offset":entity.offset if offset is None else offset,"length":entity.length if length is None else length}
    for name in ("url","language","custom_emoji_id","user"):
        value=getattr(entity,name,None)
        if value is not None: kwargs[name]=value
    return MessageEntity(**kwargs)


def resolve_mention_placeholder(text, entities, user):
    """Replace {mention} with a clickable text_mention while preserving formatting/entities."""
    text=text or ""
    entities=list(entities or [])
    if not user or "{mention}" not in text:
        return text, entities
    display=user.first_name or (f"@{user.username}" if user.username else "User")
    # Use one or more replacements; adjust UTF-16 offsets after each replacement.
    while "{mention}" in text:
        py_start=text.find("{mention}")
        py_end=py_start+len("{mention}")
        start_u=utf16_len(text[:py_start])
        old_len=utf16_len("{mention}")
        new_len=utf16_len(display)
        delta=new_len-old_len
        new_entities=[]
        for e in entities:
            e_start=e.offset; e_end=e.offset+e.length
            # Entities wholly before/after the placeholder can be shifted safely.
            if e_end <= start_u:
                new_entities.append(e)
            elif e_start >= start_u+old_len:
                new_entities.append(_entity_copy_with_offsets(e, e.offset+delta, e.length))
            else:
                # Do not let a formatting/custom-emoji entity accidentally cover the placeholder.
                # The placeholder itself is intended to become the text_mention entity.
                continue
        text=text[:py_start]+display+text[py_end:]
        new_entities.append(MessageEntity(type="text_mention", offset=start_u, length=new_len, user=user))
        entities=new_entities
    entities.sort(key=lambda e:(e.offset, e.length))
    return text, entities


def access_denied_config(bot, user_id):
    """Return the editable denial config matching the missing membership(s)."""
    async def _build():
        channel=await member_is_inside(bot,CHANNEL_ID,user_id)
        group=await member_is_inside(bot,FREE_GROUP_ID,user_id)
        if not channel and not group:
            return get_config("access_denied_both")
        if not channel:
            return get_config("access_denied_channel")
        return get_config("access_denied_group")
    return _build()


async def send_cfg(chat_id, cfg, bot, code=None, reply_markup=None, protect_content=None):
    markup=reply_markup or build_keyboard(cfg.get("buttons"),code)
    entities=deserialize_entities(json.dumps(cfg.get("entities",[]),ensure_ascii=False))
    text=cfg.get("text") or ""
    mention_user=cfg.get("_mention_user")
    if mention_user is not None:
        text, entities=resolve_mention_placeholder(text, entities, mention_user)
    kwargs={"chat_id":chat_id,"protect_content":protect() if protect_content is None else protect_content}
    if markup: kwargs["reply_markup"]=markup
    media_id=cfg.get("media_id"); media_type=cfg.get("media_type")
    if media_id:
        if text: kwargs["caption"]=text; kwargs["caption_entities"]=entities
        if media_type=="photo": return await bot.send_photo(photo=media_id,**kwargs)
        if media_type=="video": return await bot.send_video(video=media_id,**kwargs)
        if media_type=="animation": return await bot.send_animation(animation=media_id,**kwargs)
        if media_type=="document": return await bot.send_document(document=media_id,**kwargs)
        if media_type=="audio": return await bot.send_audio(audio=media_id,**kwargs)
    if text: return await bot.send_message(text=text,entities=entities,**kwargs)
    return None


async def send_file(chat_id,item,bot):
    entities=deserialize_entities(item["caption_entities"] if "caption_entities" in item.keys() else "[]")
    kwargs={"chat_id":chat_id,"protect_content":protect()}
    if item["caption"]: kwargs["caption"]=item["caption"]; kwargs["caption_entities"]=entities
    t=item["file_type"]; fid=item["file_id"]
    if t=="video": return await bot.send_video(video=fid,**kwargs)
    if t=="photo": return await bot.send_photo(photo=fid,**kwargs)
    if t=="animation": return await bot.send_animation(animation=fid,**kwargs)
    if t=="document": return await bot.send_document(document=fid,**kwargs)
    if t=="audio": return await bot.send_audio(audio=fid,**kwargs)
    if t=="voice": return await bot.send_voice(voice=fid,**kwargs)
    if t=="video_note": return await bot.send_video_note(video_note=fid,**kwargs)
    return None


async def schedule_delete(context, chat_id, message_ids, minutes):
    async def task():
        await asyncio.sleep(minutes*60)
        for mid in message_ids:
            try: await context.bot.delete_message(chat_id,mid)
            except Exception: pass
    asyncio.create_task(task())


async def deliver(update,context,code):
    chat_id=update.effective_chat.id; sent=[]
    if code.startswith("B_"):
        rows=get_batch(code)
        if not rows: await send_cfg(chat_id,get_config("not_found_message"),context.bot); return
        for row in rows:
            msg=await send_file(chat_id,row,context.bot)
            if msg: sent.append(msg.message_id)
    else:
        row=get_file(code)
        if not row: await send_cfg(chat_id,get_config("not_found_message"),context.bot); return
        msg=await send_file(chat_id,row,context.bot)
        if msg: sent.append(msg.message_id)
    if sent and get_setting("auto_delete_enabled")=="1":
        minutes=max(1,int(get_setting("auto_delete_minutes") or "10"))
        notice=get_config("auto_delete_notice"); notice["text"]=(notice.get("text") or DEFAULT_DELETE_NOTICE).replace("{minutes}",str(minutes))
        nmsg=await send_cfg(chat_id,notice,context.bot)
        if nmsg: sent.append(nmsg.message_id)
        await schedule_delete(context,chat_id,sent,minutes)


async def show_page(update,context,command):
    row=user_command(command)
    if not row or not row["enabled"]: await update.message.reply_text("❌ Command tidak tersedia.",protect_content=protect()); return
    cfg=json.loads(row["config"]); cfg["_mention_user"]=update.effective_user
    await send_cfg(update.effective_chat.id,cfg,context.bot)


async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user); uid=update.effective_user.id
    if is_banned(uid): await send_cfg(update.effective_chat.id,get_config("banned_message"),context.bot); return
    if get_setting("maintenance")=="1" and not is_admin(uid): await send_cfg(update.effective_chat.id,get_config("maintenance_config"),context.bot); return
    if context.args:
        code=context.args[0]
        if not (code.startswith("F_") or code.startswith("B_")): await send_cfg(update.effective_chat.id,get_config("invalid_link_message"),context.bot); return
        if not await check_access(context.bot,uid):
            fsub_cfg=get_config("fsub_config"); fsub_cfg["_mention_user"]=update.effective_user
            await send_cfg(update.effective_chat.id,fsub_cfg,context.bot,code=code,reply_markup=access_keyboard(code)); return
        ok_cfg=get_config("access_ok_message"); ok_cfg["_mention_user"]=update.effective_user
        await send_cfg(update.effective_chat.id,ok_cfg,context.bot); await deliver(update,context,code); return
    await send_cfg(update.effective_chat.id,load_target("start"),context.bot)


async def check_button(update,context):
    q=update.callback_query
    if is_banned(q.from_user.id): await q.answer("🚫 Kamu sedang dibanned.",show_alert=True); return
    if not await check_access(context.bot,q.from_user.id):
        denied=await access_denied_config(context.bot,q.from_user.id)
        denied["_mention_user"]=q.from_user
        denied_text, _ = resolve_mention_placeholder(denied.get("text") or "", deserialize_entities(json.dumps(denied.get("entities",[]),ensure_ascii=False)), q.from_user)
        await q.answer(denied_text[:200],show_alert=True); return
    await q.answer()
    try:
        ok=get_config("access_ok_message"); ok["_mention_user"]=q.from_user
        ok_text, ok_entities=resolve_mention_placeholder(ok.get("text") or DEFAULT_ACCESS_OK_TEXT, deserialize_entities(json.dumps(ok.get("entities",[]),ensure_ascii=False)), q.from_user)
        await q.edit_message_text(ok_text, entities=ok_entities)
    except Exception: pass
    await deliver(update,context,q.data.split(":",1)[1])


# ---------- Admin editor ----------
def admin_home_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("📊 Statistik",callback_data="adm:stats"),InlineKeyboardButton("📁 File",callback_data="adm:files")],[InlineKeyboardButton("🎨 Start",callback_data="adm:page:start"),InlineKeyboardButton("📢 FSUB",callback_data="adm:page:fsub")],[InlineKeyboardButton("👤 User Command",callback_data="adm:commands"),InlineKeyboardButton("📝 System Message",callback_data="adm:system")],[InlineKeyboardButton("👑 Admin",callback_data="adm:admins"),InlineKeyboardButton("🚫 Ban User",callback_data="adm:bans")],[InlineKeyboardButton("🗑️ Auto Delete",callback_data="adm:autodel"),InlineKeyboardButton("📢 Broadcast",callback_data="adm:broadcast")],[InlineKeyboardButton("💾 Backup",callback_data="adm:backup"),InlineKeyboardButton("🔧 Maintenance",callback_data="adm:maintenance")]])


def back_home(): return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Kembali",callback_data="adm:home")]])
def cancel_kb(): return InlineKeyboardMarkup([[InlineKeyboardButton("❌ BATAL",callback_data="adm:cancel")]])
def editor_cancel_kb(target): return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Kembali ke Editor",callback_data=f"adm:editcancel:{target}")]])


def editor_menu(uid,target):
    rows = [
        [InlineKeyboardButton("📝 Text", callback_data=f"edit:text:{target}"), InlineKeyboardButton("🖼️ Media", callback_data=f"edit:media:{target}")],
        [InlineKeyboardButton("🔘 Buttons", callback_data=f"edit:buttons:{target}"), InlineKeyboardButton("👁️ Preview", callback_data=f"edit:preview:{target}")],
    ]
    if target.startswith("cmd/"):
        rows.append([InlineKeyboardButton("📌 Deskripsi Command", callback_data=f"edit:description:{target}")])
    rows.extend([
        [InlineKeyboardButton("💾 Simpan", callback_data=f"edit:save:{target}"), InlineKeyboardButton("🗑️ Hapus Media", callback_data=f"edit:delmedia:{target}")],
        [InlineKeyboardButton("⬅️ Kembali", callback_data=f"adm:editorback:{target}")],
    ])
    return InlineKeyboardMarkup(rows)


def load_target(target):
    if target=="start":
        cfg=get_config("start_config")
        if not cfg.get("text") and (get_setting("start_text") or get_setting("start_media")):
            cfg=cfg_json(get_setting("start_text"),deserialize_entities(get_setting("start_entities")),get_setting("start_media"),get_setting("start_media_type"),[["⭐ JOIN MEMBERSHIP","url",get_setting("payment_link")],["📢 JOIN CHANNEL","url",get_setting("channel_link")],["👥 JOIN GROUP","url",get_setting("free_group_link")],["👤 OWNER BOT","url",get_setting("owner_link")]])
        return cfg
    if target=="fsub": return get_config("fsub_config")
    if target.startswith("cmd/"):
        row=user_command(target[4:]); return json.loads(row["config"]) if row else None
    return get_config(target)


def save_target(target,cfg):
    if target=="start":
        set_config("start_config",cfg); set_setting("start_text",cfg.get("text", "")); set_setting("start_entities",json.dumps(cfg.get("entities",[]),ensure_ascii=False)); set_setting("start_media",cfg.get("media_id", "")); set_setting("start_media_type",cfg.get("media_type", ""))
    elif target=="fsub": set_config("fsub_config",cfg)
    elif target.startswith("cmd/"):
        conn=db(); conn.execute("UPDATE user_commands SET config=? WHERE command=?",(json.dumps(cfg,ensure_ascii=False),target[4:])); conn.commit(); conn.close()
    else: set_config(target,cfg)


def session(uid,target):
    s=admin_sessions.setdefault(uid,{}); s["target"]=target; s["draft"]=json.loads(json.dumps(load_target(target),ensure_ascii=False)); return s


async def admin_command(update,context):
    if not is_admin(update.effective_user.id):
        await send_cfg(update.effective_chat.id,get_config("denied_message"),context.bot); return
    await update.message.reply_text("👑 NAKAHOSHI ADMIN PANEL\n\nPilih menu:",reply_markup=admin_home_markup(),protect_content=protect())


async def admin_callback(update,context):
    q=update.callback_query; uid=q.from_user.id
    if not is_admin(uid): await q.answer("Tidak punya akses.",show_alert=True); return
    await q.answer(); data=q.data
    if data in ("adm:home","adm:cancel"): admin_sessions.pop(uid,None); await q.edit_message_text("👑 NAKAHOSHI ADMIN PANEL\n\nPilih menu:",reply_markup=admin_home_markup()); return
    if data.startswith("adm:editcancel:"):
        target=data.split(":",2)[2]
        if uid in admin_sessions and admin_sessions[uid].get("target")==target:
            admin_sessions[uid]["action"]="editor"
            await q.edit_message_text("⚙️ EDITOR\n\nPerubahan masih berupa draft.",reply_markup=editor_menu(uid,target))
        else:
            await q.answer("Draft sudah tidak aktif.",show_alert=True)
        return
    if data.startswith("adm:editorback:"):
        target=data.split(":",2)[2]
        admin_sessions.pop(uid,None)
        if target.startswith("cmd/"):
            conn=db(); rows=conn.execute("SELECT command,description,enabled FROM user_commands ORDER BY command").fetchall(); conn.close(); kb=[[InlineKeyboardButton(("🟢 " if r["enabled"] else "🔴 ")+"/"+r["command"],callback_data=f"adm:cmd:{r['command']}")] for r in rows]; kb.append([InlineKeyboardButton("➕ Tambah Command",callback_data="adm:addcmd")]); kb.append([InlineKeyboardButton("⬅️ Kembali",callback_data="adm:home")]); await q.edit_message_text("👤 USER COMMAND\n\nPilih command:",reply_markup=InlineKeyboardMarkup(kb)); return
        if target in {"banned_message","denied_message","not_found_message","invalid_link_message","access_ok_message","access_denied_channel","access_denied_group","access_denied_both","cs_config","unban_config","auto_delete_notice"}:
            keys=[("banned_message","🚫 Pesan Banned"),("denied_message","⛔ Command Admin Ditolak"),("not_found_message","❌ File Tidak Ditemukan"),("invalid_link_message","🔗 Link Tidak Valid"),("access_ok_message","✅ Akses OK"),("access_denied_channel","❌ Cek Akses — Belum Channel"),("access_denied_group","❌ Cek Akses — Belum Group"),("access_denied_both","❌ Cek Akses — Belum Keduanya"),("cs_config","🛠️ Customer Service"),("unban_config","♻️ Unban"),("auto_delete_notice","🗑️ Notifikasi Auto Delete")]; kb=[[InlineKeyboardButton(label,callback_data=f"adm:sys:{key}")] for key,label in keys]; kb.append([InlineKeyboardButton("⬅️ Kembali",callback_data="adm:home")]); await q.edit_message_text("📝 SYSTEM MESSAGE\n\nPilih pesan:",reply_markup=InlineKeyboardMarkup(kb)); return
        await q.edit_message_text("👑 NAKAHOSHI ADMIN PANEL\n\nPilih menu:",reply_markup=admin_home_markup()); return
    if data=="adm:stats":
        conn=db(); vals=[conn.execute("SELECT COUNT(*) FROM files").fetchone()[0],conn.execute("SELECT COUNT(*) FROM batches").fetchone()[0],conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],conn.execute("SELECT COUNT(*) FROM banned_users").fetchone()[0]]; conn.close(); await q.edit_message_text(f"📊 STATISTIK\n\n📁 File: {vals[0]}\n📦 Batch: {vals[1]}\n👥 User: {vals[2]}\n🚫 Banned: {vals[3]}",reply_markup=back_home()); return
    if data=="adm:files":
        conn=db(); rows=conn.execute("SELECT code,file_type FROM files ORDER BY rowid DESC LIMIT 20").fetchall(); conn.close(); await q.edit_message_text("📁 FILE TERBARU\n\n"+(("\n".join(f"{r['code']} — {r['file_type']}" for r in rows)) if rows else "Belum ada file."),reply_markup=back_home()); return
    if data in ("adm:page:start","adm:page:fsub"):
        target="start" if data.endswith("start") else "fsub"; session(uid,target); await q.edit_message_text(f"⚙️ EDIT {target.upper()}\n\nMedia + Text + Buttons + Preview.\nSemua perubahan masih draft sampai disimpan.",reply_markup=editor_menu(uid,target)); return
    if data=="adm:commands":
        conn=db(); rows=conn.execute("SELECT command,description,enabled FROM user_commands ORDER BY command").fetchall(); conn.close(); kb=[]
        for r in rows: kb.append([InlineKeyboardButton(("🟢 " if r["enabled"] else "🔴 ")+"/"+r["command"],callback_data=f"adm:cmd:{r['command']}")])
        kb.append([InlineKeyboardButton("➕ Tambah Command",callback_data="adm:addcmd")]); kb.append([InlineKeyboardButton("⬅️ Kembali",callback_data="adm:home")]); await q.edit_message_text("👤 USER COMMAND\n\nPilih command:",reply_markup=InlineKeyboardMarkup(kb)); return
    if data.startswith("adm:cmd:"):
        command=data.split(":",2)[2]; session(uid,"cmd/"+command); row=user_command(command); status="🟢 AKTIF" if row and row["enabled"] else "🔴 NONAKTIF"; base=[list(row) for row in editor_menu(uid,"cmd/"+command).inline_keyboard]; base.append([InlineKeyboardButton("🔄 Aktif/Nonaktif",callback_data=f"adm:toggle:{command}"),InlineKeyboardButton("🗑️ Hapus",callback_data=f"adm:deletecmd:{command}")]); await q.edit_message_text(f"⚙️ EDIT /{command}\nStatus: {status}\n\nMedia + Text + Buttons + Preview",reply_markup=InlineKeyboardMarkup(base)); return
    if data=="adm:addcmd": admin_sessions[uid]={"action":"add_command"}; await q.edit_message_text("➕ TAMBAH COMMAND\n\nKirim format:\n/nama | Deskripsi",reply_markup=cancel_kb()); return
    if data.startswith("adm:toggle:"):
        command=data.split(":",2)[2]; conn=db(); row=conn.execute("SELECT enabled FROM user_commands WHERE command=?",(command,)).fetchone();
        if row: conn.execute("UPDATE user_commands SET enabled=? WHERE command=?",(0 if row["enabled"] else 1,command)); conn.commit()
        conn.close(); await refresh_command_menus(context.bot); await q.edit_message_text(f"🔄 /{command} diubah statusnya.",reply_markup=back_home()); return
    if data.startswith("adm:deletecmd:"):
        command=data.split(":",2)[2]; conn=db(); conn.execute("DELETE FROM user_commands WHERE command=?",(command,)); conn.commit(); conn.close(); admin_sessions.pop(uid,None); await refresh_command_menus(context.bot); await q.edit_message_text(f"🗑️ /{command} dihapus.",reply_markup=back_home()); return
    if data=="adm:system":
        keys=[("banned_message","🚫 Pesan Banned"),("denied_message","⛔ Command Admin Ditolak"),("not_found_message","❌ File Tidak Ditemukan"),("invalid_link_message","🔗 Link Tidak Valid"),("access_ok_message","✅ Akses OK"),("access_denied_channel","❌ Cek Akses — Belum Channel"),("access_denied_group","❌ Cek Akses — Belum Group"),("access_denied_both","❌ Cek Akses — Belum Keduanya"),("cs_config","🛠️ Customer Service"),("unban_config","♻️ Unban"),("auto_delete_notice","🗑️ Notifikasi Auto Delete")]; kb=[[InlineKeyboardButton(label,callback_data=f"adm:sys:{key}")] for key,label in keys]; kb.append([InlineKeyboardButton("⬅️ Kembali",callback_data="adm:home")]); await q.edit_message_text("📝 SYSTEM MESSAGE\n\nPilih pesan:",reply_markup=InlineKeyboardMarkup(kb)); return
    if data.startswith("adm:sys:"):
        target=data.split(":",2)[2]; session(uid,target); await q.edit_message_text("📝 EDIT SYSTEM MESSAGE\n\nBisa Text + Media + Buttons + Preview.",reply_markup=editor_menu(uid,target)); return
    if data=="adm:admins":
        conn=db(); rows=conn.execute("SELECT user_id FROM admins ORDER BY user_id").fetchall(); conn.close(); text="👑 ADMIN\n\n"+"\n".join(f"{r['user_id']}"+((" — OWNER") if r['user_id']==OWNER_ID else "") for r in rows); kb=[[InlineKeyboardButton("➕ Tambah Admin",callback_data="adm:addadmin")],[InlineKeyboardButton("🗑️ Hapus Admin",callback_data="adm:deladmin")],[InlineKeyboardButton("⬅️ Kembali",callback_data="adm:home")]]; await q.edit_message_text(text,reply_markup=InlineKeyboardMarkup(kb)); return
    if data=="adm:addadmin": admin_sessions[uid]={"action":"add_admin"}; await q.edit_message_text("➕ TAMBAH ADMIN\n\nKirim Telegram User ID.",reply_markup=cancel_kb()); return
    if data=="adm:deladmin": admin_sessions[uid]={"action":"del_admin"}; await q.edit_message_text("🗑️ HAPUS ADMIN\n\nKirim Telegram User ID. Owner tidak dapat dihapus.",reply_markup=cancel_kb()); return
    if data=="adm:bans":
        conn=db(); rows=conn.execute("SELECT user_id,reason FROM banned_users ORDER BY banned_at DESC LIMIT 50").fetchall(); conn.close(); text="🚫 BANNED USERS\n\n"+(("\n".join(f"{r['user_id']} — {r['reason'] or '-'}" for r in rows)) if rows else "Belum ada user banned."); kb=[[InlineKeyboardButton("🔨 Ban User",callback_data="adm:ban")],[InlineKeyboardButton("♻️ Unban User",callback_data="adm:unban")],[InlineKeyboardButton("⬅️ Kembali",callback_data="adm:home")]]; await q.edit_message_text(text,reply_markup=InlineKeyboardMarkup(kb)); return
    if data=="adm:ban": admin_sessions[uid]={"action":"ban"}; await q.edit_message_text("🔨 BAN USER\n\nKirim User ID.\nOpsional alasan: 123456789 | alasan",reply_markup=cancel_kb()); return
    if data=="adm:unban": admin_sessions[uid]={"action":"unban"}; await q.edit_message_text("♻️ UNBAN USER\n\nKirim User ID.",reply_markup=cancel_kb()); return
    if data=="adm:autodel":
        status="🟢 AKTIF" if get_setting("auto_delete_enabled")=="1" else "🔴 NONAKTIF"; await q.edit_message_text(f"🗑️ AUTO DELETE FILE\n\nStatus: {status}\nWaktu: {get_setting('auto_delete_minutes')} menit",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🟢 Aktifkan",callback_data="adm:ad:on"),InlineKeyboardButton("🔴 Matikan",callback_data="adm:ad:off")],[InlineKeyboardButton("⏱️ Atur Waktu",callback_data="adm:ad:time"),InlineKeyboardButton("📝 Notifikasi",callback_data="adm:ad:msg")],[InlineKeyboardButton("⬅️ Kembali",callback_data="adm:home")]])); return
    if data=="adm:ad:on": set_setting("auto_delete_enabled","1"); await q.edit_message_text("🟢 Auto Delete aktif.",reply_markup=back_home()); return
    if data=="adm:ad:off": set_setting("auto_delete_enabled","0"); await q.edit_message_text("🔴 Auto Delete dimatikan.",reply_markup=back_home()); return
    if data=="adm:ad:time": admin_sessions[uid]={"action":"ad_time"}; await q.edit_message_text("⏱️ Kirim jumlah menit. Contoh: 10",reply_markup=cancel_kb()); return
    if data=="adm:ad:msg": session(uid,"auto_delete_notice"); await q.edit_message_text("📝 EDIT NOTIFIKASI AUTO DELETE",reply_markup=editor_menu(uid,"auto_delete_notice")); return
    if data=="adm:broadcast": admin_sessions[uid]={"action":"broadcast"}; await q.edit_message_text("📢 BROADCAST\n\nKirim satu pesan/media yang ingin dibroadcast.\nSetelah itu gunakan /broadcast_confirm untuk mengirim.",reply_markup=cancel_kb()); return
    if data=="adm:backup":
        try:
            with open(DB_NAME,"rb") as f: await context.bot.send_document(uid,f,caption="💾 Backup database NakaFileBOT",protect_content=True)
        except Exception as e: await q.answer("Backup gagal: "+str(e)[:150],show_alert=True)
        return
    if data=="adm:maintenance":
        status="🟢 AKTIF" if get_setting("maintenance")=="1" else "🔴 NONAKTIF"; await q.edit_message_text(f"🔧 MAINTENANCE\n\nStatus: {status}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🟢 Aktifkan",callback_data="adm:maint:on"),InlineKeyboardButton("🔴 Matikan",callback_data="adm:maint:off")],[InlineKeyboardButton("📝 Edit Pesan",callback_data="adm:maint:msg")],[InlineKeyboardButton("⬅️ Kembali",callback_data="adm:home")]])); return
    if data=="adm:maint:on": set_setting("maintenance","1"); await q.edit_message_text("🟢 Maintenance aktif.",reply_markup=back_home()); return
    if data=="adm:maint:off": set_setting("maintenance","0"); await q.edit_message_text("🔴 Maintenance dimatikan.",reply_markup=back_home()); return
    if data=="adm:maint:msg": session(uid,"maintenance_config"); await q.edit_message_text("📝 EDIT PESAN MAINTENANCE",reply_markup=editor_menu(uid,"maintenance_config")); return
    if data.startswith("edit:"):
        _,action,target=data.split(":",2); s=admin_sessions.get(uid)
        if not s or s.get("target")!=target: session(uid,target); s=admin_sessions[uid]
        cfg=s["draft"]
        if action=="text": s["action"]="edit_text"; await q.edit_message_text("📝 KIRIM TEKS BARU\n\nKirim pesan langsung dari Telegram. Formatting Telegram akan ikut tersimpan. Gunakan {mention} untuk menyebut nama user yang sedang memakai bot.",reply_markup=editor_cancel_kb(target)); return
        if action=="description": s["action"]="edit_description"; await q.edit_message_text("📌 EDIT DESKRIPSI COMMAND\n\nKirim deskripsi baru untuk command ini. Maksimal 256 karakter.",reply_markup=editor_cancel_kb(target)); return
        if action=="media": s["action"]="edit_media"; await q.edit_message_text("🖼️ KIRIM MEDIA\n\nBisa Foto, GIF/Animation, Video, Dokumen, atau Audio.",reply_markup=editor_cancel_kb(target)); return
        if action=="delmedia": cfg["media_id"]=""; cfg["media_type"]=""; await q.edit_message_text("🗑️ Media di draft sudah dihapus. Belum tersimpan.",reply_markup=editor_menu(uid,target)); return
        if action=="buttons": await show_buttons(q,uid,target); return
        if action=="preview": await preview_cfg(q,context,uid,target,cfg); return
        if action=="save": save_target(target,cfg); admin_sessions.pop(uid,None); await q.edit_message_text("💾 PERUBAHAN TERSIMPAN.\n\nSetting lama sudah diganti dengan draft ini.",reply_markup=back_home()); return


async def show_buttons(q,uid,target):
    cfg=admin_sessions[uid]["draft"]; buttons=cfg.get("buttons",[]); kb=[]
    for i,b in enumerate(buttons): kb.append([InlineKeyboardButton(f"✏️ {b[0]}",callback_data=f"btn:edit:{target}:{i}"),InlineKeyboardButton("🗑️",callback_data=f"btn:del:{target}:{i}")])
    kb.append([InlineKeyboardButton("➕ Tambah Button",callback_data=f"btn:add:{target}")]); kb.append([InlineKeyboardButton("⬅️ Editor",callback_data=f"btn:back:{target}")]); await q.edit_message_text("🔘 BUTTON MANAGER\n\nSemua perubahan masih di draft.",reply_markup=InlineKeyboardMarkup(kb))


async def preview_cfg(q,context,uid,target,cfg):
    await q.edit_message_text("👁️ PREVIEW\n\nPreview lengkap sedang dikirim di bawah...",reply_markup=back_home()); await send_cfg(q.message.chat_id,cfg,context.bot,protect_content=False)


async def button_callback(update,context):
    q=update.callback_query; uid=q.from_user.id
    if not is_admin(uid): await q.answer("Tidak punya akses.",show_alert=True); return
    data=q.data.split(":"); action,target=data[1],data[2]; s=admin_sessions.get(uid)
    if not s or s.get("target")!=target: await q.answer("Draft sudah tidak aktif.",show_alert=True); return
    cfg=s["draft"]
    if action=="back": await q.answer(); await q.edit_message_text("⚙️ EDITOR\n\nPilih bagian:",reply_markup=editor_menu(uid,target)); return
    if action=="add": s["action"]="add_button"; await q.answer(); await q.edit_message_text("➕ TAMBAH BUTTON\n\nFormat:\n#g 👩‍🦳 JOIN CHANNEL - https://t.me/Nakahoshi && #g 😎 JOIN GROUP - https://t.me/+lYiuGXIVy1JkYWE9\n#g ⛑️ CEK AKSES -\n#r ✨ JOIN MEMBERSHIP - https://t.me/nakanosqbot?start=NakaFileBOT\n\nEnter/newline = baris baru. && = satu baris. Custom Emoji Premium di teks akan dipakai sebagai icon tombol.",reply_markup=editor_cancel_kb(target)); return
    idx=int(data[3])
    if action=="del": cfg["buttons"].pop(idx); await q.answer("Button dihapus dari draft."); await show_buttons(q,uid,target); return
    if action=="edit": s["action"]="edit_button"; s["button_index"]=idx; await q.answer(); await q.edit_message_text(f"✏️ EDIT BUTTON\n\nSaat ini: {cfg['buttons'][idx][0]}\nURL/Action: {cfg['buttons'][idx][2] if len(cfg['buttons'][idx])>2 else ''}\n\nKirim format baru seperti:\n#g 👩‍🦳 JOIN CHANNEL - https://t.me/Nakahoshi\n#g ⛑️ CEK AKSES -\n\nEnter/newline = baris baru. && = satu baris.",reply_markup=editor_cancel_kb(target)); return


async def receive_admin_media(update,context):
    uid=update.effective_user.id
    if not is_admin(uid):
        return
    save_user(update.effective_user)
    msg=update.message
    s=admin_sessions.get(uid)
    action=s.get("action") if s else None

    if action=="broadcast":
        s["broadcast_message_id"]=msg.message_id; s["broadcast_chat_id"]=uid; s["action"]="broadcast_confirm"
        await msg.reply_text("📢 Pesan siap dibroadcast.\n\nKetik /broadcast_confirm untuk KIRIM ke semua user, atau /cancel untuk batal."); return

    if action=="edit_media":
        cfg=s["draft"]
        if msg.photo: cfg["media_id"]=msg.photo[-1].file_id; cfg["media_type"]="photo"
        elif msg.video: cfg["media_id"]=msg.video.file_id; cfg["media_type"]="video"
        elif msg.animation: cfg["media_id"]=msg.animation.file_id; cfg["media_type"]="animation"
        elif msg.document: cfg["media_id"]=msg.document.file_id; cfg["media_type"]="document"
        elif msg.audio: cfg["media_id"]=msg.audio.file_id; cfg["media_type"]="audio"
        elif msg.voice: cfg["media_id"]=msg.voice.file_id; cfg["media_type"]="voice"
        elif msg.video_note: cfg["media_id"]=msg.video_note.file_id; cfg["media_type"]="video_note"
        else: return
        if msg.caption is not None:
            cfg["text"]=msg.caption; cfg["entities"]=serialize_entities(msg.caption_entities)
        s["action"]="editor"
        await msg.reply_text("🖼️ Media masuk ke draft. Belum disimpan.",reply_markup=editor_menu(uid,s["target"])); return

    is_media=bool(msg.photo or msg.video or msg.animation or msg.document or msg.audio or msg.voice or msg.video_note)
    if not is_media: return

    if pending_batches.get(uid) is not None:
        if msg.photo: item=(msg.photo[-1].file_id,"photo",msg.caption or "",msg.caption_entities or [])
        elif msg.video: item=(msg.video.file_id,"video",msg.caption or "",msg.caption_entities or [])
        elif msg.animation: item=(msg.animation.file_id,"animation",msg.caption or "",msg.caption_entities or [])
        elif msg.document: item=(msg.document.file_id,"document",msg.caption or "",msg.caption_entities or [])
        elif msg.audio: item=(msg.audio.file_id,"audio",msg.caption or "",msg.caption_entities or [])
        elif msg.voice: item=(msg.voice.file_id,"voice",msg.caption or "",msg.caption_entities or [])
        else: item=(msg.video_note.file_id,"video_note","",[])
        pending_batches[uid].append(item); await msg.reply_text(f"✅ Ditambahkan ke batch. Total: {len(pending_batches[uid])} file."); return

    # Any media that is not explicitly in broadcast/edit-media/batch mode is
    # always treated as a NEW FILE SHARE upload. This prevents a stale admin
    # editor action (for example add_button/edit_button) from swallowing the
    # media and leaving the admin without a generated F_ link.
    if action not in (None, "editor"):
        admin_sessions.pop(uid, None)

    if msg.photo: file_id,ftype=msg.photo[-1].file_id,"photo"
    elif msg.video: file_id,ftype=msg.video.file_id,"video"
    elif msg.animation: file_id,ftype=msg.animation.file_id,"animation"
    elif msg.document: file_id,ftype=msg.document.file_id,"document"
    elif msg.audio: file_id,ftype=msg.audio.file_id,"audio"
    elif msg.voice: file_id,ftype=msg.voice.file_id,"voice"
    else: file_id,ftype=msg.video_note.file_id,"video_note"
    code=create_file_record(file_id,ftype,msg.caption or "",msg.caption_entities or [])
    admin_sessions.pop(uid,None)
    bot_username=context.bot.username or (await context.bot.get_me()).username
    await msg.reply_text(f"✅ File tersimpan!\n\n🔗 Link:\nhttps://t.me/{bot_username}?start={code}\n\nCode: {code}")

def utf16_len(text):
    return len((text or "").encode("utf-16-le")) // 2


def utf16_index_to_py(text, index):
    if index <= 0:
        return 0
    units = 0
    for i, ch in enumerate(text or ""):
        units += 2 if ord(ch) > 0xFFFF else 1
        if units >= index:
            return i + 1
    return len(text or "")


def custom_emojis_for_range(text, entities, start_py, end_py):
    """Return custom-emoji entities fully contained in the exact label range.

    Telegram entity offsets are UTF-16 based.  We deliberately require the
    entity to be fully inside the label instead of accepting any overlap; an
    overlapping entity from another part of the button must never become the
    button icon.
    """
    start_u = utf16_len((text or "")[:start_py])
    end_u = utf16_len((text or "")[:end_py])
    found = []
    for entity in entities or []:
        if getattr(entity, "type", None) != "custom_emoji" or not getattr(entity, "custom_emoji_id", None):
            continue
        e_start = getattr(entity, "offset", 0)
        e_end = e_start + getattr(entity, "length", 0)
        if e_start >= start_u and e_end <= end_u:
            found.append(entity)
    return found


def custom_emoji_for_range(text, entities, start_py, end_py):
    found = custom_emojis_for_range(text, entities, start_py, end_py)
    if not found:
        return None, None
    entity = found[0]
    return str(entity.custom_emoji_id), entity


def strip_custom_emojis_from_label(label, entities, label_start_py, full_text):
    """Remove only Telegram custom-emoji characters from a button label.

    The first custom emoji becomes the button icon.  All custom-emoji
    characters are removed from the visible label so the same premium emoji
    cannot appear once as an icon and again inside the label.
    """
    if not label or not entities:
        return label
    removals = []
    for entity in entities:
        entity_start_py = utf16_index_to_py(full_text, getattr(entity, "offset", 0))
        entity_end_py = utf16_index_to_py(
            full_text,
            getattr(entity, "offset", 0) + getattr(entity, "length", 0)
        )
        rel_start = entity_start_py - label_start_py
        rel_end = entity_end_py - label_start_py
        if 0 <= rel_start < len(label) and rel_end > rel_start:
            removals.append((rel_start, min(rel_end, len(label))))
    for start, end in sorted(removals, reverse=True):
        label = label[:start] + label[end:]
    return label


def parse_button_text(message):
    text = message.text or ""
    entities = message.entities or []
    result = []
    row_id = 0
    absolute_line_start = 0
    for raw_line in text.splitlines(True):
        line_text = raw_line.rstrip("\r\n")
        if not line_text.strip():
            absolute_line_start += len(raw_line)
            continue
        cursor = absolute_line_start
        for raw_part in line_text.split("&&"):
            part_start = text.find(raw_part, cursor, absolute_line_start + len(line_text))
            if part_start < 0:
                part_start = cursor
            cursor = part_start + len(raw_part) + 2
            part = raw_part.strip()
            if not part:
                continue
            m = re.match(r"^#([grp])\s+(.+?)\s*-\s*(https?://\S+)\s*$", part, re.I)
            if m:
                style_token = "#" + m.group(1).lower()
                label = m.group(2).strip()
                url = m.group(3).strip()
                kind = "url"
            else:
                m = re.match(r"^#([grp])\s+(.+?)\s*-\s*$", part, re.I)
                if m:
                    style_token = "#" + m.group(1).lower()
                    label = m.group(2).strip()
                    url = ""
                    kind = "check"
                else:
                    m = re.match(r"^(.+?)\s*-\s*(https?://\S+)\s*$", part)
                    if m:
                        style_token = None
                        label = m.group(1).strip()
                        url = m.group(2).strip()
                        kind = "url"
                    else:
                        m = re.match(r"^(.+?)\s*-\s*$", part)
                        if m:
                            style_token = None
                            label = m.group(1).strip()
                            url = ""
                            kind = "check"
                        else:
                            raise ValueError(f"Format button salah: {part}")
            # Resolve the entity against the exact label span only.  Do not
            # search the whole button line: another custom emoji on the same
            # line must never become an extra/surprise button icon.
            label_in_part = label
            label_offset_in_part = part.find(label_in_part)
            if label_offset_in_part < 0:
                label_offset_in_part = 0
            label_pos = part_start + max(0, raw_part.find(part)) + label_offset_in_part
            label_entities = custom_emojis_for_range(
                text, entities, label_pos, label_pos + len(label)
            )
            icon = str(label_entities[0].custom_emoji_id) if label_entities else None
            if label_entities:
                label = strip_custom_emojis_from_label(label, label_entities, label_pos, text).strip()
            style = {"#g": "success", "#r": "danger", "#p": "primary"}.get(style_token)
            result.append([label, kind, url, style, icon, "new", row_id])
        row_id += 1
        absolute_line_start += len(raw_line)
    if not result:
        raise ValueError("Minimal 1 button harus diisi.")
    return result

async def admin_text_input(update,context):
    uid=update.effective_user.id
    if not is_admin(uid): return
    msg=update.message; s=admin_sessions.get(uid); action=s.get("action") if s else None
    if action=="broadcast":
        s["broadcast_message_id"]=msg.message_id; s["broadcast_chat_id"]=uid; s["action"]="broadcast_confirm"; await msg.reply_text("📢 Pesan siap dibroadcast.\n\nKetik /broadcast_confirm untuk KIRIM ke semua user, atau /cancel untuk batal."); return
    if action=="add_command":
        m=re.match(r"^/?([a-zA-Z0-9_]+)\s*\|\s*(.+)$",msg.text.strip())
        if not m: await msg.reply_text("Format salah. Contoh: /help | Bantuan Nakahoshi"); return
        cmd,desc=m.group(1).lower(),m.group(2); reserved={"start","admin","batch","done","cancelbatch","cancel","broadcast","broadcast_confirm","setpayment","setchannel","setgroup","setowner"}
        if cmd in reserved: await msg.reply_text("❌ Nama command dipakai sistem/admin."); return
        conn=db(); exists=conn.execute("SELECT 1 FROM user_commands WHERE command=?",(cmd,)).fetchone()
        if exists: conn.close(); await msg.reply_text("❌ Command sudah ada."); return
        cfg=cfg_json("Tulis isi command ini..."); conn.execute("INSERT INTO user_commands(command,description,config,enabled) VALUES(?,?,?,1)",(cmd,desc,json.dumps(cfg,ensure_ascii=False))); conn.commit(); conn.close(); admin_sessions.pop(uid,None); await refresh_command_menus(context.bot); await msg.reply_text(f"✅ /{cmd} dibuat. Buka /admin → User Command untuk mengaturnya."); return
    if action=="add_admin":
        try: new=int(msg.text.strip())
        except: await msg.reply_text("❌ User ID harus angka."); return
        conn=db(); conn.execute("INSERT OR IGNORE INTO admins(user_id,added_at,added_by) VALUES(?,?,?)",(new,datetime.now().isoformat(timespec="seconds"),uid)); conn.commit(); conn.close(); admin_sessions.pop(uid,None); await msg.reply_text(f"✅ {new} sekarang admin."); return
    if action=="del_admin":
        try: new=int(msg.text.strip())
        except: await msg.reply_text("❌ User ID harus angka."); return
        if new==OWNER_ID: await msg.reply_text("🚫 Owner utama tidak dapat dihapus."); return
        conn=db(); conn.execute("DELETE FROM admins WHERE user_id=?",(new,)); conn.commit(); conn.close(); admin_sessions.pop(uid,None); await msg.reply_text(f"🗑️ Admin {new} dihapus."); return
    if action in ("ban","unban"):
        raw=msg.text.strip(); parts=raw.split("|",1)
        try: target=int(parts[0].strip())
        except: await msg.reply_text("❌ User ID harus angka."); return
        if action=="ban":
            if target in get_admin_ids(): await msg.reply_text("🚫 Admin tidak dapat dibanned."); return
            reason=parts[1].strip() if len(parts)>1 else ""; conn=db(); conn.execute("INSERT OR REPLACE INTO banned_users(user_id,reason,banned_at,banned_by) VALUES(?,?,?,?)",(target,reason,datetime.now().isoformat(timespec="seconds"),uid)); conn.commit(); conn.close(); admin_sessions.pop(uid,None); await msg.reply_text(f"🔨 User {target} berhasil dibanned.")
        else:
            conn=db(); conn.execute("DELETE FROM banned_users WHERE user_id=?",(target,)); conn.commit(); conn.close(); admin_sessions.pop(uid,None); await msg.reply_text(f"♻️ User {target} berhasil di-unban.")
        return
    if action=="ad_time":
        try: minutes=int(msg.text.strip()); assert minutes>=1
        except: await msg.reply_text("❌ Masukkan angka menit minimal 1."); return
        set_setting("auto_delete_minutes",str(minutes)); admin_sessions.pop(uid,None); await msg.reply_text(f"⏱️ Auto Delete diatur {minutes} menit."); return
    if action=="edit_text":
        s["draft"]["text"]=msg.text; s["draft"]["entities"]=serialize_entities(msg.entities); s["action"]="editor"; await msg.reply_text("📝 Text masuk draft. Formatting Telegram ikut disimpan. Belum disimpan.",reply_markup=editor_menu(uid,s["target"])); return
    if action=="edit_description":
        if not s.get("target","").startswith("cmd/"): await msg.reply_text("❌ Deskripsi hanya tersedia untuk User Command."); return
        desc=(msg.text or "").strip()[:256]
        if not desc: await msg.reply_text("❌ Deskripsi tidak boleh kosong."); return
        command=s["target"][4:]
        conn=db(); conn.execute("UPDATE user_commands SET description=? WHERE command=?",(desc,command)); conn.commit(); conn.close()
        s["action"]="editor"; await refresh_command_menus(context.bot); await msg.reply_text("📌 Deskripsi command diperbarui. Belum ada perubahan isi yang dibuang.",reply_markup=editor_menu(uid,s["target"])); return
    if action in ("add_button","edit_button"):
        try:
            parsed=parse_button_text(msg)
        except ValueError as e:
            await msg.reply_text(f"❌ {e}\n\nContoh: Nama Tombol - https://t.me/contoh\nUntuk Cek Akses: #g ⛑️ CEK AKSES -"); return
        if action=="add_button":
            s["draft"].setdefault("buttons",[]).extend(parsed)
            note="🔘 Button ditambahkan ke draft."
        else:
            idx=s.get("button_index")
            if idx is None or idx >= len(s["draft"].get("buttons",[])):
                await msg.reply_text("❌ Button yang diedit sudah tidak tersedia."); return
            # An edit replaces one button with the first parsed button and
            # preserves the remaining saved buttons exactly.
            s["draft"]["buttons"][idx]=parsed[0]
            note="✏️ Button diperbarui di draft."
        s["action"]="editor"; await msg.reply_text(note,reply_markup=editor_menu(uid,s["target"])); return


async def cancel_command(update,context):
    if is_admin(update.effective_user.id): admin_sessions.pop(update.effective_user.id,None); pending_batches.pop(update.effective_user.id,None); await update.message.reply_text("❌ Dibatalkan.")


async def batch_command(update,context):
    if not is_admin(update.effective_user.id): return
    pending_batches[update.effective_user.id]=[]; await update.message.reply_text("📦 MODE BATCH AKTIF\n\nKirim file. Setelah selesai ketik /done.\nBatal: /cancelbatch")

async def done_command(update,context):
    uid=update.effective_user.id
    if not is_admin(uid): return
    items=pending_batches.pop(uid,None)
    if items is None: await update.message.reply_text("Tidak ada batch aktif."); return
    if not items: await update.message.reply_text("❌ Batch kosong."); return
    code=create_batch(uid,items); await update.message.reply_text(f"✅ BATCH SELESAI\n\n📦 Total: {len(items)}\n🔗 https://t.me/{context.bot.username}?start={code}\n\nCode: {code}")


async def start_broadcast(update,context):
    uid=update.effective_user.id
    if not is_admin(uid): return
    admin_sessions[uid]={"action":"broadcast"}
    await update.message.reply_text("📢 BROADCAST\n\nKirim satu pesan/media yang ingin dibroadcast.\nSetelah itu ketik /broadcast_confirm untuk KIRIM ke semua user, atau /cancel untuk batal.",protect_content=protect())


async def broadcast_confirm(update,context):
    uid=update.effective_user.id
    if not is_admin(uid): return
    s=admin_sessions.get(uid)
    if not s or s.get("action")!="broadcast_confirm" or not s.get("broadcast_message_id"): await update.message.reply_text("Tidak ada broadcast yang menunggu. Jalankan /broadcast dulu."); return
    conn=db(); users=[r["user_id"] for r in conn.execute("SELECT user_id FROM users").fetchall()]; conn.close(); ok=bad=0
    for target in users:
        try: await context.bot.copy_message(chat_id=target,from_chat_id=uid,message_id=s["broadcast_message_id"],protect_content=protect()); ok+=1
        except Exception: bad+=1
        await asyncio.sleep(0.04)
    admin_sessions.pop(uid,None); await update.message.reply_text(f"📢 BROADCAST SELESAI\n\n✅ Terkirim: {ok}\n❌ Gagal: {bad}")


async def generic_command(update,context):
    cmd=update.message.text.split()[0].lstrip("/").split("@")[0].lower()
    if cmd in {"start","admin","batch","done","cancelbatch","cancel","broadcast","broadcast_confirm","setpayment","setchannel","setgroup","setowner"}: return
    save_user(update.effective_user)
    if is_banned(update.effective_user.id): await send_cfg(update.effective_chat.id,get_config("banned_message"),context.bot); return
    row=user_command(cmd)
    if row and row["enabled"]: await show_page(update,context,cmd)


async def set_link(update,context,key,label):
    if not is_admin(update.effective_user.id): return
    if not context.args: await update.message.reply_text("Gunakan command dengan URL."); return
    set_setting(key," ".join(context.args).strip()); await update.message.reply_text(f"✅ {label} berhasil diubah.")

async def setpayment(update,context): await set_link(update,context,"payment_link","Payment link")
async def setchannel(update,context): await set_link(update,context,"channel_link","Channel link")
async def setgroup(update,context):
    await set_link(update,context,"free_group_link","Group link")

async def setowner(update,context):
    await set_link(update,context,"owner_link","Owner link")

async def refresh_command_menus(bot):
    conn=db()
    rows=conn.execute("SELECT command,description FROM user_commands WHERE enabled=1 ORDER BY rowid").fetchall()
    conn.close()
    user_cmds=[BotCommand("start","Buka bot / akses file")]
    user_cmds += [BotCommand(r["command"],(r["description"] or "")[:256]) for r in rows]
    await bot.set_my_commands(user_cmds,scope=BotCommandScopeDefault())
    admin_cmds=user_cmds+[
        BotCommand("admin","Admin panel"),
        BotCommand("batch","Mulai batch file"),
        BotCommand("done","Selesaikan batch"),
        BotCommand("cancelbatch","Batalkan batch"),
        BotCommand("cancel","Batalkan proses"),
        BotCommand("broadcast","Broadcast"),
        BotCommand("broadcast_confirm","Konfirmasi broadcast"),
    ]
    for uid in get_admin_ids():
        try:
            await bot.set_my_commands(admin_cmds,scope=BotCommandScopeChat(chat_id=uid))
        except Exception as e:
            print("set admin commands error",uid,e)

async def post_init(application):
    await refresh_command_menus(application.bot)

async def error_handler(update,context):
    print("ERROR:",context.error)

def main():
    init_db()
    app=Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("admin",admin_command))
    app.add_handler(CommandHandler("batch",batch_command))
    app.add_handler(CommandHandler("done",done_command))
    app.add_handler(CommandHandler("cancelbatch",cancel_command))
    app.add_handler(CommandHandler("cancel",cancel_command))
    app.add_handler(CommandHandler("broadcast",start_broadcast))
    app.add_handler(CommandHandler("broadcast_confirm",broadcast_confirm))
    app.add_handler(CommandHandler("setpayment",setpayment))
    app.add_handler(CommandHandler("setchannel",setchannel))
    app.add_handler(CommandHandler("setgroup",setgroup))
    app.add_handler(CommandHandler("setowner",setowner))
    app.add_handler(CallbackQueryHandler(check_button,pattern=r"^check:"))
    app.add_handler(CallbackQueryHandler(admin_callback,pattern=r"^(adm:|edit:)"))
    app.add_handler(CallbackQueryHandler(button_callback,pattern=r"^btn:"))
    media_filters=filters.PHOTO|filters.VIDEO|filters.ANIMATION|filters.Document.ALL|filters.AUDIO|filters.VOICE|filters.VIDEO_NOTE
    app.add_handler(MessageHandler(media_filters,receive_admin_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,admin_text_input))
    app.add_handler(MessageHandler(filters.COMMAND,generic_command))
    app.add_error_handler(error_handler)
    print("Bot sedang berjalan...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=="__main__":
    main()
