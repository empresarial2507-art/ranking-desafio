"""Ranking do Desafio Outubro das Gostosas (LIFE).

Lê o feed da comunidade na Cativa, pontua pelas regras do desafio e gera
site/ranking.json. Guarda em data/state.json só o que precisa para pontuar
(ids, dia, hashtags válidas, se tem foto), nunca o texto dos posts.

Uso: CATIVA_API_KEY=... python3 calc.py
"""
import html, json, os, re, sys, time, unicodedata, urllib.request, urllib.parse, urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

BASE = "https://apis.cativalab.digital/tenant/api/v2"
START_DAY, END_DAY = "2026-10-05", "2026-10-30"
BRT = timezone(timedelta(hours=-3))
START_UTC = datetime(2026, 10, 5, tzinfo=BRT).astimezone(timezone.utc)
REFRESH_HOURS = 48  # posts e comentários mais novos que isso são relidos a cada rodada

# Regras
CHECKIN_PTS = 10
TAG_PTS = 3
MAX_TAGS_PER_POST = 2
COMMENT_PTS, COMMENT_MIN_CHARS, COMMENT_MAX_PER_DAY = 1, 10, 10
TAGS = ["rotina", "alimentacao", "treino", "cardio", "agua", "autocuidado", "sono", "acerto"]
NO_PHOTO_OK = {"acerto", "sono"}  # relato sem foto vale
ALIASES = {"rotinamatinal": "rotina", "alimentacoes": "alimentacao", "treinos": "treino",
           "acertos": "acerto", "aguas": "agua"}

# Dias antes do anúncio das hashtags: pontua lendo o texto, uma vez só.
KEYWORD_DAYS = {"2026-10-05"}
KEYWORDS = {
    "rotina": r"lingua|vac+u+m|jejum|shot|sol\b|rotina matinal|morning",
    "alimentacao": r"marmita|almoc|jantar|janta\b|cafe da manha|colacao|lanche|refeic|salada|ceia|prato|balanca|pesei|suco verde|plano alimentar",
    "treino": r"treino|treinei|treinar|musculac|academia|gluteo|perna|superior|inferior|malh",
    "cardio": r"cardio|esteira|escada|bike|corrida|correr|corri\b|eliptico|hiit|corda|caminhada|spinning",
    "agua": r"\bagua|\bcha\b|\bchas\b|hidrat|litro|garrafa",
    "autocuidado": r"skin|cabelo|hair|leitura|livro|lendo|li\b|medita|yoga|orac|autocuidado|unha|mascara|banho",
    "sono": r"dormir|dormi\b|sono|cama\b|deitar",
    "acerto": r"acucar|acerto|acertei|belisc|alcool|sem doce|zero doce|furo",
}
KEYWORD_RE = {t: re.compile(p) for t, p in KEYWORDS.items()}

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "data", "state.json")
OUT = os.path.join(HERE, "site", "ranking.json")
KEY = os.environ.get("CATIVA_API_KEY")
HEADERS = {"Authorization": f"Bearer {KEY}", "User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def get(path, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(BASE + path, headers=HEADERS)
            return json.load(urllib.request.urlopen(req, timeout=30))
        except urllib.error.HTTPError as e:
            if e.code in (400, 404) or i == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if i == tries - 1:
                raise
        time.sleep(2 * (i + 1))


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def day_of(iso):
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.astimezone(BRT).date().isoformat()


def has_media(p):
    h = p.get("htmlContent") or ""
    return "<img" in h or "<video" in h or bool(p.get("images")) or bool(p.get("videos"))


def text_of(p):
    """Texto do post com as quebras de linha preservadas. O rawContent da Cativa cola
    "#sono" + <div>Deixando</div> em "#sonoDeixando", e a hashtag se perde."""
    h = p.get("htmlContent")
    if h:
        t = re.sub(r"<\s*/?\s*(br|div|p|li)\b[^>]*>", " ", h, flags=re.I)
        return html.unescape(re.sub(r"<[^>]+>", "", t))
    return p.get("rawContent") or p.get("content") or ""


# Leitura antiga: texto bruto da Cativa e hashtag até o próximo espaço/pontuação ASCII.
# Perdia "#sono…", "#sono❤️" (símbolo colado) e "#sono" + Enter + texto (linha colada).
LEGACY_TAG_RE = re.compile(r"#([^\s#.,!?;:()]+)")
TAG_RE = re.compile(r"#([A-Za-zÀ-ÖØ-öø-ÿ0-9_]+)")  # só letras/números: para antes de …, emoji etc.


def misread(p):
    """True se a leitura antiga errava neste post. Só esses posts de dias já encerrados
    são relidos; edição de hashtag (que as duas leituras enxergam igual) continua ignorada."""
    return tags_of(p, "x") != tags_of(p, "x", legacy=True)


def tags_of(p, day, legacy=False):
    """Hashtags válidas do post, na ordem em que aparecem, no máximo 2."""
    text = (p.get("rawContent") or p.get("content") or "") if legacy else text_of(p)
    found = []
    for raw in (LEGACY_TAG_RE if legacy else TAG_RE).findall(text):
        t = ALIASES.get(norm(raw), norm(raw))
        if t in TAGS and t not in found:
            found.append(t)
    if not found and day in KEYWORD_DAYS:
        t = norm(text)
        hits = sorted((m.start(), tag) for tag, rx in KEYWORD_RE.items() if (m := rx.search(t)))
        found = [tag for _, tag in hits]
    return found[:MAX_TAGS_PER_POST]


def fetch_posts_since(since_utc):
    """Feed do mais novo para o mais antigo, paginando por beforeDate."""
    posts, before = {}, None
    while True:
        q = "/community/posts?pageSize=50" + (f"&beforeDate={urllib.parse.quote(before)}" if before else "")
        page = get(q)["posts"]
        if not page:
            break
        for p in page:
            posts[p["id"]] = p
        oldest = min(p["createdAt"] for p in page)
        if oldest == before or oldest < since_utc.isoformat().replace("+00:00", "Z"):
            break
        before = oldest
    return [p for p in posts.values() if p["createdAt"] >= since_utc.isoformat().replace("+00:00", "Z")]


def fetch_comments(post_id):
    for size in (100, 50, 20):
        try:
            return get(f"/community/posts/{post_id}/comments?pageSize={size}")["comments"]
        except urllib.error.HTTPError as e:
            if e.code != 400:
                raise
    return []


def fetch_admins():
    """Contas da equipe (Paloma, Time Life Oficial): ficam fora do ranking."""
    return {u["id"] for u in get("/admin/users?page=1&pageSize=50&role=admin").get("items") or []}


def main():
    if not KEY:
        sys.exit("CATIVA_API_KEY não definida")
    now = datetime.now(timezone.utc)
    state = {"posts": {}, "comments": {}, "pics": {}}
    if os.path.exists(STATE):
        state = json.load(open(STATE))
    state.setdefault("names", {})

    refresh_from = max(START_UTC, now - timedelta(hours=REFRESH_HOURS))
    if not state["posts"]:
        refresh_from = START_UTC
    refresh_iso = refresh_from.isoformat().replace("+00:00", "Z")

    fresh = fetch_posts_since(refresh_from)
    # Posts da janela são relidos (pega post apagado). Hashtag só vale se estiver
    # no post até 23h59 do dia dele: de dias já encerrados, mantém o que foi guardado
    # e ignora edição posterior.
    today = now.astimezone(BRT).date().isoformat()
    old = state["posts"]
    state["posts"] = {k: v for k, v in old.items() if v["at"] < refresh_iso}
    for p in fresh:
        d = day_of(p["createdAt"])
        if not START_DAY <= d <= END_DAY:
            continue
        if d < today and p["id"] in old and not misread(p):
            state["posts"][p["id"]] = old[p["id"]]
        else:
            state["posts"][p["id"]] = {"u": p["userId"], "at": p["createdAt"], "d": d,
                                       "tags": tags_of(p, d), "media": has_media(p)}

    window_ids = [p["id"] for p in fresh if p["id"] in state["posts"]]
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(fetch_comments, window_ids))
    wset = set(window_ids)
    state["comments"] = {k: v for k, v in state["comments"].items() if v["post"] not in wset}
    for pid, comments in zip(window_ids, results):
        author = state["posts"][pid]["u"]
        for c in comments:
            uid = c.get("userId") or (c.get("author") or {}).get("id")
            author_info = c.get("author") or {}
            if uid and author_info.get("pictureUrl"):
                state["pics"][uid] = author_info["pictureUrl"]
            if uid and author_info.get("displayName"):
                state["names"][uid] = author_info["displayName"].strip()
            state["comments"][c["id"]] = {"u": uid, "post": pid, "pu": author, "d": day_of(c["createdAt"]),
                                          "ok": len((c.get("content") or "").strip()) >= COMMENT_MIN_CHARS}

    # Entra quem postou com hashtag do desafio (não precisa estar no grupo da Cativa).
    excluded = fetch_admins() | {get("/auth/me").get("id")}

    # Pontuação
    per = defaultdict(lambda: {"days": set(), "tags": defaultdict(int), "comments": 0, "ncom": 0})
    by_day = defaultdict(list)
    for pid, p in state["posts"].items():
        by_day[(p["u"], p["d"])].append(p)
    for (uid, d), posts in by_day.items():
        posts.sort(key=lambda p: p["at"])
        done = set()
        checkin = False
        for p in posts:
            valid = [t for t in p["tags"] if p["media"] or t in NO_PHOTO_OK]
            if p["media"] and (valid or d in KEYWORD_DAYS):
                checkin = True
            done.update(valid)
        if checkin:
            per[uid]["days"].add(d)
        for t in done:
            per[uid]["tags"][t] += 1
    com_day = defaultdict(int)
    for c in state["comments"].values():
        if c["ok"] and c["u"] and c["u"] != c["pu"] and START_DAY <= c["d"] <= END_DAY:
            com_day[(c["u"], c["d"])] += 1
    for (uid, d), n in com_day.items():
        per[uid]["comments"] += min(n, COMMENT_MAX_PER_DAY) * COMMENT_PTS
        per[uid]["ncom"] += n  # só para desempate

    participants = [uid for uid, s in per.items() if s["days"] and uid not in excluded]

    # Nome e foto: quem ainda não tem, pega do detalhe de um post dela (uma vez só).
    some_post = {}
    for pid, p in state["posts"].items():
        some_post.setdefault(p["u"], pid)
    need = [u for u in participants if (u not in state["names"] or u not in state["pics"]) and u in some_post]

    def author_of(uid):
        try:
            return uid, get(f"/community/posts/{some_post[uid]}")["post"].get("author") or {}
        except Exception:
            return uid, {}
    with ThreadPoolExecutor(8) as ex:
        for uid, a in ex.map(author_of, need):
            state["pics"][uid] = a.get("pictureUrl") or ""
            if a.get("displayName"):
                state["names"][uid] = a["displayName"].strip()

    rows = []
    for uid in participants:
        s = per[uid]
        if uid not in state["names"]:
            continue
        pts = len(s["days"]) * CHECKIN_PTS + sum(s["tags"].values()) * TAG_PTS + s["comments"]
        rows.append({"name": state["names"][uid], "pic": state["pics"].get(uid) or "",
                     "pts": pts, "checkins": len(s["days"]), "tags": {t: s["tags"].get(t, 0) for t in TAGS},
                     "comments": s["comments"], "ncom": s["ncom"]})
    # Desempate: mais dias com check-in, depois mais comentários válidos (sem teto).
    tie = lambda r: (r["pts"], r["checkins"], r["ncom"])
    rows.sort(key=lambda r: (-r["pts"], -r["checkins"], -r["ncom"], norm(r["name"])))
    pos = 0
    for i, r in enumerate(rows):
        if i == 0 or tie(r) != tie(rows[i - 1]):
            pos = i + 1
        r["pos"] = pos

    today = min(now.astimezone(BRT).date().isoformat(), END_DAY)
    total_days = (datetime.fromisoformat(today) - datetime.fromisoformat(START_DAY)).days + 1
    out = {"updatedAt": now.isoformat().replace("+00:00", "Z"), "day": max(total_days, 1),
           "totalDays": 26, "ranking": rows}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(state, open(STATE, "w"), separators=(",", ":"))
    print(f"posts={len(state['posts'])} comentários={len(state['comments'])} ranqueadas={len(rows)} "
          f"janela={len(fresh)}")


if __name__ == "__main__":
    main()
