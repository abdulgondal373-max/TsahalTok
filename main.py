import discord
import re
import os
import asyncio
import subprocess
from flask import Flask
from threading import Thread

# ==========================================
# 1. SERVEUR WEB (Pour éviter la mise en veille)
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
# 2. BOT DISCORD TIKTOK
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

TIKTOK_REGEX = r"https?://(?:www\.|vm\.|vt\.)?tiktok\.com/[^\s]+"

def download_video(url, filename):
    """Fonction de téléchargement exécutée en arrière-plan"""
    subprocess.run(
        ["yt-dlp", "-f", "best[ext=mp4]", "-o", filename, "--no-playlist", url], 
        check=True, 
        stdout=subprocess.DEVNULL, 
        stderr=subprocess.DEVNULL
    )

@client.event
async def on_ready():
    print(f'✅ Bot connecté avec succès : {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    match = re.search(TIKTOK_REGEX, message.content)
    if match:
        url = match.group(0)
        status_msg = await message.channel.send("⏳ Téléchargement de la vidéo...")
        filename = f"tiktok_{message.id}.mp4"
        
        try:
            # Lancement du téléchargement sans bloquer les autres commandes du bot
            await asyncio.to_thread(download_video, url, filename)
            
            # Vérification de la taille et envoi
            if os.path.exists(filename):
                size_mb = os.path.getsize(filename) / (1024 * 1024)
                
                if size_mb < 24: # Limite Discord à 25 Mo (on garde une marge)
                    await message.reply(file=discord.File(filename))
                    await status_msg.delete()
                else:
                    await status_msg.edit(content="❌ Cette vidéo est trop lourde pour être envoyée sur Discord (plus de 25 Mo).")
            else:
                raise Exception("Fichier non trouvé après téléchargement.")
                
        except Exception as e:
            print(f"Erreur : {e}")
            await status_msg.edit(content="❌ Impossible de télécharger cette vidéo (lien privé, supprimé ou erreur serveur).")
            
        finally:
            # Nettoyage systématique du serveur pour ne pas saturer Render
            if os.path.exists(filename):
                os.remove(filename)

# ==========================================
# 3. LANCEMENT
# ==========================================
keep_alive()

# Récupération du token depuis les variables d'environnement de Render
token = os.environ.get('DISCORD_TOKEN')
if not token:
    print("❌ ERREUR : La variable DISCORD_TOKEN n'est pas définie.")
else:
    client.run(token)
