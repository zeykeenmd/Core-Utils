import os
import json
import asyncio
import random
import re
import platform
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

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

# ==================== UTILS ====================
def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def load_json(path: str, default: Any = None) -> Any:
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

# ==================== BOT ====================
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)

# ==================== TASKS ====================
@tasks.loop(seconds=300)
async def update_check_loop():
    # système update reste inchangé

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

# ==================== RUN ====================
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN manquant")
    else:
        bot.run(TOKEN)
