import discord
import re
import os
import asyncio
import aiohttp
from urllib.parse import urlparse
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


def strip_instagram_tracking_params(url: str) -> str:
    # Les liens contenant le tracker de partage igsh/igsi posent problème
    # à certaines API. On retire tout le query string par précaution.
    return urlparse(url)._replace(query='').geturl()


# Depuis le 15 juin 2026, Meta a rouvert l'API oEmbed d'Instagram sans
# nécessiter de token/app développeur (elle était fermée depuis 2020).
# C'est donc la source la plus fiable pour récupérer une miniature/titre
# d'un post public, bien plus stable que les fixers tiers non-officiels
# (InstaFix, kkinstagram, etc.) qui reposent sur du scraping bloqué par Meta.
META_OEMBED_URL = 'https://graph.facebook.com/v25.0/instagram_oembed'


async def fetch_instagram_oembed(url: str) -> dict | None:
    try:
        async with http_session.get(
            META_OEMBED_URL,
            params={'url': url, 'maxwidth': 540},
            headers=BROWSER_HEADERS,
            timeout=aiohttp.ClientTimeout(total=8)
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                print(f"[Instagram oEmbed] status {resp.status} pour {url} -> {body}", flush=True)
                return None
            data = await resp.json(content_type=None)
            print(f"[Instagram oEmbed] OK pour {url} (thumbnail: {bool(data.get('thumbnail_url'))})", flush=True)
            return data
    except Exception as e:
        print(f"[Instagram oEmbed] erreur pour {url} : {e}", flush=True)
        return None


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
    insta_match = INSTAGRAM_REGEX.search(message.content)

    if tiktok_match:
        original_url = tiktok_match.group(0)
        if await is_tiktok_photo_post(original_url):
            fixed_url = swap_domain(original_url, 'tiktok.com', 'tnktok.com')
        else:
            fixed_url = swap_domain(original_url, 'tiktok.com', 'kktiktok.com')

        await reply_with_retry(message, content=f"🎥 Voici la vidéo :\n{fixed_url}")
        await suppress_original_embed(message)

    elif insta_match:
        original_url = strip_instagram_tracking_params(insta_match.group(0))
        data = await fetch_instagram_oembed(original_url)

        if data and data.get('thumbnail_url'):
            embed = discord.Embed(
                title=data.get('title') or 'Publication Instagram',
                url=original_url,
                description=f"Par {data['author_name']}" if data.get('author_name') else None,
                color=0xE1306C,
            )
            embed.set_image(url=data['thumbnail_url'])
            sent = await reply_with_retry(message, embed=embed)
            if not sent:
                await reply_with_retry(message, content=f"🎬 Voici le reel :\n{original_url}")
        else:
            # oEmbed a échoué (post privé/supprimé ou souci ponctuel de l'API) :
            # on renvoie simplement le lien d'origine plutôt que rien du tout.
            await reply_with_retry(message, content=f"🎬 Voici le reel :\n{original_url}")

        await suppress_original_embed(message)

# ==========================================
# 4. DÉMARRAGE
# ==========================================
keep_alive()

token = os.environ.get('DISCORD_TOKEN')
if token:
    client.run(token)
