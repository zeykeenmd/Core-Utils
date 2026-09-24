import os
import json
import asyncio
import random
import re
import platform
import time
import hashlib
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import aiohttp

load_dotenv()

# ==================== CONFIG ====================
TOKEN = os.getenv("DISCORD_TOKEN")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "0"))

START_TIME = time.time()
BOT_VERSION = "2.1.2"
BOT_CREATOR = "9kr"

LOG_CHANNEL_ID = None
TICKET_LOG_CHANNEL_ID = None

DATA_DIR = "data"
OWNERS_FILE = os.path.join(DATA_DIR, "owners.json")
BLACKLIST_FILE = os.path.join(DATA_DIR, "blacklist.json")
LOCKED_NAMES_FILE = os.path.join(DATA_DIR, "locked_names.json")
GIVEAWAYS_FILE = os.path.join(DATA_DIR, "giveaways.json")
TICKETS_FILE = os.path.join(DATA_DIR, "tickets.json")

SNIPE_CACHE: Dict[int, discord.Message] = {}

# ==================== UPDATE (sécurisé) ====================
UPDATE_ENABLED = os.getenv("UPDATE_ENABLED", "1").strip() in ("1", "true", "True", "yes")
UPDATE_AUTO_INSTALL = os.getenv("UPDATE_AUTO_INSTALL", "1").strip() in ("1", "true", "True", "yes")
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "300"))
UPDATE_VERSION_URL = os.getenv("UPDATE_VERSION_URL")
UPDATE_CODE_URL = os.getenv("UPDATE_CODE_URL")
UPDATE_WEBHOOK_ENABLED = os.getenv("UPDATE_WEBHOOK_ENABLED", "1").strip() in ("1", "true", "True", "yes")
UPDATE_WEBHOOK_SECRET = os.getenv("UPDATE_WEBHOOK_SECRET", "CoreUpdate2026!")

WEBHOOK_HEADERS = {
    "User-Agent": f"CoreBot/{BOT_VERSION}",
    "Content-Type": "application/json",
    "X-GitHub-Secret": UPDATE_WEBHOOK_SECRET,
}

# ==================== DOUBLE CONFIRMATION + PASSWORD ====================
UPDATE_PASSWORD = os.getenv("UPDATE_PASSWORD", "CoreUpdate2026!")

# Rate limit anti-spam
COMMAND_LIMIT = {}
COMMAND_LIMIT_TIME = 5  # secondes

# ==================== UTILS ====================
def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def load_json(path: str, default: Any = None) -> Any:
    ensure_data_dir()
    if default is None: default = []
    if not os.path.exists(path):
        save_json(path, default)
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path: str, data: Any):
    ensure_data_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_owners():
    return load_json(OWNERS_FILE, [])

def save_owners(owners):
    save_json(OWNERS_FILE, owners)

def is_owner(user_id: int) -> bool:
    return user_id in get_owners()

def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

BOT_FILE = os.path.abspath("bot.py")

def read_local_file_version() -> str:
    try:
        with open(BOT_FILE, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if "BOT_VERSION" in line:
                    return re.search(r'BOT_VERSION\s*=\s*["\']([^"\']+)["\']', line).group(1)
    except Exception:
        pass
    return BOT_VERSION

# ==================== BOT ====================
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)

# ==================== TASKS ====================
@tasks.loop(seconds=UPDATE_INTERVAL)
async def update_check_loop():
    if not UPDATE_ENABLED or not UPDATE_VERSION_URL:
        return
    remote = await fetch_remote_version()
    if not remote:
        return
    if parse_version(remote) <= parse_version(BOT_VERSION):
        return
    if UPDATE_AUTO_INSTALL:
        await apply_update_and_restart(reason="auto", remote=remote)
        return
    await notify_update_available(remote)

# ==================== UPDATE FUNCTIONS ====================
def parse_version(v: str) -> tuple:
    parts = [int(x) for x in re.findall(r"\d+", str(v or "0").lstrip("\ufeff"))]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])

def is_version_notified(remote: str) -> bool:
    st = load_json(os.path.join(DATA_DIR, "update_state.json"), {})
    return remote in (st.get("notified") or [])

def mark_version_notified(remote: str):
    st = load_json(os.path.join(DATA_DIR, "update_state.json"), {})
    notified = list(st.get("notified") or [])
    if remote not in notified:
        notified.append(remote)
    st["notified"] = notified[-20:]
    save_json(os.path.join(DATA_DIR, "update_state.json"), st)

async def fetch_remote_version() -> Optional[str]:
    try:
        async with aiohttp.ClientSession(headers=WEBHOOK_HEADERS) as session:
            async with session.get(UPDATE_VERSION_URL, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return None
                return (await resp.text()).strip().splitlines()[0]
    except Exception:
        return None

async def fetch_remote_bot_text() -> Optional[str]:
    try:
        async with aiohttp.ClientSession(headers=WEBHOOK_HEADERS) as session:
            async with session.get(UPDATE_CODE_URL, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                return (await resp.read()).decode("utf-8", errors="replace") if resp.status == 200 else None
    except Exception:
        return None

async def download_bot_update() -> tuple:
    if not UPDATE_CODE_URL:
        return False, "UPDATE_CODE_URL non défini"
    try:
        async with aiohttp.ClientSession(headers=WEBHOOK_HEADERS) as session:
            async with session.get(UPDATE_CODE_URL, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status == 403:
                    return False, "Accès refusé (403) - Mauvais secret"
                if resp.status != 200:
                    return False, f"HTTP {resp.status}"
                data = await resp.read()
        if len(data) < 500:
            return False, "Fichier trop petit"
        target = BOT_FILE
        tmp = target + ".update"
        with open(tmp, "wb") as f:
            f.write(data)
        bak = target + ".bak"
        if os.path.exists(target):
            with open(target, "rb") as src, open(bak, "wb") as dst:
                dst.write(src.read())
        os.replace(tmp, target)
        return True, f"OK — {len(data)} octets"
    except Exception as e:
        return False, str(e)

async def apply_update_and_restart(channel_id: Optional[int] = None, reason: str = "update", remote: str = None):
    ok, detail = await download_bot_update()
    if not ok:
        return False
    try:
        await bot.close()
    except Exception:
        pass
    args = [sys.executable] + sys.argv
    subprocess.Popen(args, cwd=os.getcwd())
    os._exit(0)
    return True

# ==================== EVENTS ====================
@bot.event
async def on_ready():
    print(f"Bot connecté : {bot.user} ({bot.user.id})")
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.CustomActivity(name="MP moi pour du support")
    )
    update_check_loop.start()

# ==================== COMMANDS ====================
@bot.command(name="help")
async def help_cmd(ctx: commands.Context):
    if not is_owner(ctx.author.id):
        return
    emb = discord.Embed(title="📖 Commandes (préfixe +)", color=0x5865F2)
    emb.add_field(name="👑 Propriétaire / Owners", value="`+owner` `+owner @user` `+owner reset` `+unowner`", inline=False)
    emb.add_field(name="🚫 Blacklist", value="`+bl` `+bl clear` `+unbl`", inline=False)
    emb.add_field(name="🛡️ Modération", value="`+kick` `+mute` `+unmute` `+ban` `+ban clear` `+unban` `+derank` `+userinfo` `+lockname` `+unlockname`", inline=False)
    emb.add_field(name="📊 Serveur & Salons", value="`+stats` `+renew` `+lock` `+unlock` `+clear` `+say` `+snipe` `+leave` `+infobot`", inline=False)
    emb.add_field(name="🎫 Tickets", value="`+ticket` `+ticket list` `+ticket close` `+ticket reopen` `+ticketinfo`", inline=False)
    emb.add_field(name="🎉 Giveaway", value="`+giveaway` `+g` `+gend` `+reroll`", inline=False)
    emb.add_field(name="🔧 Update", value="`+update` `+update install` `+errors`", inline=False)
    emb.add_field(name="🎮 Jeux", value="`+coreguess` `+corememory` `+coreduel` `+corequiz` `+coreflip`", inline=False)
    emb.add_field(name="🎛️ Webhooks", value="`+webhook`", inline=False)
    await ctx.send(embed=emb)

# ==================== UPDATE COMMAND (avec double confirmation + password) ====================
@bot.command(name="update")
async def update_cmd(ctx: commands.Context):
    if not is_owner(ctx.author.id):
        return
    remote = await fetch_remote_version()
    if not remote or parse_version(remote) <= parse_version(BOT_VERSION):
        await ctx.send("Le bot est déjà à jour.")
        return
    await ctx.send(f"**Nouvelle version disponible** : `{BOT_VERSION}` → `{remote}`\n\nRéponds **oui** pour mettre à jour (délai 30 secondes).")

@bot.command(name="update", aliases=["updateinstall"])
async def update_install_cmd(ctx: commands.Context, password: Optional[str] = None):
    if not is_owner(ctx.author.id):
        return
    if password != UPDATE_PASSWORD:
        await ctx.send("❌ Mot de passe incorrect.")
        return

    # Rate limit anti-spam
    now = time.time()
    if ctx.author.id in COMMAND_LIMIT and now - COMMAND_LIMIT[ctx.author.id] < COMMAND_LIMIT_TIME:
        await ctx.send("❌ Tu dois attendre 5 secondes entre les commandes.")
        return
    COMMAND_LIMIT[ctx.author.id] = now

    remote = await fetch_remote_version()
    if not remote or parse_version(remote) <= parse_version(BOT_VERSION):
        await ctx.send("Le bot est déjà à jour.")
        return

    emb = discord.Embed(title="🔄 Mise à jour", color=0x57F287)
    emb.add_field(name="Version locale", value=f"`{BOT_VERSION}`")
    emb.add_field(name="Version distante", value=f"`{remote}`")
    emb.add_field(name="Par", value=f"{ctx.author.mention} ({ctx.author.id})")
    emb.description = "Voulez-vous vraiment mettre à jour le bot ?"

    class ConfirmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=30)

        @discord.ui.button(label="Oui, mettre à jour", style=discord.ButtonStyle.success)
        async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("Seul l'auteur peut confirmer.", ephemeral=True)
                return
            await interaction.response.edit_message(content="⏳ Mise à jour en cours...", view=None)
            ok = await apply_update_and_restart(channel_id=interaction.channel.id, reason="manuel", remote=remote)
            if ok:
                await interaction.followup.send("✅ Mise à jour terminée et redémarrage en cours.")
            else:
                await interaction.followup.send("❌ Échec de la mise à jour.")

        @discord.ui.button(label="Non, plus tard", style=discord.ButtonStyle.secondary)
        async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(content="Mise à jour annulée.", view=None)

    await ctx.send(embed=emb, view=ConfirmView())

# ==================== COMMANDS ====================
# (les commandes help, kick, ban, ticket, giveaway, etc. restent inchangées)

# ==================== RUN ====================
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN manquant")
    else:
        bot.run(TOKEN)
