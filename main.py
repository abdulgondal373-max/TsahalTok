import discord
import re
import os
import subprocess
import asyncio
import tempfile
from flask import Flask
from threading import Thread
import yt_dlp
import imageio_ffmpeg

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

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

# Limite Discord (mise à jour 2024 : 10 Mo pour les comptes gratuits, 50 Mo Nitro Basic, 500 Mo Nitro).
# Les boosts de serveur ne changent PAS cette limite individuelle (elle dépend du compte de l'expéditeur, pas du serveur),
# donc on reste prudent. On vise une marge de sécurité car Discord compte en Mo décimaux (1 Mo = 1 000 000 octets).
DISCORD_LIMIT_BYTES = 10_000_000
COMPRESS_TARGET_BYTES = 9_000_000  # cible un peu sous la limite pour la marge de conteneur/métadonnées


def get_duration_seconds(path: str) -> float:
    """Récupère la durée d'une vidéo en secondes via ffmpeg (lecture du stderr)."""
    try:
        result = subprocess.run(
            [FFMPEG_PATH, '-i', path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        for line in result.stderr.splitlines():
            line = line.strip()
            if line.startswith('Duration:'):
                time_str = line.split('Duration:')[1].split(',')[0].strip()
                h, m, s = time_str.split(':')
                return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception as e:
        print(f"Erreur de lecture de durée : {e}")
    return 0.0


def compress_video(input_path: str, output_path: str, target_size_bytes: int) -> bool:
    """Recompresse une vidéo pour viser une taille cible, en ajustant bitrate + résolution."""
    duration = get_duration_seconds(input_path)
    if duration <= 0:
        duration = 30.0  # valeur prudente si la durée n'a pas pu être lue

    audio_bitrate = 64_000  # 64 kbps, suffisant pour une vidéo TikTok
    # On vise 92% de la taille cible pour laisser de la marge au conteneur/métadonnées
    target_bits = target_size_bytes * 8 * 0.92
    video_bitrate = max(int(target_bits / duration) - audio_bitrate, 150_000)

    cmd = [
        FFMPEG_PATH, '-y', '-i', input_path,
        '-c:v', 'libx264', '-b:v', str(video_bitrate), '-maxrate', str(int(video_bitrate * 1.2)),
        '-bufsize', str(int(video_bitrate * 2)),
        '-vf', 'scale=720:-2',
        '-c:a', 'aac', '-b:a', str(audio_bitrate),
        output_path,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return os.path.exists(output_path)
    except Exception as e:
        print(f"Erreur de compression : {e}")
        return False


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
                await message.reply(
                    "🔒 Cette vidéo est restreinte par TikTok (âge, privée, ou supprimée) et je ne peux pas "
                    f"l'afficher ici.\nVoir directement sur TikTok : {original_url}"
                )
                return

            size = os.path.getsize(filepath)
            if size > DISCORD_LIMIT_BYTES:
                compressed_path = os.path.join(tmp_dir, "compressed.mp4")
                ok = await asyncio.to_thread(
                    compress_video, filepath, compressed_path, COMPRESS_TARGET_BYTES
                )
                if ok and os.path.exists(compressed_path) and os.path.getsize(compressed_path) <= DISCORD_LIMIT_BYTES:
                    filepath = compressed_path
                else:
                    await message.reply(
                        f"⚠️ Vidéo trop lourde même après compression ({size / 1_000_000:.1f} Mo).\n"
                        f"Voir directement sur TikTok : {original_url}"
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
