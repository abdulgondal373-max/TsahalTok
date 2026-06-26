import discord
import re
import os
import json
import asyncio
import tempfile
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

# On cherche un lien TikTok (qu'il soit court avec vm./vt. ou long avec www.)
TIKTOK_REGEX = re.compile(r'https?://(?:www\.|vm\.|vt\.)?tiktok\.com/[^\s]+')

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

# TikTok intègre les données de chaque page dans ce bloc <script>
REHYDRATION_SCRIPT_RE = re.compile(
    r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
    re.DOTALL
)

# Session HTTP partagée, créée une seule fois au démarrage
http_session: aiohttp.ClientSession | None = None

# On ne traite qu'un post photo à la fois (téléchargement d'images)
PROCESSING_SEMAPHORE = asyncio.Semaphore(1)


def fix_tiktok_url(url: str) -> str:
    """Remplace uniquement le domaine tiktok.com par kktiktok.com, peu importe le sous-domaine (vm., vt., www.)."""
    return re.sub(r'tiktok\.com', 'kktiktok.com', url, count=1)


async def resolve_tiktok_url(url: str) -> str:
    """Suit les redirections (liens courts vm./vt.) pour obtenir l'URL finale (avec /video/ ou /photo/)."""
    try:
        async with http_session.get(
            url, headers=BROWSER_HEADERS, allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            return str(resp.url)
    except Exception as e:
        print(f"Erreur de résolution d'URL : {e}", flush=True)
        return url


async def fetch_photo_image_urls(resolved_url: str):
    """Lit les données intégrées de la page TikTok pour en extraire les URLs des images d'un post photo."""
    try:
        async with http_session.get(
            resolved_url, headers=BROWSER_HEADERS, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            html = await resp.text()
    except Exception as e:
        print(f"Erreur de récupération de la page : {e}", flush=True)
        return []

    match = REHYDRATION_SCRIPT_RE.search(html)
    if not match:
        print("Bloc de données introuvable sur la page (structure TikTok peut-être changée).", flush=True)
        return []

    try:
        data = json.loads(match.group(1))
        item_struct = (
            data.get('__DEFAULT_SCOPE__', {})
            .get('webapp.video-detail', {})
            .get('itemInfo', {})
            .get('itemStruct', {})
        )
        images = item_struct.get('imagePost', {}).get('images', [])
        urls = []
        for img in images:
            url_list = img.get('imageURL', {}).get('urlList', [])
            if url_list:
                urls.append(url_list[0])
        return urls
    except Exception as e:
        print(f"Erreur de lecture des données de la page : {e}", flush=True)
        return []


async def download_images(urls, out_dir: str, referer: str):
    """Télécharge chaque image et retourne la liste des chemins locaux obtenus."""
    headers = dict(BROWSER_HEADERS)
    headers['Referer'] = referer
    paths = []
    for i, img_url in enumerate(urls[:10]):  # Discord limite à 10 fichiers par message
        try:
            async with http_session.get(
                img_url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    continue
                content = await resp.read()
            path = os.path.join(out_dir, f"photo_{i}.jpg")
            with open(path, 'wb') as f:
                f.write(content)
            paths.append(path)
        except Exception as e:
            print(f"Erreur de téléchargement de l'image {i} : {e}", flush=True)
    return paths


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
    # On ignore les messages des bots
    if message.author.bot:
        return

    match = TIKTOK_REGEX.search(message.content)
    if not match:
        return

    original_url = match.group(0)
    resolved_url = await resolve_tiktok_url(original_url)

    if '/photo/' in resolved_url:
        # Vrai carrousel photo : on télécharge les images nous-mêmes
        async with PROCESSING_SEMAPHORE:
            async with message.channel.typing():
                with tempfile.TemporaryDirectory() as tmp_dir:
                    image_urls = await fetch_photo_image_urls(resolved_url)
                    print(f"[photo] {len(image_urls)} URL(s) d'image trouvée(s) pour {resolved_url}", flush=True)
                    paths = await download_images(image_urls, tmp_dir, resolved_url) if image_urls else []
                    print(f"[photo] {len(paths)} image(s) téléchargée(s) avec succès", flush=True)

                    if not paths:
                        await message.reply(
                            "❌ Impossible de récupérer les photos de ce post.\n"
                            f"Voir directement sur TikTok : {original_url}"
                        )
                        return

                    files = [discord.File(p) for p in paths]
                    try:
                        await message.reply(files=files)
                    except discord.HTTPException as e:
                        await message.reply(f"❌ Erreur en envoyant les photos : {e}")
                        return
    else:
        # Vidéo : lien kktiktok instantané
        fixed_url = fix_tiktok_url(original_url)
        await message.reply(f"🎥 Voici la vidéo :\n{fixed_url}")

    # On supprime l'aperçu original (souvent cassé) de TikTok
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
