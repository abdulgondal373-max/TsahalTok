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


def fix_instagram_url(url: str, domain: str) -> str:
    return swap_domain(url, 'instagram.com', domain)


# Liste de fixers testés par ordre de préférence. Le bot vérifie lequel
# répond correctement (pas de 404/erreur) avant de l'utiliser, car ces
# services tiers non-officiels tombent fréquemment.
INSTAGRAM_FIXERS = [
    'ddinstagram.com',
    'fxig.seria.moe',
    'eeinstagram.com',
    'instagramez.com',
    'uuinstagram.com',
    'toinstagram.com',
]


async def get_working_instagram_fixer(original_url: str) -> str:
    for domain in INSTAGRAM_FIXERS:
        candidate = fix_instagram_url(original_url, domain)
        try:
            # GET plutôt que HEAD : plusieurs de ces services (edge workers)
            # ne supportent pas HEAD et renvoient une erreur, faisant
            # échouer la vérification alors que le lien fonctionne réellement.
            async with http_session.get(
                candidate, headers=BROWSER_HEADERS, allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=6)
            ) as resp:
                if resp.status >= 400:
                    continue
                # Un simple statut 200 ne suffit pas : certains services morts
                # renvoient leur page d'accueil générique (200 OK) au lieu du
                # post demandé. On vérifie donc que la réponse contient bien
                # les balises Open Graph d'un post réel (og:video/og:image).
                html = await resp.text()
                if 'og:video' in html or 'og:image' in html:
                    return candidate
        except Exception:
            continue
    # Aucun fixer disponible : on renvoie le lien Instagram original
    return original_url


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
        if await is_tiktok_photo_post(original_url):
            fixed_url = swap_domain(original_url, 'tiktok.com', 'tnktok.com')
        else:
            fixed_url = swap_domain(original_url, 'tiktok.com', 'kktiktok.com')
        label = "🎥 Voici la vidéo :"
    elif insta_match:
        original_url = insta_match.group(0)
        fixed_url = await get_working_instagram_fixer(original_url)
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
