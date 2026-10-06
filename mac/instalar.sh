#!/bin/bash
# Instala o disparo do ranking no launchd. Copia para ~/.life-growth-os porque o
# TCC do macOS impede o launchd de ler arquivos dentro do Desktop.
# Desinstalar: launchctl unload ~/Library/LaunchAgents/com.life.ranking-desafio.plist
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.life-growth-os/ranking"
PLIST="$HOME/Library/LaunchAgents/com.life.ranking-desafio.plist"
mkdir -p "$DEST"
cp "$SRC/disparar.sh" "$DEST/"
chmod +x "$DEST/disparar.sh"
cp "$SRC/com.life.ranking-desafio.plist" "$PLIST"
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Instalado. Log: $DEST/disparos.log"
