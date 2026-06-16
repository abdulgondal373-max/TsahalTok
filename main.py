import discord
import re
import os
import asyncio
import subprocess
from flask import Flask
from threading import Thread

# ==========================================
# 1. SERVEUR WEB (Pour éviter la mise en veille sur Render)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Le bot est en ligne et actif !"

def run_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_server)
    t.start()

# ==========================================
# 2. CONFIGURATION DU BOT DISCORD
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Détection de tous les formats de liens TikTok
TIKTOK_REGEX = r"https?://(?:www\.|vm\.|vt\.)?tiktok\.com/[^\s]+"

# ==========================================
# 3. FONCTION DE TÉLÉCHARGEMENT OPTIMISÉE
# ==========================================
def download_video(url, filename):
    """Télécharge le meilleur fichier vidéo déjà fusionné pour ne pas saturer le CPU"""
    subprocess.run(
        [
            "yt-dlp", 
            "-f", "b[ext=mp4]/b", # Cherche la meilleure qualité déjà assemblée
            "--no-playlist",      # Ne prend pas toute une playlist
            "--no-warnings",      # Cache les avertissements inutiles
            "--quiet",            # Rend la console plus propre
            "-o", filename, 
            url
        ], 
        check=True, 
        stdout=subprocess.DEVNULL, 
        stderr=subprocess.DEVNULL
    )

# ==========================================
# 4. ÉVÉNEMENTS DU BOT
# ==========================================
@client.event
async def on_ready():
    print(f'✅ Bot connecté avec succès : {client.user}')

@client.event
async def on_message(message):
    # Ignorer les messages du bot lui-même
    if message.author == client.user:
        return

    # Si un lien TikTok est trouvé
    match = re.search(TIKTOK_REGEX, message.content)
    if match:
        url = match.group(0)
        status_msg = await message.channel.send("⚡ Téléchargement en cours...")
        filename = f"tiktok_{message.id}.mp4"
        
        try:
            # Lancer le téléchargement en arrière-plan sans bloquer le bot
            await asyncio.to_thread(download_video, url, filename)
            
            # Vérifier si le fichier a bien été créé
            if os.path.exists(filename):
                size_mb = os.path.getsize(filename) / (1024 * 1024)
                
                # Vérifier la taille (Discord limite à 25 Mo)
                if size_mb < 24: 
                    await message.reply(file=discord.File(filename))
                    await status_msg.delete()
                else:
                    await status_msg.edit(content="❌ La vidéo est trop lourde pour être envoyée sur Discord (plus de 25 Mo).")
            else:
                raise Exception("Fichier non généré.")
                
        except Exception as e:
            print(f"Erreur de téléchargement : {e}")
            await status_msg.edit(content="❌ Impossible de télécharger cette vidéo (elle est peut-être privée ou supprimée).")
            
        finally:
            # Toujours supprimer la vidéo du serveur une fois envoyée
            if os.path.exists(filename):
                os.remove(filename)

# ==========================================
# 5. DÉMARRAGE
# ==========================================
keep_alive()

token = os.environ.get('DISCORD_TOKEN')
if not token:
    print("❌ ERREUR : La variable d'environnement DISCORD_TOKEN est introuvable.")
else:
    client.run(token)
