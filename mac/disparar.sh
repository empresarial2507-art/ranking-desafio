#!/bin/bash
# Pede ao GitHub uma rodada do ranking (o cron do próprio GitHub atrasa horas).
# Roda pelo launchd a cada 30 min enquanto o Mac está acordado.
GH=/Users/natancarvalhoguedes/.local/bin/gh
REPO=empresarial2507-art/ranking-desafio

# Desafio acabou em 30/10: depois de 31/10 não faz nada.
[ "$(date +%Y%m%d)" -gt 20261031 ] && exit 0

for tentativa in 1 2 3; do
  if "$GH" workflow run update.yml -R "$REPO" --ref main >/dev/null 2>&1; then
    echo "$(date '+%d/%m %H:%M') ok"
    exit 0
  fi
  sleep 60  # Mac acabou de acordar e a rede ainda não voltou
done
echo "$(date '+%d/%m %H:%M') falhou após 3 tentativas"
exit 1
