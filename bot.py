import os
import sys
import json
import asyncio
import random
import re
import platform
import time
import sqlite3
import hashlib
import secrets
import hmac
import subprocess
from collections import deque
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

CURRENT_GUILD_ID: ContextVar[Optional[int]] = ContextVar("CURRENT_GUILD_ID", default=None)


import aiohttp
from aiohttp import web
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()


TOKEN = os.getenv("DISCORD_TOKEN")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "0"))
DBRESET_ENABLED = False
UPDATE_ENABLED = os.getenv("UPDATE_ENABLED", "0").strip() in ("1", "true", "True", "yes")
UPDATE_AUTO_INSTALL = os.getenv("UPDATE_AUTO_INSTALL", "0").strip() in ("1", "true", "True", "yes")
# Détecte toute modification du bot.py GitHub (même sans changer version.txt)
UPDATE_DETECT_HASH = os.getenv("UPDATE_DETECT_HASH", "1").strip() in ("1", "true", "True", "yes")
UPDATE_VERSION_URL = os.getenv("UPDATE_VERSION_URL", "").strip()
UPDATE_CODE_URL = os.getenv("UPDATE_CODE_URL", "").strip()
try:
    UPDATE_INTERVAL = max(5, int(os.getenv("UPDATE_INTERVAL", "300")))  # minimum 5 secondes
except Exception:
    UPDATE_INTERVAL = 300

START_TIME = time.time()
BOT_VERSION = "2.1.3"
BOT_CREATOR = "9kr"
try:
    BOT_FILE = os.path.abspath(__file__)
except Exception:
    BOT_FILE = os.path.abspath("bot.py")

DATA_DIR = "data"
DB_PATH = os.path.join(DATA_DIR, "bot.db")
OWNERS_FILE = os.path.join(DATA_DIR, "owners.json")
BLACKLIST_FILE = os.path.join(DATA_DIR, "blacklist.json")
BANNED_WORDS_FILE = os.path.join(DATA_DIR, "banned_words.json")
OWNERPLUS_FILE = os.path.join(DATA_DIR, "ownerplus.json")
OWNERPLUS_LOG = os.path.join(DATA_DIR, "logs", "ownerplus.log")
LOCKED_NAMES_FILE = os.path.join(DATA_DIR, "locked_names.json")
GIVEAWAYS_FILE = os.path.join(DATA_DIR, "giveaways.json")
TICKETS_FILE = os.path.join(DATA_DIR, "tickets.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
LEVELS_FILE = os.path.join(DATA_DIR, "levels.json")
XP_FILE = os.path.join(DATA_DIR, "xp.json")
XP_COOLDOWN = {}
NUKE_FILE = os.path.join(DATA_DIR, "NUKE.json")
INFRACTIONS_FILE = os.path.join(DATA_DIR, "infractions.json")
NOTES_FILE = os.path.join(DATA_DIR, "notes.json")
SANCTIONS_FILE = os.path.join(DATA_DIR, "sanctions.json")
TEMPROLES_FILE = os.path.join(DATA_DIR, "temproles.json")
BACKUPS_FILE = os.path.join(DATA_DIR, "backups.json")
BIRTHDAYS_FILE = os.path.join(DATA_DIR, "birthdays.json")
REPORTS_FILE = os.path.join(DATA_DIR, "reports.json")
SUGGESTS_FILE = os.path.join(DATA_DIR, "suggestions.json")
VOICE_BL_FILE = os.path.join(DATA_DIR, "voice_blacklist.json")
INVITES_FILE = os.path.join(DATA_DIR, "invites.json")
WEBHOOKS_FILE = os.path.join(DATA_DIR, "webhooks.json")
ERRORS_FILE = os.path.join(DATA_DIR, "errors.json")
ERROR_DUMP_DIR = os.path.join(DATA_DIR, "error_dumps")
PARROT_UNTIL: Dict[int, float] = {}
WORD_STRIKES: Dict[int, int] = {}
PRIV_VCS: Dict[int, int] = {}

SNIPE_CACHE: Dict[int, discord.Message] = {}
JOIN_TRACKER: Dict[int, List[float]] = {}
SPAM_TRACKER: Dict[int, List[dict]] = {}
DEFAULT_CONFIG = {
    "LOG_CHANNEL_ID": None,
    "TICKET_LOG_CHANNEL_ID": None,
    "TICKET_CATEGORY_ID": None,
    "ANTILINK": True,
    "ANTIRAID": False,
    "ANTIRAID_JOINS": 5,
    "ANTIRAID_SECONDS": 10,
    "ANTI_NEW_ACCOUNT": False,
    "ANTI_NEW_ACCOUNT_DAYS": 7,
    "AUTOROLE_ID": None,
    "ANTI_MENTION_ROLES": [],
    "ANTILINK_TIMEOUT_MINUTES": 20,
    "ANTILINK_MODE": "timeout",
    "ANTISPAM": True,
    "ANTISPAM_MESSAGES": 6,
    "ANTISPAM_SECONDS": 5,
    "ANTISPAM_DUPLICATES": 3,
    "ANTISPAM_MENTIONS": 6,
    "ANTISPAM_TIMEOUT_MINUTES": 10,
    "ALLOWED_LINKS": [],
    "WELCOME_ENABLED": False,
    "WELCOME_CHANNEL_ID": None,
    "WELCOME_MESSAGE": "Bienvenue {mention} sur **{server}** !",
    "BOOST_CHANNEL_ID": None,
    "ANNOUNCE_CHANNEL_ID": None,
    "BOT_JOINED_AT": None,
    "GUILD_OWNERS": [],
    "STAFF_ROLE_ID": None,
    "AUTOMOD_CAPS": False,
    "AUTOMOD_INVITES": True,
    "AUTOMOD_MASSMENTION": True,
    "WELCOME_COLOR": "#57F287",
    "WELCOME_IMAGE": None,
    "ANTI_TIMEOUT": False,
    "ANTI_BOT": False,
    "ANTI_DM": False,
    "PRIVVC_HUB_ID": None,
    "PRIVVC_CATEGORY_ID": None,
    "RECRUIT_ENABLED": False,
    "RECRUIT_CHANNEL_ID": None,
    "RECRUIT_STAFF_CHANNEL_ID": None,
    "RECRUIT_MESSAGE": "**Recrutement ouvert !**\nClique sur le bouton pour postuler.",
    "BOOST_MESSAGE": "🚀 {mention} vient de **booster** **{server}** ! Merci 💜",
}

def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def persist_key(path: str) -> str:
    return os.path.basename(str(path))

def db_put(key: str, data: Any):
    try:
        conn = db()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS persist (key TEXT PRIMARY KEY, value TEXT)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO persist(key, value) VALUES(?, ?)",
            (key, json.dumps(data, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

def db_get(key: str, default: Any = None) -> Any:
    try:
        conn = db()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS persist (key TEXT PRIMARY KEY, value TEXT)"
        )
        row = conn.execute("SELECT value FROM persist WHERE key=?", (key,)).fetchone()
        conn.close()
        if row and row[0]:
            return json.loads(row[0])
    except Exception:
        pass
    return default

def load_json(path: str, default: Any = None) -> Any:
    ensure_data_dir()
    if default is None:
        default = {}
    key = persist_key(path)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            db_put(key, data)
            return data
        except Exception:
            cached = db_get(key, None)
            if cached is not None:
                return cached
            return default
    cached = db_get(key, None)
    if cached is not None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cached, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        return cached
    save_json(path, default)
    return default

def save_json(path: str, data: Any):
    ensure_data_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    db_put(persist_key(path), data)

def db():
    ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS guild_config (
        guild_id TEXT PRIMARY KEY,
        data TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS tickets (
        guild_id TEXT,
        user_id TEXT,
        data TEXT,
        PRIMARY KEY (guild_id, user_id)
    );
    CREATE TABLE IF NOT EXISTS xp (
        guild_id TEXT,
        user_id TEXT,
        xp INTEGER,
        level INTEGER,
        PRIMARY KEY (guild_id, user_id)
    );
    CREATE TABLE IF NOT EXISTS custom_commands (
        guild_id TEXT,
        name TEXT,
        response TEXT,
        enabled INTEGER DEFAULT 1,
        PRIMARY KEY (guild_id, name)
    );
    CREATE TABLE IF NOT EXISTS auto_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT,
        channel_id TEXT,
        content TEXT,
        interval_sec INTEGER,
        last_sent REAL DEFAULT 0,
        enabled INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS auto_reacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT,
        channel_id TEXT,
        emoji TEXT,
        enabled INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS moderation (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT,
        kind TEXT,
        payload TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS reaction_roles (
        guild_id TEXT,
        message_id TEXT,
        emoji TEXT,
        role_id TEXT,
        PRIMARY KEY (guild_id, message_id, emoji)
    );
    CREATE TABLE IF NOT EXISTS banned_words (word TEXT PRIMARY KEY, added_by TEXT, added_at TEXT);
    CREATE TABLE IF NOT EXISTS infractions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, raison TEXT, added_by TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, note TEXT, added_by TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS sanctions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, raison TEXT, added_by TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS temproles (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT, user_id TEXT, role_id TEXT, until REAL);
    CREATE TABLE IF NOT EXISTS backups (name TEXT PRIMARY KEY, guild_name TEXT, data TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS birthdays (user_id TEXT PRIMARY KEY, date TEXT);
    CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, reporter_id TEXT, target TEXT, raison TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS suggestions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, text TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS persist (key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS guilds (
        guild_id TEXT PRIMARY KEY,
        name TEXT,
        owner_id TEXT,
        member_count INTEGER,
        joined_at TEXT,
        icon TEXT
    );
    """)
    conn.commit()
    conn.close()

def db_custom_cmds(guild_id) -> list:
    conn = db()
    rows = conn.execute("SELECT name, response, enabled FROM custom_commands WHERE guild_id=?", (str(guild_id),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def db_set_custom(guild_id, name, response, enabled=1):
    conn = db()
    conn.execute(
        "INSERT OR REPLACE INTO custom_commands(guild_id,name,response,enabled) VALUES(?,?,?,?)",
        (str(guild_id), name.lower(), response, enabled)
    )
    conn.commit()
    conn.close()

def db_del_custom(guild_id, name):
    conn = db()
    conn.execute("DELETE FROM custom_commands WHERE guild_id=? AND name=?", (str(guild_id), name.lower()))
    conn.commit()
    conn.close()

def db_auto_msgs(guild_id=None):
    conn = db()
    if guild_id:
        rows = conn.execute("SELECT * FROM auto_messages WHERE guild_id=?", (str(guild_id),)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM auto_messages WHERE enabled=1").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def db_auto_reacts(guild_id, channel_id=None):
    conn = db()
    if channel_id:
        rows = conn.execute(
            "SELECT * FROM auto_reacts WHERE guild_id=? AND enabled=1 AND (channel_id=? OR channel_id='all')",
            (str(guild_id), str(channel_id))
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM auto_reacts WHERE guild_id=?", (str(guild_id),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def guild_file(filename: str, guild_id: Optional[int] = None) -> str:
    gid = guild_id or CURRENT_GUILD_ID.get()
    if gid:
        folder = os.path.join(DATA_DIR, "guilds", str(int(gid)))
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, filename)
    return os.path.join(DATA_DIR, filename)

def set_guild(guild_id: Optional[int]):
    if guild_id:
        CURRENT_GUILD_ID.set(int(guild_id))

def get_config(guild_id: Optional[int] = None) -> dict:
    data = load_json(guild_file("config.json", guild_id), DEFAULT_CONFIG.copy())
    if not isinstance(data, dict):
        data = DEFAULT_CONFIG.copy()
    for k, v in DEFAULT_CONFIG.items():
        data.setdefault(k, v)
    # Normalise les IDs numériques souvent stockés en str
    for key in (
        "TICKET_CATEGORY_ID", "LOG_CHANNEL_ID", "TICKET_LOG_CHANNEL_ID",
        "STAFF_ROLE_ID", "AUTOROLE_ID", "WELCOME_CHANNEL_ID", "BOOST_CHANNEL_ID",
    ):
        if data.get(key) not in (None, "", 0, "0"):
            try:
                data[key] = int(data[key])
            except Exception:
                pass
    return data

def save_config(data: dict, guild_id: Optional[int] = None):
    if not isinstance(data, dict):
        data = DEFAULT_CONFIG.copy()
    # Toujours écrire un int pour la catégorie tickets
    if data.get("TICKET_CATEGORY_ID") not in (None, "", 0, "0"):
        try:
            data["TICKET_CATEGORY_ID"] = int(data["TICKET_CATEGORY_ID"])
        except Exception:
            pass
    path = guild_file("config.json", guild_id)
    save_json(path, data)
    print(f"[CONFIG] save → {path} TICKET_CATEGORY_ID={data.get('TICKET_CATEGORY_ID')}")

def get_mod_memory(guild_id: Optional[int] = None) -> dict:
    return load_json(guild_file("moderation.json", guild_id), {"bans": [], "kicks": [], "mutes": [], "roles": []})

def save_mod_memory(data: dict, guild_id: Optional[int] = None):
    save_json(guild_file("moderation.json", guild_id), data)

def remember_mod(kind: str, payload: dict, guild_id: Optional[int] = None):
    mem = get_mod_memory(guild_id)
    mem.setdefault(kind, [])
    payload["at"] = discord.utils.utcnow().isoformat()
    mem[kind].append(payload)
    mem[kind] = mem[kind][-200:]
    save_mod_memory(mem, guild_id)

def get_owners() -> List[int]:
    owners = load_json(OWNERS_FILE, [])
    if BOT_OWNER_ID and BOT_OWNER_ID not in owners:
        owners.append(BOT_OWNER_ID)
        save_json(OWNERS_FILE, owners)
    return [int(x) for x in owners]

def get_guild_owners(guild_id: Optional[int] = None) -> List[int]:
    return [int(x) for x in (get_config(guild_id).get("GUILD_OWNERS") or [])]

def get_ownerplus() -> List[int]:
    return [int(x) for x in load_json(OWNERPLUS_FILE, [])]

def log_ownerplus(text: str):
    ensure_data_dir()
    os.makedirs(os.path.dirname(OWNERPLUS_LOG), exist_ok=True)
    with open(OWNERPLUS_LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} {text}\n")

def is_owner(user_id: int, guild_id: Optional[int] = None) -> bool:
    if user_id in get_owners() or user_id in get_ownerplus():
        return True
    gid = guild_id if guild_id is not None else CURRENT_GUILD_ID.get()
    if gid:
        return int(user_id) in get_guild_owners(gid)
    return False

def get_blacklist() -> List[int]:
    return [int(x) for x in load_json(BLACKLIST_FILE, [])]

def is_blacklisted(user_id: int) -> bool:
    return user_id in get_blacklist()

def get_tickets(guild_id: Optional[int] = None) -> dict:
    return load_json(guild_file("tickets.json", guild_id), {})

def save_tickets(data: dict, guild_id: Optional[int] = None):
    save_json(guild_file("tickets.json", guild_id), data)

DEFAULT_ANNOUNCE_MESSAGE = "✨ {mention} passe **niveau {level}** !"

def default_levels_config() -> dict:
    return {
        "enabled": True,
        "xp_min": 10,
        "xp_max": 20,
        "cooldown": 45,
        "announce": True,
        "announce_mode": "same_channel",  # same_channel | channel | dm
        "announce_channel_id": None,
        "announce_message": DEFAULT_ANNOUNCE_MESSAGE,
        "stack_roles": True,
        "ignored_channels": [],
        "ignored_roles": [],
        "card_font": "sans",
        "card_bar": "#5865F2",
        "card_overlay": 40,
        "card_bg": "#2B2D31",
        "levels": [
            {"level": 1, "xp": 0, "role_id": None},
            {"level": 2, "xp": 100, "role_id": None},
            {"level": 3, "xp": 250, "role_id": None},
            {"level": 5, "xp": 600, "role_id": None},
            {"level": 10, "xp": 1500, "role_id": None},
        ],
    }

def get_levels_cfg() -> dict:
    data = load_json(guild_file("levels.json"), default_levels_config())
    for k, v in default_levels_config().items():
        data.setdefault(k, v)
    data["levels"] = sorted(data.get("levels") or [], key=lambda x: int(x.get("xp", 0)))
    return data

def save_levels_cfg(data: dict):
    data["levels"] = sorted(data.get("levels") or [], key=lambda x: int(x.get("xp", 0)))
    save_json(guild_file("levels.json"), data)

def get_xp_data() -> dict:
    return load_json(XP_FILE, {})

def save_xp_data(data: dict):
    save_json(XP_FILE, data)

def level_for_xp(total_xp: int, cfg: dict) -> dict:
    current = {"level": 1, "xp": 0, "role_id": None}
    for row in cfg.get("levels") or []:
        if total_xp >= int(row.get("xp", 0)):
            current = row
        else:
            break
    return current

def next_level(total_xp: int, cfg: dict):
    for row in cfg.get("levels") or []:
        if total_xp < int(row.get("xp", 0)):
            return row
    return None




async def send_log(embed: discord.Embed):
    if not embed.footer or not embed.footer.text:
        embed.set_footer(text=datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    config = get_config()
    ch_id = config.get("LOG_CHANNEL_ID")
    if not ch_id:
        return
    channel = bot.get_channel(int(ch_id))
    if channel is None:
        try:
            channel = await bot.fetch_channel(int(ch_id))
        except Exception:
            return
    try:
        await channel.send(embed=embed)
    except Exception:
        pass

def find_ticket_by_channel(channel_id: int):
    tickets = get_tickets()
    for tid, data in tickets.items():
        if data.get("channel_id") == channel_id:
            return tid, data
    return None, None


def can_manage_ticket(user_id: int, data: dict) -> bool:
    """Owners peuvent toujours gérer. Sinon claimer / staff ajouté."""
    if is_owner(user_id):
        return True
    claimed_by = data.get("claimed_by")
    staff_list = [int(x) for x in (data.get("staff") or [])]
    if not claimed_by:
        return True
    try:
        claimed_by = int(claimed_by)
    except Exception:
        pass
    return user_id == claimed_by or user_id in staff_list

def gen_ticket_id(tickets: dict = None) -> str:
    existing = set()
    if tickets:
        for d in tickets.values():
            if isinstance(d, dict) and d.get("ticket_id"):
                existing.add(str(d["ticket_id"]).upper())
    for _ in range(30):
        tid = "T-" + secrets.token_hex(2).upper()
        if tid not in existing:
            return tid
    return "T-" + secrets.token_hex(3).upper()

def find_ticket_entry(query: str, guild_id: Optional[int] = None) -> tuple:
    """Retourne (user_key, data, guild_id) ou (None, None, None)."""
    q = (query or "").strip()
    if not q:
        return None, None, None
    guilds = [guild_id] if guild_id else [g.id for g in bot.guilds]
    for gid in guilds:
        tickets = get_tickets(gid)
        # par ID ticket
        for ukey, data in tickets.items():
            if not isinstance(data, dict):
                continue
            if str(data.get("ticket_id", "")).upper() == q.upper():
                return ukey, data, gid
            if ukey == q or str(data.get("user_id")) == q:
                return ukey, data, gid
            if str(data.get("channel_id")) == q:
                return ukey, data, gid
    return None, None, None


async def send_transcript(user: discord.User, closer_name: str, messages_list: list):
    transcript = (
        f"**Transcription du ticket**\n"
        f"Fermé par : **{closer_name}**\n"
        f"Date : {discord.utils.utcnow().strftime('%d/%m/%Y %H:%M')}\n"
        + "─" * 30 + "\n\n"
    )
    if messages_list:
        for msg in messages_list:
            transcript += f"{msg.get('content', '')}\n"
    else:
        transcript += "*Aucun message enregistré*\n"
    transcript += "\n" + "─" * 30 + "\nMerci d'avoir contacté le support."
    try:
        if len(transcript) > 1900:
            for i in range(0, len(transcript), 1900):
                await user.send(transcript[i:i + 1900])
        else:
            await user.send(transcript)
    except Exception:
        pass


async def close_ticket(user_id: str, closer, channel=None, guild_id: Optional[int] = None):
    gid = guild_id
    if channel is not None and getattr(channel, "guild", None):
        gid = channel.guild.id
        set_guild(gid)
    if gid:
        set_guild(gid)
    tickets = get_tickets(gid)
    if user_id not in tickets:
        # fallback : chercher partout
        ukey, data, found_gid = find_ticket_entry(str(user_id), None)
        if not ukey:
            return False
        user_id, gid = ukey, found_gid
        tickets = get_tickets(gid)
    data = tickets[user_id]
    tid = data.get("ticket_id") or user_id
    tickets[user_id]["closed"] = True
    tickets[user_id]["closed_at"] = discord.utils.utcnow().isoformat()
    tickets[user_id]["closed_by"] = getattr(closer, "id", None)
    # garde l'historique pour +reopen
    save_tickets(tickets, gid)
    try:
        user = await bot.fetch_user(int(data.get("user_id") or user_id))
        await user.send(
            f"Votre ticket **`{tid}`** a été fermé. "
            "Si vous pensez que cela est une erreur, veuillez envoyer à nouveau un message au support."
        )
        try:
            view = discord.ui.View(timeout=180)

            async def yes_cb(interaction: discord.Interaction):
                await send_transcript(interaction.user, closer.display_name, data.get("messages", []))
                await interaction.response.edit_message(content="Transcription envoyée.", view=None)

            async def no_cb(interaction: discord.Interaction):
                await interaction.response.edit_message(content="Pas de transcription.", view=None)

            b1 = discord.ui.Button(label="Oui, transcription", style=discord.ButtonStyle.success)
            b2 = discord.ui.Button(label="Non", style=discord.ButtonStyle.secondary)
            b1.callback = yes_cb
            b2.callback = no_cb
            view.add_item(b1)
            view.add_item(b2)
            await user.send("Voulez-vous une transcription du ticket ?", view=view)
        except Exception:
            pass
    except Exception:
        pass
    target = channel
    if target is None and data.get("channel_id"):
        target = bot.get_channel(int(data["channel_id"]))
        if target is None:
            try:
                target = await bot.fetch_channel(int(data["channel_id"]))
            except Exception:
                target = None
    if target:
        try:
            await target.send(f"Ticket `{tid}` fermé par {closer.mention}. Suppression du salon…")
        except Exception:
            pass
        try:
            await target.delete(reason=f"Ticket {tid} fermé par {closer}")
        except Exception:
            pass
    return True


def parse_duration(s: str) -> Optional[int]:
    s = s.lower().strip()
    match = re.match(r"^(\d+)([smhd])?$", s)
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2) or "m"
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return value * multipliers.get(unit, 60)


def extract_id(text: str) -> Optional[int]:
    if not text:
        return None
    match = re.search(r"(\d{17,20})", text)
    return int(match.group(1)) if match else None


async def resolve_user(ctx: commands.Context, raw: str = None) -> Optional[discord.User]:
    if ctx.message.mentions:
        return ctx.message.mentions[0]
    uid = extract_id(raw or ctx.message.content)
    if not uid:
        return None
    member = ctx.guild.get_member(uid) if ctx.guild else None
    if member:
        return member
    try:
        return await bot.fetch_user(uid)
    except Exception:
        return None


async def fetch_json(url: str) -> Optional[dict]:
    headers = {"User-Agent": "Mozilla/5.0 DiscordBot/1.5"}
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception:
        return None
    return None


FALLBACK_GIFS = {
    "kiss": [
        "https://media.tenor.com/p7mwjRYdQa4AAAAC/anime-kiss.gif",
        "https://media.tenor.com/jnndDmOm5wMAAAAC/kiss.gif",
    ],
    "hug": [
        "https://media.tenor.com/kCZjTqCKsOwAAAAC/hug.gif",
        "https://media.tenor.com/rQ2QQQ9XkXMAAAAC/anime-hug.gif",
    ],
    "slap": [
        "https://media.tenor.com/1iNIu-SZf54AAAAC/anime-slap.gif",
        "https://media.tenor.com/CsP2c3qjCQIAAAAC/anime-angry.gif",
    ],
}


async def get_reaction_gif_url(kind: str) -> Optional[str]:
    mapping = {
        "kiss": ["kiss", "kiss"],
        "hug": ["hug", "hug"],
        "slap": ["slap", "punch"],
    }
    names = mapping.get(kind, [kind, kind])
    waifu, neko = names[0], names[0]

    data = await fetch_json(f"https://api.waifu.pics/sfw/{waifu}")
    if data and data.get("url"):
        return data["url"]

    data = await fetch_json(f"https://nekos.best/api/v2/{neko}")
    if data and data.get("results"):
        return data["results"][0].get("url")

    data = await fetch_json(f"https://api.otakugifs.xyz/gif?reaction={neko}")
    if data and data.get("url"):
        return data["url"]

    pool = FALLBACK_GIFS.get(kind) or FALLBACK_GIFS["hug"]
    return random.choice(pool)


async def send_reaction_gif(ctx: commands.Context, kind: str, title: str, target=None):
    url = await get_reaction_gif_url(kind)
    if not url:
        await ctx.send("❌ Impossible de récupérer le gif.")
        return
    desc = f"{ctx.author.mention} → {target.mention}" if target else ctx.author.mention
    embed = discord.Embed(title=title, description=desc, color=0xEB459E)
    embed.set_image(url=url)
    await ctx.send(embed=embed)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.moderation = True

bot = commands.Bot(
    command_prefix="+",
    intents=intents,
    help_command=None,
    case_insensitive=True,
)

CMD_COOLDOWN: Dict[int, float] = {}

async def owner_check(ctx: commands.Context) -> bool:
    if ctx.author.bot:
        return False
    if is_blacklisted(ctx.author.id):
        try:
            await ctx.send("❌ Tu es blacklisté.", delete_after=5)
        except Exception:
            pass
        return False
    if not is_owner(ctx.author.id, ctx.guild.id if ctx.guild else None):
        try:
            await ctx.send("❌ Seuls les **propriétaires** peuvent utiliser cette commande.", delete_after=8)
        except Exception:
            pass
        return False
    # anti-spam commandes owners (évite double déclenchement abusif)
    key = ctx.author.id
    now = time.time()
    if now - CMD_COOLDOWN.get(key, 0) < 0.35:
        return False
    CMD_COOLDOWN[key] = now
    return True

def format_announce_message(cfg: dict, member: discord.Member, user_data: dict, nxt: Optional[dict]) -> str:
    template = cfg.get("announce_message") or DEFAULT_ANNOUNCE_MESSAGE
    try:
        return template.format(
            mention=member.mention,
            user=str(member),
            level=user_data.get("level"),
            xp=user_data.get("xp"),
            next_level=nxt["level"] if nxt else "max",
            next_xp=nxt["xp"] if nxt else "-",
        )
    except Exception:
        return DEFAULT_ANNOUNCE_MESSAGE.format(mention=member.mention, level=user_data.get("level"))

async def grant_xp(message: discord.Message):
    if not message.guild or message.author.bot or not message.content:
        return
    cfg = get_levels_cfg()
    if not cfg.get("enabled"):
        return

    ignored_channels = {int(x) for x in (cfg.get("ignored_channels") or [])}
    if message.channel.id in ignored_channels or getattr(message.channel, "category_id", None) in ignored_channels:
        return
    ignored_roles = {int(x) for x in (cfg.get("ignored_roles") or [])}
    if isinstance(message.author, discord.Member) and any(r.id in ignored_roles for r in message.author.roles):
        return

    key = f"{message.guild.id}:{message.author.id}"
    now = time.time()
    if now - XP_COOLDOWN.get(key, 0) < int(cfg.get("cooldown") or 45):
        return
    XP_COOLDOWN[key] = now

    gained = random.randint(int(cfg.get("xp_min") or 10), int(cfg.get("xp_max") or 20))
    all_xp = get_xp_data()
    gid, uid = str(message.guild.id), str(message.author.id)
    all_xp.setdefault(gid, {})
    user = all_xp[gid].setdefault(uid, {"xp": 0, "level": 1})
    old_level = int(user.get("level") or 1)
    user["xp"] = int(user.get("xp") or 0) + gained
    reached = level_for_xp(user["xp"], cfg)
    user["level"] = int(reached.get("level") or 1)
    save_xp_data(all_xp)

    if user["level"] > old_level:
        try:
            if cfg.get("stack_roles", True):
                for row in cfg.get("levels") or []:
                    if old_level < int(row.get("level")) <= user["level"] and row.get("role_id"):
                        role = message.guild.get_role(int(row["role_id"]))
                        if role:
                            await message.author.add_roles(role, reason=f"Niveau {row['level']}")
            else:
                all_role_ids = {int(r["role_id"]) for r in (cfg.get("levels") or []) if r.get("role_id")}
                new_role_id = int(reached["role_id"]) if reached.get("role_id") else None
                to_remove = [message.guild.get_role(rid) for rid in all_role_ids if rid != new_role_id]
                to_remove = [r for r in to_remove if r and r in message.author.roles]
                if to_remove:
                    await message.author.remove_roles(*to_remove, reason="Changement de niveau")
                if new_role_id:
                    role = message.guild.get_role(new_role_id)
                    if role:
                        await message.author.add_roles(role, reason=f"Niveau {user['level']}")
        except Exception:
            pass

        if cfg.get("announce"):
            nxt = next_level(user["xp"], cfg)
            text = format_announce_message(cfg, message.author, user, nxt)
            mode = cfg.get("announce_mode", "same_channel")
            try:
                if mode == "dm":
                    await message.author.send(text)
                elif mode == "channel" and cfg.get("announce_channel_id"):
                    channel = message.guild.get_channel(int(cfg["announce_channel_id"]))
                    if channel:
                        await channel.send(text)
                    else:
                        await message.channel.send(text, delete_after=20)
                else:
                    await message.channel.send(text, delete_after=20)
            except Exception:
                pass

def setup_embed(guild_id: Optional[int] = None) -> discord.Embed:
    if guild_id:
        set_guild(guild_id)
    c = get_config(guild_id)
    on = lambda v: "🟢 Activé" if v else "🔴 Désactivé"
    log_ch = f"<#{c['LOG_CHANNEL_ID']}>" if c.get("LOG_CHANNEL_ID") else "*non défini*"
    cat = f"`{c['TICKET_CATEGORY_ID']}`" if c.get("TICKET_CATEGORY_ID") else "*non défini*"
    role = f"<@&{c['AUTOROLE_ID']}>" if c.get("AUTOROLE_ID") else "*non défini*"
    roles = c.get("ANTI_MENTION_ROLES") or []
    allowed = c.get("ALLOWED_LINKS") or []
    embed = discord.Embed(
        title="Configuration du serveur",
        description="Utilise les sélecteurs et boutons ci-dessous.\nLes réglages sont **sauvegardés automatiquement**.",
        color=0x2B2D31
    )
    staff = f"<@&{c['STAFF_ROLE_ID']}>" if c.get("STAFF_ROLE_ID") else "*non défini*"
    embed.add_field(
        name="Salons & rôles",
        value=f"Logs : {log_ch}\nCatégorie tickets : {cat}\nAutorole : {role}\nRôle staff tickets : {staff}",
        inline=False
    )
    embed.add_field(
        name="Contenu du salon logs",
        value="Bienvenue / départs · messages supprimés / modifiés · rôles ajoutés / retirés · bans / kicks / mutes · boosts · anti-lien / anti-raid / anti-spam",
        inline=False
    )
    embed.add_field(
        name="Protections",
        value=(
            f"Anti-lien : {on(c.get('ANTILINK'))} · timeout `{c.get('ANTILINK_TIMEOUT_MINUTES', 20)} min`\n"
            f"Anti-raid : {on(c.get('ANTIRAID'))} · `{c.get('ANTIRAID_JOINS')}` joins / `{c.get('ANTIRAID_SECONDS')}s`\n"
            f"Anti nouveau compte : {on(c.get('ANTI_NEW_ACCOUNT'))} · `{c.get('ANTI_NEW_ACCOUNT_DAYS')} jours`\n"
            f"Anti-timeout : {on(c.get('ANTI_TIMEOUT'))} · Anti-bot : {on(c.get('ANTI_BOT'))} · Anti-DM : {on(c.get('ANTI_DM'))}"
        ),
        inline=False
    )
    embed.add_field(
        name="Anti-mention",
        value=" ".join(f"<@&{x}>" for x in roles) or "*aucun rôle protégé*",
        inline=False
    )
    embed.add_field(
        name="Liens",
        value="Aucun lien accepté — suppression + brouillage + timeout 20 min",
        inline=False
    )
    welcome_ch = f"<#{c['WELCOME_CHANNEL_ID']}>" if c.get("WELCOME_CHANNEL_ID") else "*non défini*"
    embed.add_field(
        name="Bienvenue",
        value=f"{'ON' if c.get('WELCOME_ENABLED') else 'OFF'} · salon {welcome_ch}\n`+welcome` pour le message / salon / image",
        inline=False
    )
    embed.add_field(
        name="Rôles & embeds",
        value="`+perms` `+createrole` `+delrole` `+giverole` · `+embed`",
        inline=False
    )
    embed.set_footer(text=f"Config du serveur {guild_id or CURRENT_GUILD_ID.get() or ''} — data/guilds/<id>/config.json")
    return embed

LEVELS_PAGES = [
    ("overview", "🏠 Vue d'ensemble"),
    ("xp", "✨ XP & Cooldown"),
    ("levels", "🏆 Paliers de niveaux"),
    ("announce", "📢 Annonces"),
    ("ignored", "🚫 Salons / rôles ignorés"),
]
ANNOUNCE_MODES = [
    ("same_channel", "💬 Salon où le message a été envoyé"),
    ("channel", "📌 Salon dédié"),
    ("dm", "✉️ Message privé"),
]


def levels_embed(page: str = "overview", selected_level: Optional[int] = None) -> discord.Embed:
    cfg = get_levels_cfg()
    embed = discord.Embed(title="⚙️ Système de niveaux", color=0x6C8CFF, timestamp=discord.utils.utcnow())
    embed.add_field(name="État", value="🟢 Activé" if cfg.get("enabled") else "🔴 Désactivé", inline=True)

    if page == "overview":
        embed.description = "Vue d'ensemble. Utilise le menu ci-dessous pour naviguer entre les sections — tout est **100% configurable** et sauvegardé automatiquement."
        embed.add_field(name="XP par message", value=f"{cfg.get('xp_min')} – {cfg.get('xp_max')}", inline=True)
        embed.add_field(name="Cooldown", value=f"{cfg.get('cooldown')}s", inline=True)
        embed.add_field(name="Paliers configurés", value=str(len(cfg.get("levels") or [])), inline=True)
        embed.add_field(name="Annonces", value="🟢 Activées" if cfg.get("announce") else "🔴 Désactivées", inline=True)
        embed.add_field(name="Salons ignorés", value=str(len(cfg.get("ignored_channels") or [])), inline=True)
        embed.add_field(name="Rôles ignorés", value=str(len(cfg.get("ignored_roles") or [])), inline=True)

    elif page == "xp":
        embed.description = "Règle le gain d'XP par message et le cooldown anti-spam."
        embed.add_field(name="XP minimum", value=str(cfg.get("xp_min")), inline=True)
        embed.add_field(name="XP maximum", value=str(cfg.get("xp_max")), inline=True)
        embed.add_field(name="Cooldown", value=f"{cfg.get('cooldown')}s", inline=True)

    elif page == "levels":
        embed.description = "Choisis un palier dans le menu pour le modifier (rôle) ou le supprimer, ou crée-en un nouveau."
        lines = []
        for row in cfg.get("levels") or []:
            role = f"<@&{row['role_id']}>" if row.get("role_id") else "*aucun rôle*"
            marker = "➡️ " if selected_level is not None and int(row.get("level")) == selected_level else ""
            lines.append(f"{marker}Niv. **{row['level']}** — `{row['xp']}` XP — {role}")
        embed.add_field(name=f"Paliers ({len(cfg.get('levels') or [])})", value="\n".join(lines) or "*aucun*", inline=False)
        embed.add_field(
            name="Cumul des rôles",
            value="🟢 Garde les rôles des anciens niveaux" if cfg.get("stack_roles", True) else "🔴 Retire les rôles des niveaux précédents",
            inline=False
        )

    elif page == "announce":
        embed.description = "Configure les annonces de passage de niveau."
        mode = cfg.get("announce_mode", "same_channel")
        mode_label = dict(ANNOUNCE_MODES).get(mode, mode)
        embed.add_field(name="Annonces", value="🟢 Activées" if cfg.get("announce") else "🔴 Désactivées", inline=True)
        embed.add_field(name="Mode", value=mode_label, inline=True)
        if mode == "channel":
            chan = f"<#{cfg['announce_channel_id']}>" if cfg.get("announce_channel_id") else "*non défini*"
            embed.add_field(name="Salon d'annonce", value=chan, inline=True)
        embed.add_field(name="Message personnalisé", value=f"```{cfg.get('announce_message')}```", inline=False)
        embed.add_field(name="Variables disponibles", value="`{mention}` `{user}` `{level}` `{xp}` `{next_level}` `{next_xp}`", inline=False)

    elif page == "ignored":
        embed.description = "Les messages envoyés dans ces salons, ou par ces rôles, ne donnent pas d'XP."
        chans = cfg.get("ignored_channels") or []
        roles = cfg.get("ignored_roles") or []
        embed.add_field(name=f"Salons ignorés ({len(chans)})", value=" ".join(f"<#{c}>" for c in chans) or "*aucun*", inline=False)
        embed.add_field(name=f"Rôles ignorés ({len(roles)})", value=" ".join(f"<@&{r}>" for r in roles) or "*aucun*", inline=False)

    embed.set_footer(text="Système de niveaux • Enregistré automatiquement dans data/levels.json")
    return embed


class XpCooldownModal(discord.ui.Modal, title="XP gagnée par message"):
    def __init__(self, cfg: dict):
        super().__init__()
        self.xp_min = discord.ui.TextInput(label="XP minimum", default=str(cfg.get("xp_min", 10)), required=True, max_length=4)
        self.xp_max = discord.ui.TextInput(label="XP maximum", default=str(cfg.get("xp_max", 20)), required=True, max_length=4)
        self.cooldown = discord.ui.TextInput(label="Cooldown (secondes)", default=str(cfg.get("cooldown", 45)), required=True, max_length=5)
        self.add_item(self.xp_min)
        self.add_item(self.xp_max)
        self.add_item(self.cooldown)

    async def on_submit(self, interaction: discord.Interaction):
        if not (self.xp_min.value.isdigit() and self.xp_max.value.isdigit() and self.cooldown.value.isdigit()):
            await interaction.response.send_message("❌ Nombres uniquement.", ephemeral=True)
            return
        mn, mx, cd = int(self.xp_min.value), int(self.xp_max.value), int(self.cooldown.value)
        if mn < 1 or mx < mn:
            await interaction.response.send_message("❌ XP min ≥ 1 et ≤ XP max.", ephemeral=True)
            return
        cfg = get_levels_cfg()
        cfg["xp_min"], cfg["xp_max"], cfg["cooldown"] = mn, mx, max(0, cd)
        save_levels_cfg(cfg)
        await interaction.response.edit_message(embed=levels_embed("xp"), view=LevelsView(interaction.user.id, "xp"))


class AddLevelModal(discord.ui.Modal, title="Créer / modifier un palier"):
    def __init__(self, prefill_level: Optional[int] = None, prefill_xp: Optional[int] = None):
        super().__init__()
        self.level = discord.ui.TextInput(label="Numéro du niveau", placeholder="5", default=str(prefill_level) if prefill_level else None, required=True, max_length=4)
        self.xp = discord.ui.TextInput(label="XP requise", placeholder="600", default=str(prefill_xp) if prefill_xp else None, required=True, max_length=8)
        self.add_item(self.level)
        self.add_item(self.xp)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.level.value.isdigit() or not self.xp.value.isdigit():
            await interaction.response.send_message("❌ Niveau et XP = nombres.", ephemeral=True)
            return
        cfg = get_levels_cfg()
        lvl, need = int(self.level.value), int(self.xp.value)
        existing = next((r for r in cfg.get("levels") or [] if int(r.get("level")) == lvl), None)
        rid = existing.get("role_id") if existing else None
        levels = [r for r in cfg.get("levels") or [] if int(r.get("level")) != lvl]
        levels.append({"level": lvl, "xp": need, "role_id": rid})
        cfg["levels"] = levels
        save_levels_cfg(cfg)
        await interaction.response.edit_message(embed=levels_embed("levels", lvl), view=LevelsView(interaction.user.id, "levels", lvl))


class AnnounceMessageModal(discord.ui.Modal, title="Message d'annonce personnalisé"):
    def __init__(self, cfg: dict):
        super().__init__()
        self.message = discord.ui.TextInput(
            label="Message (variables : {mention} {level} ...)",
            style=discord.TextStyle.paragraph,
            default=cfg.get("announce_message", DEFAULT_ANNOUNCE_MESSAGE),
            required=True,
            max_length=300,
        )
        self.add_item(self.message)

    async def on_submit(self, interaction: discord.Interaction):
        cfg = get_levels_cfg()
        cfg["announce_message"] = self.message.value
        save_levels_cfg(cfg)
        await interaction.response.edit_message(embed=levels_embed("announce"), view=LevelsView(interaction.user.id, "announce"))


class ConfirmResetXPView(discord.ui.View):
    def __init__(self, guild_id: int, author_id: int):
        super().__init__(timeout=30)
        self.guild_id = guild_id
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id

    @discord.ui.button(label="Oui, réinitialiser", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        all_xp = get_xp_data()
        all_xp[str(self.guild_id)] = {}
        save_xp_data(all_xp)
        await interaction.response.edit_message(content="✅ XP de tous les membres réinitialisée pour ce serveur.", view=None)

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ Réinitialisation annulée.", view=None)


class LevelsNavSelect(discord.ui.Select):
    def __init__(self, current_page: str):
        options = [
            discord.SelectOption(label=label, value=key, default=(key == current_page))
            for key, label in LEVELS_PAGES
        ]
        super().__init__(placeholder="📋 Choisir une section à configurer", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        page = self.values[0]
        await interaction.response.edit_message(embed=levels_embed(page), view=LevelsView(self.view.author_id, page))


class ToggleEnabledButton(discord.ui.Button):
    def __init__(self, cfg: dict):
        enabled = cfg.get("enabled")
        super().__init__(
            label="Désactiver le système" if enabled else "Activer le système",
            style=discord.ButtonStyle.danger if enabled else discord.ButtonStyle.success,
            emoji="🔴" if enabled else "🟢",
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        cfg = get_levels_cfg()
        cfg["enabled"] = not cfg.get("enabled")
        save_levels_cfg(cfg)
        await interaction.response.edit_message(embed=levels_embed("overview"), view=LevelsView(self.view.author_id, "overview"))


class ResetXPButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Réinitialiser l'XP du serveur", style=discord.ButtonStyle.secondary, emoji="🗑️", row=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "⚠️ Es-tu sûr de vouloir **réinitialiser l'XP de tous les membres** de ce serveur ? Action irréversible.",
            view=ConfirmResetXPView(interaction.guild.id, interaction.user.id),
            ephemeral=True,
        )


class EditXPButton(discord.ui.Button):
    def __init__(self, cfg: dict):
        self.cfg = cfg
        super().__init__(label="Modifier XP / Cooldown", style=discord.ButtonStyle.primary, emoji="✏️", row=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(XpCooldownModal(self.cfg))


class LevelPickSelect(discord.ui.Select):
    def __init__(self, cfg: dict, selected_level: Optional[int]):
        levels = cfg.get("levels") or []
        if levels:
            options = [
                discord.SelectOption(
                    label=f"Niveau {row['level']} — {row['xp']} XP",
                    value=str(row["level"]),
                    default=(selected_level is not None and int(row["level"]) == selected_level),
                )
                for row in levels[:25]
            ]
        else:
            options = [discord.SelectOption(label="Aucun palier créé", value="none")]
        super().__init__(placeholder="🏆 Choisir un palier à modifier / supprimer", options=options, row=1, disabled=not levels)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.defer()
            return
        lvl = int(self.values[0])
        await interaction.response.edit_message(embed=levels_embed("levels", lvl), view=LevelsView(self.view.author_id, "levels", lvl))


class AddLevelButton(discord.ui.Button):
    def __init__(self, selected_level: Optional[int]):
        self.selected_level = selected_level
        super().__init__(
            label="Modifier ce palier" if selected_level else "Créer un palier",
            style=discord.ButtonStyle.primary if selected_level else discord.ButtonStyle.success,
            emoji="✏️" if selected_level else "➕",
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        prefill_xp = None
        if self.selected_level:
            cfg = get_levels_cfg()
            row = next((r for r in cfg.get("levels") or [] if int(r.get("level")) == self.selected_level), None)
            prefill_xp = row.get("xp") if row else None
        await interaction.response.send_modal(AddLevelModal(self.selected_level, prefill_xp))


class DeleteLevelButton(discord.ui.Button):
    def __init__(self, selected_level: int):
        self.selected_level = selected_level
        super().__init__(label=f"Supprimer le niveau {selected_level}", style=discord.ButtonStyle.danger, emoji="🗑️", row=2)

    async def callback(self, interaction: discord.Interaction):
        cfg = get_levels_cfg()
        cfg["levels"] = [r for r in cfg.get("levels") or [] if int(r.get("level")) != self.selected_level]
        save_levels_cfg(cfg)
        await interaction.response.edit_message(embed=levels_embed("levels"), view=LevelsView(interaction.user.id, "levels"))


class LevelRoleSelect(discord.ui.RoleSelect):
    def __init__(self, selected_level: int):
        self.selected_level = selected_level
        super().__init__(placeholder=f"🎭 Rôle attribué au niveau {selected_level}", min_values=1, max_values=1, row=3)

    async def callback(self, interaction: discord.Interaction):
        role = self.values[0]
        cfg = get_levels_cfg()
        for r in cfg.get("levels") or []:
            if int(r.get("level")) == self.selected_level:
                r["role_id"] = role.id
        save_levels_cfg(cfg)
        await interaction.response.edit_message(embed=levels_embed("levels", self.selected_level), view=LevelsView(self.view.author_id, "levels", self.selected_level))


class StackRolesToggleButton(discord.ui.Button):
    def __init__(self, cfg: dict):
        stack = cfg.get("stack_roles", True)
        super().__init__(
            label="Ne garder que le dernier rôle" if stack else "Cumuler les rôles",
            style=discord.ButtonStyle.secondary,
            emoji="🔁",
            row=4,
        )

    async def callback(self, interaction: discord.Interaction):
        cfg = get_levels_cfg()
        cfg["stack_roles"] = not cfg.get("stack_roles", True)
        save_levels_cfg(cfg)
        await interaction.response.edit_message(embed=levels_embed("levels"), view=LevelsView(self.view.author_id, "levels"))


class AnnounceModeSelect(discord.ui.Select):
    def __init__(self, cfg: dict):
        options = [
            discord.SelectOption(label=label, value=key, default=(cfg.get("announce_mode", "same_channel") == key))
            for key, label in ANNOUNCE_MODES
        ]
        super().__init__(placeholder="📍 Mode d'annonce", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        cfg = get_levels_cfg()
        cfg["announce_mode"] = self.values[0]
        save_levels_cfg(cfg)
        await interaction.response.edit_message(embed=levels_embed("announce"), view=LevelsView(self.view.author_id, "announce"))


class AnnounceChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="📌 Choisir le salon d'annonce", channel_types=[discord.ChannelType.text], min_values=1, max_values=1, row=2)

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        cfg = get_levels_cfg()
        cfg["announce_channel_id"] = channel.id
        save_levels_cfg(cfg)
        await interaction.response.edit_message(embed=levels_embed("announce"), view=LevelsView(self.view.author_id, "announce"))


class ToggleAnnounceButton(discord.ui.Button):
    def __init__(self, cfg: dict):
        announce = cfg.get("announce")
        super().__init__(
            label="Désactiver les annonces" if announce else "Activer les annonces",
            style=discord.ButtonStyle.danger if announce else discord.ButtonStyle.success,
            row=3,
        )

    async def callback(self, interaction: discord.Interaction):
        cfg = get_levels_cfg()
        cfg["announce"] = not cfg.get("announce")
        save_levels_cfg(cfg)
        await interaction.response.edit_message(embed=levels_embed("announce"), view=LevelsView(self.view.author_id, "announce"))


class EditAnnounceMessageButton(discord.ui.Button):
    def __init__(self, cfg: dict):
        self.cfg = cfg
        super().__init__(label="Modifier le message", style=discord.ButtonStyle.primary, emoji="✏️", row=3)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AnnounceMessageModal(self.cfg))


class IgnoredChannelsSelect(discord.ui.ChannelSelect):
    def __init__(self, cfg: dict):
        super().__init__(
            placeholder="🚫 Salons ignorés (ré-sélectionner = mise à jour)",
            channel_types=[discord.ChannelType.text],
            min_values=0,
            max_values=25,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        cfg = get_levels_cfg()
        cfg["ignored_channels"] = [c.id for c in self.values]
        save_levels_cfg(cfg)
        await interaction.response.edit_message(embed=levels_embed("ignored"), view=LevelsView(self.view.author_id, "ignored"))


class IgnoredRolesSelect(discord.ui.RoleSelect):
    def __init__(self, cfg: dict):
        super().__init__(
            placeholder="🚫 Rôles ignorés (ré-sélectionner = mise à jour)",
            min_values=0,
            max_values=25,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        cfg = get_levels_cfg()
        cfg["ignored_roles"] = [r.id for r in self.values]
        save_levels_cfg(cfg)
        await interaction.response.edit_message(embed=levels_embed("ignored"), view=LevelsView(self.view.author_id, "ignored"))


class LevelsView(discord.ui.View):
    """Menu interactif multi-pages, 100% configurable, pour le système de niveaux."""

    def __init__(self, author_id: int, page: str = "overview", selected_level: Optional[int] = None):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.page = page
        self.selected_level = selected_level
        self._build()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if is_blacklisted(interaction.user.id):
            return False
        if not is_owner(interaction.user.id):
            await interaction.response.send_message("❌ Seuls les **owners** peuvent configurer ce menu.", ephemeral=True)
            return False
        return True

    def _build(self):
        cfg = get_levels_cfg()
        self.add_item(LevelsNavSelect(self.page))

        if self.page == "overview":
            self.add_item(ToggleEnabledButton(cfg))
            self.add_item(ResetXPButton())

        elif self.page == "xp":
            self.add_item(EditXPButton(cfg))

        elif self.page == "levels":
            self.add_item(LevelPickSelect(cfg, self.selected_level))
            self.add_item(AddLevelButton(self.selected_level))
            if self.selected_level is not None and any(int(r.get("level")) == self.selected_level for r in cfg.get("levels") or []):
                self.add_item(DeleteLevelButton(self.selected_level))
                self.add_item(LevelRoleSelect(self.selected_level))
            self.add_item(StackRolesToggleButton(cfg))

        elif self.page == "announce":
            self.add_item(AnnounceModeSelect(cfg))
            if cfg.get("announce_mode") == "channel":
                self.add_item(AnnounceChannelSelect())
            self.add_item(ToggleAnnounceButton(cfg))
            self.add_item(EditAnnounceMessageButton(cfg))

        elif self.page == "ignored":
            self.add_item(IgnoredChannelsSelect(cfg))
            self.add_item(IgnoredRolesSelect(cfg))


@bot.command(name="levels", aliases=["niveaux", "levelsetup"])
async def levels_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    await ctx.send(embed=levels_embed(), view=LevelsView(ctx.author.id))


@bot.command(name="top", aliases=["leaderboard", "classement"])
async def top_cmd(ctx: commands.Context):
    cfg = get_levels_cfg()
    data = get_xp_data().get(str(ctx.guild.id), {})
    if not data:
        await ctx.send("❌ Personne n'a encore d'XP sur ce serveur.")
        return
    ranked = sorted(data.items(), key=lambda kv: int(kv[1].get("xp") or 0), reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (uid, udata) in enumerate(ranked):
        prefix = medals[i] if i < 3 else f"`#{i + 1}`"
        member = ctx.guild.get_member(int(uid))
        name = member.display_name if member else f"`{uid}`"
        lines.append(f"{prefix} **{name}** — niveau {udata.get('level', 1)} ({udata.get('xp', 0)} XP)")
    embed = discord.Embed(title=f"🏆 Classement — {ctx.guild.name}", description="\n".join(lines), color=0x6C8CFF)
    await ctx.send(embed=embed)

@bot.command(name="rank", aliases=["level", "xp"])
async def rank_cmd(ctx: commands.Context, raw: str = None):
    target = await resolve_user(ctx, raw) if (raw or ctx.message.mentions) else ctx.author
    if target is None:
        target = ctx.author
    cfg = get_levels_cfg()
    data = get_xp_data().get(str(ctx.guild.id), {}).get(str(target.id), {"xp": 0, "level": 1})
    total = int(data.get("xp") or 0)
    current = level_for_xp(total, cfg)
    nxt = next_level(total, cfg)
    need = f"{nxt['xp'] - total} XP pour le niveau {nxt['level']}" if nxt else "Niveau max"
    cur_xp = int(current.get("xp") or 0)
    nxt_xp = int(nxt["xp"]) if nxt else max(total, 1)
    pct = 0 if nxt_xp == cur_xp else int(min(10, max(0, (total - cur_xp) / max(nxt_xp - cur_xp, 1) * 10)))
    bar = "█" * pct + "░" * (10 - pct)
    color_hex = (cfg.get("card_bar") or "#5865F2").replace("#", "")
    try:
        color = int(color_hex, 16)
    except Exception:
        color = 0x5865F2
    font = cfg.get("card_font") or "sans"
    overlay = cfg.get("card_overlay", 40)
    bg = cfg.get("card_bg") or "#2B2D31"
    embed = discord.Embed(title=f"Carte de rang — {target.display_name}", color=color)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Niveau", value=str(current.get("level") or 1), inline=True)
    embed.add_field(name="XP", value=str(total), inline=True)
    embed.add_field(name="Barre", value=f"`{bar}` {need}", inline=False)
    embed.set_footer(text=f"Police {font} · overlay {overlay}% · fond {bg}")
    await ctx.send(embed=embed)

@bot.command(name="addxp")
async def addxp_cmd(ctx: commands.Context, raw: str = None, amount: int = None):
    if not await owner_check(ctx):
        return
    target = await resolve_user(ctx, raw)
    if target is None or amount is None:
        await ctx.send("❌ `+addxp @user 100`")
        return
    cfg = get_levels_cfg()
    all_xp = get_xp_data()
    gid, uid = str(ctx.guild.id), str(target.id)
    all_xp.setdefault(gid, {})
    user = all_xp[gid].setdefault(uid, {"xp": 0, "level": 1})
    user["xp"] = max(0, int(user.get("xp") or 0) + amount)
    user["level"] = int(level_for_xp(user["xp"], cfg).get("level") or 1)
    save_xp_data(all_xp)
    await ctx.send(f"✅ {target.mention} a **{user['xp']} XP** (niveau {user['level']}).")


class NewAccountModal(discord.ui.Modal, title="Âge minimum du compte"):
    days = discord.ui.TextInput(label="Nombre de jours", placeholder="7", required=True, max_length=3)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.days.value.isdigit() or int(self.days.value) < 1:
            await interaction.response.send_message("❌ Entre un nombre valide.", ephemeral=True)
            return
        config = get_config()
        config["ANTI_NEW_ACCOUNT_DAYS"] = int(self.days.value)
        save_config(config)
        await interaction.response.edit_message(embed=setup_embed(), view=SetupView(interaction.user.id))


class AntiRaidModal(discord.ui.Modal, title="Réglages anti-raid"):
    joins = discord.ui.TextInput(label="Nombre de joins max", placeholder="5", required=True, max_length=3)
    seconds = discord.ui.TextInput(label="Durée en secondes", placeholder="10", required=True, max_length=4)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.joins.value.isdigit() or not self.seconds.value.isdigit():
            await interaction.response.send_message("❌ Entre des nombres valides.", ephemeral=True)
            return
        config = get_config()
        config["ANTIRAID_JOINS"] = max(1, int(self.joins.value))
        config["ANTIRAID_SECONDS"] = max(1, int(self.seconds.value))
        save_config(config)
        await interaction.response.edit_message(embed=setup_embed(), view=SetupView(interaction.user.id))


class SetupView(discord.ui.View):
    def __init__(self, author_id: int, guild_id: Optional[int] = None):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.guild_id = guild_id

    def _gid(self, interaction: discord.Interaction) -> Optional[int]:
        gid = self.guild_id or (interaction.guild.id if interaction.guild else None)
        if gid:
            set_guild(gid)
        return gid

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id and not is_owner(interaction.user.id):
            await interaction.response.send_message("❌ Ce menu n'est pas pour toi.", ephemeral=True)
            return False
        return True

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="📋 Choisir le salon de logs",
        channel_types=[discord.ChannelType.text],
        min_values=1,
        max_values=1,
        row=0
    )
    async def pick_logs(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        channel = select.values[0]
        gid = self._gid(interaction)
        config = get_config(gid)
        config["LOG_CHANNEL_ID"] = channel.id
        save_config(config, gid)
        await interaction.response.edit_message(embed=setup_embed(gid), view=SetupView(self.author_id, gid))

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="🎫 Choisir la catégorie tickets",
        channel_types=[discord.ChannelType.category],
        min_values=1,
        max_values=1,
        row=1
    )
    async def pick_category(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        category = select.values[0]
        gid = self._gid(interaction) or (interaction.guild.id if interaction.guild else None)
        if gid is None:
            await interaction.response.send_message("Serveur introuvable.", ephemeral=True)
            return
        config = get_config(gid)
        config["TICKET_CATEGORY_ID"] = int(category.id)
        save_config(config, gid)
        # miroir global + confirm
        try:
            glob = load_json(CONFIG_FILE, DEFAULT_CONFIG.copy())
            glob["TICKET_CATEGORY_ID"] = int(category.id)
            save_json(CONFIG_FILE, glob)
        except Exception:
            pass
        print(f"[SETUP] Catégorie tickets={category.id} guild={gid}")
        try:
            cat_obj = interaction.guild.get_channel(int(category.id)) if interaction.guild else None
            if cat_obj is None and interaction.guild:
                try:
                    cat_obj = await bot.fetch_channel(int(category.id))
                except Exception:
                    cat_obj = None
            if isinstance(cat_obj, discord.CategoryChannel):
                await cat_obj.set_permissions(interaction.guild.default_role, view_channel=False)
                await cat_obj.set_permissions(interaction.guild.me, view_channel=True, manage_channels=True)
                staff_id = config.get("STAFF_ROLE_ID")
                if staff_id:
                    sr = interaction.guild.get_role(int(staff_id))
                    if sr:
                        await cat_obj.set_permissions(sr, view_channel=True)
                for oid in get_owners() + get_ownerplus():
                    m = interaction.guild.get_member(oid)
                    if m:
                        await cat_obj.set_permissions(m, view_channel=True)
        except Exception as e:
            print(f"[SETUP] perms catégorie: {e}")
        await interaction.response.edit_message(embed=setup_embed(gid), view=SetupView(self.author_id, gid))

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="🎭 Choisir l'autorole",
        min_values=1,
        max_values=1,
        row=2
    )
    async def pick_autorole(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        role = select.values[0]
        gid = self._gid(interaction)
        config = get_config(gid)
        config["AUTOROLE_ID"] = role.id
        save_config(config, gid)
        await interaction.response.edit_message(embed=setup_embed(gid), view=SetupView(self.author_id, gid))

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="🚫 Ajouter un rôle anti-mention",
        min_values=1,
        max_values=1,
        row=3
    )
    async def pick_antimention(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        role = select.values[0]
        gid = self._gid(interaction)
        config = get_config(gid)
        roles = list(config.get("ANTI_MENTION_ROLES") or [])
        if role.id not in roles:
            roles.append(role.id)
        config["ANTI_MENTION_ROLES"] = roles
        save_config(config, gid)
        await interaction.response.edit_message(embed=setup_embed(gid), view=SetupView(self.author_id, gid))

    @discord.ui.button(label="Anti-link", style=discord.ButtonStyle.secondary, row=4)
    async def toggle_antilink(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = self._gid(interaction)
        config = get_config(gid)
        config["ANTILINK"] = not config.get("ANTILINK")
        save_config(config, gid)
        await interaction.response.edit_message(embed=setup_embed(gid), view=SetupView(self.author_id, gid))

    @discord.ui.button(label="Anti-raid", style=discord.ButtonStyle.secondary, row=4)
    async def toggle_antiraid(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = self._gid(interaction)
        config = get_config(gid)
        config["ANTIRAID"] = not config.get("ANTIRAID")
        save_config(config, gid)
        await interaction.response.edit_message(embed=setup_embed(gid), view=SetupView(self.author_id, gid))

    @discord.ui.button(label="Anti new", style=discord.ButtonStyle.secondary, row=4)
    async def toggle_antinew(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = self._gid(interaction)
        config = get_config(gid)
        config["ANTI_NEW_ACCOUNT"] = not config.get("ANTI_NEW_ACCOUNT")
        save_config(config, gid)
        await interaction.response.edit_message(embed=setup_embed(gid), view=SetupView(self.author_id, gid))

    @discord.ui.button(label="⏱ Jours comptes", style=discord.ButtonStyle.primary, row=4)
    async def edit_days(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NewAccountModal())

    @discord.ui.button(label="⏱ Anti-raid", style=discord.ButtonStyle.primary, row=4)
    async def edit_raid(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AntiRaidModal())


class LinkTimeoutModal(discord.ui.Modal, title="Timeout anti-lien"):
    minutes = discord.ui.TextInput(label="Minutes de timeout", placeholder="20", required=True, max_length=3)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.minutes.value.isdigit() or int(self.minutes.value) < 1:
            await interaction.response.send_message("❌ Nombre invalide.", ephemeral=True)
            return
        gid = interaction.guild.id if interaction.guild else None
        if gid:
            set_guild(gid)
        config = get_config(gid)
        config["ANTILINK_TIMEOUT_MINUTES"] = min(int(self.minutes.value), 40320)
        save_config(config, gid)
        await interaction.response.edit_message(embed=setup_embed(gid), view=SetupView(interaction.user.id, gid))


ROLE_PERM_OPTIONS = [
    ("Voir les salons", "view_channel"),
    ("Envoyer des messages", "send_messages"),
    ("Envoyer des messages TTS", "send_tts_messages"),
    ("Gérer les messages", "manage_messages"),
    ("Intégrer des liens", "embed_links"),
    ("Joindre des fichiers", "attach_files"),
    ("Historique des messages", "read_message_history"),
    ("Mention everyone", "mention_everyone"),
    ("Utiliser les emojis externes", "external_emojis"),
    ("Ajouter des réactions", "add_reactions"),
    ("Se connecter au vocal", "connect"),
    ("Parler", "speak"),
    ("Mute membres", "mute_members"),
    ("Deaf membres", "deafen_members"),
    ("Déplacer membres", "move_members"),
    ("Kick", "kick_members"),
    ("Ban", "ban_members"),
    ("Timeout", "moderate_members"),
    ("Gérer les rôles", "manage_roles"),
    ("Gérer les salons", "manage_channels"),
    ("Gérer le serveur", "manage_guild"),
    ("Gérer les webhooks", "manage_webhooks"),
    ("Gérer les events", "manage_events"),
    ("Créer des invitations", "create_instant_invite"),
    ("Admin", "administrator"),
]


class RolePermsView(discord.ui.View):
    def __init__(self, author_id: int, role: Optional[discord.Role] = None):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.role = role

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return is_owner(interaction.user.id)

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Choisir un rôle", min_values=1, max_values=1)
    async def pick_role(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        self.role = select.values[0]
        perms = self.role.permissions
        lines = []
        for label, attr in ROLE_PERM_OPTIONS:
            val = getattr(perms, attr, False)
            lines.append(f"{'🟢' if val else '🔴'} {label}")
        embed = discord.Embed(title=f"Permissions — {self.role.name}", description="\n".join(lines), color=self.role.color or 0x2B2D31)
        embed.set_footer(text="Choisis une permission à inverser")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.select(
        placeholder="Permission à activer / désactiver",
        options=[discord.SelectOption(label=label, value=attr) for label, attr in ROLE_PERM_OPTIONS]
    )
    async def pick_perm(self, interaction: discord.Interaction, select: discord.ui.Select):
        if self.role is None:
            await interaction.response.send_message("❌ Choisis d'abord un rôle.", ephemeral=True)
            return
        attr = select.values[0]
        perms = self.role.permissions
        current = getattr(perms, attr)
        perms.update(**{attr: not current})
        try:
            await self.role.edit(permissions=perms, reason=f"Modifié par {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message("❌ Impossible de modifier ce rôle (hiérarchie / permissions).", ephemeral=True)
            return
        except Exception as e:
            await interaction.response.send_message(f"❌ Erreur : `{e}`", ephemeral=True)
            return
        self.role = interaction.guild.get_role(self.role.id)
        perms = self.role.permissions
        lines = []
        for label, name in ROLE_PERM_OPTIONS:
            val = getattr(perms, name, False)
            lines.append(f"{'🟢' if val else '🔴'} {label}")
        embed = discord.Embed(title=f"Permissions — {self.role.name}", description="\n".join(lines), color=self.role.color or 0x2B2D31)
        await interaction.response.edit_message(embed=embed, view=self)

class TicketView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=None)
        self.user_id = str(user_id)
        if len(self.children) >= 1:
            self.children[0].custom_id = f"ticket_claim:{self.user_id}"
        if len(self.children) >= 2:
            self.children[1].custom_id = f"ticket_close:{self.user_id}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not is_owner(interaction.user.id):
            await interaction.response.send_message("❌ Seuls les owners peuvent utiliser ces boutons.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🙋 Claim", style=discord.ButtonStyle.primary, custom_id="ticket_claim")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = interaction.guild.id if interaction.guild else None
        if gid:
            set_guild(gid)
        tickets = get_tickets(gid)
        if self.user_id not in tickets or tickets[self.user_id].get("closed"):
            await interaction.response.send_message("❌ Ticket introuvable ou fermé.", ephemeral=True)
            return

        if tickets[self.user_id].get("claimed_by"):
            claimed = tickets[self.user_id]["claimed_by"]
            await interaction.response.send_message(f"❌ Déjà claim par <@{claimed}>.", ephemeral=True)
            return

        tickets[self.user_id]["claimed_by"] = interaction.user.id
        staff = [int(x) for x in (tickets[self.user_id].get("staff") or [])]
        if interaction.user.id not in staff:
            staff.append(interaction.user.id)
        tickets[self.user_id]["staff"] = staff
        save_tickets(tickets, gid)

        tid = tickets[self.user_id].get("ticket_id") or self.user_id
        try:
            await interaction.channel.edit(name=f"claimed-{str(tid).lower()}-{interaction.user.name.lower()[:10]}"[:90])
        except Exception:
            pass

        # Ajoute le claimer SANS retirer owners / staff
        try:
            await interaction.channel.set_permissions(
                interaction.user,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            )
        except Exception:
            pass

        await interaction.response.send_message(
            f"✅ Ticket **`{tid}`** claim par {interaction.user.mention}",
            ephemeral=False,
        )

    @discord.ui.button(label="🔒 Fermer", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = interaction.guild.id if interaction.guild else None
        if gid:
            set_guild(gid)
        tickets = get_tickets(gid)
        if self.user_id not in tickets:
            # fallback recherche
            ukey, data, found = find_ticket_entry(self.user_id, gid)
            if not ukey:
                await interaction.response.send_message("❌ Ticket introuvable.", ephemeral=True)
                return
            self.user_id = ukey
            gid = found
            tickets = get_tickets(gid)

        data = tickets[self.user_id]
        if not can_manage_ticket(interaction.user.id, data):
            await interaction.response.send_message(
                "❌ Tu ne peux pas fermer ce ticket (claim requis, sauf owners).",
                ephemeral=True,
            )
            return

        tid = data.get("ticket_id") or self.user_id
        view = ConfirmCloseView(self.user_id, interaction.user, gid)
        await interaction.response.send_message(
            f"⚠️ Fermer le ticket **`{tid}`** ?\nLe salon sera **supprimé** (réouvrable avec `+reopen {tid}`).",
            view=view,
            ephemeral=True,
        )


class ConfirmCloseView(discord.ui.View):
    def __init__(self, user_id: str, closer: discord.Member, guild_id: Optional[int] = None):
        super().__init__(timeout=60)
        self.user_id = str(user_id)
        self.closer = closer
        self.guild_id = guild_id

    @discord.ui.button(label="Oui, fermer", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.closer.id:
            await interaction.response.send_message("❌ Seule la personne qui a demandé peut confirmer.", ephemeral=True)
            return
        gid = self.guild_id or (interaction.guild.id if interaction.guild else None)
        if gid:
            set_guild(gid)
        tickets = get_tickets(gid)
        if self.user_id not in tickets:
            await interaction.response.send_message("❌ Ticket introuvable.", ephemeral=True)
            return
        tid = tickets[self.user_id].get("ticket_id") or self.user_id
        await interaction.response.edit_message(
            content=f"✅ Ticket **`{tid}`** fermé. Salon en suppression…",
            view=None,
        )
        await close_ticket(self.user_id, self.closer, interaction.channel, guild_id=gid)

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.closer.id:
            await interaction.response.send_message("❌ Seule la personne qui a demandé peut annuler.", ephemeral=True)
            return
        await interaction.response.edit_message(content="❌ Fermeture annulée.", view=None)


class RecruitModal(discord.ui.Modal, title="Candidature recrutement"):
    age = discord.ui.TextInput(label="Âge / disponibilité", max_length=100)
    experience = discord.ui.TextInput(label="Expérience", style=discord.TextStyle.paragraph, max_length=500)
    why = discord.ui.TextInput(label="Pourquoi postuler ?", style=discord.TextStyle.paragraph, max_length=800)

    async def on_submit(self, interaction: discord.Interaction):
        if is_blacklisted(interaction.user.id):
            await interaction.response.send_message("Tu es blacklisté.", ephemeral=True)
            return
        cfg = get_config(interaction.guild.id if interaction.guild else None)
        if not cfg.get("RECRUIT_ENABLED"):
            await interaction.response.send_message("Le recrutement est **fermé**.", ephemeral=True)
            return
        emb = discord.Embed(
            title="Nouvelle candidature",
            color=0x5865F2,
            timestamp=discord.utils.utcnow(),
        )
        emb.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        emb.add_field(name="Membre", value=f"{interaction.user.mention}\n`{interaction.user.id}`", inline=False)
        emb.add_field(name="Âge / dispo", value=str(self.age.value)[:200], inline=False)
        emb.add_field(name="Expérience", value=str(self.experience.value)[:500], inline=False)
        emb.add_field(name="Motivation", value=str(self.why.value)[:800], inline=False)
        staff_id = cfg.get("RECRUIT_STAFF_CHANNEL_ID") or cfg.get("LOG_CHANNEL_ID")
        sent = False
        if staff_id and interaction.guild:
            ch = interaction.guild.get_channel(int(staff_id))
            if ch:
                try:
                    await ch.send(embed=emb)
                    sent = True
                except Exception:
                    pass
        await interaction.response.send_message(
            "Candidature envoyée." if sent else "Candidature enregistrée (configure le salon staff).",
            ephemeral=True,
        )
        await send_log(emb)

class RecruitView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Postuler", style=discord.ButtonStyle.success, emoji="📝", custom_id="recruit_apply_btn")
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        if is_blacklisted(interaction.user.id):
            await interaction.response.send_message("Tu es blacklisté.", ephemeral=True)
            return
        cfg = get_config(interaction.guild.id if interaction.guild else None)
        if not cfg.get("RECRUIT_ENABLED"):
            await interaction.response.send_message("Le recrutement est **fermé**.", ephemeral=True)
            return
        await interaction.response.send_modal(RecruitModal())

@bot.event
async def on_ready():
    cmds = sorted(bot.commands, key=lambda c: c.name)
    total = max(len(cmds), 1)
    print("\n  ────────────────────────────────────────")
    print(f"  {bot.user}   v{BOT_VERSION}")
    print("  ────────────────────────────────────────")
    print("  Chargement")
    groups = [
        ("Propriétaire", ["owner", "unowner", "help", "debug", "restart", "status", "servers"]),
        ("Modération", ["kick", "ban", "unban", "mute", "unmute", "bl", "unbl"]),
        ("Serveur", ["setup", "welcome", "boost", "annonce", "nuke", "giverole"]),
        ("Tickets", ["ticket", "claim", "add", "remove"]),
        ("Niveaux", ["levels", "rank", "top", "addxp"]),
    ]
    loaded = 0
    for label, names in groups:
        print(f"   · {label}")
        loaded += 1
    for i, cmd in enumerate(cmds, 1):
        if i % 12 == 0 or i == total:
            print(f"   [{i}/{total}] commandes")
    print("  ────────────────────────────────────────")
    print(f"  Commandes : {len(cmds)}")
    print(f"  Serveurs  : {len(bot.guilds)}")
    print(f"  Ping      : {round(bot.latency * 1000)} ms")
    print(f"  Propriétaires : {len(get_owners())}")
    print("  ────────────────────────────────────────\n")
    print(f"  Ready : {bot.user} — {len(cmds)} commandes")

    flag = os.path.join(DATA_DIR, "restart.json")
    if os.path.exists(flag):
        try:
            info = load_json(flag, {})
            os.remove(flag)
            ch = bot.get_channel(int(info.get("channel_id") or 0))
            if ch:
                await ch.send(embed=discord.Embed(
                    title="Bot redémarré",
                    description=f"Relancé avec succès.\nPing **{round(bot.latency*1000)} ms** · **{len(cmds)}** commandes",
                    color=0x57F287,
                    timestamp=discord.utils.utcnow()
                ))
        except Exception:
            pass

    init_db()
    try:
        conn = db()
        for g in bot.guilds:
            conn.execute(
                "INSERT OR REPLACE INTO guilds(guild_id,name,owner_id,member_count,joined_at,icon) VALUES(?,?,?,?,?,?)",
                (str(g.id), g.name, str(g.owner_id), g.member_count or 0, discord.utils.utcnow().isoformat(), str(g.icon.url) if g.icon else None),
            )
        conn.commit()
        conn.close()
    except Exception:
        pass
    for path in (
        OWNERS_FILE, OWNERPLUS_FILE, BLACKLIST_FILE, BANNED_WORDS_FILE,
        INFRACTIONS_FILE, NOTES_FILE, SANCTIONS_FILE, BACKUPS_FILE,
        BIRTHDAYS_FILE, REPORTS_FILE, SUGGESTS_FILE, XP_FILE, LEVELS_FILE,
        CONFIG_FILE, TICKETS_FILE,
    ):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    db_put(os.path.basename(path), json.load(f))
            except Exception:
                pass

    if not auto_message_loop.is_running():
        auto_message_loop.start()

    if not stats_loop.is_running():
        stats_loop.start()
    if not owner_presence_scan.is_running():
        owner_presence_scan.start()
        print("  Owner protect scan : toutes les 5s")
    if not temprole_loop.is_running():
        temprole_loop.start()
    if UPDATE_ENABLED and UPDATE_VERSION_URL and not update_check_loop.is_running():
        update_check_loop.start()
        print(f"  Auto-update : toutes les {UPDATE_INTERVAL}s")

    tickets = get_tickets()
    for tid, data in tickets.items():
        if not data.get("closed"):
            bot.add_view(TicketView(tid))

    giveaways = load_json(GIVEAWAYS_FILE, {})
    for gid, g in giveaways.items():
        if not g.get("ended"):
            bot.add_view(GiveawayView(gid))
            try:
                end_time = datetime.fromisoformat(g["end_time"])
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=timezone.utc)
                remaining = (end_time - discord.utils.utcnow()).total_seconds()
                if remaining > 0:
                    bot.loop.create_task(end_giveaway_after(gid, remaining))
                else:
                    bot.loop.create_task(end_giveaway(gid))
            except Exception as e:
                print(f"Erreur giveaway {gid}: {e}")
    bot.add_view(RecruitView())

    # Sync commandes slash
    try:
        synced = await bot.tree.sync()
        print(f"  Slash sync : {len(synced)} commande(s)")
    except Exception as e:
        print(f"  Slash sync échec : {e}")
        record_error("slash", "tree.sync", str(e))

    # Diagnostic démarrage
    try:
        diag = run_system_diagnostics()
        bad = [c for c in diag["checks"] if not c["ok"]]
        if bad:
            print("  ⚠ Diagnostics :")
            for c in bad:
                print(f"    · {c['name']}: {c['detail']}")
        else:
            print("  Diagnostics : OK")
    except Exception as e:
        print(f"  Diagnostics échec : {e}")

def record_error(kind: str, title: str, detail: str, extra: dict = None):
    if TOKEN and TOKEN in (detail or ""):
        detail = detail.replace(TOKEN, "[TOKEN]")
    extra = extra or {}
    if TOKEN:
        for k, v in list(extra.items()):
            if isinstance(v, str) and TOKEN in v:
                extra[k] = v.replace(TOKEN, "[TOKEN]")
    row = {
        "kind": kind,
        "title": str(title)[:120],
        "detail": (detail or "")[:2000],
        "extra": extra,
        "at": datetime.now().isoformat(),
    }
    data = load_json(ERRORS_FILE, [])
    if not isinstance(data, list):
        data = []
    data.append(row)
    save_json(ERRORS_FILE, data[-150:])
    print(f"[ERR {kind}] {title}: {detail[:200]}")
    # Sauvegarde détaillée automatique
    try:
        os.makedirs(ERROR_DUMP_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = re.sub(r"[^\w\-]+", "_", str(title))[:40]
        path = os.path.join(ERROR_DUMP_DIR, f"{stamp}_{kind}_{safe}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(row, f, ensure_ascii=False, indent=2)
        # garde 80 dumps max
        dumps = sorted(
            [os.path.join(ERROR_DUMP_DIR, x) for x in os.listdir(ERROR_DUMP_DIR) if x.endswith(".json")],
            key=os.path.getmtime,
        )
        for old in dumps[:-80]:
            try:
                os.remove(old)
            except Exception:
                pass
    except Exception as e:
        print(f"[ERR] dump write failed: {e}")
    return row

def run_system_diagnostics() -> dict:
    """Vérifie data, token, fichiers, permissions basiques — détails auto."""
    checks = []
    ok = True

    def add(name, status, detail=""):
        nonlocal ok
        if not status:
            ok = False
        checks.append({"name": name, "ok": bool(status), "detail": detail})

    add("TOKEN", bool(TOKEN and len(str(TOKEN)) > 20), "DISCORD_TOKEN manquant ou trop court" if not TOKEN else "OK")
    add("BOT_OWNER_ID", bool(BOT_OWNER_ID), "BOT_OWNER_ID=0 — owner protect limité" if not BOT_OWNER_ID else "OK")
    add("DATA_DIR", os.path.isdir(DATA_DIR) or True, DATA_DIR)
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        test = os.path.join(DATA_DIR, ".write_test")
        with open(test, "w") as f:
            f.write("ok")
        os.remove(test)
        add("Écriture data/", True, "OK")
    except Exception as e:
        add("Écriture data/", False, str(e))
    for label, path in [
        ("owners.json", OWNERS_FILE),
        ("blacklist.json", BLACKLIST_FILE),
        ("config.json", CONFIG_FILE),
        ("errors.json", ERRORS_FILE),
    ]:
        try:
            load_json(path, [] if "owners" in label or "black" in label or "error" in label else {})
            add(f"Fichier {label}", True, "lisible")
        except Exception as e:
            add(f"Fichier {label}", False, str(e))
    try:
        add("Bot connecté", bot.is_ready(), f"user={bot.user}" if bot.is_ready() else "pas encore ready")
        add("Latence", bot.latency < 2.0 if bot.is_ready() else True, f"{round(bot.latency*1000)} ms" if bot.is_ready() else "N/A")
        add("Serveurs", True, str(len(bot.guilds)))
        add("Commandes prefix", True, str(len(bot.commands)))
        add("Commandes slash", True, str(len(bot.tree.get_commands())))
    except Exception as e:
        add("État bot", False, str(e))
    if UPDATE_ENABLED:
        add("Update URLs", bool(UPDATE_VERSION_URL and UPDATE_CODE_URL), "UPDATE_* manquant" if not (UPDATE_VERSION_URL and UPDATE_CODE_URL) else "OK")
    result = {
        "ok": ok,
        "checks": checks,
        "at": datetime.now().isoformat(),
        "version": BOT_VERSION,
        "guilds": len(bot.guilds) if bot.is_ready() else 0,
        "commands": len(bot.commands),
        "slash": len(bot.tree.get_commands()),
        "ping_ms": round(bot.latency * 1000) if bot.is_ready() else None,
        "file": None,
    }
    # Fichier détaillé automatique
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        report_dir = os.path.join(DATA_DIR, "diagnostics")
        os.makedirs(report_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(report_dir, f"diagnostic_{stamp}.txt")
        lines = [
            f"=== DIAGNOSTIC CORE v{BOT_VERSION} ===",
            f"Date : {result['at']}",
            f"Statut global : {'OK' if ok else 'PROBLEMES'}",
            f"Serveurs : {result['guilds']}",
            f"Commandes + : {result['commands']}",
            f"Commandes / : {result['slash']}",
            f"Ping : {result['ping_ms']} ms",
            "",
            "--- Checks ---",
        ]
        for c in checks:
            lines.append(f"[{'OK' if c['ok'] else 'FAIL'}] {c['name']} — {c['detail']}")
        lines.append("")
        lines.append("--- Environnement ---")
        lines.append(f"Python : {platform.python_version()}")
        lines.append(f"discord.py : {discord.__version__}")
        lines.append(f"Platform : {platform.platform()}")
        lines.append(f"DATA_DIR : {os.path.abspath(DATA_DIR)}")
        lines.append(f"BOT_FILE : {BOT_FILE}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        result["file"] = path
        # JSON twin
        jpath = path.replace(".txt", ".json")
        with open(jpath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        # garder 30 rapports
        reports = sorted(
            [os.path.join(report_dir, x) for x in os.listdir(report_dir) if x.startswith("diagnostic_")],
            key=os.path.getmtime,
        )
        for old in reports[:-60]:
            try:
                os.remove(old)
            except Exception:
                pass
    except Exception as e:
        result["file_error"] = str(e)
    return result

async def report_system_error(kind: str, title: str, detail: str, extra: dict = None):
    row = record_error(kind, title, detail, extra)
    emb = discord.Embed(title=f"Erreur — {kind}", color=0xED4245, timestamp=discord.utils.utcnow())
    emb.add_field(name="Titre", value=str(title)[:200], inline=False)
    emb.add_field(name="Détail", value=f"```{str(detail)[:900]}```", inline=False)
    if extra:
        emb.add_field(name="Contexte", value=f"```{json.dumps(extra, ensure_ascii=False)[:500]}```", inline=False)
    try:
        await send_log(emb)
    except Exception:
        pass
    return row

SENSITIVE_CMDS = {
    "nuke", "backup", "dm", "ban", "kick", "bl", "owner", "ownerplus",
    "giverole", "delrole", "normalize", "leave", "restart",
}

@bot.event
async def on_command(ctx: commands.Context):
    if ctx.author.bot:
        return
    if is_blacklisted(ctx.author.id):
        return
    name = ctx.command.name if ctx.command else "?"
    if name in SENSITIVE_CMDS or name.startswith("ban"):
        await send_log(discord.Embed(
            title="Commande sensible",
            description=f"`+{ctx.message.content[:200]}`\nPar {ctx.author.mention} (`{ctx.author.id}`)\nSalon : {getattr(ctx.channel, 'mention', 'MP')}",
            color=0xFEE75C,
            timestamp=discord.utils.utcnow(),
        ))

@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    if isinstance(error, (commands.CommandNotFound, commands.CheckFailure)):
        return
    err = getattr(error, "original", error)
    err_s = str(err)
    if TOKEN:
        err_s = err_s.replace(TOKEN, "[TOKEN]")
    import traceback
    tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))[-2000:]
    await report_system_error("commande", str(ctx.command), err_s, {
        "user": ctx.author.id,
        "guild": ctx.guild.id if ctx.guild else None,
        "channel": ctx.channel.id if ctx.channel else None,
        "content": (ctx.message.content if ctx.message else "")[:200],
        "trace": tb[-1200:],
    })
    embed = discord.Embed(title="Erreur commande", color=0xED4245, timestamp=discord.utils.utcnow())
    embed.add_field(name="Commande", value=f"`+{ctx.command}`" if ctx.command else "?", inline=True)
    embed.add_field(name="Auteur", value=f"{ctx.author} (`{ctx.author.id}`)", inline=True)
    embed.add_field(name="Type", value=type(err).__name__, inline=True)
    embed.add_field(name="Erreur", value=f"`{err_s[:900]}`", inline=False)
    if is_owner(ctx.author.id):
        try:
            await ctx.send(embed=embed, delete_after=25)
        except Exception:
            pass

@bot.event
async def on_error(event, *args, **kwargs):
    import traceback
    tb = traceback.format_exc()
    await report_system_error("bot", event, tb[-2000:], {"args": str(args)[:300]})

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    err = getattr(error, "original", error)
    import traceback
    tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))[-2000:]
    await report_system_error("slash", getattr(interaction.command, "name", "slash"), str(err), {
        "user": interaction.user.id,
        "guild": interaction.guild.id if interaction.guild else None,
        "trace": tb[-1200:],
    })
    msg = f"Erreur slash : `{err}`"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass

@bot.event
async def on_member_join(member: discord.Member):
    set_guild(member.guild.id)
    config = get_config(member.guild.id)
    embed = discord.Embed(title="📥 Membre rejoint", description=f"{member.mention} (`{member.id}`)\nServeur : **{member.guild.name}**", color=0x57F287, timestamp=discord.utils.utcnow())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Compte créé", value=discord.utils.format_dt(member.created_at, "R"))
    await send_log(embed)

    if member.bot:
        if config.get("ANTI_BOT"):
            try:
                await member.kick(reason="Anti-bot")
            except Exception:
                pass
            await send_log(discord.Embed(title="Anti-bot", description=f"{member} kick", color=0xED4245))
        return

    if config.get("ANTI_NEW_ACCOUNT"):
        days = int(config.get("ANTI_NEW_ACCOUNT_DAYS") or 7)
        age = discord.utils.utcnow() - member.created_at
        if age.days < days:
            try:
                await member.send(
                    f"Tu as été expulsé de **{member.guild.name}** : ton compte a moins de **{days} jours** ({age.days}j)."
                )
            except Exception:
                pass
            try:
                await member.kick(reason=f"Anti nouveau compte ({age.days}j < {days}j)")
            except Exception:
                pass
            remember_mod("kicks", {"user_id": member.id, "reason": "anti-new-account", "guild": member.guild.id}, member.guild.id)
            await send_log(discord.Embed(
                title="🛡️ Compte refusé (anti nouveau compte)",
                description=f"{member} (`{member.id}`) kick de **{member.guild.name}** — compte trop récent ({age.days}j < {days}j).",
                color=0xED4245,
                timestamp=discord.utils.utcnow()
            ))
            return

    if config.get("ANTIRAID"):
        now = time.time()
        gid = member.guild.id
        window = int(config.get("ANTIRAID_SECONDS") or 10)
        limit = int(config.get("ANTIRAID_JOINS") or 5)
        JOIN_TRACKER.setdefault(gid, [])
        JOIN_TRACKER[gid] = [t for t in JOIN_TRACKER[gid] if now - t < window]
        JOIN_TRACKER[gid].append(now)
        if len(JOIN_TRACKER[gid]) >= limit:
            try:
                await member.send(f"Tu as été expulsé de **{member.guild.name}** (anti-raid).")
            except Exception:
                pass
            try:
                await member.kick(reason="Anti-raid : trop de joins")
            except Exception:
                pass
            remember_mod("kicks", {"user_id": member.id, "reason": "anti-raid", "guild": member.guild.id}, member.guild.id)
            await send_log(discord.Embed(
                title="🚨 Anti-raid",
                description=f"**{member.guild.name}** — {len(JOIN_TRACKER[gid])} joins / {window}s. {member} (`{member.id}`) kick.",
                color=0xED4245,
                timestamp=discord.utils.utcnow()
            ))
            return

    role_id = config.get("AUTOROLE_ID")
    if role_id:
        role = member.guild.get_role(int(role_id))
        if role:
            try:
                await member.add_roles(role, reason="Autorole")
            except Exception:
                pass

    if config.get("WELCOME_ENABLED") and config.get("WELCOME_CHANNEL_ID"):
        ch = member.guild.get_channel(int(config["WELCOME_CHANNEL_ID"]))
        if ch:
            text = (config.get("WELCOME_MESSAGE") or "Bienvenue {mention}").format(
                mention=member.mention, user=str(member), server=member.guild.name, count=member.guild.member_count
            )
            try:
                color_hex = (config.get("WELCOME_COLOR") or "#57F287").replace("#", "")
                try:
                    color = int(color_hex, 16)
                except Exception:
                    color = 0x57F287
                emb = discord.Embed(title=f"Bienvenue sur {member.guild.name}", description=text, color=color)
                emb.set_thumbnail(url=member.display_avatar.url)
                if member.guild.icon:
                    emb.set_author(name=member.guild.name, icon_url=member.guild.icon.url)
                if config.get("WELCOME_IMAGE"):
                    emb.set_image(url=config["WELCOME_IMAGE"])
                emb.set_footer(text=f"Membre #{member.guild.member_count}")
                await ch.send(embed=emb)
            except Exception:
                pass

async def owner_protection_leave(guild: discord.Guild, reason: str):
    """Le bot quitte le serveur si le propriétaire n'y est plus."""
    try:
        await send_log(discord.Embed(
            title="Owner protection — départ serveur",
            description=f"**{guild.name}** (`{guild.id}`)\n{reason}",
            color=0xED4245,
            timestamp=discord.utils.utcnow(),
        ))
    except Exception:
        pass
    print(f"[OWNER PROTECT] Leave {guild.name} ({guild.id}) — {reason}")
    try:
        await guild.leave()
    except Exception:
        pass

@tasks.loop(seconds=5)
async def owner_presence_scan():
    """Toutes les 5s : si le Propriétaire (BOT_OWNER_ID) n'est plus sur un serveur, le bot leave."""
    if not BOT_OWNER_ID:
        return
    for guild in list(bot.guilds):
        try:
            member = guild.get_member(BOT_OWNER_ID)
            if member is not None:
                continue
            try:
                await guild.fetch_member(BOT_OWNER_ID)
                continue
            except discord.NotFound:
                await owner_protection_leave(
                    guild,
                    f"Propriétaire `{BOT_OWNER_ID}` introuvable (scan 5s)",
                )
            except discord.HTTPException:
                pass
        except Exception as e:
            record_error("bot", "owner_presence_scan", str(e), {"guild": guild.id})
        await asyncio.sleep(0.2)

@owner_presence_scan.before_loop
async def owner_presence_scan_before():
    await bot.wait_until_ready()

@bot.event
async def on_member_remove(member: discord.Member):
    embed = discord.Embed(title="📤 Membre parti", description=f"{member} (`{member.id}`)", color=0xED4245, timestamp=discord.utils.utcnow())
    await send_log(embed)

    if is_owner(member.id):
        reason = "a quitté le serveur"
        # On consulte l'audit log pour distinguer un kick d'un départ volontaire.
        try:
            async for entry in member.guild.audit_logs(limit=5, action=discord.AuditLogAction.kick):
                if entry.target and entry.target.id == member.id:
                    if (discord.utils.utcnow() - entry.created_at).total_seconds() < 15:
                        reason = f"a été kick par {entry.user} (`{entry.user.id}`)"
                    break
        except Exception:
            pass
        await owner_protection_leave(member.guild, f"owner {member} (`{member.id}`) {reason}")

@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    embed = discord.Embed(title="🔨 Membre banni", description=f"{user} (`{user.id}`)", color=0xED4245, timestamp=discord.utils.utcnow())
    await send_log(embed)
    set_guild(guild.id)
    remember_mod("bans", {"user_id": user.id, "name": str(user)}, guild.id)

    if is_owner(user.id):
        banned_by = None
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
                if entry.target and entry.target.id == user.id:
                    if (discord.utils.utcnow() - entry.created_at).total_seconds() < 15:
                        banned_by = entry.user
                    break
        except Exception:
            pass
        who = f" par {banned_by} (`{banned_by.id}`)" if banned_by else ""
        await owner_protection_leave(guild, f"owner {user} (`{user.id}`) a été banni{who}")

@bot.event
async def on_member_unban(guild: discord.Guild, user: discord.User):
    embed = discord.Embed(title="🔓 Membre débanni", description=f"{user} (`{user.id}`)", color=0x57F287, timestamp=discord.utils.utcnow())
    await send_log(embed)

@bot.event
async def on_message_delete(message: discord.Message):
    if message.guild and not message.author.bot:
        SNIPE_CACHE[message.channel.id] = message
        embed = discord.Embed(title="🗑️ Message supprimé", color=0xED4245, timestamp=discord.utils.utcnow())
        embed.add_field(name="Auteur", value=f"{message.author} (`{message.author.id}`)", inline=True)
        embed.add_field(name="Salon", value=message.channel.mention, inline=True)
        embed.add_field(name="Contenu", value=message.content[:1000] or "*vide*", inline=False)
        await send_log(embed)

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if before.guild and not before.author.bot and before.content != after.content:
        embed = discord.Embed(title="✏️ Message modifié", color=0xFEE75C, timestamp=discord.utils.utcnow())
        embed.add_field(name="Auteur", value=f"{before.author} (`{before.author.id}`)", inline=True)
        embed.add_field(name="Salon", value=before.channel.mention, inline=True)
        embed.add_field(name="Avant", value=before.content[:500] or "*vide*", inline=False)
        embed.add_field(name="Après", value=after.content[:500] or "*vide*", inline=False)
        await send_log(embed)

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    set_guild(after.guild.id)
    locked = load_json(LOCKED_NAMES_FILE, {})
    if str(after.id) in locked:
        target_name = locked[str(after.id)]
        if after.display_name != target_name:
            try:
                await after.edit(nick=target_name)
            except Exception:
                pass

    added = [r for r in after.roles if r not in before.roles]
    removed = [r for r in before.roles if r not in after.roles]
    if added or removed:
        desc = ""
        if added:
            desc += "Ajouté : " + ", ".join(r.mention for r in added) + "\n"
        if removed:
            desc += "Retiré : " + ", ".join(r.mention for r in removed)
        await send_log(discord.Embed(
            title="🎭 Rôles modifiés",
            description=f"{after.mention} (`{after.id}`) sur **{after.guild.name}**\n{desc}",
            color=0x5865F2,
            timestamp=discord.utils.utcnow()
        ))
        remember_mod("roles", {"user_id": after.id, "added": [r.id for r in added], "removed": [r.id for r in removed]}, after.guild.id)

    if before.timed_out_until != after.timed_out_until:
        if after.timed_out_until and get_config(after.guild.id).get("ANTI_TIMEOUT") and not is_owner(after.id):
            try:
                await after.timeout(None, reason="Anti-timeout")
            except Exception:
                pass
        if after.timed_out_until:
            await send_log(discord.Embed(title="🔇 Mute / timeout", description=f"{after.mention} jusqu'à {discord.utils.format_dt(after.timed_out_until, 'R')} sur **{after.guild.name}**", color=0xFEE75C, timestamp=discord.utils.utcnow()))
            remember_mod("mutes", {"user_id": after.id}, after.guild.id)
        else:
            await send_log(discord.Embed(title="🔊 Unmute", description=f"{after.mention} sur **{after.guild.name}**", color=0x57F287, timestamp=discord.utils.utcnow()))

    if before.premium_since is None and after.premium_since is not None:
        cfg = get_config(after.guild.id)
        tpl = cfg.get("BOOST_MESSAGE") or "🚀 {mention} vient de **booster** **{server}** ! Merci 💜"
        try:
            text = tpl.format(mention=after.mention, server=after.guild.name, user=str(after), name=after.display_name)
        except Exception:
            text = f"🚀 {after.mention} vient de **booster** **{after.guild.name}** ! Merci 💜"
        emb = discord.Embed(
            title="🚀 Nouveau boost !",
            description=text,
            color=0xF47FFF,
            timestamp=discord.utils.utcnow(),
        )
        emb.set_thumbnail(url=after.display_avatar.url)
        emb.add_field(name="Membre", value=f"{after.mention}\n`{after.id}`", inline=True)
        emb.add_field(name="Boosts serveur", value=str(after.guild.premium_subscription_count or 0), inline=True)
        ch = None
        if cfg.get("BOOST_CHANNEL_ID"):
            ch = after.guild.get_channel(int(cfg["BOOST_CHANNEL_ID"]))
        if ch is None and after.guild.system_channel:
            ch = after.guild.system_channel
        if ch:
            try:
                await ch.send(content=after.mention, embed=emb)
            except Exception:
                try:
                    await ch.send(text)
                except Exception:
                    pass
        await send_log(emb)

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    cfg = get_config(member.guild.id) if member.guild else {}
    if after.channel:
        bl = [int(x) for x in load_json(VOICE_BL_FILE, [])]
        if member.id in bl:
            try:
                await member.move_to(None, reason="bl-voice")
            except Exception:
                pass
            return
        hub = cfg.get("PRIVVC_HUB_ID")
        if hub and after.channel.id == int(hub):
            cat = member.guild.get_channel(int(cfg["PRIVVC_CATEGORY_ID"])) if cfg.get("PRIVVC_CATEGORY_ID") else after.channel.category
            overwrites = {
                member.guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=True),
                member: discord.PermissionOverwrite(connect=True, speak=True, manage_channels=True, move_members=True),
                member.guild.me: discord.PermissionOverwrite(connect=True, manage_channels=True),
            }
            try:
                vc = await member.guild.create_voice_channel(
                    name=f"🔊 {member.display_name}"[:100],
                    category=cat,
                    overwrites=overwrites,
                    reason="vocal privé auto",
                )
                PRIV_VCS[vc.id] = member.id
                await member.move_to(vc)
            except Exception:
                pass
    if before.channel and before.channel.id in PRIV_VCS:
        if len(before.channel.members) == 0:
            PRIV_VCS.pop(before.channel.id, None)
            try:
                await before.channel.delete(reason="vocal privé vide")
            except Exception:
                pass

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.author.id in PARROT_UNTIL and time.time() < PARROT_UNTIL[message.author.id]:
        try:
            await message.channel.send(message.content[:1900] or "…")
        except Exception:
            pass
    elif message.author.id in PARROT_UNTIL:
        PARROT_UNTIL.pop(message.author.id, None)

    if message.guild:
        set_guild(message.guild.id)
        config = get_config()
        content_l = message.content.lower()
        link_re = re.compile(
            r"(https?://[^\s]+|www\.[^\s]+|discord\.gg/[^\s]+|discord\.com/invite/[^\s]+|[a-z0-9-]+\.(com|net|org|gg|io|xyz|fr|tv|me)/[^\s]*)",
            re.I,
        )

        async def punish(reason: str, minutes: int = 20, blur: bool = False):
            original = message.content
            try:
                await message.delete()
            except Exception:
                pass
            shown = original
            if blur:
                shown = link_re.sub("[lien brouillé]", original)
            try:
                await message.channel.send(
                    f"{message.author.mention} — {reason}\n{shown[:1500]}",
                    delete_after=20,
                )
            except Exception:
                pass
            try:
                until = discord.utils.utcnow() + timedelta(minutes=minutes)
                await message.author.timeout(until, reason=reason)
            except Exception:
                pass
            await send_log(discord.Embed(
                title=reason,
                description=f"{message.author.mention} (`{message.author.id}`)\nTimeout {minutes} min\n`{original[:400]}`",
                color=0xFEE75C,
                timestamp=discord.utils.utcnow(),
            ))

        if config.get("ANTILINK") is not False:
            if link_re.search(message.content):
                await punish("Anti-lien", int(config.get("ANTILINK_TIMEOUT_MINUTES") or 20), blur=True)
                return

        if config.get("ANTISPAM"):
            now = time.time()
            uid = message.author.id
            window = int(config.get("ANTISPAM_SECONDS") or 5)
            limit = int(config.get("ANTISPAM_MESSAGES") or 6)
            dup_limit = int(config.get("ANTISPAM_DUPLICATES") or 3)
            mention_limit = int(config.get("ANTISPAM_MENTIONS") or 6)
            SPAM_TRACKER.setdefault(uid, [])
            SPAM_TRACKER[uid] = [x for x in SPAM_TRACKER[uid] if now - x["t"] < window]
            SPAM_TRACKER[uid].append({"t": now, "c": message.content})
            mentions = len(message.mentions) + len(message.role_mentions)
            same = sum(1 for x in SPAM_TRACKER[uid] if x["c"] == message.content)
            reason = None
            if len(SPAM_TRACKER[uid]) >= limit:
                reason = f"{limit} messages / {window}s"
            elif same >= dup_limit:
                reason = "messages identiques"
            elif mentions >= mention_limit:
                reason = "mass mention"
            if reason:
                SPAM_TRACKER[uid] = []
                await punish(f"Anti-spam ({reason})", int(config.get("ANTISPAM_TIMEOUT_MINUTES") or 20))
                return

        letters = re.sub(r"[^A-Za-z]", "", message.content)
        if config.get("AUTOMOD_CAPS") and len(letters) >= 8 and sum(1 for c in letters if c.isupper()) / max(len(letters), 1) > 0.7:
            await punish("Trop de majuscules", 20)
            return

        protected = [int(x) for x in (config.get("ANTI_MENTION_ROLES") or [])]
        if protected and message.role_mentions:
            mentioned = [r.id for r in message.role_mentions]
            if any(rid in protected for rid in mentioned):
                await punish("Mention interdite", 20)
                return

        banned = [w.lower() for w in load_json(BANNED_WORDS_FILE, []) if w]
        if banned:
            text = message.content.lower()
            if any(w and w in text for w in banned):
                try:
                    await message.delete()
                except Exception:
                    pass
                uid = message.author.id
                WORD_STRIKES[uid] = WORD_STRIKES.get(uid, 0) + 1
                strikes = WORD_STRIKES[uid]
                await send_log(discord.Embed(
                    title="Mot interdit",
                    description=f"{message.author.mention} (`{uid}`) · avertissement {strikes}/3",
                    color=0xFEE75C,
                    timestamp=discord.utils.utcnow(),
                ))
                if strikes >= 3:
                    WORD_STRIKES[uid] = 0
                    try:
                        until = discord.utils.utcnow() + timedelta(minutes=20)
                        await message.author.timeout(until, reason="3 mots interdits")
                    except Exception:
                        pass
                    try:
                        await message.channel.send(
                            f"{message.author.mention} timeout 20 min (3 mots interdits).",
                            delete_after=8,
                        )
                    except Exception:
                        pass
                return

    if message.guild is None or isinstance(message.channel, discord.DMChannel):
        # ----- Tickets MP : trouver serveur + catégorie -----
        guild = None
        category = None
        config = None

        async def resolve_category(g: discord.Guild, cid) -> Optional[discord.CategoryChannel]:
            if cid in (None, "", 0, "0"):
                return None
            try:
                cid = int(cid)
            except Exception:
                return None
            raw = g.get_channel(cid)
            if raw is None:
                try:
                    raw = await bot.fetch_channel(cid)
                except Exception as e:
                    print(f"[TICKET] fetch_channel({cid}) fail: {e}")
                    return None
            if isinstance(raw, discord.CategoryChannel):
                if raw.guild and raw.guild.id != g.id:
                    return None
                return raw
            # ID d'un salon → prendre sa catégorie parente
            if getattr(raw, "category", None) is not None:
                return raw.category
            return None

        # Logs debug configs
        for g in bot.guilds:
            cfg = get_config(g.id)
            print(f"[TICKET] scan guild={g.name} ({g.id}) TICKET_CATEGORY_ID={cfg.get('TICKET_CATEGORY_ID')}")

        # 1) Premier serveur avec une catégorie tickets valide
        for g in bot.guilds:
            cfg = get_config(g.id)
            cat = await resolve_category(g, cfg.get("TICKET_CATEGORY_ID"))
            if cat is not None:
                guild, category, config = g, cat, cfg
                break

        # 2) Config globale data/config.json
        if guild is None:
            try:
                glob = load_json(CONFIG_FILE, {})
                for g in bot.guilds:
                    cat = await resolve_category(g, glob.get("TICKET_CATEGORY_ID"))
                    if cat is not None:
                        guild, category = g, cat
                        config = get_config(g.id)
                        config["TICKET_CATEGORY_ID"] = int(cat.id)
                        save_config(config, g.id)
                        break
            except Exception as e:
                print(f"[TICKET] global config: {e}")

        # 3) Serveur où l'utilisateur est membre
        if guild is None:
            for g in bot.guilds:
                m = g.get_member(message.author.id)
                if m is None:
                    try:
                        m = await g.fetch_member(message.author.id)
                    except Exception:
                        m = None
                if m is not None:
                    guild = g
                    config = get_config(g.id)
                    break

        # 4) N'importe quel serveur du bot
        if guild is None and bot.guilds:
            guild = bot.guilds[0]
            config = get_config(guild.id)

        if guild is None:
            await message.channel.send("❌ Le bot n'est présent sur aucun serveur.")
            return

        set_guild(guild.id)
        if config is None:
            config = get_config(guild.id)

        # Catégorie manquante → récupérer / créer, mais NE PAS bloquer le ticket
        if category is None:
            cid = config.get("TICKET_CATEGORY_ID")
            category = await resolve_category(guild, cid)
        if category is None:
            category = discord.utils.get(guild.categories, name="tickets")
        if category is None:
            try:
                category = await guild.create_category("tickets", reason="Tickets auto")
                print(f"[TICKET] Catégorie créée: {category.id}")
            except Exception as e:
                print(f"[TICKET] Création catégorie impossible: {e}")
                category = None
        if category is not None:
            config["TICKET_CATEGORY_ID"] = int(category.id)
            save_config(config, guild.id)
            try:
                glob = load_json(CONFIG_FILE, DEFAULT_CONFIG.copy())
                glob["TICKET_CATEGORY_ID"] = int(category.id)
                save_json(CONFIG_FILE, glob)
            except Exception:
                pass

        # Plus de message "non configuré" bloquant : on crée le salon même sans catégorie
        tickets = get_tickets(guild.id)
        print(f"[TICKET] MP de {message.author} → guild={guild.name} cat={getattr(category, 'id', None)}")
        user_id = str(message.author.id)
        try:
            await message.add_reaction("✉️")
        except Exception:
            pass

        # Staff répond avec +r en MP
        if message.content.startswith("+r ") and is_owner(message.author.id):
            parts = message.content.split(" ", 2)
            if len(parts) < 3:
                await message.channel.send("❌ Utilisation : `+r <ID> <message>`")
                return
            target_id = parts[1]
            reply_content = parts[2]
            # chercher le ticket dans tous les serveurs
            found_g = None
            found_t = None
            for g in bot.guilds:
                tks = get_tickets(g.id)
                if target_id in tks and not tks[target_id].get("closed"):
                    found_g, found_t = g, tks
                    break
            if not found_t:
                await message.channel.send("❌ Aucun ticket ouvert.")
                return
            try:
                target_user = await bot.fetch_user(int(target_id))
                await target_user.send(f"**{message.author.display_name}** : {reply_content}")
                await message.channel.send(f"✅ Envoyé à {target_user}")
                ch_id = found_t[target_id].get("channel_id")
                if ch_id:
                    tch = bot.get_channel(int(ch_id))
                    if tch:
                        await tch.send(f"**{message.author.display_name}** (MP) : {reply_content}")
            except Exception as e:
                await message.channel.send(f"❌ Erreur : `{e}`")
            return

        if user_id not in tickets or tickets[user_id].get("closed"):
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, manage_channels=True, read_message_history=True
                ),
            }
            for oid in get_owners() + get_ownerplus() + get_guild_owners(guild.id):
                member = guild.get_member(oid)
                if member:
                    overwrites[member] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=True, read_message_history=True
                    )
            staff_id = config.get("STAFF_ROLE_ID")
            if staff_id:
                staff_role = guild.get_role(int(staff_id))
                if staff_role:
                    overwrites[staff_role] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=True, read_message_history=True
                    )

            topic_raw = re.sub(r"[^a-z0-9\- ]", "", message.content.lower())[:24].strip().replace(" ", "-") or "demande"
            channel_name = f"ticket-{topic_raw}"[:90]

            ticket_channel = None
            last_err = None
            attempts = [
                dict(name=channel_name, overwrites=overwrites, category=category, topic=f"Ticket {message.author.id}"),
                dict(name=channel_name, overwrites=overwrites, topic=f"Ticket {message.author.id}"),
                dict(name=channel_name, category=category),
                dict(name=channel_name),
            ]
            for kwargs in attempts:
                try:
                    ticket_channel = await guild.create_text_channel(**kwargs)
                    break
                except Exception as e:
                    last_err = e
                    continue
            if ticket_channel is None:
                await message.channel.send(
                    f"Impossible de créer le salon sur **{guild.name}**.\n"
                    f"Erreur : `{last_err}`\n"
                    "Donne au bot : Gérer les salons + Voir les salons, puis `+setup`."
                )
                return

            new_tid = gen_ticket_id(tickets)
            tickets[user_id] = {
                "ticket_id": new_tid,
                "user_id": message.author.id,
                "username": str(message.author),
                "channel_id": ticket_channel.id,
                "guild_id": guild.id,
                "claimed_by": None,
                "staff": [],
                "created_at": discord.utils.utcnow().isoformat(),
                "closed": False,
                "messages": [{
                    "content": f"**{message.author.display_name}** : {message.content}",
                    "timestamp": discord.utils.utcnow().isoformat(),
                }],
            }
            save_tickets(tickets, guild.id)
            try:
                await ticket_channel.edit(name=f"ticket-{new_tid.lower()}"[:90])
            except Exception:
                pass

            info = discord.Embed(title=f"🎫 Ticket `{new_tid}`", color=0x57F287, timestamp=discord.utils.utcnow())
            info.set_thumbnail(url=message.author.display_avatar.url)
            info.add_field(name="ID", value=f"`{new_tid}`", inline=True)
            info.add_field(name="Utilisateur", value=f"{message.author.mention}\n`{message.author.id}`", inline=True)
            info.add_field(name="Compte créé", value=discord.utils.format_dt(message.author.created_at, "R"), inline=True)
            info.add_field(name="Serveur", value=guild.name, inline=True)
            info.add_field(name="Message", value=message.content[:1000] or "*vide*", inline=False)
            info.set_footer(text=f"Claim / Fermer • +close {new_tid} • +reopen {new_tid}")

            await ticket_channel.send(embed=info, view=TicketView(user_id))
            bot.add_view(TicketView(user_id))
            await ticket_channel.send(f"**{message.author.display_name}** : {message.content}")
            print(f"[TICKET] {new_tid} salon={ticket_channel.id} guild={guild.name}")
            await message.channel.send(
                f"Merci pour votre message , un(e) membre du staff reviendras vers vous très vite\n"
                f"ID du ticket : **`{new_tid}`**"
            )
        else:
            channel_id = tickets[user_id].get("channel_id")
            ticket_channel = bot.get_channel(channel_id) if channel_id else None
            if ticket_channel is None and channel_id:
                try:
                    ticket_channel = await bot.fetch_channel(int(channel_id))
                except Exception:
                    ticket_channel = None
            if ticket_channel is None:
                tickets[user_id]["closed"] = True
                save_tickets(tickets, guild.id)
                await message.channel.send("Ancien ticket introuvable. Renvoie un message pour en ouvrir un nouveau.")
                return
            await ticket_channel.send(f"**{message.author.display_name}** : {message.content}")
            tickets[user_id].setdefault("messages", []).append({
                "content": f"**{message.author.display_name}** : {message.content}",
                "timestamp": discord.utils.utcnow().isoformat(),
            })
            save_tickets(tickets, guild.id)
        return

    # ========== Réponse staff dans le salon ticket ==========
    if message.guild:
        set_guild(message.guild.id)
        tickets = get_tickets(message.guild.id)
        # Les commandes (+close, +reopen, etc.) doivent TOUJOURS passer
        is_cmd = message.content.startswith("+") or message.content.startswith(str(bot.command_prefix))
        for tid, data in tickets.items():
            if data.get("closed"):
                continue
            if data.get("channel_id") == message.channel.id:
                if is_cmd:
                    break  # laisse process_commands gérer +close / +add / etc.

                claimed_by = data.get("claimed_by")
                staff_list = [int(x) for x in (data.get("staff") or [])]
                try:
                    claimed_by_i = int(claimed_by) if claimed_by else None
                except Exception:
                    claimed_by_i = claimed_by

                # Owners toujours autorisés ; si claim → claimer/staff seulement
                if claimed_by_i and not is_owner(message.author.id):
                    if message.author.id not in staff_list and message.author.id != claimed_by_i:
                        return

                try:
                    user = await bot.fetch_user(int(tid))
                    await user.send(f"**{message.author.display_name}** : {message.content}")
                    tickets[tid].setdefault("messages", []).append({
                        "content": f"**{message.author.display_name}** : {message.content}",
                        "timestamp": discord.utils.utcnow().isoformat()
                    })
                    save_tickets(tickets, message.guild.id)
                except Exception:
                    await message.channel.send("❌ Impossible d'envoyer le MP à l'utilisateur.", delete_after=5)
                return

    if message.guild and not message.content.startswith("+"):
        await grant_xp(message)
        set_guild(message.guild.id)
        for ar in db_auto_reacts(message.guild.id, message.channel.id):
            try:
                await message.add_reaction(ar["emoji"])
            except Exception:
                pass

    if message.guild and message.content.startswith("+") and not is_owner(message.author.id, message.guild.id):
        name = message.content[1:].split()[0].lower()
        for cc in db_custom_cmds(message.guild.id):
            if cc["enabled"] and cc["name"] == name:
                await message.channel.send(cc["response"])
                return

    if message.guild and message.content.startswith("+"):
        name = message.content[1:].split()[0].lower()
        if name not in [c.name for c in bot.commands] and name not in [a for c in bot.commands for a in (c.aliases or [])]:
            for cc in db_custom_cmds(message.guild.id):
                if cc["enabled"] and cc["name"] == name:
                    await message.channel.send(cc["response"])
                    return

    await bot.process_commands(message)

def reset_guild_config(guild_id: Optional[int], keep_owners: bool = True) -> dict:
    cfg = get_config(guild_id) if guild_id else load_json(CONFIG_FILE, DEFAULT_CONFIG.copy())
    owners = list(cfg.get("GUILD_OWNERS") or []) if keep_owners else []
    joined = cfg.get("BOT_JOINED_AT")
    fresh = DEFAULT_CONFIG.copy()
    fresh["GUILD_OWNERS"] = owners
    fresh["BOT_JOINED_AT"] = joined
    if guild_id:
        save_config(fresh, guild_id)
    else:
        save_json(CONFIG_FILE, fresh)
    return fresh

@bot.command(name="resetsetup", aliases=["setupreset"])
async def resetsetup_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    if not ctx.guild:
        await ctx.send("Utilise cette commande sur un serveur.")
        return
    set_guild(ctx.guild.id)
    reset_guild_config(ctx.guild.id, keep_owners=True)
    await ctx.send("✅ Configuration `+setup` de **ce serveur** réinitialisée.")

@bot.command(name="resetall", aliases=["resetglobal", "resetconfigs"])
async def resetall_cmd(ctx: commands.Context):
    """Reset la config du bot sur TOUS les serveurs où il est présent."""
    if not await owner_check(ctx):
        return
    if BOT_OWNER_ID and ctx.author.id != BOT_OWNER_ID:
        await ctx.send("Réservé au **Propriétaire** (`BOT_OWNER_ID`).")
        return

    n = len(bot.guilds)
    emb = discord.Embed(
        title="Reset global des configurations",
        description=(
            f"Tu vas réinitialiser la config **`+setup`** sur **{n} serveur(s)**.\n\n"
            "• Logs, tickets, anti-lien, anti-raid, welcome, recruit, etc.\n"
            "• Les **owners** globaux / `BOT_OWNER_ID` sont **conservés**\n"
            "• Blacklist, XP, notes : **non** touchés\n\n"
            "**Cette action est irréversible.**"
        ),
        color=0xED4245,
    )

    class ConfirmResetAll(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)

        async def interaction_check(self, inter: discord.Interaction) -> bool:
            if inter.user.id != ctx.author.id:
                await inter.response.send_message("Seul l’auteur de la commande peut confirmer.", ephemeral=True)
                return False
            return True

        @discord.ui.button(label="Tout réinitialiser", style=discord.ButtonStyle.danger, emoji="🗑️")
        async def confirm(self, inter: discord.Interaction, button: discord.ui.Button):
            await inter.response.defer()
            reset_guild_config(None, keep_owners=True)
            save_json(CONFIG_FILE, DEFAULT_CONFIG.copy())
            count = 0
            names = []
            for g in list(bot.guilds):
                try:
                    reset_guild_config(g.id, keep_owners=True)
                    count += 1
                    names.append(g.name)
                except Exception as e:
                    record_error("config", f"resetall {g.id}", str(e))
            # dossiers data/guilds/* déjà présents
            guilds_root = os.path.join(DATA_DIR, "guilds")
            if os.path.isdir(guilds_root):
                for name in os.listdir(guilds_root):
                    if name.isdigit():
                        try:
                            reset_guild_config(int(name), keep_owners=True)
                        except Exception:
                            pass
            emb2 = discord.Embed(
                title="Reset global terminé",
                description=f"**{count}** serveur(s) réinitialisé(s).\n" + ("\n".join(f"• {n}" for n in names[:25]) or "*aucun*"),
                color=0x57F287,
            )
            await inter.followup.send(embed=emb2)
            await send_log(discord.Embed(
                title="Resetall",
                description=f"Par {ctx.author.mention} — {count} serveurs",
                color=0xED4245,
                timestamp=discord.utils.utcnow(),
            ))
            self.stop()

        @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
        async def cancel(self, inter: discord.Interaction, button: discord.ui.Button):
            await inter.response.edit_message(content="Annulé.", embed=None, view=None)
            self.stop()

    await ctx.send(embed=emb, view=ConfirmResetAll())

@bot.command(name="setup")
async def setup_cmd(ctx: commands.Context, setting: str = None, value: str = None):
    if not await owner_check(ctx):
        return
    if ctx.guild:
        set_guild(ctx.guild.id)
    config = get_config(ctx.guild.id if ctx.guild else None)
    if ctx.guild:
        legacy = load_json(CONFIG_FILE, {})
        changed = False
        for k, v in legacy.items():
            if v in (None, [], "", False):
                continue
            if config.get(k) in (None, [], ""):
                config[k] = v
                changed = True
        if changed:
            save_config(config, ctx.guild.id)

    if setting is None:
        gid = ctx.guild.id if ctx.guild else None
        await ctx.send(embed=setup_embed(gid), view=SetupView(ctx.author.id, gid))
        return

    setting = setting.lower()

    if setting in ("anti-timeout", "antitmeout", "antitimo"):
        config["ANTI_TIMEOUT"] = not config.get("ANTI_TIMEOUT")
        save_config(config, ctx.guild.id if ctx.guild else None)
        await ctx.send(f"Anti-timeout : **{'ON' if config['ANTI_TIMEOUT'] else 'OFF'}**")
        return
    if setting in ("anti-bot", "antibot"):
        config["ANTI_BOT"] = not config.get("ANTI_BOT")
        save_config(config, ctx.guild.id if ctx.guild else None)
        await ctx.send(f"Anti-bot : **{'ON' if config['ANTI_BOT'] else 'OFF'}**")
        return
    if setting in ("anti-dm", "antidm"):
        config["ANTI_DM"] = not config.get("ANTI_DM")
        save_config(config, ctx.guild.id if ctx.guild else None)
        await ctx.send(f"Anti-DM : **{'ON' if config['ANTI_DM'] else 'OFF'}** (le bot n'envoie plus de MP hors tickets)")
        return
    if setting in ["reset", "clear", "wipe"]:
        keep_owners = list(config.get("GUILD_OWNERS") or [])
        joined = config.get("BOT_JOINED_AT")
        config = DEFAULT_CONFIG.copy()
        config["GUILD_OWNERS"] = keep_owners
        config["BOT_JOINED_AT"] = joined
        save_config(config, ctx.guild.id if ctx.guild else None)
        await ctx.send("✅ Configuration `+setup` de **ce serveur** réinitialisée.")
        return

    if setting in ["logs", "log"]:
        if ctx.message.channel_mentions:
            channel = ctx.message.channel_mentions[0]
            config["LOG_CHANNEL_ID"] = channel.id
            save_config(config)
            await ctx.send(f"✅ Salon de logs défini : {channel.mention}")
        else:
            await ctx.send("❌ Mentionne un salon : `+setup logs #salon`")

    elif setting in ["staff", "staffrole"]:
        role = ctx.message.role_mentions[0] if ctx.message.role_mentions else None
        if role is None:
            await ctx.send("❌ `+setup staff @role` — seuls ce rôle + les owners voient les tickets.")
            return
        config["STAFF_ROLE_ID"] = role.id
        save_config(config)
        await ctx.send(f"✅ Rôle staff tickets : {role.mention}")

    elif setting in ["ticketlog", "ticketlogs"]:
        if ctx.message.channel_mentions:
            channel = ctx.message.channel_mentions[0]
            config["TICKET_LOG_CHANNEL_ID"] = channel.id
            save_config(config)
            await ctx.send(f"✅ Salon de logs tickets défini : {channel.mention}")
        else:
            await ctx.send("❌ Mentionne un salon : `+setup ticketlog #salon`")

    elif setting in ["category", "cat", "categorie"]:
        if value and value.isdigit():
            config["TICKET_CATEGORY_ID"] = int(value)
            save_config(config)
            await ctx.send(f"✅ Catégorie tickets définie : `{value}`")
        elif ctx.message.channel_mentions:
            channel = ctx.message.channel_mentions[0]
            if channel.category:
                config["TICKET_CATEGORY_ID"] = channel.category.id
                save_config(config)
                await ctx.send(f"✅ Catégorie définie : **{channel.category.name}** (`{channel.category.id}`)")
            else:
                await ctx.send("❌ Ce salon n'a pas de catégorie.")
        else:
            await ctx.send("❌ Utilise : `+setup category <ID>` ou `+setup category #salon`")

    elif setting == "autorole":
        role = ctx.message.role_mentions[0] if ctx.message.role_mentions else None
        rid = extract_id(value or "")
        if role:
            config["AUTOROLE_ID"] = role.id
        elif rid:
            config["AUTOROLE_ID"] = rid
        else:
            await ctx.send("❌ Utilise `+setup autorole @role`")
            return
        save_config(config)
        await ctx.send(f"✅ Autorole défini : `{config['AUTOROLE_ID']}`")

    elif setting == "antilink":
        config["ANTILINK"] = (value or "").lower() in ["on", "true", "1", "oui"]
        save_config(config)
        await ctx.send(f"✅ Anti-link : **{'activé' if config['ANTILINK'] else 'désactivé'}**")

    elif setting == "antiraid":
        config["ANTIRAID"] = (value or "").lower() in ["on", "true", "1", "oui"]
        save_config(config)
        await ctx.send(f"✅ Anti-raid : **{'activé' if config['ANTIRAID'] else 'désactivé'}**")

    elif setting == "antiraidlimit" and value and value.isdigit():
        config["ANTIRAID_JOINS"] = int(value)
        save_config(config)
        await ctx.send(f"✅ Seuil anti-raid : {value} joins")

    elif setting == "antiraidtime" and value and value.isdigit():
        config["ANTIRAID_SECONDS"] = int(value)
        save_config(config)
        await ctx.send(f"✅ Fenêtre anti-raid : {value}s")

    elif setting == "antinew":
        config["ANTI_NEW_ACCOUNT"] = (value or "").lower() in ["on", "true", "1", "oui"]
        save_config(config)
        await ctx.send(f"✅ Anti nouveau compte : **{'activé' if config['ANTI_NEW_ACCOUNT'] else 'désactivé'}**")

    elif setting == "antinewdays" and value and value.isdigit():
        config["ANTI_NEW_ACCOUNT_DAYS"] = int(value)
        save_config(config)
        await ctx.send(f"✅ Âge minimum du compte : {value} jours")

    elif setting == "antimention":
        roles = list(config.get("ANTI_MENTION_ROLES") or [])
        if ctx.message.role_mentions:
            for r in ctx.message.role_mentions:
                if r.id not in roles:
                    roles.append(r.id)
        elif value and value.isdigit():
            if int(value) not in roles:
                roles.append(int(value))
        else:
            await ctx.send("❌ Utilise `+setup antimention @role`")
            return
        config["ANTI_MENTION_ROLES"] = roles
        save_config(config)
        await ctx.send("✅ Rôle(s) protégé(s) ajouté(s).")

    elif setting == "antimentionremove":
        roles = list(config.get("ANTI_MENTION_ROLES") or [])
        rid = ctx.message.role_mentions[0].id if ctx.message.role_mentions else extract_id(value or "")
        if rid and rid in roles:
            roles.remove(rid)
            config["ANTI_MENTION_ROLES"] = roles
            save_config(config)
            await ctx.send("✅ Rôle retiré de l'anti-mention.")
        else:
            await ctx.send("❌ Rôle introuvable dans la liste.")
    else:
        await ctx.send("❌ Option inconnue. Tape `+setup` pour voir la liste.")

@bot.command(name="roleperms", aliases=["roleperm", "perms"])
async def roleperms_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    embed = discord.Embed(
        title="Gestion des permissions de rôles",
        description="1. Choisis un rôle\n2. Choisis une permission pour l’activer ou la désactiver",
        color=0x2B2D31
    )
    await ctx.send(embed=embed, view=RolePermsView(ctx.author.id))

class LinkDomainModal(discord.ui.Modal, title="Ajouter un domaine"):
    domain = discord.ui.TextInput(label="Domaine", placeholder="youtube.com", required=True, max_length=80)

    async def on_submit(self, interaction: discord.Interaction):
        domain = self.domain.value.lower().replace("https://", "").replace("http://", "").split("/")[0]
        config = get_config()
        allowed = list(config.get("ALLOWED_LINKS") or [])
        if domain not in allowed:
            allowed.append(domain)
            config["ALLOWED_LINKS"] = allowed
            save_config(config)
        await interaction.response.send_message(f"✅ Domaine autorisé : `{domain}`", ephemeral=True)


class RemoveLinkModal(discord.ui.Modal, title="Retirer un domaine"):
    domain = discord.ui.TextInput(label="Domaine", placeholder="youtube.com", required=True, max_length=80)

    async def on_submit(self, interaction: discord.Interaction):
        domain = self.domain.value.lower().replace("https://", "").replace("http://", "").split("/")[0]
        config = get_config()
        config["ALLOWED_LINKS"] = [d for d in (config.get("ALLOWED_LINKS") or []) if d != domain]
        save_config(config)
        await interaction.response.send_message(f"✅ Domaine retiré : `{domain}`", ephemeral=True)


class LinksView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=180)
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return is_owner(interaction.user.id)

    @discord.ui.button(label="Ajouter un domaine", style=discord.ButtonStyle.success)
    async def add_dom(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LinkDomainModal())

    @discord.ui.button(label="Retirer un domaine", style=discord.ButtonStyle.danger)
    async def del_dom(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RemoveLinkModal())

    @discord.ui.select(
        placeholder="Mode anti-lien",
        options=[
            discord.SelectOption(label="Timeout", value="timeout", description="Supprime + timeout"),
            discord.SelectOption(label="Delete", value="delete", description="Supprime seulement"),
            discord.SelectOption(label="Strip", value="strip", description="Remplace le lien par [lien bloqué]"),
        ]
    )
    async def mode(self, interaction: discord.Interaction, select: discord.ui.Select):
        config = get_config()
        config["ANTILINK_MODE"] = select.values[0]
        save_config(config)
        await interaction.response.send_message(f"✅ Mode : `{select.values[0]}`", ephemeral=True)

    @discord.ui.button(label="Anti-lien ON/OFF", style=discord.ButtonStyle.secondary)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_config()
        config["ANTILINK"] = not config.get("ANTILINK")
        save_config(config)
        await interaction.response.send_message(f"Anti-lien : **{'ON' if config['ANTILINK'] else 'OFF'}**", ephemeral=True)


def links_embed():
    c = get_config()
    allowed = c.get("ALLOWED_LINKS") or []
    embed = discord.Embed(title="Gestion des liens", color=0x2B2D31)
    embed.add_field(name="État", value="🟢 Activé" if c.get("ANTILINK") else "🔴 Désactivé", inline=True)
    embed.add_field(name="Mode", value=f"`{c.get('ANTILINK_MODE')}`", inline=True)
    embed.add_field(name="Timeout", value=f"{c.get('ANTILINK_TIMEOUT_MINUTES')} min", inline=True)
    embed.add_field(name="Domaines autorisés", value="\n".join(f"• `{d}`" for d in allowed) or "*aucun*", inline=False)
    return embed


@bot.command(name="links")
async def links_menu_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    await ctx.send(embed=links_embed(), view=LinksView(ctx.author.id))


@bot.command(name="allowlink")
async def allowlink_cmd(ctx: commands.Context, domain: str = None):
    if not await owner_check(ctx):
        return
    config = get_config()
    allowed = list(config.get("ALLOWED_LINKS") or [])
    if not domain:
        await ctx.send(embed=links_embed(), view=LinksView(ctx.author.id))
        return
    domain = domain.lower().replace("https://", "").replace("http://", "").split("/")[0]
    if domain not in allowed:
        allowed.append(domain)
        config["ALLOWED_LINKS"] = allowed
        save_config(config)
    await ctx.send(f"✅ Domaine autorisé : `{domain}`")

@bot.command(name="denylink")
async def denylink_cmd(ctx: commands.Context, domain: str = None):
    if not await owner_check(ctx):
        return
    if not domain:
        await ctx.send("❌ `+denylink youtube.com`")
        return
    config = get_config()
    domain = domain.lower().replace("https://", "").replace("http://", "").split("/")[0]
    allowed = [d for d in (config.get("ALLOWED_LINKS") or []) if d != domain]
    config["ALLOWED_LINKS"] = allowed
    save_config(config)
    await ctx.send(f"✅ Domaine retiré : `{domain}`")

@bot.command(name="linkmode")
async def linkmode_cmd(ctx: commands.Context, mode: str = None):
    if not await owner_check(ctx):
        return
    if mode not in ["timeout", "delete", "strip"]:
        await ctx.send("❌ Modes : `timeout` · `delete` · `strip`")
        return
    config = get_config()
    config["ANTILINK_MODE"] = mode
    save_config(config)
    await ctx.send(f"✅ Mode anti-lien : `{mode}`")

@bot.command(name="debug")
async def debug_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    status = await ctx.send("Diagnostic des commandes…")
    ok, bad = [], []
    for cmd in sorted(bot.commands, key=lambda c: c.name):
        try:
            if not cmd.name or not cmd.callback:
                bad.append(f"`+{cmd.name}` callback manquant")
            else:
                ok.append(cmd.name)
        except Exception as e:
            bad.append(f"`+{cmd.name}` {e}")
    embed = discord.Embed(title="Diagnostic", color=0x57F287 if not bad else 0xFEE75C)
    embed.add_field(name="Ping", value=f"{round(bot.latency*1000)} ms", inline=True)
    embed.add_field(name="Opérationnelles", value=str(len(ok)), inline=True)
    embed.add_field(name="Problèmes", value=str(len(bad)), inline=True)
    embed.add_field(name="OK", value=", ".join(f"`+{n}`" for n in ok[:40]) + ("…" if len(ok) > 40 else ""), inline=False)
    if bad:
        embed.add_field(name="KO", value="\n".join(bad[:15]), inline=False)
    await status.edit(content=None, embed=embed)

UPDATE_STATE_FILE = os.path.join(DATA_DIR, "update_state.json")
UPDATE_HTTP_HEADERS = {
    "User-Agent": f"CoreBot/{BOT_VERSION}",
    "Accept": "text/plain,application/octet-stream,*/*",
}

def parse_version(v: str) -> tuple:
    parts = []
    for p in re.findall(r"\d+", str(v or "0").lstrip("\ufeff")):
        parts.append(int(p))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:4])

def load_update_state() -> dict:
    return load_json(UPDATE_STATE_FILE, {"notified": [], "pending": None, "last_ok": None})

def save_update_state(data: dict):
    save_json(UPDATE_STATE_FILE, data)

def mark_version_notified(remote: str):
    st = load_update_state()
    notified = list(st.get("notified") or [])
    if remote not in notified:
        notified.append(remote)
    st["notified"] = notified[-20:]
    save_update_state(st)

def is_version_notified(remote: str) -> bool:
    st = load_update_state()
    return remote in (st.get("notified") or [])

async def fetch_remote_version() -> Optional[str]:
    if not UPDATE_VERSION_URL:
        return None
    try:
        # anti-cache GitHub
        url = UPDATE_VERSION_URL
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}_={int(time.time())}"
        async with aiohttp.ClientSession(headers=UPDATE_HTTP_HEADERS) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    record_error("update", "fetch_version", f"HTTP {resp.status}")
                    return None
                text = (await resp.text()).lstrip("\ufeff").strip()
                if not text:
                    return None
                # première ligne non vide, sans espaces parasites
                for line in text.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        return line
                return None
    except Exception as e:
        record_error("update", "fetch_version", str(e))
        return None

def normalize_code_bytes(data: bytes) -> bytes:
    """Ignore CRLF/LF et BOM pour comparer le vrai contenu."""
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    text = data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    return text.encode("utf-8")

def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(normalize_code_bytes(data)).hexdigest()

def local_bot_hash() -> Optional[str]:
    try:
        path = get_bot_target_path()
        with open(path, "rb") as f:
            return hash_bytes(f.read())
    except Exception:
        return None

async def fetch_remote_bot_hash() -> tuple:
    """Retourne (hash, size) du bot.py distant ou (None, 0)."""
    if not UPDATE_CODE_URL:
        return None, 0
    try:
        url = UPDATE_CODE_URL
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}_={int(time.time())}"
        async with aiohttp.ClientSession(headers=UPDATE_HTTP_HEADERS) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    return None, 0
                data = await resp.read()
        if len(data) < 500:
            return None, 0
        return hash_bytes(data), len(data)
    except Exception as e:
        record_error("update", "fetch_hash", str(e))
        return None, 0

async def code_changed_on_github() -> tuple:
    """True si le bot.py GitHub diffère du local (hors fins de ligne)."""
    local_h = local_bot_hash()
    remote_h, _ = await fetch_remote_bot_hash()
    if not local_h or not remote_h:
        return False, local_h, remote_h
    return local_h != remote_h, local_h, remote_h

def _extract_symbols(text: str) -> set:
    """Commandes et fonctions définies dans le code."""
    names = set()
    for m in re.finditer(r'@bot\.(?:command|tree\.command|hybrid_command)\s*\(\s*name\s*=\s*["\']([^"\']+)["\']', text):
        names.add(f"+{m.group(1)}")
    for m in re.finditer(r'@bot\.tree\.command\s*\(\s*name\s*=\s*["\']([^"\']+)["\']', text):
        names.add(f"/{m.group(1)}")
    for m in re.finditer(r'^async def ([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', text, re.M):
        n = m.group(1)
        if not n.startswith("_") and not n.endswith("_cmd"):
            continue
        if n.endswith("_cmd"):
            names.add(n)
    for m in re.finditer(r'^def ([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', text, re.M):
        n = m.group(1)
        if n.startswith("get_") or n.startswith("save_") or n.startswith("load_"):
            names.add(n)
    return names

def analyze_code_changes(local_text: str, remote_text: str) -> dict:
    """
    Résumé : ajouts / retraits / corrections entre local et distant.
    """
    import difflib
    local_lines = local_text.splitlines()
    remote_lines = remote_text.splitlines()
    added_lines = 0
    removed_lines = 0
    changed_hunks = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, local_lines, remote_lines).get_opcodes():
        if tag == "insert":
            added_lines += (j2 - j1)
        elif tag == "delete":
            removed_lines += (i2 - i1)
        elif tag == "replace":
            changed_hunks += 1
            added_lines += (j2 - j1)
            removed_lines += (i2 - i1)

    local_sym = _extract_symbols(local_text)
    remote_sym = _extract_symbols(remote_text)
    ajouts = sorted(remote_sym - local_sym)
    retraits = sorted(local_sym - remote_sym)
    # corrections = symboles présents des deux côtés mais lignes modifiées autour — approx via replace count
    corrections = []
    if changed_hunks:
        corrections.append(f"{changed_hunks} zone(s) de code modifiée(s)")
    # BOT_VERSION change
    lv = re.search(r'BOT_VERSION\s*=\s*["\']([^"\']+)["\']', local_text)
    rv = re.search(r'BOT_VERSION\s*=\s*["\']([^"\']+)["\']', remote_text)
    if lv and rv and lv.group(1) != rv.group(1):
        corrections.insert(0, f"Version `{lv.group(1)}` → `{rv.group(1)}`")

    return {
        "ajouts": ajouts[:25],
        "retraits": retraits[:25],
        "corrections": corrections[:15],
        "lignes_ajoutees": added_lines,
        "lignes_retirees": removed_lines,
        "hunks": changed_hunks,
    }

async def fetch_remote_bot_text() -> Optional[str]:
    if not UPDATE_CODE_URL:
        return None
    try:
        url = UPDATE_CODE_URL
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}_={int(time.time())}"
        async with aiohttp.ClientSession(headers=UPDATE_HTTP_HEADERS) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()
        return data.decode("utf-8", errors="replace")
    except Exception as e:
        record_error("update", "fetch_text", str(e))
        return None

def format_changelog(diff: dict) -> str:
    parts = []
    aj = diff.get("ajouts") or []
    re = diff.get("retraits") or []
    co = diff.get("corrections") or []
    if aj:
        parts.append("**➕ Ajouts**\n" + "\n".join(f"• `{x}`" for x in aj[:15]))
        if len(aj) > 15:
            parts[-1] += f"\n• … +{len(aj)-15}"
    else:
        parts.append("**➕ Ajouts**\n• *aucun*")
    if re:
        parts.append("**➖ Retraits**\n" + "\n".join(f"• `{x}`" for x in re[:15]))
        if len(re) > 15:
            parts[-1] += f"\n• … +{len(re)-15}"
    else:
        parts.append("**➖ Retraits**\n• *aucun*")
    if co:
        parts.append("**🔧 Corrections**\n" + "\n".join(f"• {x}" for x in co[:12]))
    else:
        la, lr = diff.get("lignes_ajoutees", 0), diff.get("lignes_retirees", 0)
        if la or lr:
            parts.append(f"**🔧 Corrections**\n• ~{la} lignes ajoutées / ~{lr} retirées")
        else:
            parts.append("**🔧 Corrections**\n• *aucune*")
    return "\n\n".join(parts)[:3800]

def get_bot_target_path() -> str:
    target = BOT_FILE
    if not os.path.isfile(target):
        target = os.path.abspath("bot.py")
    return target

def extract_version_from_bytes(data: bytes) -> Optional[str]:
    """Assignation réelle en début de ligne uniquement (ignore le texte dans les messages)."""
    try:
        text = data.decode("utf-8", errors="ignore")
        m = re.search(r'(?m)^BOT_VERSION\s*=\s*["\']([^"\']+)["\']', text)
        return m.group(1).strip() if m else None
    except Exception:
        return None

def read_local_file_version() -> Optional[str]:
    try:
        with open(get_bot_target_path(), "rb") as f:
            return extract_version_from_bytes(f.read(50000))
    except Exception:
        return None

async def download_bot_update() -> tuple:
    """Télécharge vers bot.py.new (pas d'écrasement tant que le process tourne). Retourne (ok, message, new_path, file_version)."""
    if not UPDATE_CODE_URL:
        return False, "UPDATE_CODE_URL non défini dans le .env", None, None
    try:
        async with aiohttp.ClientSession(headers=UPDATE_HTTP_HEADERS) as session:
            async with session.get(UPDATE_CODE_URL, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status == 404:
                    return False, "Fichier introuvable (404) — vérifie UPDATE_CODE_URL", None, None
                if resp.status == 403:
                    return False, "Accès refusé (403)", None, None
                if resp.status != 200:
                    return False, f"HTTP {resp.status} lors du téléchargement", None, None
                data = await resp.read()
        if len(data) < 500:
            return False, f"Fichier trop petit ({len(data)} octets)", None, None
        head = data[:12000].lower()
        if b"discord" not in head and b"import" not in head:
            return False, "Contenu invalide (ne ressemble pas à un bot.py)", None, None
        file_ver = extract_version_from_bytes(data)
        target = get_bot_target_path()
        new_path = target + ".new"
        try:
            with open(new_path, "wb") as f:
                f.write(data)
        except Exception as e:
            return False, f"Impossible d'écrire {new_path}: {e}", None, None
        # backup de l'ancien
        try:
            bak = target + ".bak"
            if os.path.exists(target):
                with open(target, "rb") as src, open(bak, "wb") as dst:
                    dst.write(src.read())
        except Exception as e:
            record_error("update", "backup", str(e))
        msg = f"OK — {len(data)} octets → {new_path}"
        if file_ver:
            msg += f" (BOT_VERSION dans fichier = {file_ver})"
        else:
            msg += " (BOT_VERSION introuvable dans le fichier GitHub !)"
        return True, msg, new_path, file_ver
    except asyncio.TimeoutError:
        msg = "Délai dépassé (timeout)"
        record_error("update", "download", msg)
        return False, msg, None, None
    except aiohttp.ClientError as e:
        msg = f"Erreur réseau : {e}"
        record_error("update", "download", msg)
        return False, msg, None, None
    except Exception as e:
        msg = f"Erreur inattendue : {e}"
        record_error("update", "download", msg)
        return False, msg, None, None

async def report_update_error(channel_id: Optional[int], title: str, detail: str):
    print(f"[UPDATE] {title}: {detail}")
    record_error("update", title, detail)
    emb = discord.Embed(
        title=f"Erreur mise à jour — {title}",
        description=f"```{detail[:1500]}```",
        color=0xED4245,
        timestamp=discord.utils.utcnow(),
    )
    emb.set_footer(text=f"Version locale {BOT_VERSION}")
    if channel_id:
        try:
            ch = bot.get_channel(int(channel_id))
            if ch:
                await ch.send(embed=emb)
                return
        except Exception:
            pass
    try:
        cfg = get_config()
        log_id = cfg.get("LOG_CHANNEL_ID")
        if log_id:
            ch = bot.get_channel(int(log_id))
            if ch:
                await ch.send(embed=emb)
    except Exception:
        pass

def write_and_launch_updater(new_path: str, target: str) -> bool:
    """
    Lance un script externe qui :
    1) attend que ce process se termine
    2) remplace bot.py par bot.py.new
    3) relance python bot.py
    """
    cwd = os.path.dirname(target) or os.getcwd()
    py = sys.executable
    script_name = target if os.path.basename(sys.argv[0]).endswith(".py") else target
    # Utilise le chemin du .py cible
    bot_py = target
    if os.name == "nt":
        updater = os.path.join(cwd, "_core_updater.bat")
        # escape for bat
        content = f"""@echo off
cd /d "{cwd}"
echo [UPDATE] Attente arret du bot...
timeout /t 3 /nobreak >nul
if exist "{new_path}" (
  copy /Y "{new_path}" "{bot_py}" >nul
  del "{new_path}" >nul 2>&1
  echo [UPDATE] bot.py remplace
) else (
  echo [UPDATE] Fichier .new introuvable
)
echo [UPDATE] Relance...
"{py}" "{bot_py}"
del "%~f0"
"""
        with open(updater, "w", encoding="utf-8") as f:
            f.write(content)
        flags = 0
        if hasattr(subprocess, "CREATE_NEW_CONSOLE"):
            flags = subprocess.CREATE_NEW_CONSOLE
        subprocess.Popen(["cmd.exe", "/c", updater], cwd=cwd, creationflags=flags)
        print(f"[UPDATE] Updater bat lancé : {updater}")
        return True
    else:
        updater = os.path.join(cwd, "_core_updater.sh")
        content = f"""#!/bin/bash
cd "{cwd}"
echo "[UPDATE] Attente..."
sleep 2
if [ -f "{new_path}" ]; then
  cp -f "{new_path}" "{bot_py}"
  rm -f "{new_path}"
  echo "[UPDATE] bot.py remplacé"
fi
echo "[UPDATE] Relance..."
exec "{py}" "{bot_py}"
"""
        with open(updater, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(updater, 0o755)
        subprocess.Popen(["/bin/bash", updater], cwd=cwd, start_new_session=True)
        print(f"[UPDATE] Updater sh lancé : {updater}")
        return True

def restart_bot_process():
    args = [sys.executable] + sys.argv
    print(f"[UPDATE] Restart simple: {args}")
    if os.name == "nt":
        subprocess.Popen(args, cwd=os.getcwd(), close_fds=True)
        os._exit(0)
    try:
        os.execv(sys.executable, args)
    except Exception:
        subprocess.Popen(args, cwd=os.getcwd())
        os._exit(0)

async def log_github_transfer(
    *,
    remote: Optional[str],
    file_ver: Optional[str],
    detail: str,
    reason: str,
    new_path: Optional[str] = None,
    success: bool = True,
    error: str = None,
):
    """Log salon + webhooks nommés github / update / logs pour les transferts GitHub."""
    emb = discord.Embed(
        title="Transfert GitHub" if success else "Échec transfert GitHub",
        color=0x57F287 if success else 0xED4245,
        timestamp=discord.utils.utcnow(),
    )
    emb.add_field(name="Version locale", value=f"`{BOT_VERSION}`", inline=True)
    emb.add_field(name="Version distante", value=f"`{remote or '—'}`", inline=True)
    emb.add_field(name="BOT_VERSION fichier", value=f"`{file_ver or '—'}`", inline=True)
    emb.add_field(name="Raison", value=f"`{reason}`", inline=True)
    emb.add_field(name="Détail", value=f"```{(detail or error or '')[:800]}```", inline=False)
    if new_path:
        emb.add_field(name="Fichier", value=f"`{new_path}`", inline=False)
    emb.set_footer(text="Core · sync GitHub → bot.py")

    # Salon logs Discord
    try:
        await send_log(emb)
    except Exception:
        pass

    # Webhooks enregistrés (+webhook) : noms ciblés ou tous si UPDATE_WEBHOOK_ALL
    hooks = load_json(WEBHOOKS_FILE, {})
    if not isinstance(hooks, dict):
        return
    names = {"github", "update", "updates", "logs", "log", "core"}
    payload = {"embeds": [emb.to_dict()]}
    async with aiohttp.ClientSession() as session:
        for name, h in hooks.items():
            if name.lower() not in names and not os.getenv("UPDATE_WEBHOOK_ALL", "").strip() in ("1", "true", "yes"):
                continue
            url = (h or {}).get("url")
            if not url:
                continue
            try:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status >= 300:
                        print(f"[UPDATE] webhook {name} HTTP {resp.status}")
            except Exception as e:
                print(f"[UPDATE] webhook {name}: {e}")

async def apply_update_and_restart(channel_id: Optional[int] = None, reason: str = "update", remote: str = None):
    print(f"[UPDATE] Application maj ({reason})…")
    ok, detail, new_path, file_ver = await download_bot_update()
    if not ok:
        await report_update_error(channel_id, "téléchargement", detail)
        await log_github_transfer(
            remote=remote, file_ver=file_ver, detail=detail, reason=reason, success=False, error=detail
        )
        return False
    print(f"[UPDATE] {detail}")
    if remote and file_ver and parse_version(file_ver) < parse_version(remote):
        warn = (
            f"Attention : version.txt = {remote} mais BOT_VERSION dans bot.py GitHub = {file_ver}. "
            f"Après maj le bot affichera encore {file_ver}. Mets BOT_VERSION = \"{remote}\" dans le bot.py GitHub."
        )
        print(f"[UPDATE] {warn}")
        await report_update_error(channel_id, "version fichier", warn)

    await log_github_transfer(
        remote=remote, file_ver=file_ver, detail=detail, reason=reason, new_path=new_path, success=True
    )

    st = load_update_state()
    st["last_ok"] = {
        "at": datetime.now().isoformat(),
        "remote": remote,
        "file_version": file_ver,
        "detail": detail,
        "reason": reason,
        "new_path": new_path,
    }
    try:
        if new_path and os.path.isfile(new_path):
            with open(new_path, "rb") as f:
                st["last_applied_hash"] = hash_bytes(f.read())
    except Exception:
        pass
    if remote:
        notified = list(st.get("notified") or [])
        if remote not in notified:
            notified.append(remote)
        st["notified"] = notified
        st["pending"] = None
    save_update_state(st)
    if channel_id:
        save_json(
            os.path.join(DATA_DIR, "restart.json"),
            {"channel_id": channel_id, "by": 0, "reason": reason, "remote": remote, "file_version": file_ver},
        )

    target = get_bot_target_path()
    try:
        write_and_launch_updater(new_path, target)
    except Exception as e:
        await report_update_error(channel_id, "updater", str(e))
        await log_github_transfer(
            remote=remote, file_ver=file_ver, detail=str(e), reason=reason, success=False, error=str(e)
        )
        return False

    print("[UPDATE] Le script d'update va remplacer bot.py puis relancer le bot dans ~3s.")
    await asyncio.sleep(0.5)
    try:
        await bot.close()
    except Exception as e:
        record_error("update", "close", str(e))
    await asyncio.sleep(0.2)
    os._exit(0)
    return True

class UpdateConfirmView(discord.ui.View):
    def __init__(self, remote: str, channel_id: Optional[int] = None):
        super().__init__(timeout=300)
        self.remote = remote
        self.channel_id = channel_id
        self._busy = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not is_owner(interaction.user.id):
            await interaction.response.send_message("Réservé aux owners.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Mettre à jour", style=discord.ButtonStyle.success, emoji="✅")
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._busy:
            await interaction.response.send_message("Mise à jour déjà en cours…", ephemeral=True)
            return
        self._busy = True
        mark_version_notified(self.remote)  # évite de re-proposer pendant le process
        await interaction.response.edit_message(
            content=(
                f"⏳ Mise à jour **`{BOT_VERSION}` → `{self.remote}`**…\n"
                "1. Téléchargement\n2. Remplacement de `bot.py`\n3. Redémarrage\n"
                "Ne relance pas le bot à la main."
            ),
            embed=None,
            view=None,
        )
        ch = self.channel_id or (interaction.channel.id if interaction.channel else None)
        ok = await apply_update_and_restart(
            channel_id=ch,
            reason=f"confirmé {BOT_VERSION}->{self.remote}",
            remote=self.remote,
        )
        if not ok:
            self._busy = False
            try:
                await interaction.followup.send(
                    "❌ Échec — regarde le message d’erreur ou `+errors`.\n"
                    "Sous Windows : ferme le terminal et relance `python bot.py` si le fichier a été téléchargé (`bot.py.bak` présent).",
                    ephemeral=True,
                )
            except Exception:
                pass

    @discord.ui.button(label="Plus tard", style=discord.ButtonStyle.secondary, emoji="⏳")
    async def later(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Ne marque pas notified → pourra redemander plus tard via +update
        await interaction.response.edit_message(
            content=f"Maj `{self.remote}` reportée. Refais `+update` quand tu veux.",
            embed=None,
            view=None,
        )

    @discord.ui.button(label="Ignorer cette version", style=discord.ButtonStyle.danger, emoji="✖️")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        mark_version_notified(self.remote)
        await interaction.response.edit_message(
            content=f"Version `{self.remote}` ignorée (plus de notif auto pour celle-ci).",
            embed=None,
            view=None,
        )

def update_embed(remote: Optional[str], changelog: Optional[dict] = None, hash_changed: bool = False) -> discord.Embed:
    disk_ver = read_local_file_version()
    emb = discord.Embed(title="Gestion des versions", color=0x5865F2, timestamp=discord.utils.utcnow())
    emb.add_field(name="Version en mémoire", value=f"`{BOT_VERSION}`", inline=True)
    emb.add_field(name="Version sur disque", value=f"`{disk_ver or '?'}`", inline=True)
    emb.add_field(name="Version distante", value=f"`{remote or 'N/A'}`", inline=True)
    emb.add_field(name="Vérif auto", value="ON" if UPDATE_ENABLED else "OFF", inline=True)
    emb.add_field(name="Auto-install", value="ON" if UPDATE_AUTO_INSTALL else "OFF", inline=True)
    emb.add_field(name="Détection hash", value="ON" if UPDATE_DETECT_HASH else "OFF", inline=True)

    newer = bool(remote and parse_version(remote) > parse_version(BOT_VERSION))
    if newer or hash_changed:
        emb.color = 0x57F287
        if newer:
            emb.description = f"**Nouvelle version disponible**\n`{BOT_VERSION}` → **`{remote}`**"
        else:
            emb.description = f"**Modifications détectées sur GitHub** (même version `{BOT_VERSION}`)"
        emb.description += "\nClique **Mettre à jour** pour télécharger et redémarrer."
    elif remote:
        emb.description = "Le bot est **à jour** (version + code)."
    else:
        emb.description = "Impossible de lire la version distante (URL / réseau)."

    if changelog:
        emb.add_field(
            name="Changements (local → GitHub)",
            value=format_changelog(changelog)[:1020] or "*aucun détail*",
            inline=False,
        )
        stats = f"+{changelog.get('lignes_ajoutees', 0)} / -{changelog.get('lignes_retirees', 0)} lignes"
        emb.set_footer(text=f"{stats} · {get_bot_target_path()}")
    else:
        emb.set_footer(text=str(get_bot_target_path()))
    return emb

async def notify_update_available(remote: str):
    if is_version_notified(remote):
        return
    if not UPDATE_CODE_URL:
        print("[UPDATE] UPDATE_CODE_URL manquant")
        await report_update_error(None, "config", "UPDATE_CODE_URL manquant dans le .env")
        mark_version_notified(remote)
        return
    emb = update_embed(remote)
    sent = False
    try:
        cfg = get_config()
        ch_id = cfg.get("LOG_CHANNEL_ID")
        if ch_id:
            ch = bot.get_channel(int(ch_id))
            if ch:
                await ch.send(embed=emb, view=UpdateConfirmView(remote, channel_id=ch.id))
                sent = True
    except Exception as e:
        record_error("update", "notify", str(e))
    if not sent:
        print(f"[UPDATE] Pas de salon logs — maj {remote} visible via +update")
    mark_version_notified(remote)
    print(f"[UPDATE] Notification maj {BOT_VERSION} -> {remote} (salon logs)")

@tasks.loop(seconds=5)
async def update_check_loop():
    """
    Scan GitHub :
    - version.txt plus récente → maj
    - OU hash du bot.py différent (modification du code) → maj
    Ne redémarre que s'il y a un vrai changement.
    """
    if not UPDATE_ENABLED:
        return
    if not UPDATE_VERSION_URL and not UPDATE_CODE_URL:
        return
    now = time.time()
    last = getattr(update_check_loop, "_last_check", 0)
    if now - last < UPDATE_INTERVAL:
        return
    update_check_loop._last_check = now

    remote = await fetch_remote_version() if UPDATE_VERSION_URL else None
    version_newer = bool(remote and parse_version(remote) > parse_version(BOT_VERSION))
    # Local en avance sur GitHub → ne pas "mettre à jour" vers une version plus vieille
    local_ahead = bool(remote and parse_version(remote) < parse_version(BOT_VERSION))

    hash_changed = False
    local_h = remote_h = None
    if UPDATE_DETECT_HASH and UPDATE_CODE_URL and not local_ahead:
        hash_changed, local_h, remote_h = await code_changed_on_github()
        st = load_update_state()
        if hash_changed and remote_h and remote_h == st.get("last_applied_hash"):
            hash_changed = False
        if hash_changed and remote_h and remote_h in (st.get("ignored_hashes") or []):
            hash_changed = False
        # Même numéro de version + hash différent seulement
        if hash_changed and remote and parse_version(remote) != parse_version(BOT_VERSION):
            # versions différentes déjà gérées par version_newer / local_ahead
            if not version_newer:
                hash_changed = False

    if not version_newer and not hash_changed:
        return

    label = remote or BOT_VERSION
    if hash_changed and not version_newer:
        label = f"{BOT_VERSION}+hash"
        print(f"[UPDATE] Code GitHub modifié (hash {str(local_h)[:8]}… → {str(remote_h)[:8]}…)")
    else:
        print(f"[UPDATE] Version distante {remote} > locale {BOT_VERSION}")

    if UPDATE_AUTO_INSTALL and UPDATE_CODE_URL:
        notify_key = remote if version_newer else f"hash:{remote_h}"
        if is_version_notified(notify_key):
            return
        mark_version_notified(notify_key)
        print(f"[UPDATE] AUTO-INSTALL ({label})")
        try:
            cfg = get_config()
            ch_id = cfg.get("LOG_CHANNEL_ID")
            if ch_id:
                ch = bot.get_channel(int(ch_id))
                if ch:
                    desc = f"`{BOT_VERSION}` → **`{remote or 'code modifié'}`**\n"
                    if hash_changed:
                        desc += f"Hash : `{str(local_h)[:10]}` → `{str(remote_h)[:10]}`\n"
                    desc += "Téléchargement et redémarrage…"
                    await ch.send(embed=discord.Embed(
                        title="Mise à jour automatique",
                        description=desc,
                        color=0x57F287,
                        timestamp=discord.utils.utcnow(),
                    ))
        except Exception:
            pass
        ok = await apply_update_and_restart(
            reason=f"auto {label}",
            remote=remote or label,
        )
        if ok and remote_h:
            st = load_update_state()
            st["last_applied_hash"] = remote_h
            save_update_state(st)
        return

    notify_key = remote if version_newer else f"hash:{remote_h}"
    if is_version_notified(notify_key):
        return
    print(f"[UPDATE] Changement détecté ({label}) — confirmation")
    await notify_update_available(remote or label)

@update_check_loop.before_loop
async def update_check_before():
    await bot.wait_until_ready()

@bot.command(name="update", aliases=["maj", "checkupdate"])
async def update_cmd(ctx: commands.Context, action: str = None):
    if not await owner_check(ctx):
        return
    action = (action or "check").lower()
    if action in ("status", "info", "check", ""):
        status = await ctx.send("Analyse des différences avec GitHub…")
        remote = await fetch_remote_version() if UPDATE_VERSION_URL else None
        changelog = None
        hash_changed = False
        if UPDATE_CODE_URL:
            try:
                local_path = get_bot_target_path()
                with open(local_path, "r", encoding="utf-8", errors="replace") as f:
                    local_text = f.read()
                remote_text = await fetch_remote_bot_text()
                if remote_text:
                    local_n = local_text.replace("\r\n", "\n").replace("\r", "\n")
                    remote_n = remote_text.replace("\r\n", "\n").replace("\r", "\n")
                    hash_changed = hash_bytes(local_n.encode("utf-8")) != hash_bytes(remote_n.encode("utf-8"))
                    # Ne pas signaler de maj si le local est plus récent que GitHub
                    if remote and parse_version(remote) < parse_version(BOT_VERSION):
                        hash_changed = False
                    changelog = analyze_code_changes(local_n, remote_n)
            except Exception as e:
                record_error("update", "changelog", str(e))
        emb = update_embed(remote, changelog=changelog, hash_changed=hash_changed)
        newer = bool(remote and parse_version(remote) > parse_version(BOT_VERSION))
        try:
            await status.delete()
        except Exception:
            pass
        if (newer or hash_changed) and UPDATE_CODE_URL:
            await ctx.send(embed=emb, view=UpdateConfirmView(remote or BOT_VERSION, channel_id=ctx.channel.id))
        else:
            await ctx.send(embed=emb)
        return
    if action in ("install", "apply", "now", "yes"):
        if not UPDATE_CODE_URL:
            await ctx.send("Configure `UPDATE_CODE_URL` dans le `.env`.")
            return
        remote = await fetch_remote_version() if UPDATE_VERSION_URL else None
        await ctx.send(f"Téléchargement et redémarrage… (`{BOT_VERSION}` → `{remote or 'GitHub'}`)")
        ok = await apply_update_and_restart(channel_id=ctx.channel.id, reason="manuel", remote=remote)
        if not ok:
            await ctx.send("Échec — vois `+errors` ou les logs.")
        return
    await ctx.send("`+update` — vérifier + changelog · `+update install` — forcer")

@bot.command(name="restart")
async def restart_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    msg = await ctx.send("```\n[    ] arrêt des tâches\n```")
    save_json(os.path.join(DATA_DIR, "restart.json"), {"channel_id": ctx.channel.id, "by": ctx.author.id})
    frames = [
        "```\n[#   ] fermeture gateway\n```",
        "```\n[##  ] sauvegarde data\n```",
        "```\n[### ] relance process\n```",
        "```\n[####] redémarrage…\n```",
    ]
    for fr in frames:
        await asyncio.sleep(0.6)
        try:
            await msg.edit(content=fr)
        except Exception:
            pass
    print(f"Restart demandé par {ctx.author}")
    try:
        await bot.close()
    except Exception:
        pass
    restart_bot_process()

class OwnerScopeView(discord.ui.View):
    def __init__(self, author_id: int, target: discord.User):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.target = target

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id

    @discord.ui.button(label="Global (tous les serveurs)", style=discord.ButtonStyle.danger)
    async def global_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        owners = get_owners()
        if self.target.id not in owners:
            owners.append(self.target.id)
            save_json(OWNERS_FILE, owners)
        await interaction.response.edit_message(content=f"{self.target.mention} est **Propriétaire global**.", view=None)

    @discord.ui.button(label="Ce serveur seulement", style=discord.ButtonStyle.primary)
    async def local_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            await interaction.response.send_message("❌ Pas de serveur.", ephemeral=True)
            return
        set_guild(interaction.guild.id)
        cfg = get_config(interaction.guild.id)
        local = [int(x) for x in (cfg.get("GUILD_OWNERS") or [])]
        if self.target.id not in local:
            local.append(self.target.id)
            cfg["GUILD_OWNERS"] = local
            save_config(cfg, interaction.guild.id)
        await interaction.response.edit_message(content=f"{self.target.mention} est propriétaire **de ce serveur uniquement**.", view=None)

@bot.command(name="owner")
async def owner_cmd(ctx: commands.Context, raw: str = None):
    if not await owner_check(ctx):
        return
    owners = get_owners()
    content = ctx.message.content.lower().strip()

    if "reset" in content:
        if ctx.author.id != BOT_OWNER_ID and BOT_OWNER_ID != 0:
            await ctx.send("❌ Seul le Propriétaire peut reset.")
            return
        save_json(OWNERS_FILE, [BOT_OWNER_ID] if BOT_OWNER_ID else [])
        await ctx.send("✅ Propriétaires globaux réinitialisés.")
        return

    target = await resolve_user(ctx, raw)
    if target is None and not ctx.message.mentions and not extract_id(ctx.message.content.replace("+owner", "", 1)):
        lines = []
        for oid in owners:
            user = bot.get_user(oid) or await bot.fetch_user(oid)
            tag = " · Propriétaire" if oid == BOT_OWNER_ID else " · global"
            lines.append(f"• {user.mention if user else oid} (`{oid}`){tag}")
        if ctx.guild:
            for oid in get_guild_owners(ctx.guild.id):
                user = bot.get_user(oid)
                lines.append(f"• {user.mention if user else oid} (`{oid}`) · ce serveur")
        embed = discord.Embed(title="Propriétaires", description="\n".join(lines) or "Aucun", color=0x5865F2)
        await ctx.send(embed=embed)
        return

    if target is None:
        await ctx.send("❌ `+owner @user`")
        return
    await ctx.send(f"Ajouter {target.mention} comme propriétaire :", view=OwnerScopeView(ctx.author.id, target))

@bot.command(name="unowner")
async def unowner_cmd(ctx: commands.Context, raw: str = None):
    if not await owner_check(ctx):
        return
    target = await resolve_user(ctx, raw)
    if target is None:
        await ctx.send("❌ `+unowner @user`")
        return
    if target.id == BOT_OWNER_ID:
        await ctx.send("❌ Impossible de retirer le Propriétaire.")
        return
    owners = [o for o in get_owners() if o != target.id]
    save_json(OWNERS_FILE, owners)
    if ctx.guild:
        cfg = get_config(ctx.guild.id)
        cfg["GUILD_OWNERS"] = [o for o in (cfg.get("GUILD_OWNERS") or []) if int(o) != target.id]
        save_config(cfg, ctx.guild.id)
    await ctx.send(f"✅ {target.mention} retiré des propriétaires.")

@bot.command(name="ownerplus")
async def ownerplus_cmd(ctx: commands.Context, raw: str = None):
    if not await owner_check(ctx):
        return
    if raw is None:
        ids = get_ownerplus()
        await ctx.send("Owner+ : " + (", ".join(f"<@{i}>" for i in ids) if ids else "aucun"))
        return
    target = await resolve_user(ctx, raw)
    if target is None:
        await ctx.send("❌ `+ownerplus @user`")
        return
    ids = get_ownerplus()
    if target.id in ids:
        ids = [i for i in ids if i != target.id]
        save_json(OWNERPLUS_FILE, ids)
        log_ownerplus(f"REMOVE {target.id} by {ctx.author.id}")
        await ctx.send(f"✅ {target.mention} retiré des owner+")
    else:
        ids.append(target.id)
        save_json(OWNERPLUS_FILE, ids)
        log_ownerplus(f"ADD {target.id} by {ctx.author.id}")
        await ctx.send(f"✅ {target.mention} ajouté owner+ (log : data/logs/ownerplus.log)")

@bot.command(name="bl")
async def bl_cmd(ctx: commands.Context, *args):
    if not await owner_check(ctx):
        return
    content = ctx.message.content.lower()
    if "clear" in content:
        save_json(BLACKLIST_FILE, [])
        await ctx.send("✅ Blacklist vidée.")
        return

    blacklist = get_blacklist()
    ids_to_add = [m.id for m in ctx.message.mentions]
    uid = extract_id(ctx.message.content)
    if uid and uid not in ids_to_add:
        ids_to_add.append(uid)
    if ids_to_add:
        added = []
        for mid in ids_to_add:
            if is_owner(mid):
                await ctx.send(f"❌ Impossible de blacklist un owner (`{mid}`).")
                continue
            if mid not in blacklist:
                blacklist.append(mid)
                added.append(f"<@{mid}>")
        save_json(BLACKLIST_FILE, blacklist)
        if not added:
            await ctx.send("❌ Déjà blacklisté.")
            return
        await ctx.send(
            f"✅ Blacklist globale : {', '.join(added)}\n"
            f"Bloqué sur **tous** les serveurs où le bot est présent (commandes / interactions)."
        )
        await send_log(discord.Embed(
            title="Blacklist globale",
            description=f"{', '.join(added)}\nPar {ctx.author.mention}\nActif sur {len(bot.guilds)} serveur(s) — sans ban.",
            color=0xED4245,
            timestamp=discord.utils.utcnow(),
        ))
        return

    if not blacklist:
        await ctx.send("Blacklist vide.")
        return
    lines = []
    for uid in blacklist:
        user = bot.get_user(uid) or await bot.fetch_user(uid)
        lines.append(f"• {user.mention if user else uid} (`{uid}`)")
    embed = discord.Embed(title="🚫 Blacklist", description="\n".join(lines), color=0xED4245)
    await ctx.send(embed=embed)

@bot.command(name="unbl")
async def unbl_cmd(ctx: commands.Context, raw: str = None):
    if not await owner_check(ctx):
        return
    target = await resolve_user(ctx, raw)
    if target is None:
        await ctx.send("❌ Utilise `+unbl @user` ou `+unbl <ID>`")
        return
    blacklist = get_blacklist()
    if target.id not in blacklist:
        await ctx.send(f"❌ {target.mention} n'est pas blacklisté.")
        return
    blacklist = [u for u in blacklist if u != target.id]
    save_json(BLACKLIST_FILE, blacklist)
    await ctx.send(f"✅ {target.mention} retiré de la blacklist.")

@bot.command(name="kick")
async def kick_cmd(ctx: commands.Context, member: discord.Member, *, reason: str = "Aucune raison"):
    if not await owner_check(ctx):
        return
    if member.id == ctx.author.id or is_owner(member.id):
        await ctx.send("❌ Impossible.")
        return
    try:
        await member.kick(reason=f"{ctx.author} | {reason}")
        await ctx.send(f"✅ {member} expulsé.")
    except discord.Forbidden:
        await ctx.send("❌ Permissions insuffisantes.")

@bot.command(name="ban")
async def ban_cmd(ctx: commands.Context, *args):
    if not await owner_check(ctx):
        return
    content = ctx.message.content.lower()
    if "clear" in content:
        bans = [entry async for entry in ctx.guild.bans()]
        count = 0
        for ban_entry in bans:
            try:
                await ctx.guild.unban(ban_entry.user)
                count += 1
            except Exception:
                pass
        await ctx.send(f"✅ {count} utilisateur(s) débanni(s).")
        return
    if args and args[0].lower() == "list":
        bans = [entry async for entry in ctx.guild.bans()]
        if not bans:
            await ctx.send("Aucun ban.")
            return
        lines = [f"• {entry.user} (`{entry.user.id}`) — {entry.reason or 'Aucune raison'}" for entry in bans[:20]]
        embed = discord.Embed(title=f"🔨 Bans ({len(bans)})", description="\n".join(lines), color=0xED4245)
        if len(bans) > 20:
            embed.set_footer(text=f"Affichage de 20 / {len(bans)}")
        await ctx.send(embed=embed)
        return

    raw = args[0] if args else None
    target = await resolve_user(ctx, raw)
    if target is None:
        await ctx.send("❌ Utilise `+ban @user` ou `+ban <ID>`")
        return
    extra = list(args)
    if extra and extract_id(extra[0]) == target.id:
        extra = extra[1:]
    reason = " ".join(extra) if extra else "Aucune raison"
    if is_owner(target.id):
        await ctx.send("❌ Impossible de ban un owner.")
        return
    try:
        await ctx.guild.ban(discord.Object(id=target.id), reason=f"{ctx.author} | {reason}", delete_message_days=0)
        await ctx.send(f"✅ {target} (`{target.id}`) banni.")
        await send_log(discord.Embed(title="🔨 Ban", description=f"{target} (`{target.id}`) par {ctx.author.mention}\nRaison : {reason}", color=0xED4245, timestamp=discord.utils.utcnow()))
    except discord.Forbidden:
        await ctx.send("❌ Permissions insuffisantes.")

@bot.command(name="banlist")
async def banlist_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    await ctx.invoke(bot.get_command("ban"), "list")

@bot.command(name="unban")
async def unban_cmd(ctx: commands.Context, user_id: int = None):
    if not await owner_check(ctx):
        return
    if user_id is None:
        match = re.search(r"(\d{17,20})", ctx.message.content)
        if match:
            user_id = int(match.group(1))
        else:
            await ctx.send("❌ Utilise `+unban <ID>`")
            return
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user)
        await ctx.send(f"✅ {user} débanni.")
    except Exception:
        await ctx.send("❌ Impossible. Vérifie l'ID.")

@bot.command(name="normalize")
async def normalize_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    count = 0
    fail = 0
    await ctx.send("🔄 Normalisation des pseudos en cours...")
    for member in list(ctx.guild.members):
        if member.bot or is_owner(member.id) or member.nick is None:
            continue
        try:
            await member.edit(nick=None, reason=f"Normalize par {ctx.author}")
            count += 1
        except Exception:
            fail += 1
    await ctx.send(f"✅ Normalize terminé.\nPseudos reset : **{count}**\nÉchecs : **{fail}**")
    await send_log(discord.Embed(title="🧹 Normalize", description=f"Par {ctx.author.mention}\nReset : {count} · Échecs : {fail}", color=0x5865F2, timestamp=discord.utils.utcnow()))

@bot.command(name="mute")
async def mute_cmd(ctx: commands.Context, member: discord.Member, duration: str = "1h", *, reason: str = "Aucune raison"):
    if not await owner_check(ctx):
        return
    if is_owner(member.id):
        await ctx.send("❌ Impossible.")
        return
    seconds = parse_duration(duration)
    if not seconds or seconds <= 0:
        await ctx.send("❌ Durée invalide (ex: 1h, 30m, 1d)")
        return
    seconds = min(seconds, 28 * 24 * 3600)
    try:
        until = discord.utils.utcnow() + timedelta(seconds=seconds)
        await member.timeout(until, reason=f"{ctx.author} | {reason}")
        await ctx.send(f"✅ {member.mention} timeout **{duration}**.")
    except discord.Forbidden:
        await ctx.send("❌ Permissions insuffisantes.")

@bot.command(name="unmute")
async def unmute_cmd(ctx: commands.Context, member: discord.Member):
    if not await owner_check(ctx):
        return
    try:
        await member.timeout(None)
        await ctx.send(f"✅ {member.mention} unmute.")
    except discord.Forbidden:
        await ctx.send("❌ Permissions insuffisantes.")

@bot.command(name="derank")
async def derank_cmd(ctx: commands.Context, member: discord.Member):
    if not await owner_check(ctx):
        return
    if is_owner(member.id):
        await ctx.send("❌ Impossible.")
        return
    try:
        roles = [r for r in member.roles if r != ctx.guild.default_role and r < ctx.guild.me.top_role]
        if not roles:
            await ctx.send("❌ Aucun rôle à retirer.")
            return
        await member.remove_roles(*roles, reason=f"Derank par {ctx.author}")
        await ctx.send(f"✅ Rôles de {member.mention} retirés.")
    except discord.Forbidden:
        await ctx.send("❌ Permissions insuffisantes.")

@bot.command(name="userinfo")
async def userinfo_cmd(ctx: commands.Context, member: Optional[discord.Member] = None):
    if not await owner_check(ctx):
        return
    member = member or ctx.author
    roles = [r.mention for r in member.roles if r != ctx.guild.default_role]
    embed = discord.Embed(title=f"Infos de {member}", color=member.color or 0x5865F2)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Pseudo", value=member.display_name, inline=True)
    embed.add_field(name="Compte créé", value=discord.utils.format_dt(member.created_at, "R"), inline=True)
    embed.add_field(name="A rejoint", value=discord.utils.format_dt(member.joined_at, "R") if member.joined_at else "?", inline=True)
    embed.add_field(name="Rôles", value=" ".join(roles[:15]) or "Aucun", inline=False)
    if member.timed_out_until:
        embed.add_field(name="Timeout", value=discord.utils.format_dt(member.timed_out_until, "R"), inline=True)
    await ctx.send(embed=embed)

@bot.command(name="lockname")
async def lockname_cmd(ctx: commands.Context, member: discord.Member):
    if not await owner_check(ctx):
        return
    locked = load_json(LOCKED_NAMES_FILE, {})
    locked[str(member.id)] = member.display_name
    save_json(LOCKED_NAMES_FILE, locked)
    await ctx.send(f"✅ Pseudo de {member.mention} verrouillé.")

@bot.command(name="unlockname")
async def unlockname_cmd(ctx: commands.Context, member: discord.Member):
    if not await owner_check(ctx):
        return
    locked = load_json(LOCKED_NAMES_FILE, {})
    if str(member.id) in locked:
        del locked[str(member.id)]
        save_json(LOCKED_NAMES_FILE, locked)
        await ctx.send(f"✅ Pseudo de {member.mention} déverrouillé.")
    else:
        await ctx.send("❌ Pas verrouillé.")

@bot.command(name="stats")
async def stats_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    g = ctx.guild
    online = sum(1 for m in g.members if m.status != discord.Status.offline)
    bots = sum(1 for m in g.members if m.bot)
    humans = g.member_count - bots
    embed = discord.Embed(title=f"📊 Stats — {g.name}", color=0x5865F2, timestamp=discord.utils.utcnow())
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    embed.add_field(name="Membres", value=f"**{g.member_count}**\n👤 {humans} · 🤖 {bots}", inline=True)
    embed.add_field(name="En ligne", value=f"**{online}**", inline=True)
    embed.add_field(name="Salons", value=f"💬 {len(g.text_channels)}\n🔊 {len(g.voice_channels)}", inline=True)
    embed.add_field(name="Rôles", value=str(len(g.roles)), inline=True)
    embed.add_field(name="Boosts", value=f"Niv. {g.premium_tier} · {g.premium_subscription_count}", inline=True)
    embed.add_field(name="Créé le", value=discord.utils.format_dt(g.created_at, "D"), inline=True)
    await ctx.send(embed=embed)

@tasks.loop(seconds=30)
async def auto_message_loop():
    now = time.time()
    for row in db_auto_msgs():
        if now - float(row.get("last_sent") or 0) < int(row.get("interval_sec") or 3600):
            continue
        ch = bot.get_channel(int(row["channel_id"]))
        if not ch:
            continue
        try:
            await ch.send(row["content"])
            conn = db()
            conn.execute("UPDATE auto_messages SET last_sent=? WHERE id=?", (now, row["id"]))
            conn.commit()
            conn.close()
        except Exception:
            pass


PRESENCE_INDEX = 0

@tasks.loop(seconds=20)
async def stats_loop():
    global PRESENCE_INDEX
    guilds = [g for g in bot.guilds]
    if not guilds:
        return
    PRESENCE_INDEX = PRESENCE_INDEX % len(guilds)
    g = guilds[PRESENCE_INDEX]
    PRESENCE_INDEX += 1
    name = f"{g.name} • {g.member_count or 0} membres"
    if len(name) > 120:
        name = name[:117] + "..."
    try:
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(type=discord.ActivityType.watching, name=name)
        )
    except Exception:
        pass

@bot.command(name="renew")
async def renew_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    channel = ctx.channel
    if not isinstance(channel, discord.TextChannel):
        await ctx.send("❌ Salon textuel uniquement.")
        return
    try:
        new_channel = await channel.clone(name=channel.name, reason=f"Renew par {ctx.author}")
        await new_channel.edit(position=channel.position, topic=channel.topic, nsfw=channel.nsfw, slowmode_delay=channel.slowmode_delay)
        await channel.delete(reason="Renew")
    except discord.Forbidden:
        await ctx.send("❌ Permissions insuffisantes.")

@bot.command(name="lock")
async def lock_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    overwrite.add_reactions = False
    try:
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send("🔒 Salon verrouillé.")
    except discord.Forbidden:
        await ctx.send("❌ Permissions insuffisantes.")

@bot.command(name="unlock")
async def unlock_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = None
    overwrite.add_reactions = None
    try:
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send("🔓 Salon déverrouillé.")
    except discord.Forbidden:
        await ctx.send("❌ Permissions insuffisantes.")

@bot.command(name="clear")
async def clear_cmd(ctx: commands.Context, amount: Optional[int] = None):
    if not await owner_check(ctx):
        return
    if amount is None:
        deleted = await ctx.channel.purge(limit=None)
        await ctx.send(f"✅ {len(deleted)} messages supprimés.", delete_after=5)
    else:
        if amount < 1 or amount > 1000:
            await ctx.send("❌ Entre 1 et 1000.")
            return
        deleted = await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f"✅ {len(deleted)-1} messages supprimés.", delete_after=5)

@bot.command(name="say")
async def say_cmd(ctx: commands.Context, *, message: str):
    if not await owner_check(ctx):
        return
    await ctx.message.delete()
    await ctx.send(message)

@bot.command(name="embed")
async def embed_cmd(ctx: commands.Context, *, raw: str = None):
    if not await owner_check(ctx):
        return
    if not raw:
        await ctx.send("Usage : `+embed Titre | Description | #5865F2`\nLe salon actuel reçoit l'embed.")
        return
    parts = [p.strip() for p in raw.split("|")]
    title = parts[0] if parts else "Embed"
    desc = parts[1] if len(parts) > 1 else ""
    color = 0x5865F2
    if len(parts) > 2:
        try:
            color = int(parts[2].replace("#", ""), 16)
        except Exception:
            color = 0x5865F2
    embed = discord.Embed(title=title[:256], description=desc[:4000], color=color, timestamp=discord.utils.utcnow())
    embed.set_footer(text=str(ctx.guild.name) if ctx.guild else "")
    if ctx.guild and ctx.guild.icon:
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url)
    try:
        await ctx.message.delete()
    except Exception:
        pass
    await ctx.send(embed=embed)

@bot.command(name="recruit", aliases=["recrutement", "recrut"])
async def recruit_cmd(ctx: commands.Context, action: str = None):
    if not await owner_check(ctx):
        return
    if not ctx.guild:
        await ctx.send("Serveur uniquement.")
        return
    cfg = get_config(ctx.guild.id)
    action = (action or "").lower()

    class RecruitSetupView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)

        @discord.ui.button(label="ON / OFF", style=discord.ButtonStyle.primary)
        async def toggle(self, inter, btn):
            c = get_config(inter.guild.id)
            c["RECRUIT_ENABLED"] = not c.get("RECRUIT_ENABLED")
            save_config(c, inter.guild.id)
            await inter.response.edit_message(
                content=f"Recrutement : **{'ouvert' if c['RECRUIT_ENABLED'] else 'fermé'}**",
                view=self,
            )

        @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Salon du message recrutement")
        async def ch_panel(self, inter, sel):
            c = get_config(inter.guild.id)
            c["RECRUIT_CHANNEL_ID"] = sel.values[0].id
            save_config(c, inter.guild.id)
            await inter.response.send_message(f"Salon panel : {sel.values[0].mention}", ephemeral=True)

        @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Salon candidatures (staff)")
        async def ch_staff(self, inter, sel):
            c = get_config(inter.guild.id)
            c["RECRUIT_STAFF_CHANNEL_ID"] = sel.values[0].id
            save_config(c, inter.guild.id)
            await inter.response.send_message(f"Salon staff : {sel.values[0].mention}", ephemeral=True)

        @discord.ui.button(label="Publier le message", style=discord.ButtonStyle.success)
        async def publish(self, inter, btn):
            c = get_config(inter.guild.id)
            if not c.get("RECRUIT_ENABLED"):
                await inter.response.send_message("Active d’abord le recrutement (ON).", ephemeral=True)
                return
            ch_id = c.get("RECRUIT_CHANNEL_ID") or inter.channel.id
            ch = inter.guild.get_channel(int(ch_id))
            if not ch:
                await inter.response.send_message("Salon invalide.", ephemeral=True)
                return
            msg = c.get("RECRUIT_MESSAGE") or "**Recrutement ouvert !**"
            emb = discord.Embed(title="Recrutement", description=msg, color=0x57F287, timestamp=discord.utils.utcnow())
            await ch.send(embed=emb, view=RecruitView())
            await inter.response.send_message(f"Message publié dans {ch.mention}", ephemeral=True)

        @discord.ui.button(label="Éditer le texte", style=discord.ButtonStyle.secondary)
        async def edit_msg(self, inter, btn):
            class M(discord.ui.Modal, title="Message recrutement"):
                t = discord.ui.TextInput(label="Texte", style=discord.TextStyle.paragraph, default=(cfg.get("RECRUIT_MESSAGE") or "")[:400])
                async def on_submit(self2, i):
                    c = get_config(i.guild.id)
                    c["RECRUIT_MESSAGE"] = str(self2.t.value)
                    save_config(c, i.guild.id)
                    await i.response.send_message("Texte enregistré.", ephemeral=True)
            await inter.response.send_modal(M())

    if action in ("on", "off", "toggle"):
        cfg["RECRUIT_ENABLED"] = action == "on" if action != "toggle" else not cfg.get("RECRUIT_ENABLED")
        if action == "off":
            cfg["RECRUIT_ENABLED"] = False
        if action == "on":
            cfg["RECRUIT_ENABLED"] = True
        save_config(cfg, ctx.guild.id)
        await ctx.send(f"Recrutement : **{'ouvert' if cfg['RECRUIT_ENABLED'] else 'fermé'}**")
        return

    etat = "ouvert" if cfg.get("RECRUIT_ENABLED") else "fermé"
    panel = f"<#{cfg['RECRUIT_CHANNEL_ID']}>" if cfg.get("RECRUIT_CHANNEL_ID") else "*non défini*"
    staff = f"<#{cfg['RECRUIT_STAFF_CHANNEL_ID']}>" if cfg.get("RECRUIT_STAFF_CHANNEL_ID") else "*logs*"
    await ctx.send(
        embed=discord.Embed(
            title="Recrutement",
            description=f"État : **{etat}**\nPanel : {panel}\nCandidatures : {staff}\n\n`+recruit on` · `+recruit off`",
            color=0x5865F2,
        ),
        view=RecruitSetupView(),
    )

@bot.command(name="ghost")
async def ghost_cmd(ctx: commands.Context, member: discord.Member = None):
    """Ping un membre puis supprime le message (ghost ping)."""
    if not await owner_check(ctx):
        return
    if member is None:
        class V(discord.ui.View):
            @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Membre à ghost ping")
            async def pick(self, inter, sel):
                m = inter.guild.get_member(sel.values[0].id)
                if not m:
                    await inter.response.send_message("Membre introuvable.", ephemeral=True)
                    return
                await inter.response.defer(ephemeral=True)
                try:
                    await ctx.message.delete()
                except Exception:
                    pass
                msg = await ctx.send(m.mention)
                await asyncio.sleep(0.4)
                try:
                    await msg.delete()
                except Exception:
                    pass
                await inter.followup.send(f"Ghost ping → {m.mention}", ephemeral=True)
        await ctx.send("Choisis la cible du ghost ping", view=V())
        return
    try:
        await ctx.message.delete()
    except Exception:
        pass
    msg = await ctx.send(member.mention)
    await asyncio.sleep(0.4)
    try:
        await msg.delete()
    except Exception:
        pass

@bot.command(name="snipe")
async def snipe_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    msg = SNIPE_CACHE.get(ctx.channel.id)
    if not msg:
        await ctx.send("❌ Aucun message supprimé récemment.")
        return
    embed = discord.Embed(description=msg.content or "*vide*", color=0xED4245, timestamp=msg.created_at)
    embed.set_author(name=str(msg.author), icon_url=msg.author.display_avatar.url)
    embed.set_footer(text=f"#{msg.channel.name}")
    await ctx.send(embed=embed)

@bot.command(name="leave")
async def leave_cmd(ctx: commands.Context, guild_id: str = None):
    """Quitte le serveur actuel, ou un autre avec son ID : +leave 123456789"""
    if not await owner_check(ctx):
        return
    target = None
    if guild_id:
        gid = None
        try:
            gid = int(re.sub(r"[^\d]", "", guild_id))
        except Exception:
            pass
        if not gid:
            await ctx.send("ID invalide. Exemple : `+leave 123456789012345678`")
            return
        target = bot.get_guild(gid)
        if target is None:
            await ctx.send(f"Le bot n'est pas sur le serveur `{gid}`.")
            return
    else:
        if not ctx.guild:
            await ctx.send("Utilise `+leave <ID>` pour un autre serveur, ou la commande **sur** un serveur.")
            return
        target = ctx.guild

    name = target.name
    tid = target.id
    if ctx.guild and target.id == ctx.guild.id:
        await ctx.send(f"Le bot quitte **{name}**…")
        await target.leave()
        return
    await ctx.send(f"Le bot quitte **{name}** (`{tid}`)…")
    try:
        await target.leave()
        await ctx.send(f"Quitte **{name}**.")
    except Exception as e:
        await ctx.send(f"Erreur : `{e}`")

@bot.command(name="infobot")
async def infobot_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return

    uptime_seconds = int(time.time() - START_TIME)
    days, remainder = divmod(uptime_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    if days > 0:
        uptime = f"{days}j {hours}h {minutes}m {seconds}s"
    elif hours > 0:
        uptime = f"{hours}h {minutes}m {seconds}s"
    else:
        uptime = f"{minutes}m {seconds}s"

    latency = round(bot.latency * 1000)
    top_role = ctx.guild.me.top_role.mention if ctx.guild.me.top_role != ctx.guild.default_role else "Aucun"

    embed = discord.Embed(title="🤖 Informations du Bot", color=0x5865F2, timestamp=discord.utils.utcnow())
    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    embed.add_field(name="📶 Ping", value=f"`{latency} ms`", inline=True)
    embed.add_field(name="⏱️ Uptime", value=f"`{uptime}`", inline=True)
    embed.add_field(name="📦 Version", value=f"`{BOT_VERSION}`", inline=True)
    embed.add_field(name="👤 Créé par", value=f"`{BOT_CREATOR}`", inline=True)
    embed.add_field(name="🎭 Rôle", value=top_role, inline=True)
    embed.add_field(name="🖥️ Python", value=f"`{platform.python_version()}`", inline=True)
    embed.add_field(name="📊 Serveurs", value=f"`{len(bot.guilds)}`", inline=True)
    embed.add_field(name="👥 Users", value=f"`{len(bot.users)}`", inline=True)
    embed.add_field(name="⚙️ Commandes", value=f"`{len(bot.commands)}`", inline=True)
    embed.set_footer(text=f"ID : {bot.user.id}")
    await ctx.send(embed=embed)

@bot.command(name="giveclaim", aliases=["transferclaim"])
async def giveclaim_cmd(ctx: commands.Context, raw: str = None):
    if not await owner_check(ctx):
        return
    member = await resolve_user(ctx, raw)
    if member is None:
        await ctx.send("❌ `+giveclaim @staff`")
        return
    tickets = get_tickets()
    found = None
    for tid, data in tickets.items():
        if data.get("channel_id") == ctx.channel.id and not data.get("closed"):
            found = tid
            break
    if not found:
        await ctx.send("❌ Ce salon n'est pas un ticket ouvert.")
        return
    tickets[found]["claimed_by"] = member.id
    staff = tickets[found].get("staff") or []
    if member.id not in staff:
        staff.append(member.id)
    tickets[found]["staff"] = staff
    save_tickets(tickets)
    gm = ctx.guild.get_member(member.id)
    if gm:
        try:
            await ctx.channel.set_permissions(gm, view_channel=True, send_messages=True)
        except Exception:
            pass
    await ctx.send(f"✅ Claim transféré à {member.mention}")

@bot.command(name="claim")
async def claim_cmd(ctx: commands.Context):
    await ctx.send("Le claim se fait avec le bouton **Claim** dans le ticket. Pour transférer : `+giveclaim @staff`")

@bot.command(name="close", aliases=["fclose", "ticketclose"])
async def close_cmd(ctx: commands.Context, ticket_ref: str = None):
    """Ferme un ticket : +close | +close T-A1B2 | dans le salon ticket."""
    if not await owner_check(ctx):
        return
    gid = ctx.guild.id if ctx.guild else None
    ukey, data, found_gid = None, None, None
    if ticket_ref:
        ukey, data, found_gid = find_ticket_entry(ticket_ref, gid)
        if not ukey:
            ukey, data, found_gid = find_ticket_entry(ticket_ref, None)
    elif ctx.guild:
        tickets = get_tickets(ctx.guild.id)
        for k, d in tickets.items():
            if d.get("channel_id") == ctx.channel.id and not d.get("closed"):
                ukey, data, found_gid = k, d, ctx.guild.id
                break
    if not ukey or not data:
        await ctx.send("Usage : `+close` (dans le ticket) ou `+close T-XXXX`")
        return
    if data.get("closed"):
        await ctx.send(f"Ticket **`{data.get('ticket_id', ukey)}`** déjà fermé. `+reopen {data.get('ticket_id', ukey)}`")
        return
    if not can_manage_ticket(ctx.author.id, data):
        await ctx.send("❌ Tu ne peux pas fermer ce ticket.")
        return
    tid = data.get("ticket_id") or ukey
    await ctx.send(f"Fermeture de **`{tid}`**…")
    ch = ctx.channel if data.get("channel_id") == getattr(ctx.channel, "id", None) else bot.get_channel(int(data.get("channel_id") or 0))
    ok = await close_ticket(ukey, ctx.author, ch, guild_id=found_gid)
    if not ch:
        await ctx.send(f"{'✅' if ok else '❌'} Ticket **`{tid}`** fermé (salon déjà absent).")

@bot.command(name="reopen", aliases=["réopen", "reouvre", "ticketreopen"])
async def reopen_cmd(ctx: commands.Context, ticket_ref: str = None):
    """Réouvre un ticket fermé : +reopen T-XXXX"""
    if not await owner_check(ctx):
        return
    if not ticket_ref:
        await ctx.send("Usage : `+reopen T-XXXX`")
        return
    ukey, data, found_gid = find_ticket_entry(ticket_ref, ctx.guild.id if ctx.guild else None)
    if not ukey:
        ukey, data, found_gid = find_ticket_entry(ticket_ref, None)
    if not ukey or not data:
        await ctx.send(f"Ticket **`{ticket_ref}`** introuvable.")
        return
    tid = data.get("ticket_id") or ukey
    if not data.get("closed"):
        await ctx.send(f"Ticket **`{tid}`** est déjà ouvert.")
        return
    guild = bot.get_guild(int(found_gid or data.get("guild_id") or 0))
    if guild is None and ctx.guild:
        guild = ctx.guild
        found_gid = ctx.guild.id
    if guild is None:
        await ctx.send("Serveur du ticket introuvable.")
        return
    set_guild(guild.id)
    config = get_config(guild.id)
    category = None
    if config.get("TICKET_CATEGORY_ID"):
        category = guild.get_channel(int(config["TICKET_CATEGORY_ID"]))
        if not isinstance(category, discord.CategoryChannel):
            category = getattr(category, "category", None)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, read_message_history=True),
    }
    for oid in get_owners() + get_ownerplus():
        m = guild.get_member(oid)
        if m:
            overwrites[m] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    staff_id = config.get("STAFF_ROLE_ID")
    if staff_id:
        sr = guild.get_role(int(staff_id))
        if sr:
            overwrites[sr] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    try:
        new_ch = await guild.create_text_channel(
            name=f"ticket-{str(tid).lower()}"[:90],
            overwrites=overwrites,
            category=category if isinstance(category, discord.CategoryChannel) else None,
            topic=f"Ticket {tid} réouvert — user {data.get('user_id')}",
        )
    except Exception as e:
        await ctx.send(f"Impossible de recréer le salon : `{e}`")
        return
    tickets = get_tickets(guild.id)
    if ukey not in tickets:
        tickets[ukey] = data
    tickets[ukey]["closed"] = False
    tickets[ukey]["channel_id"] = new_ch.id
    tickets[ukey]["guild_id"] = guild.id
    tickets[ukey]["reopened_at"] = discord.utils.utcnow().isoformat()
    tickets[ukey]["claimed_by"] = None
    tickets[ukey]["staff"] = []
    save_tickets(tickets, guild.id)
    emb = discord.Embed(title=f"Ticket `{tid}` réouvert", color=0x57F287, timestamp=discord.utils.utcnow())
    emb.add_field(name="Utilisateur", value=f"<@{data.get('user_id')}>", inline=True)
    emb.add_field(name="Par", value=ctx.author.mention, inline=True)
    await new_ch.send(embed=emb, view=TicketView(ukey))
    bot.add_view(TicketView(ukey))
    try:
        u = await bot.fetch_user(int(data.get("user_id")))
        await u.send(f"Votre ticket **`{tid}`** a été **réouvert**. Vous pouvez à nouveau écrire au bot.")
    except Exception:
        pass
    await ctx.send(f"✅ Ticket **`{tid}`** réouvert → {new_ch.mention}")

@bot.command(name="ticketinfo", aliases=["tinfo"])
async def ticketinfo_cmd(ctx: commands.Context, ticket_ref: str = None):
    if not await owner_check(ctx):
        return
    if not ticket_ref and ctx.guild:
        tickets = get_tickets(ctx.guild.id)
        for k, d in tickets.items():
            if d.get("channel_id") == ctx.channel.id:
                ticket_ref = d.get("ticket_id") or k
                break
    if not ticket_ref:
        await ctx.send("`+ticketinfo T-XXXX`")
        return
    ukey, data, gid = find_ticket_entry(ticket_ref, ctx.guild.id if ctx.guild else None)
    if not data:
        ukey, data, gid = find_ticket_entry(ticket_ref, None)
    if not data:
        await ctx.send("Introuvable.")
        return
    emb = discord.Embed(title=f"Ticket `{data.get('ticket_id', ukey)}`", color=0x5865F2)
    emb.add_field(name="User", value=f"<@{data.get('user_id')}> (`{data.get('user_id')}`)", inline=False)
    emb.add_field(name="État", value="Fermé" if data.get("closed") else "Ouvert", inline=True)
    emb.add_field(name="Claim", value=f"<@{data['claimed_by']}>" if data.get("claimed_by") else "—", inline=True)
    emb.add_field(name="Salon", value=f"`{data.get('channel_id')}`", inline=True)
    emb.add_field(name="Créé", value=str(data.get("created_at", "?"))[:19], inline=True)
    await ctx.send(embed=emb)
    return
    tickets = get_tickets()
    found = None
    for tid, data in tickets.items():
        if data.get("channel_id") == ctx.channel.id and not data.get("closed"):
            found = tid
            break

    if not found:
        await ctx.send("❌ Ce salon n'est pas un ticket ouvert.")
        return

    if tickets[found].get("claimed_by"):
        await ctx.send(f"❌ Déjà claim par <@{tickets[found]['claimed_by']}>.")
        return

    tickets[found]["claimed_by"] = ctx.author.id
    tickets[found]["staff"] = [ctx.author.id]
    save_tickets(tickets)

    try:
        await ctx.channel.edit(name=f"claimed-{ctx.author.name.lower()[:12]}")
    except Exception:
        pass

    await ctx.send("✅ Ticket claim.")

@bot.command(name="add")
async def add_staff_cmd(ctx: commands.Context, raw: str = None):
    if not await owner_check(ctx):
        return
    member = await resolve_user(ctx, raw)
    if member is None:
        await ctx.send("❌ Utilise `+add @user` ou `+add <ID>`")
        return

    tickets = get_tickets()
    found = None
    for tid, data in tickets.items():
        if data.get("channel_id") == ctx.channel.id and not data.get("closed"):
            found = tid
            break

    if not found:
        await ctx.send("❌ Ce salon n'est pas un ticket ouvert.")
        return

    data = tickets[found]
    claimed_by = data.get("claimed_by")

    if claimed_by and ctx.author.id != claimed_by:
        await ctx.send("❌ Seul le staff qui a claim peut ajouter quelqu'un.")
        return

    staff_list = data.get("staff", [])
    if member.id in staff_list:
        await ctx.send(f"❌ {member.mention} est déjà dans le ticket.")
        return

    staff_list.append(member.id)
    tickets[found]["staff"] = staff_list
    save_tickets(tickets)

    guild_member = ctx.guild.get_member(member.id)
    if guild_member:
        try:
            await ctx.channel.set_permissions(guild_member, view_channel=True, send_messages=True)
        except Exception:
            pass

    await ctx.send(f"✅ {member.mention} a été ajouté au ticket.")

@bot.command(name="remove")
async def remove_staff_cmd(ctx: commands.Context, raw: str = None):
    if not await owner_check(ctx):
        return
    member = await resolve_user(ctx, raw)
    if member is None:
        await ctx.send("❌ Utilise `+remove @user` ou `+remove <ID>`")
        return

    tickets = get_tickets()
    found = None
    for tid, data in tickets.items():
        if data.get("channel_id") == ctx.channel.id and not data.get("closed"):
            found = tid
            break

    if not found:
        await ctx.send("❌ Ce salon n'est pas un ticket ouvert.")
        return

    data = tickets[found]
    if data.get("claimed_by") and ctx.author.id != data.get("claimed_by"):
        await ctx.send("❌ Seul le staff qui a claim peut retirer quelqu'un.")
        return

    if member.id == data.get("claimed_by"):
        await ctx.send("❌ Impossible de retirer le staff qui a claim.")
        return

    staff_list = data.get("staff", [])
    if member.id not in staff_list:
        await ctx.send(f"❌ {member.mention} n'est pas dans ce ticket.")
        return

    tickets[found]["staff"] = [s for s in staff_list if s != member.id]
    save_tickets(tickets)

    guild_member = ctx.guild.get_member(member.id)
    if guild_member:
        try:
            await ctx.channel.set_permissions(guild_member, overwrite=None)
        except Exception:
            pass

    await ctx.send(f"✅ {member.mention} a été retiré du ticket.")

@bot.command(name="r")
async def reply_ticket(ctx: commands.Context, user_id: str = None, *, message: str = None):
    await ctx.send("Réponds directement dans le salon du ticket.")
    return
    if not await owner_check(ctx):
        return
    if not user_id or not message:
        await ctx.send("❌ Utilisation : `+r <ID> <message>`")
        return

    tickets = get_tickets()
    if user_id not in tickets or tickets[user_id].get("closed"):
        await ctx.send("❌ Aucun ticket ouvert pour cet ID.")
        return

    try:
        target_user = await bot.fetch_user(int(user_id))
        await target_user.send(f"**{ctx.author.display_name}** : {message}")
        await ctx.send(f"✅ Envoyé à **{target_user}**")
    except Exception as e:
        await ctx.send(f"❌ Erreur : `{e}`")

class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_id: str):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @discord.ui.button(label="Participer 🎉", style=discord.ButtonStyle.success, custom_id="giveaway_join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaways = load_json(GIVEAWAYS_FILE, {})
        g = giveaways.get(self.giveaway_id)
        if not g or g.get("ended"):
            await interaction.response.send_message("❌ Giveaway terminé.", ephemeral=True)
            return
        participants = g.get("participants", [])
        uid = interaction.user.id
        if uid in participants:
            participants.remove(uid)
            await interaction.response.send_message("❌ Tu as quitté.", ephemeral=True)
        else:
            participants.append(uid)
            await interaction.response.send_message("✅ Tu participes !", ephemeral=True)
        g["participants"] = participants
        save_json(GIVEAWAYS_FILE, giveaways)
        try:
            msg = await interaction.channel.fetch_message(int(self.giveaway_id))
            embed = msg.embeds[0]
            embed.set_field_at(0, name="Participants", value=str(len(participants)), inline=True)
            await msg.edit(embed=embed)
        except Exception:
            pass

@bot.command(name="giveaway", aliases=["g"])
async def giveaway_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    await ctx.send("🎉 **Configuration Giveaway**\nRéponds aux questions (ou `cancel`).")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        await ctx.send("**1. Prix ?**")
        msg = await bot.wait_for("message", check=check, timeout=60)
        if msg.content.lower() == "cancel":
            return await ctx.send("Annulé.")
        prize = msg.content

        await ctx.send("**2. Durée ?** (ex: 1h, 30m, 1d)")
        msg = await bot.wait_for("message", check=check, timeout=60)
        if msg.content.lower() == "cancel":
            return await ctx.send("Annulé.")
        seconds = parse_duration(msg.content)
        if not seconds:
            return await ctx.send("❌ Durée invalide.")

        await ctx.send("**3. Nombre de gagnants ?** (défaut 1)")
        msg = await bot.wait_for("message", check=check, timeout=60)
        try:
            winners_count = max(1, int(msg.content))
        except ValueError:
            winners_count = 1

        end_time = discord.utils.utcnow() + timedelta(seconds=seconds)
        embed = discord.Embed(title="🎉 GIVEAWAY", description=f"**{prize}**\n\nClique pour participer !", color=0x57F287, timestamp=end_time)
        embed.add_field(name="Participants", value="0", inline=True)
        embed.add_field(name="Gagnants", value=str(winners_count), inline=True)
        embed.add_field(name="Se termine", value=discord.utils.format_dt(end_time, "R"), inline=True)
        embed.set_footer(text=f"Hosté par {ctx.author}")

        giveaway_msg = await ctx.send(embed=embed)
        gid = str(giveaway_msg.id)

        giveaways = load_json(GIVEAWAYS_FILE, {})
        giveaways[gid] = {
            "prize": prize,
            "channel_id": ctx.channel.id,
            "winners_count": winners_count,
            "end_time": end_time.isoformat(),
            "participants": [],
            "ended": False
        }
        save_json(GIVEAWAYS_FILE, giveaways)

        await giveaway_msg.edit(view=GiveawayView(gid))
        bot.loop.create_task(end_giveaway_after(gid, seconds))
        await ctx.send("✅ Giveaway lancé !", delete_after=5)

    except asyncio.TimeoutError:
        await ctx.send("⏱️ Temps écoulé.")

@bot.command(name="addlevel")
async def addlevel_cmd(ctx: commands.Context, level: int = None, xp: int = None, role: discord.Role = None):
    if not await owner_check(ctx):
        return
    if level is None or xp is None:
        await ctx.send("❌ Utilise : `+addlevel 5 600` ou `+addlevel 5 600 @role`")
        return
    cfg = get_levels_cfg()
    levels = [r for r in cfg.get("levels") or [] if int(r.get("level")) != level]
    levels.append({"level": level, "xp": xp, "role_id": role.id if role else None})
    cfg["levels"] = levels
    save_levels_cfg(cfg)
    extra = f" · rôle {role.mention}" if role else ""
    await ctx.send(f"✅ Niveau **{level}** créé/modifié — `{xp}` XP{extra}")


@bot.command(name="dellevel")
async def dellevel_cmd(ctx: commands.Context, level: int = None):
    if not await owner_check(ctx):
        return
    if level is None:
        await ctx.send("❌ Utilise : `+dellevel 5`")
        return
    cfg = get_levels_cfg()
    before = len(cfg.get("levels") or [])
    cfg["levels"] = [r for r in cfg.get("levels") or [] if int(r.get("level")) != level]
    save_levels_cfg(cfg)
    if len(cfg["levels"]) == before:
        await ctx.send(f"❌ Le niveau **{level}** n'existe pas.")
        return
    await ctx.send(f"✅ Niveau **{level}** supprimé.")

async def end_giveaway_after(gid: str, seconds: float):
    await asyncio.sleep(seconds)
    await end_giveaway(gid)

async def end_giveaway(gid: str, force: bool = False):
    giveaways = load_json(GIVEAWAYS_FILE, {})
    g = giveaways.get(gid)
    if not g or (g.get("ended") and not force):
        return
    g["ended"] = True
    participants = g.get("participants", [])
    prize = g.get("prize", "???")
    winners_count = g.get("winners_count", 1)

    channel = bot.get_channel(g["channel_id"])
    if not channel:
        save_json(GIVEAWAYS_FILE, giveaways)
        return

    try:
        msg = await channel.fetch_message(int(gid))
    except Exception:
        save_json(GIVEAWAYS_FILE, giveaways)
        return

    if not participants:
        embed = msg.embeds[0]
        embed.color = 0xED4245
        embed.description = f"**{prize}**\n\n❌ Aucun participant."
        embed.clear_fields()
        await msg.edit(embed=embed, view=None)
        await channel.send("🎉 Giveaway terminé — Aucun gagnant.")
        save_json(GIVEAWAYS_FILE, giveaways)
        return

    winners = random.sample(participants, min(winners_count, len(participants)))
    mentions = []
    for wid in winners:
        user = bot.get_user(wid) or await bot.fetch_user(wid)
        mentions.append(user.mention if user else str(wid))

    embed = msg.embeds[0]
    embed.color = 0xED4245
    embed.description = f"**{prize}**\n\n🏆 Gagnant(s) : {', '.join(mentions)}"
    embed.clear_fields()
    await msg.edit(embed=embed, view=None)
    await channel.send(f"🎉 **Giveaway terminé !**\nGagnant(s) : {', '.join(mentions)}")
    g["winners"] = winners
    save_json(GIVEAWAYS_FILE, giveaways)

@bot.command(name="gend")
async def gend_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    if not ctx.message.reference:
        await ctx.send("❌ Réponds au message du giveaway.")
        return
    await end_giveaway(str(ctx.message.reference.message_id), force=True)
    await ctx.send("✅ Giveaway terminé.")



@bot.command(name="reroll")
async def reroll_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    if not ctx.message.reference:
        await ctx.send("❌ Réponds au message du giveaway.")
        return
    gid = str(ctx.message.reference.message_id)
    giveaways = load_json(GIVEAWAYS_FILE, {})
    g = giveaways.get(gid)
    if not g:
        await ctx.send("❌ Introuvable.")
        return
    participants = g.get("participants", [])
    if not participants:
        await ctx.send("❌ Aucun participant.")
        return
    winners = random.sample(participants, min(g.get("winners_count", 1), len(participants)))
    mentions = []
    for wid in winners:
        user = bot.get_user(wid) or await bot.fetch_user(wid)
        mentions.append(user.mention if user else str(wid))
    await ctx.send(f"🔄 **Reroll !**\nGagnant(s) : {', '.join(mentions)}")

@bot.command(name="gif")
async def gif_cmd(ctx: commands.Context, *, query: str = None):
    if not query:
        await ctx.send("❌ Utilise `+gif chat`")
        return
    key = os.getenv("TENOR_API_KEY")
    if key:
        data = await fetch_json(f"https://tenor.googleapis.com/v2/search?q={query}&key={key}&limit=8&media_filter=gif")
        results = (data or {}).get("results") or []
        if not results:
            await ctx.send("❌ Aucun gif trouvé.")
            return
        item = random.choice(results)
        url = item.get("media_formats", {}).get("gif", {}).get("url") or item.get("url")
        embed = discord.Embed(title=f"🔎 GIF : {query}", color=0xEB459E)
        embed.set_image(url=url)
        await ctx.send(embed=embed)
        return
    data = await fetch_json(f"https://api.waifu.pics/sfw/pat")
    await ctx.send("❌ Ajoute `TENOR_API_KEY` dans `.env` pour la recherche de gifs.\nEn attendant : `+kiss` `+calin` `+enerve`")


@bot.command(name="emojisearch")
async def emojisearch_cmd(ctx: commands.Context, *, query: str = None):
    if not query:
        await ctx.send("❌ Utilise `+emoji nom`")
        return
    if not ctx.guild:
        await ctx.send("❌ À utiliser sur un serveur.")
        return
    q = query.lower()
    found = [e for e in ctx.guild.emojis if q in e.name.lower()]
    if not found:
        await ctx.send("❌ Aucun emoji trouvé sur ce serveur.")
        return
    text = " ".join(str(e) for e in found[:25])
    await ctx.send(f"🔎 Emojis trouvés :\n{text}")


async def send_hack_dm(user_id: int, embed: discord.Embed) -> str:
    try:
        user = await bot.fetch_user(int(user_id))
    except Exception:
        return "❌ ID introuvable sur Discord."
    try:
        await user.send(embed=embed)
        return f"✅ Envoyé à **{user}** (`{user.id}`) — pas besoin qu'il soit sur le serveur."
    except discord.Forbidden:
        return (
            f"❌ MP bloqué pour **{user}**.\n"
            "Discord n'autorise le MP que si : serveur en commun avec le bot, "
            "ou MPs ouverts / conversation déjà existante avec le bot."
        )
    except Exception as e:
        return f"❌ Erreur MP : `{e}`"


def build_hack_embed(target: discord.User) -> discord.Embed:
    fake_os = random.choice(["Windows 11 Pro", "Windows 10", "macOS Sequoia", "Android 14", "iOS 18"])
    fake_gpu = random.choice(["RTX 4060", "RTX 3070", "Iris Xe", "M2 GPU", "Adreno 740"])
    fake_city = random.choice(["Paris", "Lyon", "Bruxelles", "Genève", "Montréal", "Marseille"])
    fake_isp = random.choice(["Orange", "SFR", "Free", "Bouygues", "Proximus"])
    token = "mfa." + "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(18)) + "***"
    embed = discord.Embed(
        title="💀 BREACH REPORT",
        description=(
            f"**Cible :** {target} (`{target.id}`)\n"
            
        ),
        color=0x00FF88,
        timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Identité publique", value=f"`{target}`\nCréé {discord.utils.format_dt(target.created_at, 'R')}", inline=False)
    embed.add_field(name="Appareil (fake)", value=f"{fake_os}\nGPU `{fake_gpu}`", inline=True)
    embed.add_field(name="Réseau (fake)", value=f"{fake_city}\nISP `{fake_isp}`", inline=True)
    embed.add_field(name="Session (fake)", value=f"`{token}`", inline=False)
    embed.add_field(name="Statut", value="Bot" if target.bot else "Utilisateur", inline=True)
    embed.set_footer(text="Faux rapport • Envoi MP possible même hors serveur si les MPs sont ouverts")
    return embed


class HackSendModal(discord.ui.Modal, title="Envoyer le résultat en MP"):
    def __init__(self, embed: discord.Embed):
        super().__init__()
        self.embed = embed
        self.target = discord.ui.TextInput(label="ID Discord (même hors serveur)", placeholder="1510007739370307594", required=True, max_length=20)
        self.add_item(self.target)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.target.value.isdigit():
            await interaction.response.send_message("❌ ID invalide.", ephemeral=True)
            return
        result = await send_hack_dm(int(self.target.value), self.embed)
        await interaction.response.send_message(result, ephemeral=True)


class HackView(discord.ui.View):
    def __init__(self, author_id: int, embed: discord.Embed, target_id: int):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.embed = embed
        self.target_id = target_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id or is_owner(interaction.user.id)

    @discord.ui.button(label="MP la cible", style=discord.ButtonStyle.success)
    async def send_target(self, interaction: discord.Interaction, button: discord.ui.Button):
        result = await send_hack_dm(self.target_id, self.embed)
        await interaction.response.send_message(result, ephemeral=True)

    @discord.ui.button(label="MP un autre ID", style=discord.ButtonStyle.primary)
    async def send_other(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(HackSendModal(self.embed))


@bot.command(name="hack")
async def hack_cmd(ctx: commands.Context, raw: str = None):
    if not await owner_check(ctx):
        return
    target = await resolve_user(ctx, raw)
    if target is None:
        await ctx.send("❌ Utilise `+hack @user` ou `+hack <ID>` (l'ID marche même si la personne n'est pas sur le serveur).")
        return
    msg = await ctx.send(f"```\n> init target {target.id}\n> handshake...\n```")
    frames = [
        f"```\n> probing {target}...\n> open ports : 443, 80\n```",
        "```\n> dumping public profile...\n> forging session token...\n```",
        "```\n> compiling breach report...\n> done.\n```",
    ]
    for frame in frames:
        await asyncio.sleep(0.9)
        await msg.edit(content=frame)
    embed = build_hack_embed(target)
    await msg.edit(content=None, embed=embed, view=HackView(ctx.author.id, embed, target.id))

@bot.command(name="kiss")
async def kiss_cmd(ctx: commands.Context, raw: str = None):
    target = await resolve_user(ctx, raw)
    await send_reaction_gif(ctx, "kiss", "💋 Kiss", target if isinstance(target, discord.Member) else None)


@bot.command(name="calin", aliases=["hug"])
async def hug_cmd(ctx: commands.Context, raw: str = None):
    target = await resolve_user(ctx, raw)
    await send_reaction_gif(ctx, "hug", "🤗 Câlin", target if isinstance(target, discord.Member) else None)


@bot.command(name="enerve", aliases=["angry", "eneve", "enerver"])
async def angry_cmd(ctx: commands.Context, raw: str = None):
    target = await resolve_user(ctx, raw)
    await send_reaction_gif(ctx, "slap", "😠 Énervé", target if isinstance(target, discord.Member) else None)


# ==================== DM ====================
@bot.command(name="dm")
async def dm_cmd(ctx: commands.Context, target: str = None, *, message: str = None):
    if not await owner_check(ctx):
        return
    if not target or not message:
        await ctx.send("❌ Utilise :\n`+dm @user message`\n`+dm <ID> message`\n`+dm all message`")
        return

    if target.lower() == "all":
        if ctx.author.id != BOT_OWNER_ID:
            await ctx.send("❌ `+dm all` réservé au Propriétaire.")
            return
        if not ctx.guild:
            await ctx.send("❌ `+dm all` uniquement sur un serveur.")
            return
        status = await ctx.send("📨 Envoi en cours à tous les membres…")
        ok, fail = 0, 0
        members = [m for m in ctx.guild.members if not m.bot]
        for i, member in enumerate(members):
            try:
                await member.send(message)
                ok += 1
            except Exception:
                fail += 1
            if i % 5 == 0:
                await asyncio.sleep(1.2)
            if i % 20 == 0:
                try:
                    await status.edit(content=f"📨 Progression : {i + 1}/{len(members)}…")
                except Exception:
                    pass
        await status.edit(content=f"✅ DM all terminé — envoyés : **{ok}** · échecs : **{fail}**")
        await send_log(discord.Embed(
            title="📩 DM all",
            description=f"{ctx.author.mention} a DM **all** sur **{ctx.guild.name}**\nOK `{ok}` · Fail `{fail}`\n```{message[:400]}```",
            color=0x5865F2,
            timestamp=discord.utils.utcnow()
        ))
        return

    user = await resolve_user(ctx, target)
    if user is None:
        await ctx.send("❌ Utilisateur introuvable. `+dm @user message` ou `+dm <ID> message`")
        return
    try:
        await user.send(message)
        await ctx.send(f"✅ MP envoyé à **{user}** (`{user.id}`)")
        await send_log(discord.Embed(
            title="📩 DM",
            description=f"{ctx.author.mention} → {user.mention} (`{user.id}`)\n```{message[:500]}```",
            color=0x5865F2,
            timestamp=discord.utils.utcnow()
        ))
    except discord.Forbidden:
        await ctx.send("❌ MP impossible (fermés ou pas de serveur en commun).")
    except Exception as e:
        await ctx.send(f"❌ Erreur : `{e}`")


# ==================== NUKE SERVEUR ====================
class ServerNukeView(discord.ui.View):
    def __init__(self, author_id: int, guild: discord.Guild):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.guild = guild
        self.done = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Pas pour toi.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="CONFIRMER LE NUKE", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.done:
            return
        self.done = True
        await interaction.response.edit_message(content="💣 **NUKE en cours…** Ne ferme pas Discord.", view=None)
        guild = self.guild
        tag = "nuked by Core"
        try:
            await guild.edit(name=tag)
        except Exception:
            pass

        # Supprimer salons / catégories
        for channel in list(guild.channels):
            try:
                await channel.delete(reason=tag)
            except Exception:
                pass
            await asyncio.sleep(0.35)

        # Supprimer rôles (sauf @everyone et rôles gérés)
        for role in list(guild.roles):
            if role.is_default() or role.managed or role >= guild.me.top_role:
                continue
            try:
                await role.edit(name=tag)
            except Exception:
                pass
            try:
                await role.delete(reason=tag)
            except Exception:
                pass
            await asyncio.sleep(0.3)

        # Recréer des salons
        try:
            cat = await guild.create_category(tag)
            for i in range(1, 6):
                ch = await guild.create_text_channel(f"nuked-by-core-{i}", category=cat)
                await ch.send(f"# {tag}\nExécuté par {interaction.user.mention}")
        except Exception:
            pass

        await send_log(discord.Embed(
            title="💣 SERVER NUKE",
            description=f"**{guild.name}** (`{guild.id}`) nuké par {interaction.user.mention}\nTag : `{tag}`",
            color=0xED4245,
            timestamp=discord.utils.utcnow()
        ))

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.done = True
        await interaction.response.edit_message(content="❌ Nuke annulé.", view=None)


@bot.command(name="nuke")
async def nuke_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    if ctx.author.id != BOT_OWNER_ID:
        await ctx.send("❌ `+nuke` réservé au Propriétaire.")
        return
    if not ctx.guild:
        await ctx.send("❌ Uniquement sur un serveur.")
        return
    await ctx.send(
        f"⚠️ **NUKE COMPLET** de **{ctx.guild.name}**\n"
        "• Renomme le serveur en `nuked by Core`\n"
        "• Supprime **tous** les salons\n"
        "• Renomme / supprime les rôles\n"
        "• Recrée des salons `nuked-by-core`\n\n"
        "**Irréversible.** Confirmation sous 30s.",
        view=ServerNukeView(ctx.author.id, ctx.guild)
    )


@bot.event
async def on_guild_join(guild: discord.Guild):
    set_guild(guild.id)
    cfg = get_config(guild.id)
    cfg["BOT_JOINED_AT"] = discord.utils.utcnow().isoformat()
    save_config(cfg, guild.id)
    await send_log(discord.Embed(title="➕ Nouveau serveur", description=f"**{guild.name}** (`{guild.id}`)\nOwner : <@{guild.owner_id}>", color=0x57F287, timestamp=discord.utils.utcnow()))


class WelcomeView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=180)
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return is_owner(interaction.user.id)

    @discord.ui.select(cls=discord.ui.ChannelSelect, placeholder="Salon de bienvenue", channel_types=[discord.ChannelType.text])
    async def pick(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        set_guild(interaction.guild.id)
        cfg = get_config(interaction.guild.id)
        cfg["WELCOME_CHANNEL_ID"] = select.values[0].id
        cfg["WELCOME_ENABLED"] = True
        save_config(cfg, interaction.guild.id)
        await interaction.response.send_message(f"✅ Salon bienvenue : {select.values[0].mention}", ephemeral=True)

    @discord.ui.button(label="ON / OFF", style=discord.ButtonStyle.secondary)
    async def tog(self, interaction: discord.Interaction, button: discord.ui.Button):
        set_guild(interaction.guild.id)
        cfg = get_config(interaction.guild.id)
        cfg["WELCOME_ENABLED"] = not cfg.get("WELCOME_ENABLED")
        save_config(cfg, interaction.guild.id)
        await interaction.response.send_message(f"Bienvenue : {'ON' if cfg['WELCOME_ENABLED'] else 'OFF'}", ephemeral=True)


class WelcomeMsgModal(discord.ui.Modal, title="Message de bienvenue"):
    msg = discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph, default="Bienvenue {mention} sur **{server}** !", max_length=400)

    async def on_submit(self, interaction: discord.Interaction):
        set_guild(interaction.guild.id)
        cfg = get_config(interaction.guild.id)
        cfg["WELCOME_MESSAGE"] = self.msg.value
        save_config(cfg, interaction.guild.id)
        await interaction.response.send_message("✅ Message enregistré.", ephemeral=True)


class WelcomeViewFull(WelcomeView):
    @discord.ui.button(label="Éditer le message", style=discord.ButtonStyle.primary)
    async def editmsg(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WelcomeMsgModal())


@bot.command(name="welcome", aliases=["bienvenue"])
async def welcome_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    set_guild(ctx.guild.id)
    cfg = get_config(ctx.guild.id)
    color_hex = (cfg.get("WELCOME_COLOR") or "#57F287").replace("#", "")
    try:
        color = int(color_hex, 16)
    except Exception:
        color = 0x57F287
    preview = (cfg.get("WELCOME_MESSAGE") or "Bienvenue {mention} sur **{server}** !").format(
        mention=ctx.author.mention, user=str(ctx.author), server=ctx.guild.name, count=ctx.guild.member_count
    )
    embed = discord.Embed(title=f"Bienvenue sur {ctx.guild.name}", description=preview, color=color)
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    if ctx.guild.icon:
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url)
    if cfg.get("WELCOME_IMAGE"):
        embed.set_image(url=cfg["WELCOME_IMAGE"])
    embed.add_field(name="Salon", value=f"<#{cfg['WELCOME_CHANNEL_ID']}>" if cfg.get("WELCOME_CHANNEL_ID") else "*à définir*", inline=True)
    embed.add_field(name="Système", value="Activé" if cfg.get("WELCOME_ENABLED") else "Désactivé", inline=True)
    embed.add_field(name="Membres", value=str(ctx.guild.member_count), inline=True)
    embed.set_footer(text="Aperçu du message • {mention} {user} {server} {count}")
    await ctx.send(embed=embed, view=WelcomeViewFull(ctx.author.id))


class BoostView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=180)
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return is_owner(interaction.user.id)

    @discord.ui.select(cls=discord.ui.ChannelSelect, placeholder="Salon des boosts", channel_types=[discord.ChannelType.text])
    async def pick(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        set_guild(interaction.guild.id)
        cfg = get_config(interaction.guild.id)
        cfg["BOOST_CHANNEL_ID"] = select.values[0].id
        save_config(cfg, interaction.guild.id)
        await interaction.response.send_message(f"✅ Boosts → {select.values[0].mention}", ephemeral=True)


@bot.command(name="boost")
async def boost_setup_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    set_guild(ctx.guild.id)
    cfg = get_config(ctx.guild.id)
    ch = f"<#{cfg['BOOST_CHANNEL_ID']}>" if cfg.get("BOOST_CHANNEL_ID") else "non défini"
    await ctx.send(embed=discord.Embed(title="🚀 Boosts", description=f"Salon actuel : {ch}", color=0xF47FFF), view=BoostView(ctx.author.id))


class AnnonceView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=180)
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return is_owner(interaction.user.id)

    @discord.ui.select(cls=discord.ui.ChannelSelect, placeholder="Salon d'annonces", channel_types=[discord.ChannelType.text])
    async def pick(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        set_guild(interaction.guild.id)
        cfg = get_config(interaction.guild.id)
        cfg["ANNOUNCE_CHANNEL_ID"] = select.values[0].id
        save_config(cfg, interaction.guild.id)
        await interaction.response.send_message(f"✅ Annonces → {select.values[0].mention}", ephemeral=True)


@bot.command(name="annonce", aliases=["announce"])
async def annonce_cmd(ctx: commands.Context, *, message: str = None):
    if not await owner_check(ctx):
        return
    set_guild(ctx.guild.id)
    cfg = get_config(ctx.guild.id)
    if not message:
        ch = f"<#{cfg['ANNOUNCE_CHANNEL_ID']}>" if cfg.get("ANNOUNCE_CHANNEL_ID") else "non défini"
        await ctx.send(embed=discord.Embed(title="📢 Annonces", description=f"Salon : {ch}\nEnvoie : `+annonce ton texte`", color=0x5865F2), view=AnnonceView(ctx.author.id))
        return
    ch_id = cfg.get("ANNOUNCE_CHANNEL_ID")
    channel = ctx.guild.get_channel(int(ch_id)) if ch_id else ctx.channel
    embed = discord.Embed(title="📢 Annonce", description=message, color=0x5865F2, timestamp=discord.utils.utcnow())
    embed.set_footer(text=f"Par {ctx.author}")
    if channel:
        await channel.send(embed=embed)
        await ctx.send("✅ Annonce envoyée.", delete_after=5)


@bot.command(name="giverole", aliases=["addrole", "roleall"])
async def giverole_cmd(ctx: commands.Context, role: discord.Role = None, *, who: str = None):
    if not await owner_check(ctx):
        return
    if role is None:
        class GiveRoleView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=180)
                self.role = None
                self.user = None

            @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Rôle à donner")
            async def rsel(self, inter, select):
                self.role = select.values[0]
                await inter.response.send_message(f"Rôle : {self.role.mention}", ephemeral=True)

            @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Membre")
            async def usel(self, inter, select):
                self.user = select.values[0]
                await inter.response.send_message(f"Membre : {self.user.mention}", ephemeral=True)

            @discord.ui.button(label="Donner au membre", style=discord.ButtonStyle.success)
            async def give_one(self, inter, btn):
                if not self.role or not self.user:
                    await inter.response.send_message("Choisis un rôle et un membre.", ephemeral=True)
                    return
                m = inter.guild.get_member(self.user.id)
                if not m:
                    await inter.response.send_message("Membre introuvable.", ephemeral=True)
                    return
                try:
                    await m.add_roles(self.role, reason=f"giverole par {inter.user}")
                    await inter.response.send_message(f"{self.role.mention} → {m.mention}", ephemeral=True)
                except Exception as e:
                    await inter.response.send_message(f"❌ `{e}`", ephemeral=True)

            @discord.ui.button(label="Donner à tout le monde", style=discord.ButtonStyle.danger)
            async def give_all(self, inter, btn):
                if not self.role:
                    await inter.response.send_message("Choisis un rôle.", ephemeral=True)
                    return
                ok = fail = 0
                for m in [x for x in inter.guild.members if not x.bot]:
                    try:
                        await m.add_roles(self.role, reason=f"giverole all par {inter.user}")
                        ok += 1
                    except Exception:
                        fail += 1
                await inter.response.send_message(f"Donné à {ok} membres (échecs {fail}).", ephemeral=True)

        await ctx.send(embed=discord.Embed(title="Donner un rôle", description="Choisis le rôle, le membre, puis le bouton.", color=0x5865F2), view=GiveRoleView())
        return
    targets = []
    if who and who.lower().strip() == "all":
        targets = [m for m in ctx.guild.members if not m.bot]
    else:
        targets = list(ctx.message.mentions)
        if not targets and who:
            u = await resolve_user(ctx, who)
            if u:
                m = ctx.guild.get_member(u.id)
                if m:
                    targets = [m]
    if not targets:
        await ctx.send("❌ Aucune cible. Utilise `@user`, plusieurs mentions, ou `all`.")
        return
    ok, fail = 0, 0
    for m in targets:
        try:
            await m.add_roles(role, reason=f"giverole par {ctx.author}")
            ok += 1
        except Exception:
            fail += 1
    await ctx.send(f"✅ Rôle {role.mention} donné à **{ok}** membre(s) (échecs : {fail}).")


@bot.command(name="servers", aliases=["guilds", "serveurs"])
async def servers_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    for g in bot.guilds:
        set_guild(g.id)
        cfg = get_config(g.id)
        joined = cfg.get("BOT_JOINED_AT") or "inconnu"
        embed = discord.Embed(title=g.name, color=0x5865F2)
        embed.add_field(name="ID", value=str(g.id), inline=True)
        embed.add_field(name="Owner", value=f"<@{g.owner_id}>", inline=True)
        embed.add_field(name="Membres", value=str(g.member_count), inline=True)
        embed.add_field(name="Rôles", value=str(len(g.roles)), inline=True)
        embed.add_field(name="Créé", value=discord.utils.format_dt(g.created_at, "D"), inline=True)
        embed.add_field(name="Bot arrivé", value=joined[:19], inline=True)
        embed.add_field(name="Config", value=f"antilink `{cfg.get('ANTILINK')}` · antiraid `{cfg.get('ANTIRAID')}` · antinew `{cfg.get('ANTI_NEW_ACCOUNT')}`", inline=False)
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        await ctx.send(embed=embed)


@bot.command(name="gcancel", aliases=["gannule", "giveawaycancel"])
async def gcancel_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    if not ctx.message.reference:
        await ctx.send("❌ Réponds au message du giveaway avec `+gcancel`.")
        return
    gid = str(ctx.message.reference.message_id)
    giveaways = load_json(GIVEAWAYS_FILE, {})
    g = giveaways.get(gid)
    if not g:
        await ctx.send("❌ Giveaway introuvable.")
        return
    g["ended"] = True
    save_json(GIVEAWAYS_FILE, giveaways)
    try:
        msg = await ctx.channel.fetch_message(int(gid))
        embed = msg.embeds[0]
        embed.color = 0x95A5A6
        embed.description = (embed.description or "") + "\n\n❌ **Giveaway annulé.**"
        await msg.edit(embed=embed, view=None)
    except Exception:
        pass
    await ctx.send("✅ Giveaway annulé.")


@bot.command(name="autoreact")
async def autoreact_cmd(ctx: commands.Context, message_id: str = None, role: discord.Role = None, emoji: str = None):
    if not await owner_check(ctx):
        return
    if not message_id or role is None or not emoji:
        await ctx.send("❌ `+autoreact <id_message> @role emoji`\nClic sur l'emoji = rôle donné · retrait de la réaction = rôle enlevé.")
        return
    mid = extract_id(message_id) or (int(message_id) if str(message_id).isdigit() else None)
    if not mid:
        await ctx.send("❌ ID message invalide.")
        return
    conn = db()
    conn.execute(
        "INSERT OR REPLACE INTO reaction_roles(guild_id,message_id,emoji,role_id) VALUES(?,?,?,?)",
        (str(ctx.guild.id), str(mid), emoji, str(role.id))
    )
    conn.commit()
    conn.close()
    try:
        msg = await ctx.channel.fetch_message(mid)
        await msg.add_reaction(emoji)
    except Exception:
        for ch in ctx.guild.text_channels:
            try:
                msg = await ch.fetch_message(mid)
                await msg.add_reaction(emoji)
                break
            except Exception:
                continue
    await ctx.send(f"✅ {emoji} → {role.mention} sur le message `{mid}`")


@bot.command(name="rankstyle")
async def rankstyle_cmd(ctx: commands.Context, key: str = None, *, value: str = None):
    if not await owner_check(ctx):
        return
    cfg = get_levels_cfg()
    if key is None:
        await ctx.send(
            f"Carte XP :\nPolice `{cfg.get('card_font')}` · barre `{cfg.get('card_bar')}`\n"
            f"Overlay `{cfg.get('card_overlay')}%` · fond `{cfg.get('card_bg')}`\n"
            "`+rankstyle font sans|serif|mono`\n`+rankstyle bar #5865F2`\n`+rankstyle overlay 40`\n`+rankstyle bg #2B2D31`"
        )
        return
    key = key.lower()
    if key == "font" and value in ("sans", "serif", "mono"):
        cfg["card_font"] = value
    elif key == "bar" and value:
        cfg["card_bar"] = value if value.startswith("#") else f"#{value}"
    elif key == "overlay" and value and value.isdigit():
        cfg["card_overlay"] = max(0, min(100, int(value)))
    elif key == "bg" and value:
        cfg["card_bg"] = value if value.startswith("#") else f"#{value}"
    else:
        await ctx.send("❌ Clé invalide.")
        return
    save_levels_cfg(cfg)
    await ctx.send("✅ Style de carte enregistré. Teste avec `+rank`.")


@bot.command(name="automsg")
async def automsg_cmd(ctx: commands.Context, interval: str = None, *, message: str = None):
    if not await owner_check(ctx):
        return
    if not interval:
        rows = db_auto_msgs(ctx.guild.id)
        txt = "\n".join(f"`#{r['id']}` <#{r['channel_id']}> toutes les {r['interval_sec']}s — {r['content'][:40]}" for r in rows) or "Aucun"
        await ctx.send(f"**Messages auto**\n{txt}\n`+automsg 1h Bonjour` · `+automsg del 1`")
        return
    if interval.lower() in ("del", "delete") and message and message.isdigit():
        conn = db()
        conn.execute("DELETE FROM auto_messages WHERE id=? AND guild_id=?", (int(message), str(ctx.guild.id)))
        conn.commit()
        conn.close()
        await ctx.send("✅ Message auto supprimé.")
        return
    seconds = parse_duration(interval)
    if not seconds or not message:
        await ctx.send("❌ `+automsg 30m Texte`")
        return
    conn = db()
    conn.execute(
        "INSERT INTO auto_messages(guild_id,channel_id,content,interval_sec,last_sent,enabled) VALUES(?,?,?,?,0,1)",
        (str(ctx.guild.id), str(ctx.channel.id), message, seconds)
    )
    conn.commit()
    conn.close()
    await ctx.send(f"✅ Message auto toutes les **{interval}** dans {ctx.channel.mention}")


class CustomCmdView(discord.ui.View):
    def __init__(self, author_id: int, guild_id: int, names: list):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.guild_id = guild_id
        options = [discord.SelectOption(label=n, value=n) for n in names[:25]]
        if options:
            sel = discord.ui.Select(placeholder="Commande à gérer", options=options)

            async def cb(interaction: discord.Interaction):
                self.chosen = sel.values[0]
                await interaction.response.send_message(f"Sélection : `+{self.chosen}` — clique 🗑️ pour supprimer.", ephemeral=True)

            sel.callback = cb
            self.add_item(sel)

    @discord.ui.button(label="🗑️", style=discord.ButtonStyle.danger)
    async def trash(self, interaction: discord.Interaction, button: discord.ui.Button):
        name = getattr(self, "chosen", None)
        if not name:
            await interaction.response.send_message("Choisis d'abord une commande.", ephemeral=True)
            return
        db_del_custom(self.guild_id, name)
        await interaction.response.send_message(f"✅ `+{name}` supprimée.", ephemeral=True)


@bot.command(name="custom", aliases=["ccmd"])
async def custom_cmd(ctx: commands.Context, name: str = None, *, response: str = None):
    if not await owner_check(ctx):
        return
    if not name:
        cmds = db_custom_cmds(ctx.guild.id)
        listing = "\n".join(f"{'🟢' if c['enabled'] else '🔴'} `+{c['name']}`" for c in cmds) or "Aucune"
        await ctx.send(f"**Commandes perso**\n{listing}\n`+custom ping pong` · `+custom toggle ping`", view=CustomCmdView(ctx.author.id, ctx.guild.id, [c["name"] for c in cmds]))
        return
    name = name.lower().lstrip("+")
    if name == "toggle" and response:
        target = response.split()[0].lower()
        rows = db_custom_cmds(ctx.guild.id)
        hit = next((c for c in rows if c["name"] == target), None)
        if not hit:
            await ctx.send("❌ Introuvable.")
            return
        db_set_custom(ctx.guild.id, target, hit["response"], 0 if hit["enabled"] else 1)
        await ctx.send(f"✅ `+{target}` {'activée' if not hit['enabled'] else 'désactivée'}")
        return
    if not response:
        await ctx.send("❌ `+custom nom réponse`")
        return
    db_set_custom(ctx.guild.id, name, response, 1)
    await ctx.send(f"✅ Commande perso `+{name}` créée.")


@bot.command(name="automod")
async def automod_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    set_guild(ctx.guild.id)
    cfg = get_config(ctx.guild.id)
    embed = discord.Embed(title="Auto-modération", color=0xED4245)
    embed.add_field(name="Anti-lien", value="ON" if cfg.get("ANTILINK") else "OFF", inline=True)
    embed.add_field(name="Anti-raid", value="ON" if cfg.get("ANTIRAID") else "OFF", inline=True)
    embed.add_field(name="Anti-spam", value="ON" if cfg.get("ANTISPAM") else "OFF", inline=True)
    embed.add_field(name="Anti nouveau compte", value="ON" if cfg.get("ANTI_NEW_ACCOUNT") else "OFF", inline=True)
    embed.add_field(name="Invites", value="ON" if cfg.get("AUTOMOD_INVITES") else "OFF", inline=True)
    embed.add_field(name="Mass mention", value="ON" if cfg.get("AUTOMOD_MASSMENTION") else "OFF", inline=True)
    embed.set_footer(text="Utilise aussi +setup et +links")
    await ctx.send(embed=embed, view=SetupView(ctx.author.id))


def words_embed() -> discord.Embed:
    words = [w.lower() for w in load_json(BANNED_WORDS_FILE, [])]
    listing = "\n".join(f"• `{w}`" for w in words) or "*aucun mot interdit*"
    embed = discord.Embed(title="Mots interdits", description=listing, color=0xED4245)
    embed.set_footer(text="Ajoute / retire uniquement avec les boutons • timeout 20 min")
    return embed


class WordAddModal(discord.ui.Modal, title="Ajouter un mot interdit"):
    word = discord.ui.TextInput(label="Mot ou expression", placeholder="insulte", required=True, max_length=80)

    async def on_submit(self, interaction: discord.Interaction):
        w = str(self.word.value).strip().lower()
        words = [x.lower() for x in load_json(BANNED_WORDS_FILE, [])]
        if w not in words:
            words.append(w)
            save_json(BANNED_WORDS_FILE, words)
        await interaction.response.edit_message(embed=words_embed(), view=WordsView(interaction.user.id))


class WordsView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=300)
        self.author_id = author_id
        words = load_json(BANNED_WORDS_FILE, [])
        options = [discord.SelectOption(label=w[:100], value=w) for w in words[:25]]
        if options:
            sel = discord.ui.Select(placeholder="Mot à retirer", options=options)

            async def cb(interaction: discord.Interaction):
                chosen = sel.values[0]
                rest = [w for w in load_json(BANNED_WORDS_FILE, []) if w.lower() != chosen.lower()]
                save_json(BANNED_WORDS_FILE, rest)
                await interaction.response.edit_message(embed=words_embed(), view=WordsView(self.author_id))

            sel.callback = cb
            self.add_item(sel)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return is_owner(interaction.user.id)

    @discord.ui.button(label="Ajouter un mot", style=discord.ButtonStyle.success)
    async def add(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WordAddModal())

    @discord.ui.button(label="Tout vider", style=discord.ButtonStyle.danger)
    async def clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        save_json(BANNED_WORDS_FILE, [])
        await interaction.response.edit_message(embed=words_embed(), view=WordsView(self.author_id))

    @discord.ui.button(label="Rafraîchir", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=words_embed(), view=WordsView(self.author_id))


@bot.command(name="words", aliases=["mot", "mots", "filter", "censure"])
async def words_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    await ctx.send(embed=words_embed(), view=WordsView(ctx.author.id))


@bot.command(name="errors", aliases=["erreurs", "error"])
async def errors_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    def listing():
        rows = load_json(ERRORS_FILE, [])
        if not isinstance(rows, list) or not rows:
            return "*aucune erreur enregistrée*"
        lines = []
        for i, r in enumerate(reversed(rows[-15:]), 1):
            lines.append(f"**{i}.** `{r.get('kind')}` · {r.get('title')} · {str(r.get('detail'))[:80]}\n*{r.get('at','')}*")
        return "\n".join(lines)

    def diag_text():
        d = run_system_diagnostics()
        lines = []
        for c in d["checks"]:
            mark = "✅" if c["ok"] else "❌"
            lines.append(f"{mark} **{c['name']}** — {c['detail']}")
        return ("\n".join(lines)[:3900], d["ok"])

    class V(discord.ui.View):
        @discord.ui.button(label="Rafraîchir", style=discord.ButtonStyle.secondary)
        async def rf(self, inter, btn):
            await inter.response.edit_message(
                embed=discord.Embed(title="Erreurs", description=listing()[:3900], color=0xED4245),
                view=self,
            )

        @discord.ui.button(label="Diagnostic", style=discord.ButtonStyle.primary)
        async def dg(self, inter, btn):
            d = run_system_diagnostics()
            text = "\n".join(
                f"{'✅' if c['ok'] else '❌'} **{c['name']}** — {c['detail']}" for c in d["checks"]
            )
            emb = discord.Embed(
                title="Diagnostic système",
                description=text[:3500],
                color=0x57F287 if d["ok"] else 0xED4245,
            )
            if d.get("file"):
                emb.set_footer(text=f"Fichier : {d['file']}")
            await inter.response.edit_message(embed=emb, view=self)
            if d.get("file"):
                try:
                    await inter.followup.send(f"Rapport enregistré : `{d['file']}`", ephemeral=True)
                except Exception:
                    pass

        @discord.ui.button(label="Tout vider", style=discord.ButtonStyle.danger)
        async def cl(self, inter, btn):
            save_json(ERRORS_FILE, [])
            await inter.response.edit_message(
                embed=discord.Embed(title="Erreurs", description="Journal vidé.", color=0x57F287),
                view=self,
            )

    dumps = 0
    if os.path.isdir(ERROR_DUMP_DIR):
        dumps = len([x for x in os.listdir(ERROR_DUMP_DIR) if x.endswith(".json")])
    emb = discord.Embed(
        title="Gestion des erreurs",
        description=listing()[:3500],
        color=0xED4245,
    )
    emb.set_footer(text=f"Dumps détaillés : {dumps} dans data/error_dumps/")
    await ctx.send(embed=emb, view=V())

@bot.command(name="privvc", aliases=["vocalprive", "privatevc"])
async def privvc_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    cfg = get_config(ctx.guild.id)
    class V(discord.ui.View):
        @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.voice], placeholder="Salon créateur (hub)")
        async def hub(self, inter, sel):
            c = get_config(inter.guild.id)
            c["PRIVVC_HUB_ID"] = sel.values[0].id
            save_config(c, inter.guild.id)
            await inter.response.send_message(f"Hub : {sel.values[0].mention}", ephemeral=True)
        @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.category], placeholder="Catégorie des vocaux privés")
        async def cat(self, inter, sel):
            c = get_config(inter.guild.id)
            c["PRIVVC_CATEGORY_ID"] = sel.values[0].id
            save_config(c, inter.guild.id)
            await inter.response.send_message(f"Catégorie : {sel.values[0].name}", ephemeral=True)
    hub = f"<#{cfg['PRIVVC_HUB_ID']}>" if cfg.get("PRIVVC_HUB_ID") else "*non défini*"
    await ctx.send(embed=discord.Embed(title="Vocal privé auto", description=f"Hub actuel : {hub}\nRejoindre le hub = création d’un vocal privé, suppression s’il est vide.", color=0x5865F2), view=V())

@bot.command(name="rchannel")
async def rchannel_cmd(ctx: commands.Context, *, nom: str = None):
    if not await owner_check(ctx):
        return
    if nom:
        await ctx.channel.edit(name=nom[:100])
        await ctx.send(f"Salon renommé : **{nom}**")
        return
    class M(discord.ui.Modal, title="Renommer le salon"):
        n = discord.ui.TextInput(label="Nouveau nom", max_length=100)
        async def on_submit(self, inter):
            await inter.channel.edit(name=str(self.n.value)[:100])
            await inter.response.send_message(f"Renommé : **{self.n.value}**", ephemeral=True)
    class V(discord.ui.View):
        @discord.ui.button(label="Renommer", style=discord.ButtonStyle.primary)
        async def go(self, inter, btn):
            await inter.response.send_modal(M())
    await ctx.send("Renommer ce salon", view=V())

@bot.command(name="chdelete")
async def chdelete_cmd(ctx: commands.Context, channel: discord.TextChannel = None):
    if not await owner_check(ctx):
        return
    if channel:
        await ctx.send("Suppression…")
        await channel.delete(reason=f"chdelete {ctx.author}")
        return
    class V(discord.ui.View):
        @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Salon à supprimer")
        async def pick(self, inter, sel):
            ch = sel.values[0]
            try:
                await ch.delete(reason=f"chdelete {inter.user}")
                await inter.response.send_message("Salon supprimé.", ephemeral=True)
            except Exception as e:
                await inter.response.send_message(f"❌ `{e}`", ephemeral=True)
    await ctx.send("Choisis le salon à supprimer", view=V())

@bot.command(name="allban")
async def allban_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    bans = [entry async for entry in ctx.guild.bans(limit=200)]
    txt = "\n".join(f"• {e.user} (`{e.user.id}`)" for e in bans) or "*aucun*"
    await ctx.send(embed=discord.Embed(title=f"Bans ({len(bans)})", description=txt[:3900], color=0xED4245))

@bot.command(name="allrole")
async def allrole_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    txt = "\n".join(f"{r.mention} — {len(r.members)}" for r in ctx.guild.roles[:50])
    await ctx.send(embed=discord.Embed(title="Rôles", description=txt, color=0x5865F2))

@bot.command(name="vockick")
async def vockick_cmd(ctx: commands.Context, member: discord.Member):
    if not await owner_check(ctx):
        return
    if not member.voice:
        await ctx.send("Pas en vocal.")
        return
    await member.move_to(None)
    await ctx.send(f"{member.mention} exclu du vocal.")

@bot.command(name="vocmove")
async def vocmove_cmd(ctx: commands.Context, member: discord.Member, channel: discord.VoiceChannel):
    if not await owner_check(ctx):
        return
    await member.move_to(channel)
    await ctx.send(f"{member.mention} → {channel.mention}")

@bot.command(name="vockickall")
async def vockickall_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    n = 0
    for vc in ctx.guild.voice_channels:
        for m in list(vc.members):
            try:
                await m.move_to(None)
                n += 1
            except Exception:
                pass
    await ctx.send(f"{n} membre(s) exclus des vocaux.")

@bot.command(name="bl-voice", aliases=["blvoice"])
async def blvoice_cmd(ctx: commands.Context, member: discord.Member = None):
    if not await owner_check(ctx):
        return
    async def apply(m):
        bl = [int(x) for x in load_json(VOICE_BL_FILE, [])]
        if m.id not in bl:
            bl.append(m.id)
            save_json(VOICE_BL_FILE, bl)
        if m.voice:
            try:
                await m.move_to(None)
            except Exception:
                pass
    if member:
        await apply(member)
        await ctx.send(f"{member.mention} blacklist vocal.")
        return
    class V(discord.ui.View):
        @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Membre")
        async def pick(self, inter, sel):
            m = inter.guild.get_member(sel.values[0].id)
            if m:
                await apply(m)
            await inter.response.send_message("Blacklist vocal ajoutée.", ephemeral=True)
    await ctx.send("Blacklist vocal", view=V())

@bot.command(name="bl-vlist", aliases=["blvlist"])
async def blvlist_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    bl = load_json(VOICE_BL_FILE, [])
    await ctx.send("\n".join(f"<@{i}>" for i in bl) or "*vide*")

def _inv(gid):
    data = load_json(INVITES_FILE, {})
    data.setdefault(str(gid), {})
    return data

@bot.command(name="invites-add")
async def invadd_cmd(ctx: commands.Context, member: discord.Member, n: int = 1):
    if not await owner_check(ctx):
        return
    data = _inv(ctx.guild.id)
    uid = str(member.id)
    data[str(ctx.guild.id)][uid] = int(data[str(ctx.guild.id)].get(uid) or 0) + n
    save_json(INVITES_FILE, data)
    await ctx.send(f"{member.mention} : **{data[str(ctx.guild.id)][uid]}** invitations")

@bot.command(name="invites-info")
async def invinfo_cmd(ctx: commands.Context, member: discord.Member = None):
    member = member or ctx.author
    data = _inv(ctx.guild.id)
    await ctx.send(f"{member.mention} : **{data[str(ctx.guild.id)].get(str(member.id), 0)}** invitations")

@bot.command(name="invites-leaderboard")
async def invlb_cmd(ctx: commands.Context):
    data = _inv(ctx.guild.id).get(str(ctx.guild.id), {})
    rows = sorted(data.items(), key=lambda x: int(x[1]), reverse=True)[:15]
    txt = "\n".join(f"**{i+1}.** <@{u}> — {n}" for i, (u, n) in enumerate(rows)) or "*vide*"
    await ctx.send(embed=discord.Embed(title="Invitations", description=txt, color=0x57F287))

@bot.command(name="invites-remove")
async def invrm_cmd(ctx: commands.Context, member: discord.Member, n: int = 1):
    if not await owner_check(ctx):
        return
    data = _inv(ctx.guild.id)
    uid = str(member.id)
    data[str(ctx.guild.id)][uid] = max(0, int(data[str(ctx.guild.id)].get(uid) or 0) - n)
    save_json(INVITES_FILE, data)
    await ctx.send(f"{member.mention} : **{data[str(ctx.guild.id)][uid]}**")

@bot.command(name="invites-reset")
async def invreset_cmd(ctx: commands.Context, member: discord.Member):
    if not await owner_check(ctx):
        return
    data = _inv(ctx.guild.id)
    data[str(ctx.guild.id)][str(member.id)] = 0
    save_json(INVITES_FILE, data)
    await ctx.send(f"Invites de {member.mention} à 0.")

@bot.command(name="ticket-rename")
async def ticketrename_cmd(ctx: commands.Context, *, nom: str = None):
    if not await owner_check(ctx):
        return
    if not nom:
        return
    await ctx.channel.edit(name=nom[:100])
    await ctx.send(f"Ticket : **{nom}**")

@bot.command(name="giveaway-list", aliases=["glist"])
async def glist_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    g = load_json(GIVEAWAYS_FILE, {})
    txt = "\n".join(f"`{k}` — {v.get('prize','?')} {'terminé' if v.get('ended') else 'en cours'}" for k, v in g.items()) or "*aucun*"
    await ctx.send(embed=discord.Embed(title="Giveaways", description=txt[:3900]))

@bot.command(name="giveaway-reset")
async def greset_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    save_json(GIVEAWAYS_FILE, {})
    await ctx.send("Giveaways vidés.")

@bot.command(name="giveaway-win")
async def gwin_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    await ctx.invoke(bot.get_command("reroll"))

@bot.command(name="giveaway-edit")
async def gedit_cmd(ctx: commands.Context, *, prize: str = None):
    if not await owner_check(ctx):
        return
    if not ctx.message.reference or not prize:
        await ctx.send("Réponds au giveaway : `+giveaway-edit nouveau prix`")
        return
    mid = str(ctx.message.reference.message_id)
    g = load_json(GIVEAWAYS_FILE, {})
    if mid in g:
        g[mid]["prize"] = prize
        save_json(GIVEAWAYS_FILE, g)
        await ctx.send(f"Prix : **{prize}**")

@bot.command(name="giveaway-end")
async def gend2_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    cmd = bot.get_command("gend")
    if cmd:
        await ctx.invoke(cmd)

@bot.command(name="lockall")
async def lockall_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    n = 0
    for ch in ctx.guild.text_channels:
        try:
            await ch.set_permissions(ctx.guild.default_role, send_messages=False)
            n += 1
        except Exception:
            pass
    await ctx.send(f"{n} salons lock.")

@bot.command(name="unbanall")
async def unbanall_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    n = 0
    async for e in ctx.guild.bans(limit=500):
        try:
            await ctx.guild.unban(e.user)
            n += 1
        except Exception:
            pass
    await ctx.send(f"{n} unban.")

@bot.command(name="slowmode")
async def slowmode_cmd(ctx: commands.Context, seconds: int = None, channel: discord.TextChannel = None):
    if not await owner_check(ctx):
        return
    if seconds is not None:
        ch = channel or ctx.channel
        await ch.edit(slowmode_delay=max(0, min(21600, seconds)))
        await ctx.send(f"Slowmode {ch.mention} : **{seconds}s**")
        return
    class V(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.ch = ctx.channel
        @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Salon")
        async def pick(self, inter, sel):
            self.ch = sel.values[0]
            await inter.response.send_message(f"Salon : {self.ch.mention}", ephemeral=True)
        async def setd(self, inter, sec):
            await self.ch.edit(slowmode_delay=sec)
            await inter.response.send_message(f"Slowmode {sec}s", ephemeral=True)
        @discord.ui.button(label="OFF", style=discord.ButtonStyle.secondary)
        async def off(self, i, b):
            await self.setd(i, 0)
        @discord.ui.button(label="5s", style=discord.ButtonStyle.primary)
        async def s5(self, i, b):
            await self.setd(i, 5)
        @discord.ui.button(label="10s", style=discord.ButtonStyle.primary)
        async def s10(self, i, b):
            await self.setd(i, 10)
        @discord.ui.button(label="30s", style=discord.ButtonStyle.primary)
        async def s30(self, i, b):
            await self.setd(i, 30)
    await ctx.send("Slowmode", view=V())

@bot.command(name="jeu2048", aliases=["2048"])
async def game2048_cmd(ctx: commands.Context):
    grid = [[0]*4 for _ in range(4)]

    def spawn():
        empty = [(i, j) for i in range(4) for j in range(4) if grid[i][j] == 0]
        if empty:
            i, j = random.choice(empty)
            grid[i][j] = 2

    def show():
        return "```\n" + "\n".join(" ".join(f"{n or '.':>4}" for n in row) for row in grid) + "\n```"

    spawn(); spawn()
    await ctx.send("2048 — dis haut/bas/gauche/droite\n" + show())

@bot.command(name="findemoji")
async def findemoji_cmd(ctx: commands.Context):
    target = random.choice(["🍎", "🍌", "🍇", "🍓", "🍑"])
    pool = ["🍎", "🍌", "🍇", "🍓", "🍑", "🍉", "🥝"]
    line = " ".join(random.choice(pool) for _ in range(12))
    await ctx.send(f"Trouve {target} !\n{line}")

@bot.command(name="snake")
async def snake_cmd(ctx: commands.Context):
    await ctx.send("Snake : `● ● ● ○` — dis gauche/droite pour jouer (version simple).")

# ----- Jeux exclusifs Core -----

@bot.command(name="coreguess", aliases=["cguess", "nombre"])
async def coreguess_cmd(ctx: commands.Context):
    """Devine le nombre secret Core (1-50)."""
    secret = random.randint(1, 50)
    tries = 6
    await ctx.send(f"**Core Guess** — nombre entre 1 et 50. **{tries}** essais. Envoie un nombre.")

    def check(m):
        return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id and m.content.strip().isdigit()

    while tries > 0:
        try:
            msg = await bot.wait_for("message", timeout=45.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send(f"Temps écoulé. C’était **{secret}**.")
            return
        n = int(msg.content.strip())
        tries -= 1
        if n == secret:
            await ctx.send(f"**Gagné !** `{secret}` trouvé. +XP Core ✨")
            return
        hint = "plus haut ⬆️" if n < secret else "plus bas ⬇️"
        await ctx.send(f"{hint} — essais restants : **{tries}**")
    await ctx.send(f"Perdu. Le nombre était **{secret}**.")

@bot.command(name="corememory", aliases=["cmemory", "memoire"])
async def corememory_cmd(ctx: commands.Context):
    """Mémorise la séquence d’émojis Core."""
    pool = ["🔷", "🔶", "🟢", "🟣", "⚫", "🟡"]
    seq = [random.choice(pool) for _ in range(4)]
    board = " ".join(seq)
    msg = await ctx.send(f"**Core Memory** — mémorise :\n## {board}")
    await asyncio.sleep(3.5)
    try:
        await msg.edit(content="**Core Memory** — écris la séquence (émojis séparés par des espaces)")
    except Exception:
        pass

    def check(m):
        return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

    try:
        ans = await bot.wait_for("message", timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send(f"Trop lent. Réponse : {' '.join(seq)}")
        return
    got = ans.content.replace(",", " ").split()
    if got == seq:
        await ctx.send("**Parfait !** Mémoire Core validée.")
    else:
        await ctx.send(f"Raté. C’était : {' '.join(seq)}")

@bot.command(name="coreduel", aliases=["cduel"])
async def coreduel_cmd(ctx: commands.Context, adversaire: discord.Member = None):
    """Duel de dés exclusif Core."""
    if adversaire is None or adversaire.bot or adversaire.id == ctx.author.id:
        await ctx.send("Utilise `+coreduel @membre`")
        return
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    if a > b:
        win = ctx.author.mention
    elif b > a:
        win = adversaire.mention
    else:
        win = "Égalité"
    emb = discord.Embed(title="Core Duel", color=0x5865F2)
    emb.add_field(name=str(ctx.author), value=f"🎲 **{a}**", inline=True)
    emb.add_field(name=str(adversaire), value=f"🎲 **{b}**", inline=True)
    emb.add_field(name="Résultat", value=win, inline=False)
    await ctx.send(embed=emb)

@bot.command(name="corequiz", aliases=["cquiz"])
async def corequiz_cmd(ctx: commands.Context):
    """Mini quiz exclusif Core."""
    qas = [
        ("Quelle est la couleur officielle Discord (approx) ?", ["blurple", "bleu", "bleu violet"]),
        ("Préfixe par défaut de ce bot ?", ["+", "plus"]),
        ("Combien de boosts pour le niveau 1 nitro serveur ?", ["2", "deux"]),
    ]
    q, answers = random.choice(qas)
    await ctx.send(f"**Core Quiz**\n{q}")

    def check(m):
        return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

    try:
        msg = await bot.wait_for("message", timeout=25.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send(f"Temps écoulé. Réponses acceptées : {', '.join(answers)}")
        return
    if msg.content.strip().lower() in answers:
        await ctx.send("**Bonne réponse !**")
    else:
        await ctx.send(f"Non. Réponses : {', '.join(answers)}")

@bot.command(name="coreflip", aliases=["cflip"])
async def coreflip_cmd(ctx: commands.Context, choix: str = None):
    """Pile ou face Core."""
    if not choix or choix.lower() not in ("pile", "face"):
        await ctx.send("`+coreflip pile` ou `+coreflip face`")
        return
    res = random.choice(["pile", "face"])
    win = res == choix.lower()
    await ctx.send(f"**Core Flip** → **{res}** — {'gagné' if win else 'perdu'} !")

@bot.command(name="webhook", aliases=["wh", "webhooks"])
async def webhook_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    hooks = load_json(WEBHOOKS_FILE, {})
    if not isinstance(hooks, dict):
        hooks = {}

    def listing():
        if not hooks:
            return "*aucun webhook lié*"
        return "\n".join(f"• `{n}` → <#{h.get('channel')}>" for n, h in hooks.items())

    class WHView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)

        @discord.ui.button(label="Créer ici", style=discord.ButtonStyle.success)
        async def create(self, inter, btn):
            class M(discord.ui.Modal, title="Créer un webhook"):
                n = discord.ui.TextInput(label="Nom", default="core", max_length=80)
                async def on_submit(self2, i):
                    try:
                        wh = await i.channel.create_webhook(name=str(self2.n.value)[:80], reason=f"par {i.user}")
                        hooks[str(self2.n.value).lower()] = {
                            "url": wh.url,
                            "channel": i.channel.id,
                            "by": i.user.id,
                        }
                        save_json(WEBHOOKS_FILE, hooks)
                        try:
                            await i.user.send(f"Webhook `{self2.n.value}` : ||{wh.url}||")
                        except Exception:
                            pass
                        await i.response.send_message(f"Créé dans {i.channel.mention} (URL en MP si possible).", ephemeral=True)
                    except Exception as e:
                        await i.response.send_message(f"Erreur : `{e}`", ephemeral=True)
            await inter.response.send_modal(M())

        @discord.ui.button(label="Lier une URL", style=discord.ButtonStyle.primary)
        async def link(self, inter, btn):
            class M(discord.ui.Modal, title="Lier un webhook"):
                n = discord.ui.TextInput(label="Nom")
                u = discord.ui.TextInput(label="URL webhook")
                async def on_submit(self2, i):
                    hooks[str(self2.n.value).lower()] = {
                        "url": str(self2.u.value).strip(),
                        "channel": i.channel.id,
                        "by": i.user.id,
                    }
                    save_json(WEBHOOKS_FILE, hooks)
                    await i.response.send_message(f"**{self2.n.value}** lié.", ephemeral=True)
            await inter.response.send_modal(M())

        @discord.ui.button(label="Envoyer", style=discord.ButtonStyle.secondary)
        async def send(self, inter, btn):
            class M(discord.ui.Modal, title="Envoyer via webhook"):
                n = discord.ui.TextInput(label="Nom du webhook")
                m = discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph)
                async def on_submit(self2, i):
                    h = hooks.get(str(self2.n.value).lower())
                    if not h or not h.get("url"):
                        await i.response.send_message("Webhook inconnu.", ephemeral=True)
                        return
                    try:
                        async with aiohttp.ClientSession() as s:
                            async with s.post(h["url"], json={"content": str(self2.m.value)[:2000]}) as r:
                                if r.status < 300:
                                    await i.response.send_message("Message envoyé.", ephemeral=True)
                                else:
                                    await i.response.send_message(f"Erreur HTTP {r.status}", ephemeral=True)
                    except Exception as e:
                        await i.response.send_message(f"`{e}`", ephemeral=True)
            await inter.response.send_modal(M())

        @discord.ui.button(label="Supprimer", style=discord.ButtonStyle.danger)
        async def delete(self, inter, btn):
            class M(discord.ui.Modal, title="Supprimer un webhook enregistré"):
                n = discord.ui.TextInput(label="Nom")
                async def on_submit(self2, i):
                    key = str(self2.n.value).lower()
                    if key in hooks:
                        hooks.pop(key, None)
                        save_json(WEBHOOKS_FILE, hooks)
                        await i.response.send_message(f"**{key}** retiré de la liste.", ephemeral=True)
                    else:
                        await i.response.send_message("Introuvable.", ephemeral=True)
            await inter.response.send_modal(M())

        @discord.ui.button(label="Rafraîchir", style=discord.ButtonStyle.secondary)
        async def refresh(self, inter, btn):
            await inter.response.edit_message(
                embed=discord.Embed(title="Webhooks", description=listing(), color=0x5865F2),
                view=self,
            )

    await ctx.send(
        embed=discord.Embed(title="Webhooks", description=listing(), color=0x5865F2),
        view=WHView(),
    )

HELP_CATS = {
    "accueil": ("Accueil", None),
    "proprio": ("Propriétaire", "`+owner` `+owner @user` `+unowner` `+owner reset`\n`+ownerplus` `+debug` `+restart` `+status` `+servers`\n`+botprofile` `+serverprofile` `+resetsetup`"),
    "modo": ("Modération", "`+kick` `+ban` `+unban` `+unbanall` `+mute`\n`+bl` `+derank` `+lockall` `+slowmode` `+vockick` `+vocmove`"),
    "serveur": ("Serveur", "`+setup` `+rchannel` `+chdelete` `+allban` `+allrole`\n`+bl-voice` `+lockall` `+giverole` `+perms`"),
    "tickets": (
        "Tickets",
        "MP le bot · boutons Claim / Fermer\n"
        "`+close` · `+close T-XXXX` — fermer un ticket\n"
        "`+reopen T-XXXX` — réouvrir un ticket\n"
        "`+ticketinfo T-XXXX` — infos ticket\n"
        "`+giveclaim @staff` · `+add` · `+remove`",
    ),
    "niveaux": ("Niveaux", "`+levels` `+rank` `+rankstyle` `+top`\n`+adminxp` `+adminremovexp`"),
    "auto": ("Auto", "`+custom` `+automsg` `+autoreact` `+automod` `+anniv` `+suggest`"),
    "fun": ("Jeux & fun", "`+pendu` `+bingo` `+morpion` `+quiz` `+pfc`\n`+coreguess` `+corememory` `+coreduel` `+corequiz` `+coreflip`\n`+2048` `+findemoji` `+snake`"),
    "texte": ("Texte", "`+grostexte` `+ascii` `+binaire` `+clap` `+robot` `+flip`"),
    "msg": ("Messages / Giveaway", "`+dm` `+say` `+embed` `+snipe` `+clear` `+copy`\n`+giveaway` `+gend` `+gcancel` `+reroll`"),
}

def help_embed(page: str = "accueil") -> discord.Embed:
    embed = discord.Embed(color=0x5865F2, timestamp=discord.utils.utcnow())
    embed.set_footer(text=f"v{BOT_VERSION} · {len(bot.commands)} commandes · préfixe +")
    if page == "accueil":
        embed.title = "Menu d'aide"
        embed.description = (
            f"**{len(bot.commands)}** commandes disponibles\n"
            f"Version **{BOT_VERSION}** · Créé par **{BOT_CREATOR}**\n\n"
            "Choisis une catégorie dans le menu déroulant."
        )
        embed.add_field(name="Catégories", value="\n".join(f"• {v[0]}" for k, v in HELP_CATS.items() if k != "accueil"), inline=False)
    else:
        title, body = HELP_CATS.get(page, ("Aide", ""))
        embed.title = title
        embed.description = body
    return embed

class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=v[0], value=k) for k, v in HELP_CATS.items()]
        super().__init__(placeholder="Choisir une catégorie…", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=help_embed(self.values[0]), view=HelpView())

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(HelpSelect())

@bot.command(name="help")
async def help_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    await ctx.send(embed=help_embed(), view=HelpView())

@bot.command(name="botprofile")
async def botprofile_cmd(ctx: commands.Context, action: str = None, *, value: str = None):
    if not await owner_check(ctx):
        return
    if action is None:
        await ctx.send("Usage :\n`+botprofile name NouveauNom`\n`+botprofile avatar` (image jointe)\n`+botprofile desc Texte`")
        return
    action = action.lower()
    try:
        if action in ("name", "nom"):
            await bot.user.edit(username=value)
            await ctx.send(f"✅ Nom du bot : **{value}**")
        elif action in ("avatar", "pp", "photo"):
            if not ctx.message.attachments:
                await ctx.send("❌ Joins une image.")
                return
            data = await ctx.message.attachments[0].read()
            await bot.user.edit(avatar=data)
            await ctx.send("✅ Photo de profil du bot mise à jour.")
        elif action in ("desc", "description", "bio"):
            await ctx.send("La description publique se règle aussi sur le portail développeur Discord.")
        else:
            await ctx.send("❌ Actions : `name` `avatar` `desc`")
    except Exception as e:
        await ctx.send(f"❌ `{e}`")

@bot.command(name="serverprofile")
async def serverprofile_cmd(ctx: commands.Context, action: str = None, *, value: str = None):
    if not await owner_check(ctx):
        return
    if not ctx.guild:
        return
    if action is None:
        await ctx.send("Usage :\n`+serverprofile name NouveauNom`\n`+serverprofile icon` (image jointe)\n`+serverprofile desc Texte`")
        return
    action = action.lower()
    try:
        if action in ("name", "nom"):
            await ctx.guild.edit(name=value)
            await ctx.send(f"✅ Serveur renommé : **{value}**")
        elif action in ("icon", "pp", "photo"):
            if not ctx.message.attachments:
                await ctx.send("❌ Joins une image.")
                return
            data = await ctx.message.attachments[0].read()
            await ctx.guild.edit(icon=data)
            await ctx.send("✅ Icône du serveur mise à jour.")
        elif action in ("desc", "description"):
            await ctx.guild.edit(description=value)
            await ctx.send("✅ Description du serveur mise à jour.")
        else:
            await ctx.send("❌ Actions : `name` `icon` `desc`")
    except discord.Forbidden:
        await ctx.send("❌ Permissions insuffisantes.")
    except Exception as e:
        await ctx.send(f"❌ `{e}`")

@bot.command(name="createrole")
async def createrole_cmd(ctx: commands.Context, *, name: str = None):
    if not await owner_check(ctx):
        return
    if not name:
        class CRView(discord.ui.View):
            @discord.ui.button(label="Créer un rôle", style=discord.ButtonStyle.success)
            async def cr(self, inter, btn):
                class M(discord.ui.Modal, title="Nouveau rôle"):
                    n = discord.ui.TextInput(label="Nom du rôle", required=True, max_length=100)

                    async def on_submit(self2, i):
                        role = await i.guild.create_role(name=str(self2.n.value), reason=f"Par {i.user}")
                        await i.response.send_message(f"Rôle créé : {role.mention}", ephemeral=True)
                await inter.response.send_modal(M())
        await ctx.send(embed=discord.Embed(title="Créer un rôle", description="Clique pour entrer le nom.", color=0x57F287), view=CRView())
        return
    try:
        role = await ctx.guild.create_role(name=name, reason=f"Par {ctx.author}")
        await ctx.send(f"✅ Rôle {role.mention} créé. Utilise `+perms` pour les permissions.")
    except Exception as e:
        await ctx.send(f"❌ `{e}`")

@bot.command(name="delrole")
async def delrole_cmd(ctx: commands.Context, role: discord.Role = None):
    if not await owner_check(ctx):
        return
    if role is None:
        class DRView(discord.ui.View):
            @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Rôle à supprimer")
            async def pick(self, inter, select):
                r = select.values[0]
                try:
                    await r.delete(reason=f"Par {inter.user}")
                    await inter.response.send_message(f"Rôle **{r.name}** supprimé.", ephemeral=True)
                except Exception as e:
                    await inter.response.send_message(f"❌ `{e}`", ephemeral=True)
        await ctx.send(embed=discord.Embed(title="Supprimer un rôle", description="Choisis le rôle dans la liste.", color=0xED4245), view=DRView())
        return
    try:
        await role.delete(reason=f"Par {ctx.author}")
        await ctx.send(f"✅ Rôle **{role.name}** supprimé.")
    except Exception as e:
        await ctx.send(f"❌ `{e}`")

@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if not payload.guild_id or payload.user_id == getattr(bot.user, "id", 0):
        return
    conn = db()
    row = conn.execute(
        "SELECT role_id FROM reaction_roles WHERE guild_id=? AND message_id=? AND emoji=?",
        (str(payload.guild_id), str(payload.message_id), str(payload.emoji))
    ).fetchone()
    conn.close()
    if not row:
        return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id) if guild else None
    role = guild.get_role(int(row["role_id"])) if guild else None
    if member and role:
        try:
            await member.add_roles(role, reason="autoreact")
        except Exception:
            pass


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    if not payload.guild_id:
        return
    conn = db()
    row = conn.execute(
        "SELECT role_id FROM reaction_roles WHERE guild_id=? AND message_id=? AND emoji=?",
        (str(payload.guild_id), str(payload.message_id), str(payload.emoji))
    ).fetchone()
    conn.close()
    if not row:
        return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id) if guild else None
    role = guild.get_role(int(row["role_id"])) if guild else None
    if member and role:
        try:
            await member.remove_roles(role, reason="autoreact remove")
        except Exception:
            pass


@tasks.loop(seconds=30)
async def temprole_loop():
    data = load_json(TEMPROLES_FILE, {})
    now = time.time()
    changed = False
    for key, rows in list(data.items()):
        keep = []
        for row in rows:
            if float(row.get("until", 0)) > now:
                keep.append(row)
                continue
            guild = bot.get_guild(int(row.get("guild_id") or 0))
            if guild:
                member = guild.get_member(int(row.get("user_id") or 0))
                role = guild.get_role(int(row.get("role_id") or 0))
                if member and role:
                    try:
                        await member.remove_roles(role, reason="temprole expiré")
                    except Exception:
                        pass
            changed = True
        if keep:
            data[key] = keep
        else:
            data.pop(key, None)
            changed = True
    if changed:
        save_json(TEMPROLES_FILE, data)


def _uid_store(path, uid):
    data = load_json(path, {})
    return data, data.setdefault(str(uid), [])


@bot.command(name="infraction")
async def infraction_cmd(ctx: commands.Context, raw: str = None):
    if not await owner_check(ctx):
        return
    target = await resolve_user(ctx, raw) if raw or ctx.message.mentions else None
    if target is None:
        await ctx.send("Mentionne un membre : `+infraction @user`")
        return
    data, items = _uid_store(INFRACTIONS_FILE, target.id)

    class AddM(discord.ui.Modal, title="Ajouter une infraction"):
        raison = discord.ui.TextInput(label="Raison", required=True, max_length=200)

        async def on_submit(self, interaction):
            items.append({"raison": str(self.raison.value), "by": ctx.author.id, "at": datetime.now().isoformat()})
            data[str(target.id)] = items
            save_json(INFRACTIONS_FILE, data)
            await interaction.response.send_message("Infraction ajoutée.", ephemeral=True)

    class V(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
            if items:
                sel = discord.ui.Select(placeholder="Retirer une infraction", options=[
                    discord.SelectOption(label=f"{i+1}. {x['raison'][:80]}", value=str(i)) for i, x in enumerate(items[:25])
                ])

                async def cb(inter):
                    items.pop(int(sel.values[0]))
                    data[str(target.id)] = items
                    save_json(INFRACTIONS_FILE, data)
                    await inter.response.send_message("Retirée.", ephemeral=True)
                sel.callback = cb
                self.add_item(sel)

        @discord.ui.button(label="Ajouter", style=discord.ButtonStyle.success)
        async def add(self, inter, btn):
            await inter.response.send_modal(AddM())

        @discord.ui.button(label="Liste", style=discord.ButtonStyle.secondary)
        async def lst(self, inter, btn):
            txt = "\n".join(f"**{i+1}.** {x['raison']}" for i, x in enumerate(items)) or "Aucune"
            await inter.response.send_message(txt[:1900], ephemeral=True)

    listing = "\n".join(f"**{i+1}.** {x['raison']}" for i, x in enumerate(items)) or "*aucune*"
    await ctx.send(embed=discord.Embed(title=f"Infractions — {target}", description=listing, color=0xED4245), view=V())


@bot.command(name="note")
async def note_cmd(ctx: commands.Context, raw: str = None, *, texte: str = None):
    if not await owner_check(ctx):
        return
    target = await resolve_user(ctx, raw) if raw or ctx.message.mentions else None
    data = load_json(NOTES_FILE, {})
    if target and texte:
        data.setdefault(str(target.id), []).append({"note": texte, "by": ctx.author.id, "at": datetime.now().isoformat()})
        save_json(NOTES_FILE, data)
        await ctx.send(f"Note ajoutée pour {target.mention}")
        return

    class NoteView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
            self.user = target

        @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Choisir un membre")
        async def pick(self, inter, select):
            self.user = select.values[0]
            notes = load_json(NOTES_FILE, {}).get(str(self.user.id), [])
            txt = "\n".join(f"• {n['note']}" for n in notes) or "*aucune note*"
            await inter.response.send_message(f"Notes de {self.user.mention}\n{txt}", ephemeral=True)

        @discord.ui.button(label="Ajouter une note", style=discord.ButtonStyle.success)
        async def add(self, inter, btn):
            if not self.user:
                await inter.response.send_message("Choisis d'abord un membre.", ephemeral=True)
                return

            class M(discord.ui.Modal, title="Nouvelle note"):
                t = discord.ui.TextInput(label="Note", style=discord.TextStyle.paragraph, required=True)

                async def on_submit(self2, i):
                    d = load_json(NOTES_FILE, {})
                    d.setdefault(str(self.user.id), []).append({"note": str(self2.t.value), "by": i.user.id, "at": datetime.now().isoformat()})
                    save_json(NOTES_FILE, d)
                    await i.response.send_message("Note ajoutée.", ephemeral=True)
            await inter.response.send_modal(M())

    desc = ""
    if target:
        notes = data.get(str(target.id), [])
        desc = "\n".join(f"• {n['note']}" for n in notes) or "*aucune note*"
    await ctx.send(embed=discord.Embed(title="Notes staff", description=desc or "Choisis un membre puis ajoute une note.", color=0xFEE75C), view=NoteView())


@bot.command(name="sanction")
async def sanction_cmd(ctx: commands.Context, action: str = None, index: int = None):
    if not await owner_check(ctx):
        return
    data = load_json(SANCTIONS_FILE, [])
    if action == "remove" and index:
        if 1 <= index <= len(data):
            data.pop(index - 1)
            save_json(SANCTIONS_FILE, data)
            await ctx.send("Sanction retirée.")
        else:
            await ctx.send("Index invalide.")
        return
    if action == "add" or ctx.message.mentions:
        target = ctx.message.mentions[0] if ctx.message.mentions else None
        raison = " ".join(ctx.message.content.split()[2:]) if action == "add" else "sanction"
        if target:
            data.append({"user": target.id, "raison": raison, "by": ctx.author.id, "at": datetime.now().isoformat()})
            save_json(SANCTIONS_FILE, data)
            await ctx.send(f"Sanction ajoutée pour {target.mention}")
            return
    lines = [f"**{i+1}.** <@{s['user']}> — {s.get('raison','')}" for i, s in enumerate(data)] or ["*aucune*"]

    class SanctionsView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
            self.user = None
            if data:
                sel = discord.ui.Select(placeholder="Retirer une sanction", options=[
                    discord.SelectOption(label=f"{i+1}. {s.get('raison','')[:80]}", value=str(i)) for i, s in enumerate(data[:25])
                ])

                async def cb(inter):
                    d = load_json(SANCTIONS_FILE, [])
                    d.pop(int(sel.values[0]))
                    save_json(SANCTIONS_FILE, d)
                    await inter.response.send_message("Sanction retirée.", ephemeral=True)
                sel.callback = cb
                self.add_item(sel)

        @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Membre à sanctionner")
        async def pick(self, inter, select):
            self.user = select.values[0]
            await inter.response.send_message(f"Cible : {self.user.mention}", ephemeral=True)

        @discord.ui.button(label="Ajouter", style=discord.ButtonStyle.danger)
        async def add(self, inter, btn):
            if not self.user:
                await inter.response.send_message("Choisis un membre.", ephemeral=True)
                return

            class M(discord.ui.Modal, title="Sanction"):
                r = discord.ui.TextInput(label="Raison", required=True)

                async def on_submit(self2, i):
                    d = load_json(SANCTIONS_FILE, [])
                    d.append({"user": self.user.id, "raison": str(self2.r.value), "by": i.user.id, "at": datetime.now().isoformat()})
                    save_json(SANCTIONS_FILE, d)
                    await i.response.send_message("Ajoutée.", ephemeral=True)
            await inter.response.send_modal(M())

    await ctx.send(embed=discord.Embed(title="Sanctions", description="\n".join(lines)[:3900], color=0xED4245), view=SanctionsView())


@bot.command(name="temprole")
async def temprole_cmd(ctx: commands.Context, action: str = None, raw: str = None, role: discord.Role = None, duree: str = None):
    if not await owner_check(ctx):
        return
    store = load_json(TEMPROLES_FILE, {})
    if action is None:
        class TRView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=180)
                self.member = None
                self.role = None

            @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Membre")
            async def um(self, inter, select):
                self.member = select.values[0]
                await inter.response.send_message(f"Membre : {self.member.mention}", ephemeral=True)

            @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Rôle")
            async def rm(self, inter, select):
                self.role = select.values[0]
                await inter.response.send_message(f"Rôle : {self.role.mention}", ephemeral=True)

            @discord.ui.button(label="Donner 1h", style=discord.ButtonStyle.success)
            async def h1(self, inter, btn):
                await self._give(inter, 3600, "1h")

            @discord.ui.button(label="Donner 1j", style=discord.ButtonStyle.primary)
            async def d1(self, inter, btn):
                await self._give(inter, 86400, "1j")

            async def _give(self, inter, sec, label):
                if not self.member or not self.role:
                    await inter.response.send_message("Choisis membre + rôle.", ephemeral=True)
                    return
                m = inter.guild.get_member(self.member.id)
                if m:
                    try:
                        await m.add_roles(self.role, reason="temprole")
                    except Exception as e:
                        await inter.response.send_message(f"❌ `{e}`", ephemeral=True)
                        return
                st = load_json(TEMPROLES_FILE, {})
                st.setdefault(str(self.member.id), []).append({
                    "user_id": self.member.id, "role_id": self.role.id, "guild_id": inter.guild.id, "until": time.time() + sec
                })
                save_json(TEMPROLES_FILE, st)
                await inter.response.send_message(f"{self.role.mention} → {self.member.mention} ({label})", ephemeral=True)

        await ctx.send(embed=discord.Embed(title="Rôle temporaire", description="Choisis un membre, un rôle, puis la durée.", color=0x5865F2), view=TRView())
        return
    if action == "list":
        target = await resolve_user(ctx, raw) if raw else ctx.author
        rows = store.get(str(target.id), [])
        txt = "\n".join(f"<@&{r['role_id']}> jusqu'à <t:{int(r['until'])}:R>" for r in rows) or "*aucun*"
        await ctx.send(embed=discord.Embed(title=f"Rôles temporaires — {target}", description=txt, color=0x5865F2))
        return
    if action == "reset":
        save_json(TEMPROLES_FILE, {})
        await ctx.send("Temproles vidés (les rôles déjà donnés restent jusqu'à expiration).")
        return
    if action == "remove":
        target = await resolve_user(ctx, raw)
        if not target or not role:
            await ctx.send("`+temprole remove @user @role`")
            return
        rows = [r for r in store.get(str(target.id), []) if int(r["role_id"]) != role.id]
        store[str(target.id)] = rows
        save_json(TEMPROLES_FILE, store)
        m = ctx.guild.get_member(target.id)
        if m:
            try:
                await m.remove_roles(role, reason="temprole remove")
            except Exception:
                pass
        await ctx.send(f"Rôle {role.mention} retiré de {target.mention}")
        return
    target = await resolve_user(ctx, action)
    if target is None:
        target = await resolve_user(ctx, raw)
    sec = parse_duration(duree or raw or "1h")
    if not target or not role or not sec:
        await ctx.send("`+temprole @user @role 1h` · `+temprole list @user` · `+temprole remove @user @role` · `+temprole reset`")
        return
    m = ctx.guild.get_member(target.id)
    if m:
        try:
            await m.add_roles(role, reason="temprole")
        except Exception as e:
            await ctx.send(f"❌ `{e}`")
            return
    store.setdefault(str(target.id), []).append({
        "user_id": target.id, "role_id": role.id, "guild_id": ctx.guild.id, "until": time.time() + sec
    })
    save_json(TEMPROLES_FILE, store)
    await ctx.send(f"{role.mention} donné à {target.mention} pour **{duree or raw}**")


@bot.command(name="copy")
async def copy_cmd(ctx: commands.Context, message_id: str = None):
    if not await owner_check(ctx):
        return
    mid = extract_id(message_id or "") or (ctx.message.reference.message_id if ctx.message.reference else None)
    if not mid:
        await ctx.send("`+copy <id_message>` ou réponds à un message.")
        return
    msg = None
    try:
        msg = await ctx.channel.fetch_message(mid)
    except Exception:
        for ch in ctx.guild.text_channels:
            try:
                msg = await ch.fetch_message(mid)
                break
            except Exception:
                continue
    if not msg:
        await ctx.send("Message introuvable.")
        return
    await ctx.send(f"Copie de **{msg.author}** :\n{msg.content[:1900] or '*vide*'}")


@bot.command(name="emoji")
async def emoji_cmd(ctx: commands.Context, action: str = None, *, name: str = None):
    if not await owner_check(ctx):
        return
    if action is None:
        emos = list(ctx.guild.emojis)
        txt = " ".join(str(e) for e in emos[:80]) or "*aucun*"

        class EmojiView(discord.ui.View):
            @discord.ui.button(label="Liste", style=discord.ButtonStyle.secondary)
            async def lst(self, inter, btn):
                em = list(inter.guild.emojis)
                await inter.response.send_message(" ".join(str(e) for e in em[:80]) or "*aucun*", ephemeral=True)

            @discord.ui.button(label="Supprimer (choisir)", style=discord.ButtonStyle.danger)
            async def rm(self, inter, btn):
                em = list(inter.guild.emojis)[:25]
                if not em:
                    await inter.response.send_message("Aucun emoji.", ephemeral=True)
                    return
                v = discord.ui.View(timeout=60)
                sel = discord.ui.Select(options=[discord.SelectOption(label=e.name, value=str(e.id)) for e in em])

                async def cb(i):
                    e = inter.guild.get_emoji(int(sel.values[0]))
                    if e:
                        await e.delete()
                    await i.response.send_message("Supprimé.", ephemeral=True)
                sel.callback = cb
                v.add_item(sel)
                await inter.response.send_message("Choisis l'emoji à supprimer.", view=v, ephemeral=True)

        await ctx.send(f"**Emojis ({len(emos)})**\n{txt}\nPour ajouter : `+emoji add nom` + image jointe.", view=EmojiView())
        return
    if action == "list":
        emos = list(ctx.guild.emojis)
        txt = " ".join(str(e) for e in emos[:80]) or "*aucun*"
        await ctx.send(f"**Emojis ({len(emos)})**\n{txt}")
        return
    if action in ("add", "perm"):
        if not ctx.message.attachments:
            await ctx.send("Joins une image : `+emoji add nom`")
            return
        img = await ctx.message.attachments[0].read()
        try:
            e = await ctx.guild.create_custom_emoji(name=(name or "emoji")[:32], image=img)
            await ctx.send(f"Emoji créé : {e}")
        except Exception as ex:
            await ctx.send(f"❌ `{ex}`")
        return
    if action == "remove" and name:
        e = discord.utils.get(ctx.guild.emojis, name=name.strip(":"))
        if not e:
            await ctx.send("Emoji introuvable.")
            return
        await e.delete()
        await ctx.send(f"Emoji `{name}` supprimé.")
        return
    await ctx.send("`+emoji list` · `+emoji add nom` + image · `+emoji remove nom`")


@bot.command(name="emojiperm")
async def emojiperm_cmd(ctx: commands.Context, action: str = None):
    if not await owner_check(ctx):
        return
    await emoji_cmd(ctx, "add")


@bot.command(name="inforole", aliases=["roleinfo"])
async def inforole_cmd(ctx: commands.Context, role: discord.Role = None):
    if not await owner_check(ctx):
        return
    if role is None and ctx.message.role_mentions:
        role = ctx.message.role_mentions[0]
    if role is None:
        await ctx.send("`+inforole @role`")
        return
    embed = discord.Embed(title=f"Rôle {role.name}", color=role.color or 0x2B2D31)
    embed.add_field(name="ID", value=str(role.id))
    embed.add_field(name="Membres", value=str(len(role.members)))
    embed.add_field(name="Position", value=str(role.position))
    embed.add_field(name="Mentionnable", value=str(role.mentionable))
    embed.add_field(name="Affiché", value=str(role.hoist))
    embed.add_field(name="Créé", value=discord.utils.format_dt(role.created_at, "R"))
    await ctx.send(embed=embed)


@bot.command(name="adminxp")
async def adminxp_cmd(ctx: commands.Context, amount: int = None, raw: str = None):
    if not await owner_check(ctx):
        return
    target = await resolve_user(ctx, raw)
    if amount is None or target is None:
        class XPView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=180)
                self.user = None

            @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Membre")
            async def pick(self, inter, select):
                self.user = select.values[0]
                await inter.response.send_message(str(self.user), ephemeral=True)

            @discord.ui.button(label="+100 XP", style=discord.ButtonStyle.success)
            async def p100(self, inter, btn):
                if not self.user:
                    await inter.response.send_message("Choisis un membre.", ephemeral=True)
                    return
                await addxp_cmd(ctx, str(self.user.id), 100)
                await inter.response.send_message("+100 XP", ephemeral=True)

            @discord.ui.button(label="-50 XP", style=discord.ButtonStyle.danger)
            async def m50(self, inter, btn):
                if not self.user:
                    await inter.response.send_message("Choisis un membre.", ephemeral=True)
                    return
                await addxp_cmd(ctx, str(self.user.id), -50)
                await inter.response.send_message("-50 XP", ephemeral=True)

        await ctx.send(embed=discord.Embed(title="Admin XP", description="Choisis un membre puis +100 / -50", color=0x6C8CFF), view=XPView())
        return
    await addxp_cmd(ctx, raw, amount)


@bot.command(name="adminremovexp", aliases=["adminremove"])
async def adminremovexp_cmd(ctx: commands.Context, raw: str = None, amount: int = None):
    if not await owner_check(ctx):
        return
    target = await resolve_user(ctx, raw)
    if target is None or amount is None:
        await ctx.send("`+adminremovexp @user 50`")
        return
    await addxp_cmd(ctx, raw, -abs(amount))


async def restore_guild_backup(guild: discord.Guild, snap: dict, nom: str, user=None):
    me = guild.me

    for ch in list(guild.channels):
        try:
            await ch.delete(reason=f"backup load {nom}")
        except Exception:
            pass
        await asyncio.sleep(0.15)

    bot_top = me.top_role.position if me else 0
    for role in sorted(guild.roles, key=lambda r: r.position, reverse=True):
        if role.is_default() or role.managed or role >= me.top_role:
            continue
        if role.position >= bot_top:
            continue
        try:
            await role.delete(reason=f"backup load {nom}")
        except Exception:
            pass
        await asyncio.sleep(0.15)

    created_roles = {}
    roles = list(snap.get("roles") or [])
    roles.sort(key=lambda r: int(r.get("position") or 0))
    for r in roles:
        name = r.get("name") or "role"
        if name == "@everyone":
            continue
        try:
            nr = await guild.create_role(
                name=name,
                permissions=discord.Permissions(int(r.get("perms") or 0)),
                colour=discord.Colour(int(r.get("color") or 0)),
                hoist=bool(r.get("hoist")),
                mentionable=bool(r.get("mentionable")),
                reason=f"backup load {nom}",
            )
            created_roles[name] = nr
        except Exception:
            pass
        await asyncio.sleep(0.15)

    cats = {}
    channels = list(snap.get("channels") or [])
    for ch in channels:
        if "category" in str(ch.get("type") or "").lower():
            try:
                cats[ch.get("name")] = await guild.create_category(ch.get("name") or "categorie", reason=f"backup load {nom}")
            except Exception:
                pass
            await asyncio.sleep(0.15)

    created_c = 0
    for ch in channels:
        ctype = str(ch.get("type") or "").lower()
        if "category" in ctype:
            continue
        parent = cats.get(ch.get("cat")) if ch.get("cat") else None
        name = (ch.get("name") or "salon")[:100]
        try:
            if "voice" in ctype or "stage" in ctype:
                await guild.create_voice_channel(name, category=parent, reason=f"backup load {nom}")
            else:
                await guild.create_text_channel(name, category=parent, reason=f"backup load {nom}")
            created_c += 1
        except Exception:
            pass
        await asyncio.sleep(0.15)

    gname = snap.get("guild")
    if gname:
        try:
            await guild.edit(name=gname[:100], reason=f"backup load {nom}")
        except Exception:
            pass
    done = discord.Embed(
        title="C'est fini",
        description=f"La backup **`{nom}`** a été chargée.\nAncien serveur effacé (salons + rôles).\nRôles recréés : **{len(created_roles)}**\nSalons recréés : **{created_c}**",
        color=0x57F287,
    )
    target = next((c for c in guild.text_channels), None)
    if target is None:
        try:
            target = await guild.create_text_channel("general", reason="fin backup")
        except Exception:
            target = None
    if target:
        try:
            await target.send(content="✅ **C'est fini.**", embed=done)
        except Exception:
            pass
    return target


@bot.command(name="backup")
async def backup_cmd(ctx: commands.Context, action: str = None, *, nom: str = None):
    if not await owner_check(ctx):
        return
    packs = load_json(BACKUPS_FILE, {})
    if action is None:
        txt = "\n".join(f"• `{n}` — {len(v.get('roles',[]))} rôles, {len(v.get('channels',[]))} salons" for n, v in packs.items()) or "*aucune*"

        class BView(discord.ui.View):
            @discord.ui.button(label="Créer", style=discord.ButtonStyle.success)
            async def cr(self, inter, btn):
                class M(discord.ui.Modal, title="Nom de la backup"):
                    n = discord.ui.TextInput(label="Nom", placeholder="save1", required=True)

                    async def on_submit(self2, i):
                        await backup_cmd(ctx, "create", nom=str(self2.n.value))
                        await i.response.send_message("Backup créée.", ephemeral=True)
                await inter.response.send_modal(M())

            @discord.ui.button(label="Liste", style=discord.ButtonStyle.secondary)
            async def ls(self, inter, btn):
                p = load_json(BACKUPS_FILE, {})
                t = "\n".join(f"• `{n}`" for n in p) or "*aucune*"
                await inter.response.send_message(t, ephemeral=True)

            @discord.ui.button(label="Load", style=discord.ButtonStyle.primary)
            async def ld(self, inter, btn):
                p = load_json(BACKUPS_FILE, {})
                if not p:
                    await inter.response.send_message("Aucune backup.", ephemeral=True)
                    return
                v = discord.ui.View(timeout=60)
                sel = discord.ui.Select(placeholder="Backup à charger", options=[
                    discord.SelectOption(label=n[:100], value=n) for n in list(p.keys())[:25]
                ])

                async def cb(i):
                    if not is_owner(i.user.id):
                        await i.response.send_message("Load réservé aux owners.", ephemeral=True)
                        return
                    await i.response.defer(ephemeral=True)
                    p2 = load_json(BACKUPS_FILE, {})
                    snap = p2.get(sel.values[0])
                    if not snap:
                        await i.followup.send("Backup introuvable.", ephemeral=True)
                        return
                    await i.followup.send("Suppression puis chargement en cours…", ephemeral=True)
                    await restore_guild_backup(i.guild, snap, sel.values[0], user=i.user)
                sel.callback = cb
                v.add_item(sel)
                await inter.response.send_message("Choisis la backup.", view=v, ephemeral=True)

            @discord.ui.button(label="Reset", style=discord.ButtonStyle.danger)
            async def rs(self, inter, btn):
                save_json(BACKUPS_FILE, {})
                await inter.response.send_message("Backups vidées.", ephemeral=True)

        await ctx.send(embed=discord.Embed(title="Backups", description=txt, color=0x5865F2), view=BView())
        return
    if action == "list":
        txt = "\n".join(f"• `{n}` — {len(v.get('roles',[]))} rôles, {len(v.get('channels',[]))} salons" for n, v in packs.items()) or "*aucune*"
        await ctx.send(embed=discord.Embed(title="Backups", description=txt, color=0x5865F2))
        return
    if action == "reset":
        save_json(BACKUPS_FILE, {})
        await ctx.send("Backups vidées.")
        return
    if action == "create":
        nom = nom or f"backup-{int(time.time())}"
        packs[nom] = {
            "guild": ctx.guild.name,
            "roles": [
                {
                    "name": r.name,
                    "perms": r.permissions.value,
                    "color": r.color.value,
                    "hoist": r.hoist,
                    "mentionable": r.mentionable,
                    "position": r.position,
                }
                for r in ctx.guild.roles if r.name != "@everyone"
            ],
            "channels": [
                {
                    "name": c.name,
                    "type": str(c.type),
                    "cat": getattr(c.category, "name", None),
                    "position": getattr(c, "position", 0),
                }
                for c in ctx.guild.channels
            ],
        }
        save_json(BACKUPS_FILE, packs)
        await ctx.send(f"Backup `{nom}` enregistrée.")
        return
    if action == "load":
        if not nom or nom not in packs:
            await ctx.send("Backup introuvable. `+backup` puis Load.")
            return
        await ctx.send(f"Suppression de l'ancien serveur puis chargement de `{nom}`…")
        await restore_guild_backup(ctx.guild, packs[nom], nom, user=ctx.author)
        return
    await ctx.send("`+backup create nom` · `+backup list` · `+backup reset`")


@bot.command(name="pendu")
async def pendu_cmd(ctx: commands.Context):
    word = random.choice(["python", "discord", "banane", "ordinateur", "serveur", "clavier"])
    hidden = ["_" for _ in word]
    lives = 6

    class V(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.tried = set()

        @discord.ui.button(label="Proposer une lettre", style=discord.ButtonStyle.primary)
        async def guess(self, inter, btn):
            class M(discord.ui.Modal, title="Lettre"):
                l = discord.ui.TextInput(label="Lettre", max_length=1)

                async def on_submit(self2, i):
                    nonlocal lives
                    ch = str(self2.l.value).lower()
                    if ch in self.tried:
                        await i.response.send_message("Déjà essayé.", ephemeral=True)
                        return
                    self.tried.add(ch)
                    if ch in word:
                        for idx, c in enumerate(word):
                            if c == ch:
                                hidden[idx] = ch
                    else:
                        lives -= 1
                    done = "_" not in hidden
                    desc = f"`{' '.join(hidden)}`\nVies : {lives}\nLettres : {', '.join(sorted(self.tried))}"
                    if done or lives <= 0:
                        desc += f"\n{'Gagné' if done else 'Perdu'} — mot : **{word}**"
                        await i.response.edit_message(embed=discord.Embed(title="Pendu", description=desc, color=0x57F287 if done else 0xED4245), view=None)
                    else:
                        await i.response.edit_message(embed=discord.Embed(title="Pendu", description=desc, color=0x5865F2), view=self)
            await inter.response.send_modal(M())

    await ctx.send(embed=discord.Embed(title="Pendu", description=f"`{' '.join(hidden)}`\nVies : {lives}", color=0x5865F2), view=V())


@bot.command(name="bingo")
async def bingo_cmd(ctx: commands.Context):
    nums = random.sample(range(1, 76), 12)
    await ctx.send(embed=discord.Embed(title="Bingo", description=" ".join(f"`{n:02d}`" for n in nums), color=0x57F287))


@bot.command(name="morpion")
async def morpion_cmd(ctx: commands.Context, member: discord.Member = None):
    board = [" "] * 9
    turn = 0
    players = [ctx.author, member or ctx.author]

    class V(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            for i in range(9):
                b = discord.ui.Button(label="·", style=discord.ButtonStyle.secondary, row=i // 3, custom_id=str(i))

                async def cb(inter, idx=i):
                    nonlocal turn
                    if board[idx] != " ":
                        await inter.response.defer()
                        return
                    mark = "X" if turn % 2 == 0 else "O"
                    board[idx] = mark
                    b2 = [c for c in self.children if c.custom_id == str(idx)][0]
                    b2.label = mark
                    b2.disabled = True
                    turn += 1
                    await inter.response.edit_message(view=self)
                b.callback = cb
                self.add_item(b)

    await ctx.send(f"Morpion {players[0].mention}", view=V())


@bot.command(name="dactylo")
async def dactylo_cmd(ctx: commands.Context):
    phrase = random.choice(["le roi de la vitesse tape très vite", "discord bot python", "core surveille le serveur"])
    await ctx.send(f"Tape exactement en 20s :\n`{phrase}`")

    def check(m):
        return m.channel == ctx.channel and m.author == ctx.author
    try:
        msg = await bot.wait_for("message", check=check, timeout=20)
        await ctx.send("Bravo !" if msg.content.strip().lower() == phrase else "Rate.")
    except asyncio.TimeoutError:
        await ctx.send("Trop lent.")


QUIZ = [
    ("Capitale de la France ?", "paris"),
    ("2+2 ?", "4"),
    ("Couleur du ciel par temps clair ?", "bleu"),
]


@bot.command(name="quiz")
async def quiz_cmd(ctx: commands.Context):
    q, a = random.choice(QUIZ)
    await ctx.send(f"**Quiz :** {q}")

    def check(m):
        return m.channel == ctx.channel and not m.author.bot
    try:
        msg = await bot.wait_for("message", check=check, timeout=20)
        await ctx.send("Correct !" if msg.content.strip().lower() == a else f"Non, c'était `{a}`.")
    except asyncio.TimeoutError:
        await ctx.send(f"Temps écoulé. Réponse : `{a}`")


@bot.command(name="pfc", aliases=["shifumi"])
async def pfc_cmd(ctx: commands.Context):
    class V(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=30)

        async def play(self, inter, choice):
            botc = random.choice(["pierre", "feuille", "ciseaux"])
            win = (choice, botc) in [("pierre", "ciseaux"), ("feuille", "pierre"), ("ciseaux", "feuille")]
            draw = choice == botc
            txt = f"Toi : **{choice}** · Bot : **{botc}**\n{'Égalité' if draw else ('Gagné' if win else 'Perdu')}"
            await inter.response.edit_message(content=txt, view=None)

        @discord.ui.button(label="Pierre", style=discord.ButtonStyle.secondary)
        async def p(self, i, b):
            await self.play(i, "pierre")

        @discord.ui.button(label="Feuille", style=discord.ButtonStyle.success)
        async def f(self, i, b):
            await self.play(i, "feuille")

        @discord.ui.button(label="Ciseaux", style=discord.ButtonStyle.danger)
        async def c(self, i, b):
            await self.play(i, "ciseaux")

    await ctx.send("Pierre / feuille / ciseaux", view=V())


@bot.command(name="gunfight")
async def gunfight_cmd(ctx: commands.Context, member: discord.Member = None):
    await ctx.send("Préparez-vous...")
    await asyncio.sleep(random.uniform(1.5, 4))

    class V(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=5)
            self.done = False

        @discord.ui.button(label="FEU", style=discord.ButtonStyle.danger)
        async def feu(self, inter, btn):
            if self.done:
                return
            self.done = True
            await inter.response.edit_message(content=f"{inter.user.mention} a tiré en premier !", view=None)

    await ctx.send("FEU !", view=V())


@bot.command(name="gramix")
async def gramix_cmd(ctx: commands.Context):
    word = random.choice(["python", "serveur", "clavier", "banane", "discord"])
    letters = list(word)
    random.shuffle(letters)
    await ctx.send(f"Gramix : `{''.join(letters)}` — trouve le mot (20s)")

    def check(m):
        return m.channel == ctx.channel and m.content.strip().lower() == word
    try:
        msg = await bot.wait_for("message", check=check, timeout=20)
        await ctx.send(f"{msg.author.mention} a trouvé **{word}**")
    except asyncio.TimeoutError:
        await ctx.send(f"C'était **{word}**")


@bot.command(name="anniv", aliases=["anniversaire"])
async def anniv_cmd(ctx: commands.Context, action: str = None, *, date: str = None):
    data = load_json(BIRTHDAYS_FILE, {})
    if action in ("set", "add") and date:
        data[str(ctx.author.id)] = date
        save_json(BIRTHDAYS_FILE, data)
        await ctx.send(f"Anniversaire enregistré : **{date}**")
        return
    if action == "remove":
        data.pop(str(ctx.author.id), None)
        save_json(BIRTHDAYS_FILE, data)
        await ctx.send("Anniversaire retiré.")
        return
    lines = [f"<@{u}> — {d}" for u, d in data.items()] or ["*aucun*"]
    class V(discord.ui.View):
        @discord.ui.button(label="Enregistrer le mien", style=discord.ButtonStyle.success)
        async def add(self, inter, btn):
            class M(discord.ui.Modal, title="Anniversaire"):
                d = discord.ui.TextInput(label="Date (JJ/MM)", placeholder="14/07")

                async def on_submit(self2, i):
                    data[str(i.user.id)] = str(self2.d.value)
                    save_json(BIRTHDAYS_FILE, data)
                    await i.response.send_message("Enregistré.", ephemeral=True)
            await inter.response.send_modal(M())
    await ctx.send(embed=discord.Embed(title="Anniversaires", description="\n".join(lines), color=0xEB459E), view=V())


@bot.command(name="report", aliases=["signalement"])
async def report_cmd(ctx: commands.Context, member: discord.Member = None, *, raison: str = None):
    class M(discord.ui.Modal, title="Signalement discret"):
        cible = discord.ui.TextInput(label="Membre (nom ou ID)", required=True)
        why = discord.ui.TextInput(label="Raison", style=discord.TextStyle.paragraph, required=True)

        async def on_submit(self, inter):
            reports = load_json(REPORTS_FILE, [])
            reports.append({"by": inter.user.id, "cible": str(self.cible.value), "raison": str(self.why.value), "at": datetime.now().isoformat()})
            save_json(REPORTS_FILE, reports)
            await inter.response.send_message("Signalement envoyé au staff. Merci.", ephemeral=True)
            embed = discord.Embed(title="Signalement discret", description=str(self.why.value), color=0xED4245)
            embed.add_field(name="Par", value=str(inter.user))
            embed.add_field(name="Cible", value=str(self.cible.value))
            await send_log(embed)
            try:
                await ctx.message.delete()
            except Exception:
                pass

    if member and raison:
        reports = load_json(REPORTS_FILE, [])
        reports.append({"by": ctx.author.id, "cible": str(member.id), "raison": raison, "at": datetime.now().isoformat()})
        save_json(REPORTS_FILE, reports)
        try:
            await ctx.message.delete()
        except Exception:
            pass
        await ctx.send("Signalement envoyé.", delete_after=5)
        await send_log(discord.Embed(title="Signalement discret", description=f"{ctx.author} → {member}\n{raison}", color=0xED4245))
        return
    class V(discord.ui.View):
        @discord.ui.button(label="Signaler un membre", style=discord.ButtonStyle.danger)
        async def go(self, inter, btn):
            await inter.response.send_modal(M())
    await ctx.send(view=V())


@bot.command(name="suggest", aliases=["suggestion"])
async def suggest_cmd(ctx: commands.Context, *, texte: str = None):
    class M(discord.ui.Modal, title="Suggestion"):
        s = discord.ui.TextInput(label="Ta suggestion", style=discord.TextStyle.paragraph, required=True)

        async def on_submit(self, inter):
            sugg = load_json(SUGGESTS_FILE, [])
            sugg.append({"by": inter.user.id, "text": str(self.s.value)})
            save_json(SUGGESTS_FILE, sugg)
            e = discord.Embed(title="Suggestion", description=str(self.s.value), color=0x57F287)
            e.set_author(name=str(inter.user), icon_url=inter.user.display_avatar.url)
            msg = await inter.channel.send(embed=e)
            for emo in ("👍", "👎"):
                await msg.add_reaction(emo)
            await inter.response.send_message("Suggestion envoyée.", ephemeral=True)

    class V(discord.ui.View):
        @discord.ui.button(label="Proposer", style=discord.ButtonStyle.success)
        async def go(self, inter, btn):
            await inter.response.send_modal(M())

    if texte:
        e = discord.Embed(title="Suggestion", description=texte, color=0x57F287)
        e.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
        msg = await ctx.send(embed=e)
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")
        return
    await ctx.send("Suggestions", view=V())


@bot.command(name="question", aliases=["8ball", "boule"])
async def question_cmd(ctx: commands.Context, *, q: str = None):
    await ctx.send(random.choice(["Oui.", "Non.", "Peut-être.", "Certainement.", "Repose la question.", "Sans doute.", "J'en doute."]))


VF = [
    ("La Tour Eiffel est à Paris.", True),
    ("2 + 2 = 5.", False),
    ("Discord a été lancé en 2015.", True),
    ("L'eau bout à 50°C.", False),
]


@bot.command(name="vraioufaux")
async def vf_cmd(ctx: commands.Context):
    q, ans = random.choice(VF)

    class V(discord.ui.View):
        @discord.ui.button(label="Vrai", style=discord.ButtonStyle.success)
        async def t(self, inter, btn):
            await inter.response.edit_message(content=f"{q}\n{'Correct' if ans else 'Faux'} !", view=None)

        @discord.ui.button(label="Faux", style=discord.ButtonStyle.danger)
        async def f(self, inter, btn):
            await inter.response.edit_message(content=f"{q}\n{'Correct' if not ans else 'Faux'} !", view=None)

    await ctx.send(f"**Vrai ou faux :** {q}", view=V())


async def send_gif_action(ctx, kind, target, title):
    url = await get_reaction_gif_url(kind)
    if not url:
        url = random.choice(FALLBACK_GIFS.get(kind) or FALLBACK_GIFS.get("hug") or [""])
    embed = discord.Embed(title=title, color=0xEB459E)
    if target:
        embed.description = f"{ctx.author.mention} → {target.mention}"
    if url:
        embed.set_image(url=url)
    await ctx.send(embed=embed)


@bot.command(name="compliment")
async def compliment_cmd(ctx: commands.Context, member: discord.Member = None):
    member = member or ctx.author
    txt = random.choice(["t'es une pépite", "t'as trop de style", "le serveur est mieux avec toi", "énergie de légende"])
    await ctx.send(f"{member.mention}, {txt} ✨")


@bot.command(name="caresse")
async def caresse_cmd(ctx: commands.Context, member: discord.Member = None):
    await send_gif_action(ctx, "hug", member or ctx.author, "Caresse")


@bot.command(name="poing")
async def poing_cmd(ctx: commands.Context, member: discord.Member = None):
    await send_gif_action(ctx, "slap", member or ctx.author, "Coup de poing")


@bot.command(name="wink")
async def wink_cmd(ctx: commands.Context, member: discord.Member = None):
    await send_gif_action(ctx, "kiss", member or ctx.author, "Clin d'œil")


@bot.command(name="pizza")
async def pizza_cmd(ctx: commands.Context, member: discord.Member = None):
    await send_gif_action(ctx, "hug", member or ctx.author, "Pizza")


@bot.command(name="perroquet")
async def perroquet_cmd(ctx: commands.Context, member: discord.Member = None):
    if not await owner_check(ctx):
        return
    member = member or ctx.author
    PARROT_UNTIL[member.id] = time.time() + 30
    await ctx.send(f"Je répète {member.mention} pendant 30 secondes.")


def regional(text: str) -> str:
    out = []
    for ch in text.lower():
        if "a" <= ch <= "z":
            out.append(chr(0x1F1E6 + ord(ch) - ord("a")))
        elif ch == " ":
            out.append("  ")
        else:
            out.append(ch)
    return " ".join(out)


@bot.command(name="grostexte")
async def grostexte_cmd(ctx: commands.Context, *, texte: str = None):
    if not texte:
        await ctx.send("`+grostexte bonjour`")
        return
    await ctx.send(regional(texte)[:2000])


@bot.command(name="ascii")
async def ascii_cmd(ctx: commands.Context, *, texte: str = None):
    if not texte:
        return
    await ctx.send("```\n" + texte.encode("ascii", "replace").decode("ascii")[:1900] + "\n```")


@bot.command(name="binaire")
async def binaire_cmd(ctx: commands.Context, *, texte: str = None):
    if not texte:
        return
    await ctx.send(" ".join(format(ord(c), "08b") for c in texte)[:1900])


@bot.command(name="clap")
async def clap_cmd(ctx: commands.Context, *, texte: str = None):
    if not texte:
        return
    await ctx.send(" 👏 ".join(texte.split()))


@bot.command(name="robot")
async def robot_cmd(ctx: commands.Context, *, texte: str = None):
    if not texte:
        return
    await ctx.send(" ".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(texte)))


@bot.command(name="flip")
async def flip_cmd(ctx: commands.Context, *, texte: str = None):
    if not texte:
        return
    table = str.maketrans("abcdefghijklmnopqrstuvwxyz", "ɐqɔpǝɟƃɥᴉɾʞlɯuodbɹsʇnʌʍxʎz")
    await ctx.send(texte.lower().translate(table)[::-1])


@bot.command(name="dbreset")
async def dbreset_cmd(ctx: commands.Context):
    if not await owner_check(ctx):
        return
    if not DBRESET_ENABLED:
        await ctx.send("🔒 `+dbreset` est **désactivée**. Passe `DBRESET_ENABLED = True` dans le code pour l'autoriser.")
        return
    if ctx.author.id != BOT_OWNER_ID:
        await ctx.send("❌ Réservé au Propriétaire.")
        return
    await ctx.send("Reset base de données non exécuté (sécurité).")

# ==================== COMMANDES SLASH ====================

async def slash_owner_ok(interaction: discord.Interaction) -> bool:
    if interaction.user.bot:
        return False
    if is_blacklisted(interaction.user.id):
        await interaction.response.send_message("Tu es blacklisté.", ephemeral=True)
        return False
    if not is_owner(interaction.user.id, interaction.guild.id if interaction.guild else None):
        await interaction.response.send_message("Réservé aux propriétaires du bot.", ephemeral=True)
        return False
    return True

@bot.tree.command(name="ping", description="Latence du bot")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong — **{round(bot.latency * 1000)} ms**", ephemeral=True)

@bot.tree.command(name="help", description="Aide du bot")
async def slash_help(interaction: discord.Interaction):
    emb = discord.Embed(
        title="Aide Core",
        description=(
            f"**{len(bot.commands)}** commandes préfixe `+`\n"
            f"**{len(bot.tree.get_commands())}** commandes slash `/`\n\n"
            "Principales : `/setup` `/kick` `/ban` `/userinfo` `/errors` `/update` `/recruit` `/leave` `/servers`\n"
            "Préfixe : `+help` pour le menu complet."
        ),
        color=0x5865F2,
    )
    await interaction.response.send_message(embed=emb, ephemeral=True)

@bot.tree.command(name="setup", description="Ouvrir la configuration du serveur")
async def slash_setup(interaction: discord.Interaction):
    if not await slash_owner_ok(interaction):
        return
    if not interaction.guild:
        await interaction.response.send_message("Serveur uniquement.", ephemeral=True)
        return
    set_guild(interaction.guild.id)
    await interaction.response.send_message(
        embed=setup_embed(interaction.guild.id),
        view=SetupView(interaction.user.id, interaction.guild.id),
        ephemeral=True,
    )

@bot.tree.command(name="errors", description="Journal d'erreurs et diagnostic")
async def slash_errors(interaction: discord.Interaction):
    if not await slash_owner_ok(interaction):
        return
    rows = load_json(ERRORS_FILE, [])
    lines = []
    if isinstance(rows, list) and rows:
        for i, r in enumerate(reversed(rows[-10:]), 1):
            lines.append(f"**{i}.** `{r.get('kind')}` · {r.get('title')}")
    else:
        lines.append("*aucune erreur*")
    diag = run_system_diagnostics()
    bad = sum(1 for c in diag["checks"] if not c["ok"])
    emb = discord.Embed(title="Erreurs", description="\n".join(lines)[:3500], color=0xED4245)
    emb.add_field(name="Diagnostic", value=f"{'OK' if diag['ok'] else f'{bad} problème(s)'} — `+errors` pour le détail", inline=False)
    await interaction.response.send_message(embed=emb, ephemeral=True)

@bot.tree.command(name="update", description="Vérifier les mises à jour du bot")
async def slash_update(interaction: discord.Interaction):
    if not await slash_owner_ok(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    remote = await fetch_remote_version() if UPDATE_VERSION_URL else None
    emb = update_embed(remote)
    if remote and parse_version(remote) > parse_version(BOT_VERSION) and UPDATE_CODE_URL:
        await interaction.followup.send(embed=emb, view=UpdateConfirmView(remote, channel_id=interaction.channel.id if interaction.channel else None))
    else:
        await interaction.followup.send(embed=emb)

@bot.tree.command(name="kick", description="Expulser un membre")
@app_commands.describe(member="Membre à kick", reason="Raison")
async def slash_kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucune raison"):
    if not await slash_owner_ok(interaction):
        return
    try:
        await member.kick(reason=f"{reason} | par {interaction.user}")
        await interaction.response.send_message(f"{member} kick.", ephemeral=True)
        await send_log(discord.Embed(title="Kick (slash)", description=f"{member.mention} par {interaction.user.mention}\n{reason}", color=0xFEE75C))
    except Exception as e:
        await report_system_error("slash", "kick", str(e))
        await interaction.response.send_message(f"Erreur : `{e}`", ephemeral=True)

@bot.tree.command(name="ban", description="Bannir un membre")
@app_commands.describe(member="Membre à ban", reason="Raison")
async def slash_ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Aucune raison"):
    if not await slash_owner_ok(interaction):
        return
    try:
        await member.ban(reason=f"{reason} | par {interaction.user}", delete_message_days=0)
        await interaction.response.send_message(f"{member} ban.", ephemeral=True)
        await send_log(discord.Embed(title="Ban (slash)", description=f"{member.mention} par {interaction.user.mention}\n{reason}", color=0xED4245))
    except Exception as e:
        await report_system_error("slash", "ban", str(e))
        await interaction.response.send_message(f"Erreur : `{e}`", ephemeral=True)

@bot.tree.command(name="userinfo", description="Infos sur un membre")
@app_commands.describe(member="Membre")
async def slash_userinfo(interaction: discord.Interaction, member: discord.Member = None):
    if not await slash_owner_ok(interaction):
        return
    member = member or interaction.user
    if not isinstance(member, discord.Member) and interaction.guild:
        member = interaction.guild.get_member(member.id) or member
    emb = discord.Embed(title="Userinfo", color=0x5865F2, timestamp=discord.utils.utcnow())
    emb.set_thumbnail(url=member.display_avatar.url)
    emb.add_field(name="User", value=f"{member.mention}\n`{member.id}`", inline=True)
    emb.add_field(name="Compte", value=discord.utils.format_dt(member.created_at, "R"), inline=True)
    if isinstance(member, discord.Member) and member.joined_at:
        emb.add_field(name="Arrivé", value=discord.utils.format_dt(member.joined_at, "R"), inline=True)
        roles = [r.mention for r in member.roles if r.name != "@everyone"][:15]
        emb.add_field(name="Rôles", value=", ".join(roles) or "—", inline=False)
    await interaction.response.send_message(embed=emb, ephemeral=True)

@bot.tree.command(name="bl", description="Blacklist globale (sans ban)")
@app_commands.describe(user="Utilisateur à blacklist")
async def slash_bl(interaction: discord.Interaction, user: discord.User):
    if not await slash_owner_ok(interaction):
        return
    if is_owner(user.id):
        await interaction.response.send_message("Impossible de blacklist un owner.", ephemeral=True)
        return
    bl = get_blacklist()
    if user.id not in bl:
        bl.append(user.id)
        save_json(BLACKLIST_FILE, bl)
    await interaction.response.send_message(f"{user.mention} blacklist globale.", ephemeral=True)

@bot.tree.command(name="recruit", description="Panneau recrutement")
async def slash_recruit(interaction: discord.Interaction):
    if not await slash_owner_ok(interaction):
        return
    if not interaction.guild:
        await interaction.response.send_message("Serveur uniquement.", ephemeral=True)
        return
    # Réutilise la commande préfixe via un message factice n'est pas idéal — ouvre le même panneau
    cfg = get_config(interaction.guild.id)
    etat = "ouvert" if cfg.get("RECRUIT_ENABLED") else "fermé"
    await interaction.response.send_message(
        embed=discord.Embed(
            title="Recrutement",
            description=f"État : **{etat}**\nUtilise `+recruit` pour le panneau complet (salons + publier).",
            color=0x5865F2,
        ),
        ephemeral=True,
    )

@bot.tree.command(name="leave", description="Faire quitter le bot (serveur actuel ou ID)")
@app_commands.describe(guild_id="ID du serveur (vide = serveur actuel)")
async def slash_leave(interaction: discord.Interaction, guild_id: str = None):
    if not await slash_owner_ok(interaction):
        return
    target = None
    if guild_id:
        try:
            gid = int(re.sub(r"[^\d]", "", guild_id))
        except Exception:
            await interaction.response.send_message("ID invalide.", ephemeral=True)
            return
        target = bot.get_guild(gid)
        if not target:
            await interaction.response.send_message("Bot absent de ce serveur.", ephemeral=True)
            return
    else:
        if not interaction.guild:
            await interaction.response.send_message("Précise un guild_id.", ephemeral=True)
            return
        target = interaction.guild
    name, tid = target.name, target.id
    await interaction.response.send_message(f"Départ de **{name}** (`{tid}`)…", ephemeral=True)
    try:
        await target.leave()
    except Exception as e:
        await report_system_error("slash", "leave", str(e))

@bot.tree.command(name="servers", description="Liste des serveurs du bot")
async def slash_servers(interaction: discord.Interaction):
    if not await slash_owner_ok(interaction):
        return
    lines = [f"• **{g.name}** — `{g.id}` — {g.member_count or 0} membres" for g in bot.guilds[:25]]
    await interaction.response.send_message(
        embed=discord.Embed(title=f"Serveurs ({len(bot.guilds)})", description="\n".join(lines) or "*aucun*", color=0x5865F2),
        ephemeral=True,
    )

@bot.tree.command(name="stats", description="Statistiques du bot")
async def slash_stats(interaction: discord.Interaction):
    if not await slash_owner_ok(interaction):
        return
    up = int(time.time() - START_TIME)
    h, rem = divmod(up, 3600)
    m, s = divmod(rem, 60)
    emb = discord.Embed(title="Stats", color=0x5865F2)
    emb.add_field(name="Serveurs", value=str(len(bot.guilds)))
    emb.add_field(name="Commandes", value=str(len(bot.commands)))
    emb.add_field(name="Slash", value=str(len(bot.tree.get_commands())))
    emb.add_field(name="Ping", value=f"{round(bot.latency*1000)} ms")
    emb.add_field(name="Uptime", value=f"{h}h {m}m {s}s")
    emb.add_field(name="Version", value=BOT_VERSION)
    await interaction.response.send_message(embed=emb, ephemeral=True)

@bot.tree.command(name="sync", description="Resynchroniser les commandes slash")
async def slash_sync(interaction: discord.Interaction):
    if not await slash_owner_ok(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    try:
        synced = await bot.tree.sync()
        await interaction.followup.send(f"Synchronisé : **{len(synced)}** commande(s) slash.")
    except Exception as e:
        await report_system_error("slash", "sync", str(e))
        await interaction.followup.send(f"Erreur sync : `{e}`")

@bot.tree.command(name="diagnostic", description="Vérification automatique du bot")
async def slash_diagnostic(interaction: discord.Interaction):
    if not await slash_owner_ok(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    d = run_system_diagnostics()
    lines = [f"{'✅' if c['ok'] else '❌'} **{c['name']}** — {c['detail']}" for c in d["checks"]]
    emb = discord.Embed(
        title="Diagnostic",
        description="\n".join(lines)[:3900],
        color=0x57F287 if d["ok"] else 0xED4245,
    )
    if d.get("file"):
        emb.set_footer(text=f"Fichier : {d['file']}")
    await interaction.followup.send(embed=emb)
    if d.get("file") and os.path.isfile(d["file"]):
        try:
            await interaction.followup.send(file=discord.File(d["file"]), ephemeral=True)
        except Exception:
            await interaction.followup.send(f"Rapport : `{d['file']}`", ephemeral=True)

if __name__ == "__main__":
    if not TOKEN:
        print("❌ TOKEN manquant.")
    else:
        bot.run(TOKEN)
