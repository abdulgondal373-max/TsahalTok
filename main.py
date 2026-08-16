import discord
import re
import os
import asyncio
import aiohttp
from flask import Flask
from threading import Thread

# ==========================================
# 1. SERVEUR WEB (Pour Render)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot TsahalTok en ligne !"

def run_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_server)
    t.start()

# ==========================================
# 2. CONFIGURATION DU BOT
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

TIKTOK_REGEX = re.compile(r'https?://(?:www\.|vm\.|vt\.)?tiktok\.com/[^\s]+')
INSTAGRAM_REGEX = re.compile(r'https?://(?:www\.)?instagram\.com/(?:reel|reels|p|tv)/[^\s]+')

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

http_session: aiohttp.ClientSession | None = None


def swap_domain(url: str, old_domain: str, new_domain: str) -> str:
    return re.sub(re.escape(old_domain), new_domain, url, count=1)


def fix_instagram_url(url: str) -> str:
    # zzinstagram.com répartit automatiquement vers plusieurs fixers actifs,
    # plus fiable qu'un service fixe unique (ddinstagram/gginstagram sont morts en 2026).
    return swap_domain(url, 'instagram.com', 'zzinstagram.com')


async def resolve_url(url: str) -> str:
    try:
        async with http_session.get(
            url, headers=BROWSER_HEADERS, allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            return str(resp.url)
    except Exception as e:
        print(f"Erreur de résolution d'URL : {e}", flush=True)
        return url


# ==========================================
# 3. ÉVÉNEMENTS DU BOT
# ==========================================
@client.event
async def on_ready():
    global http_session
    http_session = aiohttp.ClientSession()
    print(f'✅ Bot TsahalTok connecté : {client.user}', flush=True)

@client.event
async def on_message(message):
    if message.author.bot:
        return

    tiktok_match = TIKTOK_REGEX.search(message.content)
    insta_match = INSTAGRAM_REGEX.search(message.content)

    if tiktok_match:
        original_url = tiktok_match.group(0)
        resolved_url = await resolve_url(original_url)

        if '/photo/' in resolved_url:
            fixed_url = swap_domain(original_url, 'tiktok.com', 'tnktok.com')
        else:
            fixed_url = swap_domain(original_url, 'tiktok.com', 'kktiktok.com')
        label = "🎥 Voici la vidéo :"
    elif insta_match:
        original_url = insta_match.group(0)
        fixed_url = fix_instagram_url(original_url)
        label = "🎬 Voici le reel :"
    else:
        return

    # Envoi avec gestion du rate limit (3 tentatives max)
    for attempt in range(3):
        try:
            await message.reply(f"{label}\n{fixed_url}")
            break
        except discord.errors.HTTPException as e:
            if e.status == 429:
                wait = 5 * (attempt + 1)
                print(f"Rate limit Discord (tentative {attempt+1}), attente {wait}s...", flush=True)
                await asyncio.sleep(wait)
            else:
                print(f"Erreur Discord lors du reply : {e}", flush=True)
                break

    # Délai pour éviter de cumuler trop d'appels API en rafale
    await asyncio.sleep(1.5)

    # Supprime l'aperçu original (souvent cassé)
    try:
        await message.edit(suppress=True)
    except Exception:
        pass

# ==========================================
# 4. DÉMARRAGE
# ==========================================
keep_alive()

token = os.environ.get('DISCORD_TOKEN')
if token:
    client.run(token)
