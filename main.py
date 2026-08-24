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

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

http_session: aiohttp.ClientSession | None = None


def swap_domain(url: str, old_domain: str, new_domain: str) -> str:
    return re.sub(re.escape(old_domain), new_domain, url, count=1)


async def is_tiktok_photo_post(url: str) -> bool:
    # Utilise l'API oEmbed officielle de TikTok pour détecter le type de post
    # (plus fiable que suivre nous-mêmes les redirections, qui échouait
    # souvent silencieusement et faisait retomber tous les liens sur "vidéo").
    try:
        async with http_session.get(
            'https://www.tiktok.com/oembed',
            params={'url': url},
            headers=BROWSER_HEADERS,
            timeout=aiohttp.ClientTimeout(total=6)
        ) as resp:
            if resp.status != 200:
                return False
            data = await resp.json(content_type=None)
            return data.get('type') != 'video'
    except Exception as e:
        print(f"Erreur oEmbed TikTok : {e}", flush=True)
        return False


async def reply_with_retry(message, **kwargs):
    for attempt in range(3):
        try:
            await message.reply(**kwargs)
            return True
        except discord.errors.HTTPException as e:
            if e.status == 429:
                wait = 5 * (attempt + 1)
                print(f"Rate limit Discord (tentative {attempt+1}), attente {wait}s...", flush=True)
                await asyncio.sleep(wait)
            else:
                print(f"Erreur Discord lors du reply : {e}", flush=True)
                return False
    return False


async def suppress_original_embed(message):
    await asyncio.sleep(1.5)
    try:
        await message.edit(suppress=True)
    except Exception:
        pass


# ==========================================
# 3. ÉVÉNEMENTS DU BOT
# ==========================================
@client.event
async def on_ready():
    global http_session
    http_session = aiohttp.ClientSession()
    await client.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.playing,
            name="Shabbat shalom 🇮🇱🇮🇱🇮🇱"
        )
    )
    print(f'✅ Bot TsahalTok connecté : {client.user}', flush=True)

@client.event
async def on_message(message):
    if message.author.bot:
        return

    tiktok_match = TIKTOK_REGEX.search(message.content)
    if not tiktok_match:
        return

    original_url = tiktok_match.group(0)
    if await is_tiktok_photo_post(original_url):
        fixed_url = swap_domain(original_url, 'tiktok.com', 'tnktok.com')
    else:
        fixed_url = swap_domain(original_url, 'tiktok.com', 'kktiktok.com')

    await reply_with_retry(message, content=f"🎥 Voici la vidéo :\n{fixed_url}")
    await suppress_original_embed(message)

# ==========================================
# 4. DÉMARRAGE
# ==========================================
keep_alive()

token = os.environ.get('DISCORD_TOKEN')
if token:
    client.run(token)
