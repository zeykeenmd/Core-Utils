import os
import sys
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

load_dotenv(override=True)

TOKEN = (os.getenv("DISCORD_TOKEN") or "").strip().strip('"\'')
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
UPDATE_STATE_FILE = os.path.join(DATA_DIR, "update_state.json")

SNIPE_CACHE: Dict[int, discord.Message] = {}

TRUTHY = ("1", "true", "True", "yes")
UPDATE_ENABLED = os.getenv("UPDATE_ENABLED", "1").strip() in TRUTHY
UPDATE_AUTO_INSTALL = os.getenv("UPDATE_AUTO_INSTALL", "1").strip() in TRUTHY
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "300"))
UPDATE_VERSION_URL = os.getenv("UPDATE_VERSION_URL")
UPDATE_CODE_URL = os.getenv("UPDATE_CODE_URL")

# Plus de valeur par défaut en clair : à définir dans le fichier .env
UPDATE_WEBHOOK_SECRET = os.getenv("UPDATE_WEBHOOK_SECRET", "")
UPDATE_PASSWORD = os.getenv("UPDATE_PASSWORD", "")

WEBHOOK_HEADERS = {
    "User-Agent": f"CoreBot/{BOT_VERSION}",
}
if UPDATE_WEBHOOK_SECRET:
    WEBHOOK_HEADERS["X-GitHub-Secret"] = UPDATE_WEBHOOK_SECRET

COMMAND_LIMIT = {}
COMMAND_LIMIT_TIME = 5


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_json(path: str, default: Any = None):
    ensure_data_dir()
    if default is None:
        default = []
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


BOT_FILE = os.path.abspath(__file__)


def read_local_file_version() -> str:
    try:
        with open(BOT_FILE, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("BOT_VERSION"):
                    return re.search(r'BOT_VERSION\s*=\s*["\']([^"\']+)["\']', line).group(1)
    except Exception:
        pass
    return BOT_VERSION


def extract_version_from_source(text: str) -> Optional[str]:
    m = re.search(r'^BOT_VERSION\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    return m.group(1) if m else None


intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)


# ----------------------------------------------------------------------
# Mise à jour
# ----------------------------------------------------------------------

def parse_version(v: str) -> tuple:
    parts = [int(x) for x in re.findall(r"\d+", str(v or "0").lstrip("\ufeff"))]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])


def is_version_notified(remote: str) -> bool:
    st = load_json(UPDATE_STATE_FILE, {})
    return remote in (st.get("notified") or [])


def mark_version_notified(remote: str):
    st = load_json(UPDATE_STATE_FILE, {})
    notified = list(st.get("notified") or [])
    if remote not in notified:
        notified.append(remote)
    st["notified"] = notified[-20:]
    save_json(UPDATE_STATE_FILE, st)


async def fetch_remote_version() -> Optional[str]:
    if not UPDATE_VERSION_URL:
        return None
    try:
        async with aiohttp.ClientSession(headers=WEBHOOK_HEADERS) as session:
            async with session.get(UPDATE_VERSION_URL, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return None
                lines = (await resp.text()).strip().splitlines()
                return lines[0].strip() if lines else None
    except Exception:
        return None


async def fetch_remote_bot_text() -> Optional[str]:
    if not UPDATE_CODE_URL:
        return None
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

        text = data.decode("utf-8", errors="replace")

        # 1) Le fichier téléchargé doit être du Python valide (évite de casser le bot)
        try:
            compile(text, "bot.py", "exec")
        except SyntaxError as e:
            return False, f"Le fichier distant contient une erreur de syntaxe : {e}"

        # 2) Sa BOT_VERSION doit être plus récente que la locale (évite la boucle de mises à jour)
        remote_file_version = extract_version_from_source(text)
        if not remote_file_version:
            return False, "BOT_VERSION introuvable dans le fichier distant"
        if parse_version(remote_file_version) <= parse_version(BOT_VERSION):
            return False, (
                f"BOT_VERSION du fichier distant ({remote_file_version}) n'est pas plus récente "
                f"que la locale ({BOT_VERSION}). Mets à jour BOT_VERSION dans bot.py sur GitHub."
            )

        target = BOT_FILE
        tmp = target + ".update"
        with open(tmp, "wb") as f:
            f.write(data)

        bak = target + ".bak"
        if os.path.exists(target):
            with open(target, "rb") as src, open(bak, "wb") as dst:
                dst.write(src.read())

        os.replace(tmp, target)
        return True, f"OK — {len(data)} octets (v{remote_file_version})"
    except Exception as e:
        return False, str(e)


async def apply_update_and_restart(channel_id: Optional[int] = None, reason: str = "update", remote: str = None) -> tuple:
    ok, detail = await download_bot_update()
    if not ok:
        return False, detail
    try:
        await bot.close()
    except Exception:
        pass
    # Relance le script avec le même interpréteur Python
    subprocess.Popen([sys.executable, BOT_FILE] + sys.argv[1:], cwd=os.path.dirname(BOT_FILE))
    os._exit(0)


async def notify_update_available(remote: str):
    if is_version_notified(remote):
        return
    mark_version_notified(remote)
    for oid in get_owners():
        try:
            user = await bot.fetch_user(oid)
            await user.send(
                f"🔄 Nouvelle version disponible : `{BOT_VERSION}` → `{remote}`\n"
                f"Utilise `+update <mot de passe>` pour l'installer."
            )
        except Exception:
            pass


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
        ok, detail = await apply_update_and_restart(reason="auto", remote=remote)
        if not ok:
            print(f"[update] Échec de la mise à jour auto : {detail}")
            await notify_update_available(remote)
        return
    await notify_update_available(remote)


# ----------------------------------------------------------------------
# Événements
# ----------------------------------------------------------------------

@bot.event
async def setup_hook():
    # Synchronise les commandes slash (/ping, /help, ...)
    await bot.tree.sync()


@bot.event
async def on_ready():
    print(f"Bot connecté : {bot.user} ({bot.user.id})")
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.CustomActivity(name="MP moi pour du support")
    )
    # on_ready peut être appelé plusieurs fois (reconnexions)
    if not update_check_loop.is_running():
        update_check_loop.start()


# ----------------------------------------------------------------------
# Commandes slash
# ----------------------------------------------------------------------

@bot.tree.command(name="ping", description="Latence du bot")
async def slash_ping(inter: discord.Interaction):
    await inter.response.send_message(f"Pong ! Latence : {round(bot.latency*1000)}ms")


@bot.tree.command(name="help", description="Affiche l'aide")
async def slash_help(inter: discord.Interaction):
    if not is_owner(inter.user.id):
        await inter.response.send_message("Seuls les owners peuvent utiliser cette commande.", ephemeral=True)
        return
    emb = discord.Embed(title="📖 Commandes", color=0x5865F2)
    emb.add_field(name="👑 Propriétaire", value="`+owner` `+owner @user`", inline=False)
    emb.add_field(name="🛡️ Modération", value="`+kick` `+ban` etc.", inline=False)
    await inter.response.send_message(embed=emb)


# ----------------------------------------------------------------------
# Commande +update (une seule, l'ancien doublon a été supprimé)
# ----------------------------------------------------------------------

@bot.command(name="update", aliases=["updateinstall"])
async def update_install_cmd(ctx: commands.Context, password: Optional[str] = None):
    if not is_owner(ctx.author.id):
        return

    # Supprime le message pour ne pas laisser le mot de passe visible dans le salon
    if password is not None:
        try:
            await ctx.message.delete()
        except Exception:
            pass

    if not UPDATE_PASSWORD:
        await ctx.send("❌ UPDATE_PASSWORD n'est pas défini dans le fichier .env.")
        return
    if password != UPDATE_PASSWORD:
        await ctx.send("❌ Mot de passe incorrect.")
        return

    now = time.time()
    if ctx.author.id in COMMAND_LIMIT and now - COMMAND_LIMIT[ctx.author.id] < COMMAND_LIMIT_TIME:
        await ctx.send("❌ Tu dois attendre 5 secondes.")
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

    author_id = ctx.author.id

    class ConfirmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=30)

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if interaction.user.id != author_id:
                await interaction.response.send_message("Ce bouton ne t'est pas destiné.", ephemeral=True)
                return False
            return True

        @discord.ui.button(label="Oui, mettre à jour", style=discord.ButtonStyle.success)
        async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(content="⏳ Mise à jour en cours...", embed=None, view=None)
            ok, detail = await apply_update_and_restart(
                channel_id=interaction.channel.id, reason="manuel", remote=remote
            )
            # On n'arrive ici qu'en cas d'échec (sinon le bot redémarre)
            if not ok:
                await interaction.followup.send(f"❌ Échec de la mise à jour : {detail}")

        @discord.ui.button(label="Non, plus tard", style=discord.ButtonStyle.secondary)
        async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(content="Mise à jour annulée.", embed=None, view=None)

    await ctx.send(embed=emb, view=ConfirmView())


if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN manquant dans le fichier .env")
    else:
        try:
            bot.run(TOKEN)
        except discord.LoginFailure:
            print(
                "❌ Token refusé par Discord (401).\n"
                "   - Régénère-le dans Developer Portal > Bot > Reset Token\n"
                "   - Dans le .env : DISCORD_TOKEN=xxxx (sans guillemets, sans espace, sans 'Bot ')\n"
                f"   - Longueur du token lu : {len(TOKEN)} caractères (environ 70 attendus)"
            )
        except discord.PrivilegedIntentsRequired:
            print(
                "❌ Intents privilégiés non activés.\n"
                "   Developer Portal > Bot > Privileged Gateway Intents :\n"
                "   activer 'Message Content Intent' et 'Server Members Intent'."
            )
