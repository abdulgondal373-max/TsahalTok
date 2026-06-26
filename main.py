import discord
import re
import os
import asyncio
import tempfile
from flask import Flask
from threading import Thread
import yt_dlp

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

IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp')

# On ne traite qu'un post photo à la fois (le téléchargement d'images reste un peu coûteux en RAM).
PROCESSING_SEMAPHORE = asyncio.Semaphore(1)


def fix_tiktok_url(url: str) -> str:
    """Remplace uniquement le domaine tiktok.com par kktiktok.com, peu importe le sous-domaine (vm., vt., www.)."""
    return re.sub(r'tiktok\.com', 'kktiktok.com', url, count=1)


def is_photo_post(url: str) -> bool:
    """Détecte si le lien pointe vers un post photo (carrousel) plutôt qu'une vidéo.
    Léger appel : on résout juste les infos du post, sans rien télécharger."""
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'simulate': True, 'skip_download': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            resolved = (info.get('webpage_url') or '') if info else ''
            if '/photo/' in resolved:
                return True
            # Un post photo apparaît souvent comme une "playlist" d'images chez yt-dlp
            if info and info.get('_type') == 'playlist':
                return True
    except Exception as e:
        print(f"Erreur de détection photo/vidéo : {e}")
    return False


def download_tiktok_photos(url: str, out_dir: str):
    """Télécharge les images d'un post photo TikTok et retourne la liste des fichiers obtenus."""
    ydl_opts = {
        'outtmpl': os.path.join(out_dir, '%(id)s_%(playlist_index)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
    except Exception as e:
        print(f"Erreur de téléchargement des photos : {e}")

    images = [
        os.path.join(out_dir, f) for f in os.listdir(out_dir)
        if f.lower().endswith(IMAGE_EXTS)
    ]
    return sorted(images)


# ==========================================
# 3. ÉVÉNEMENTS DU BOT
# ==========================================
@client.event
async def on_ready():
    print(f'✅ Bot TsahalTok connecté : {client.user}')

@client.event
async def on_message(message):
    # On ignore les messages des bots
    if message.author.bot:
        return

    match = TIKTOK_REGEX.search(message.content)
    if not match:
        return

    original_url = match.group(0)

    # Petit appel léger pour savoir si c'est une vidéo ou un post photo (pas de téléchargement ici)
    photo_post = await asyncio.to_thread(is_photo_post, original_url)

    if photo_post:
        async with PROCESSING_SEMAPHORE:
            async with message.channel.typing():
                with tempfile.TemporaryDirectory() as tmp_dir:
                    images = await asyncio.to_thread(download_tiktok_photos, original_url, tmp_dir)

                    if not images:
                        await message.reply(
                            "❌ Impossible de récupérer les photos de ce post.\n"
                            f"Voir directement sur TikTok : {original_url}"
                        )
                        return

                    # Discord limite à 10 fichiers par message
                    files = [discord.File(p) for p in images[:10]]
                    try:
                        await message.reply(files=files)
                    except discord.HTTPException as e:
                        await message.reply(f"❌ Erreur en envoyant les photos : {e}")
                        return
    else:
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
