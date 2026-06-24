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

# Limite par défaut des pièces jointes Discord (8 Mo).
# Passe à 25 * 1024 * 1024 si le serveur est boosté niveau 2, ou 50/100 Mo selon le palier.
MAX_SIZE_BYTES = 8 * 1024 * 1024


def download_tiktok(url: str, out_dir: str):
    """Télécharge la vidéo TikTok dans out_dir et retourne le chemin du fichier, ou None si échec."""
    ydl_opts = {
        'outtmpl': os.path.join(out_dir, '%(id)s.%(ext)s'),
        'format': 'mp4/bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # Si le merge a changé l'extension en .mp4
            if not os.path.exists(filename):
                base, _ = os.path.splitext(filename)
                alt = base + '.mp4'
                if os.path.exists(alt):
                    return alt
            return filename
    except Exception as e:
        print(f"Erreur de téléchargement : {e}")
        return None


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

    async with message.channel.typing():
        with tempfile.TemporaryDirectory() as tmp_dir:
            filepath = await asyncio.to_thread(download_tiktok, original_url, tmp_dir)

            if not filepath or not os.path.exists(filepath):
                await message.reply("❌ Impossible de récupérer cette vidéo (lien privé, supprimé, ou non supporté).")
                return

            size = os.path.getsize(filepath)
            if size > MAX_SIZE_BYTES:
                await message.reply(
                    f"⚠️ Vidéo trop lourde pour être envoyée directement ici ({size / (1024*1024):.1f} Mo)."
                )
                return

            try:
                await message.reply(file=discord.File(filepath))
            except discord.HTTPException as e:
                await message.reply(f"❌ Erreur en envoyant le fichier : {e}")
                return

    # On supprime l'aperçu original buggé de TikTok
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
