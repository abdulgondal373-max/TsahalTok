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

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Session HTTP partagée, créée une seule fois au démarrage (juste pour résoudre les liens courts)
http_session: aiohttp.ClientSession | None = None


def swap_domain(url: str, new_domain: str) -> str:
    """Remplace uniquement le domaine tiktok.com par new_domain, peu importe le sous-domaine (vm., vt., www.)."""
    return re.sub(r'tiktok\.com', new_domain, url, count=1)


async def resolve_tiktok_url(url: str) -> str:
    """Suit les redirections (liens courts vm./vt.) pour obtenir l'URL finale (avec /video/ ou /photo/)."""
    try:
        async with http_session.get(
            url, headers=BROWSER_HEADERS, allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            return str(resp.url)
    except Exception as e:
        print(f"Erreur de résolution d'URL : {e}", flush=True)
        return url


# ==========================================
# 3. ÉVÉNEMENTS DU BOT
# ==========================================
@client.event
async def on_ready():
    global http_session
    http_session = aiohttp.ClientSession()
    print(f'✅ Bot TsahalTok connecté : {client.user}', flush=True)

@client.event
async def on_message(message):
    # On ignore les messages des bots
    if message.author.bot:
        return

    match = TIKTOK_REGEX.search(message.content)
    if not match:
        return

    original_url = match.group(0)
    resolved_url = await resolve_tiktok_url(original_url)

    if '/photo/' in resolved_url:
        # Post photo : tnktok.com gère la génération de diaporama
        fixed_url = swap_domain(original_url, 'tnktok.com')
    else:
        # Vidéo : kktiktok.com, plus fiable pour ce cas
        fixed_url = swap_domain(original_url, 'kktiktok.com')

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
