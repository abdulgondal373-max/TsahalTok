import discord
import re
import os
from flask import Flask
from threading import Thread

# ==========================================
# 1. SERVEUR WEB (Pour Render)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot ultra-rapide en ligne !"

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

@client.event
async def on_ready():
    print(f'✅ Bot ultra-rapide connecté : {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Si le message contient un lien TikTok
    if "tiktok.com" in message.content:
        # On remplace "tiktok.com" par "vxtiktok.com"
        # Cette simple action permet à Discord d'afficher la vidéo directement !
        new_content = re.sub(
            r'(https?://(?:www\.|vm\.|vt\.)?)tiktok\.com', 
            r'\1vxtiktok.com', 
            message.content
        )
        
        # On envoie le nouveau lien
        await message.reply(f"🎥 **TikTok de {message.author.display_name}** :\n{new_content}")
        
        # Optionnel : On supprime l'aperçu original (souvent buggé) du lien de base
        try:
            await message.edit(suppress=True)
        except:
            pass # Si le bot n'a pas la permission de modifier les messages, on ignore

# ==========================================
# 3. DÉMARRAGE
# ==========================================
keep_alive()

token = os.environ.get('DISCORD_TOKEN')
if token:
    client.run(token)
