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
    return "Bot Webhook Anti-Crash en ligne !"

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

# Liste des meilleurs miroirs actuels. 
# Si le #1 saute, il prend le #2, etc.
MIRRORS = [
    "vxtiktok.com",
    "tnktok.com",
    "tiktxk.com",
    "tikt0k.com"
]

async def get_working_link(original_link):
    """Teste les miroirs en temps réel et renvoie le premier qui est en ligne"""
    async with aiohttp.ClientSession() as session:
        for mirror in MIRRORS:
            # On fabrique le lien avec le miroir testé
            test_link = re.sub(r'(https?://(?:www\.|vm\.|vt\.)?)tiktok\.com', rf'\1{mirror}', original_link)
            try:
                # On fait une requête "HEAD" (très rapide, ça ne télécharge pas la vidéo)
                async with session.head(test_link, timeout=1.5) as response:
                    if response.status == 200:
                        return test_link # Bingo, ce miroir fonctionne !
            except:
                continue # Le miroir est mort (timeout ou erreur), on teste le suivant
    
    # Si par malheur TOUS les miroirs de la liste sont morts, on renvoie quand même le premier par défaut
    return re.sub(r'(https?://(?:www\.|vm\.|vt\.)?)tiktok\.com', rf'\1{MIRRORS[0]}', original_link)

# ==========================================
# 3. ÉVÉNEMENTS DU BOT
# ==========================================
@client.event
async def on_ready():
    print(f'✅ Bot automatique (avec Secours) connecté : {client.user}')

@client.event
async def on_message(message):
    if message.author.bot:
        return

    # Vérifie si le message contient un lien TikTok
    match = re.search(r'https?://(?:www\.|vm\.|vt\.)?tiktok\.com/[^\s]+', message.content)
    
    if match:
        original_url = match.group(0)
        
        # 1. Cherche le miroir qui fonctionne actuellement
        working_url = await get_working_link(original_url)
        
        # 2. Remplace le lien dans le message de base (au cas où il a écrit du texte avec)
        new_content = message.content.replace(original_url, working_url)

        try:
            # 3. Utilisation du Webhook pour se faire passer pour ton pote
            webhooks = await message.channel.webhooks()
            webhook = discord.utils.get(webhooks, name="TikTokFixer")
            if not webhook:
                webhook = await message.channel.create_webhook(name="TikTokFixer")

            await webhook.send(
                content=new_content,
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url
            )

            # 4. Suppression du message original
            await message.delete()

        except discord.errors.Forbidden:
            # Sécurité si le bot n'a pas les droits
            await message.reply(f"🎥 **Vidéo :**\n{working_url}")

# ==========================================
# 4. DÉMARRAGE
# ==========================================
keep_alive()

token = os.environ.get('DISCORD_TOKEN')
if token:
    client.run(token)
