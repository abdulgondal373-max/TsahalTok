import discord
import re
import os
import subprocess

# Configuration des intents (nécessaire pour lire le contenu des messages)
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Regex pour détecter les liens TikTok (classiques et raccourcis)
TIKTOK_REGEX = r"(https?://(?:www\.)?(?:vm\.)?tiktok\.com/[a-zA-Z0-9_]+/?|https?://(?:www\.)?tiktok\.com/@[a-zA-Z0-9_.]+/video/[0-9]+)"

@client.event
async def on_ready():
    print(f'✅ Bot connecté en tant que {client.user}')

@client.event
async def on_message(message):
    # Ignorer les messages du bot lui-même
    if message.author == client.user:
        return

    # Recherche d'un lien TikTok dans le message
    match = re.search(TIKTOK_REGEX, message.content)
    if match:
        url = match.group(0)
        status_message = await message.channel.send("⏳ Téléchargement de la vidéo TikTok...")
        
        filename = f"tiktok_{message.id}.mp4"
        
        try:
            # Utilisation de yt-dlp pour télécharger la vidéo
            # Format spécifié pour s'assurer d'avoir du mp4 compatible
            subprocess.run([
                "yt-dlp", 
                "-f", "b[ext=mp4]/best", 
                "-o", filename, 
                url
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Vérification de la taille (Discord limite à 25 Mo pour les serveurs gratuits)
            if os.path.getsize(filename) < 25 * 1024 * 1024:
                await message.reply(file=discord.File(filename))
                await status_message.delete()
            else:
                await status_message.edit(content="❌ La vidéo est trop lourde pour être envoyée sur Discord (limite de 25 Mo).")

        except Exception as e:
            print(f"Erreur: {e}")
            await status_message.edit(content="❌ Impossible de récupérer cette vidéo (elle est peut-être privée ou supprimée).")
            
        finally:
            # Nettoyage du fichier pour ne pas surcharger le serveur Koyeb
            if os.path.exists(filename):
                os.remove(filename)

# Lancement du bot avec le token récupéré dans les variables d'environnement
client.run(os.environ['DISCORD_TOKEN'])
