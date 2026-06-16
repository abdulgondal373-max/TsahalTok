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
    return "Bot Quickvids en ligne !"

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

# ==========================================
# 3. ÉVÉNEMENTS DU BOT
# ==========================================
@client.event
async def on_ready():
    print(f'✅ Bot Quickvids connecté : {client.user}')

@client.event
async def on_message(message):
    # On ignore les messages des bots
    if message.author.bot:
        return

    # On cherche un lien TikTok
    match = re.search(r'https?://(?:www\.|vm\.|vt\.)?tiktok\.com/[^\s]+', message.content)
    
    if match:
        original_url = match.group(0)
        
        # ON FORCE QUICKVIDS ICI (On remplace simplement le mot tiktok.com par quickvids.app)
        working_url = re.sub(r'(https?://(?:www\.|vm\.|vt\.)?)tiktok\.com', r'\1quickvids.app', original_url)
        
        # Le bot répond directement
        await message.reply(f"🎥 **Voici la vidéo :**\n{working_url}")
        
        # On supprime l'aperçu original buggé de TikTok
        try:
            await message.edit(suppress=True)
        except:
            pass

# ==========================================
# 4. DÉMARRAGE
# ==========================================
keep_alive()

token = os.environ.get('DISCORD_TOKEN')
if token:
    client.run(token)
