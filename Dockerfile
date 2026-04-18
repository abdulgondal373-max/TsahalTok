FROM python:3.10-slim

# Installation de FFmpeg (requis par yt-dlp pour manipuler certaines vidéos)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source
COPY . .

# Lancement du bot
CMD ["python", "main.py"]
