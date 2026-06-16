import discord
import re
import os
import aiohttp
from flask import Flask
from threading import Thread

# ==========================================
# 1. SERVEUR WEB (Pour Render)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot Rapide en ligne !"

def run_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_server)
    t.start()

# ==========================================
# 2. CONFIGURATION DU BOT ET DES MIROIRS
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Liste de secours. Si le premier est mort, il teste le 2ème, etc.
MIRRORS = [
    "quickvids.app",
    "tnktok.com",
    "tiktxk.com",
    "tikt0k.com"
]

async def get_working_link(original_link):
    """Teste les miroirs pour trouver celui qui fonctionne"""
    async with aiohttp.ClientSession() as session:
        for mirror in MIRRORS:
            test_link = re.sub(r'(https?://(?:www\.|vm\.|vt\.)?)tiktok\.com', rf'\1{mirror}', original_link)
            try:
                # Requête ultra-rapide pour vérifier si le site est en ligne
                async with session.head(test_link, timeout=1.5) as response:
                    if response.status == 200:
                        return test_link
            except:
                continue
    
    return re.sub(r'(https?://(?:www\.|vm\.|vt\.)?)tiktok\.com', rf'\1{MIRRORS[0]}', original_link)

# ==========================================
# 3. ÉVÉNEMENTS DU BOT
# ==========================================
@client.event
async def on_ready():
    print(f'✅ Bot rapide connecté : {client.user}')

@client.event
async def on_message(message):
    # On ignore les messages des autres bots ou de lui-même
    if message.author.bot:
        return

    # On cherche un lien TikTok
    match = re.search(r'https?://(?:www\.|vm\.|vt\.)?tiktok\.com/[^\s]+', message.content)
    
    if match:
        original_url = match.group(0)
        
        # Le bot trouve le bon lien miroir
        working_url = await get_working_link(original_url)
        
        # Le bot répond directement au message
        await message.reply(f"🎥 **Voici la vidéo :**\n{working_url}")
        
        # Petite astuce : on essaie de cacher l'aperçu de base du message de ton pote
        # (car TikTok affiche souvent un encart noir inutile)
        try:
            await message.edit(suppress=True)
        except:
            pass # S'il n'a pas les droits, ce n'est pas grave, il continue

# ==========================================
# 4. DÉMARRAGE
# ==========================================
keep_alive()

token = os.environ.get('DISCORD_TOKEN')
if token:
    client.run(token)
