# Ranking do Desafio Outubro das Gostosas (LIFE)

Ranking paralelo ao da Cativa, que pontua qualquer interação e permite farmar pontos com spam.
Aqui o ponto vem das metas do desafio, comprovadas por hashtag no post da comunidade.

## Regras (05 a 30/10/2026)
- Check-in: 10 pts no dia (1º post com foto e hashtag do desafio)
- `#rotina #alimentacao #treino #cardio #agua #autocuidado #sono #acerto`: 3 pts cada, 1x por dia, até 2 hashtags por post. Precisa de foto, menos `#acerto` e `#sono`.
- Comentário com 10+ caracteres no post de outra aluna: 1 pt, até 10 por dia
- Máximo de 44 pts por dia. Desempate: mais dias com check-in, depois mais comentários válidos (sem teto). O dia 05/10 (antes do anúncio das hashtags) foi pontuado lendo o texto dos posts (`KEYWORD_DAYS` em `calc.py`).
- Hashtag só vale se estiver no post até 23h59 do dia dele (BRT). Posts de dias encerrados ficam congelados no `state.json`; edição posterior é ignorada.
- Entram só membros do grupo do desafio na Cativa. Moderadoras e a conta da Paloma ficam de fora.

## Como funciona
- `calc.py` lê o feed pela API da Cativa (paginação por `beforeDate`), relê posts e comentários das últimas 48h a cada rodada e congela o que é mais antigo.
- `data/state.json` guarda só ids, dia, hashtags e se tem foto. Fica no cache do GitHub Actions, nunca no repositório.
- Gera `site/ranking.json`, que a página `site/index.html` lê.
- GitHub Actions calcula e publica `site/` no GitHub Pages. Secret necessário: `CATIVA_API_KEY`.
- **Disparo:** o cron do GitHub atrasa horas em repositório gratuito (em 06/10 rodou 1x a cada 5 a 7h). O disparo confiável vem do n8n do LIFE: fluxo `n8n-disparo-ranking.json` (Schedule 30 min → POST `actions/workflows/update.yml/dispatches`), com credencial Header Auth `Authorization: Bearer <token>`. Token: fine-grained PAT só deste repo, permissão Actions: read and write. O cron do workflow fica só de reserva.
- O deploy no Pages tenta 2x (o Pages devolve 502 de vez em quando).

Rodar local: `source ~/.cativa.env && CATIVA_API_KEY=$CATIVA_API_KEY python3 calc.py && cd site && python3 -m http.server`
