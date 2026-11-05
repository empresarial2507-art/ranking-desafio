# Ranking do Desafio (LIFE)

Ranking paralelo ao da Cativa, que pontua qualquer interação e permite farmar pontos com spam.
Aqui o ponto vem das metas do desafio, comprovadas por hashtag no post da comunidade.

**Desafio atual: Fim de Ano das Gostosas, 16/11 a 18/12/2026** (docs em `~/Desktop/CLAUDE COWORKING/pontuação LIFE/`). Outubro (05 a 30/10) foi o primeiro; trocar de desafio = mudar `START_DAY`, `END_DAY`, `START_UTC` e `CHALLENGE` em `calc.py` (o state antigo é descartado sozinho) e a janela de datas em `mac/disparar.sh`.

## Regras (documento "Ranking do Desafio · Novembro")
- 1º post do dia com foto e hashtag: 10 pts
- `#rotina #alimentacao #treino #cardio #agua #autocuidado #sono #acerto`: 3 pts cada, 1x por dia, até 2 hashtags por post. **Toda hashtag precisa de foto, inclusive `#acerto` e `#sono`** (em outubro essas duas valiam sem foto).
- Comentário com 10+ caracteres no post de outra aluna: 1 pt, até 10 por dia. Comentário no próprio post não conta.
- Limite de 20 posts por dia (`MAX_POSTS_PER_DAY`): do 21º em diante não pontua.
- Só contam posts e comentários de 16/11 a 18/12.
- Máximo de 44 pts por dia. Empate: mesma posição no painel; quem decide é a equipe ("maior quantidade e qualidade nos posts, relatos e comentários"). Dias com check-in só ordenam a lista.
- Fora do painel (conferência manual da equipe): hashtag sem cumprir a meta, foto repetida ou antiga, comentário apagado para comentar em mais posts, e a pontuação extra de antes/depois e relatos.
- Hashtag só vale se estiver no post até 23h59 do dia dele (BRT). O dia congela 3h depois da meia-noite (`GRACE_HOURS`, folga para rodadas atrasadas); depois disso o post fica congelado no `state.json` e edição posterior é ignorada.
- Hashtag negada no próprio post não conta (`negated_tags`, desde 21/10, retroativo): "não teve #treino", "sem #cardio", "#treino não rolou", e listas ("sem #treino e #cardio"). Negação só colada na hashtag; "#acerto sem açúcar" vale. Resultado: 26 posts de 11 alunas. Em 22/10: "#cardio hoje não teve #treino" negava os dois; o "não teve" seguido de hashtag agora só vale para a hashtag de depois (1 post, Júlia Queiroz, +3 no cardio de 11/10).
- Erro de digitação óbvio é aceito (`canon_tag`): até 2 letras em #alimentacao/#autocuidado e 1 nas de 6 letras; sinônimos (#almoco, #cafe) e hashtags curtas (#agua, #sono) só exatas. Mudou a leitura? Subir `PARSE_VERSION`.
- Entra quem fez pelo menos 1 check-in (post com foto e hashtag do desafio), esteja ou não no grupo do desafio na Cativa. Contas admin (Paloma, Time Life Oficial) ficam de fora.

## Como funciona
- `calc.py` lê o feed pela API da Cativa (paginação por `beforeDate`), relê posts e comentários das últimas 48h a cada rodada e congela o que é mais antigo.
- `data/state.json` guarda só ids, dia, hashtags e se tem foto. Fica no cache do GitHub Actions, nunca no repositório.
- Gera `site/ranking.json`, que a página `site/index.html` lê.
- GitHub Actions calcula e publica `site/` no GitHub Pages. Secret necessário: `CATIVA_API_KEY`.
- **Disparo:** o cron do GitHub atrasa horas em repositório gratuito (em 06/10 rodou 1x a cada 5 a 7h). O disparo vem do Mac do Natan: launchd `com.life.ranking-desafio` roda `mac/disparar.sh` (`gh workflow run`) a cada 30 min enquanto o Mac está acordado; instalar com `mac/instalar.sh`, log em `~/.life-growth-os/ranking/disparos.log`. Só dispara de 16/11 a 19/12 (o dia 18 congela 3h depois da meia-noite). Alternativa que roda 24h: fluxo n8n `n8n-disparo-ranking.json` (PAT fine-grained só deste repo, Actions read/write). O cron do workflow fica de reserva.
- O deploy no Pages tenta 2x (o Pages devolve 502 de vez em quando).

Rodar local: `source ~/.cativa.env && CATIVA_API_KEY=$CATIVA_API_KEY python3 calc.py && cd site && python3 -m http.server`
