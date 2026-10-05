# Ranking do Desafio Outubro das Gostosas (LIFE)

Ranking paralelo ao da Cativa, que pontua qualquer interação e permite farmar pontos com spam.
Aqui o ponto vem das metas do desafio, comprovadas por hashtag no post da comunidade.

## Regras (05 a 30/10/2026)
- Check-in: 10 pts no dia (1º post com foto e hashtag do desafio)
- `#rotina #alimentacao #treino #cardio #agua #autocuidado #sono #acerto`: 3 pts cada, 1x por dia, até 2 hashtags por post. Precisa de foto, menos `#acerto` e `#sono`.
- Comentário com 10+ caracteres no post de outra aluna: 1 pt, até 10 por dia
- Máximo de 44 pts por dia. Desempate: mais dias com check-in, depois mais comentários válidos (sem teto). O dia 05/10 (antes do anúncio das hashtags) foi pontuado lendo o texto dos posts (`KEYWORD_DAYS` em `calc.py`).
- Entram só membros do grupo do desafio na Cativa. Moderadoras e a conta da Paloma ficam de fora.

## Como funciona
- `calc.py` lê o feed pela API da Cativa (paginação por `beforeDate`), relê posts e comentários das últimas 48h a cada rodada e congela o que é mais antigo.
- `data/state.json` guarda só ids, dia, hashtags e se tem foto. Fica no cache do GitHub Actions, nunca no repositório.
- Gera `site/ranking.json`, que a página `site/index.html` lê.
- GitHub Actions roda a cada 30 min e publica `site/` no GitHub Pages. Secret necessário: `CATIVA_API_KEY`.

Rodar local: `source ~/.cativa.env && CATIVA_API_KEY=$CATIVA_API_KEY python3 calc.py && cd site && python3 -m http.server`
