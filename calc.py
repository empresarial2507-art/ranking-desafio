"""Ranking do Desafio Outubro das Gostosas (LIFE).

Lê o feed da comunidade na Cativa, pontua pelas regras do desafio e gera
site/ranking.json. Guarda em data/state.json só o que precisa para pontuar
(ids, dia, hashtags válidas, se tem foto), nunca o texto dos posts.

Uso: CATIVA_API_KEY=... python3 calc.py
"""
import json, os, re, sys, time, unicodedata, urllib.request, urllib.parse, urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

BASE = "https://apis.cativalab.digital/tenant/api/v2"
GROUP_ID = "cc16e22a-ce22-48f7-7e30-08defc87194e"  # Desafio Outubro das Gostosas
START_DAY, END_DAY = "2026-10-05", "2026-10-30"
BRT = timezone(timedelta(hours=-3))
START_UTC = datetime(2026, 10, 5, tzinfo=BRT).astimezone(timezone.utc)
REFRESH_HOURS = 48  # posts e comentários mais novos que isso são relidos a cada rodada

# Regras
CHECKIN_PTS = 10
TAG_PTS = 3
MAX_TAGS_PER_POST = 2
COMMENT_PTS, COMMENT_MIN_CHARS, COMMENT_MAX_PER_DAY = 1, 10, 4
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


def tags_of(p, day):
    """Hashtags válidas do post, na ordem em que aparecem, no máximo 2."""
    text = p.get("rawContent") or p.get("content") or ""
    found = []
    for raw in re.findall(r"#([^\s#.,!?;:()]+)", text):
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


def fetch_members():
    members, page = {}, 1
    while True:
        r = get(f"/community/groups/{GROUP_ID}/members?page={page}&pageSize=50")
        for m in r.get("items") or []:
            members[m["id"]] = m
        if not r.get("hasNextPage"):
            return members
        page += 1


def main():
    if not KEY:
        sys.exit("CATIVA_API_KEY não definida")
    now = datetime.now(timezone.utc)
    state = {"posts": {}, "comments": {}, "pics": {}}
    if os.path.exists(STATE):
        state = json.load(open(STATE))

    refresh_from = max(START_UTC, now - timedelta(hours=REFRESH_HOURS))
    if not state["posts"]:
        refresh_from = START_UTC
    refresh_iso = refresh_from.isoformat().replace("+00:00", "Z")

    fresh = fetch_posts_since(refresh_from)
    # Posts da janela são recalculados do zero (pega edição e post apagado).
    state["posts"] = {k: v for k, v in state["posts"].items() if v["at"] < refresh_iso}
    for p in fresh:
        d = day_of(p["createdAt"])
        if START_DAY <= d <= END_DAY:
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
            pic = (c.get("author") or {}).get("pictureUrl")
            if uid and pic:
                state["pics"][uid] = pic
            state["comments"][c["id"]] = {"u": uid, "post": pid, "pu": author, "d": day_of(c["createdAt"]),
                                          "ok": len((c.get("content") or "").strip()) >= COMMENT_MIN_CHARS}

    members = fetch_members()
    me = get("/auth/me")
    excluded = {me.get("id")} | {uid for uid, m in members.items() if m.get("isModerator") or m.get("role") not in (0, "user")}

    # Pontuação
    per = defaultdict(lambda: {"days": set(), "tags": defaultdict(int), "comments": 0})
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

    # Foto: quem ainda não tem, pega do detalhe de um post dela (uma vez só).
    need = [uid for uid in per if uid in members and uid not in excluded and uid not in state["pics"]]
    some_post = {}
    for pid, p in state["posts"].items():
        some_post.setdefault(p["u"], pid)

    def pic_for(uid):
        try:
            return uid, (get(f"/community/posts/{some_post[uid]}")["post"].get("author") or {}).get("pictureUrl")
        except Exception:
            return uid, None
    with ThreadPoolExecutor(8) as ex:
        for uid, pic in ex.map(pic_for, [u for u in need if u in some_post]):
            state["pics"][uid] = pic or ""

    rows = []
    for uid, s in per.items():
        if uid not in members or uid in excluded:
            continue
        pts = len(s["days"]) * CHECKIN_PTS + sum(s["tags"].values()) * TAG_PTS + s["comments"]
        if pts <= 0:
            continue
        rows.append({"name": members[uid]["displayName"].strip(), "pic": state["pics"].get(uid) or "",
                     "pts": pts, "checkins": len(s["days"]), "tags": {t: s["tags"].get(t, 0) for t in TAGS},
                     "comments": s["comments"]})
    rows.sort(key=lambda r: (-r["pts"], norm(r["name"])))
    pos = 0
    for i, r in enumerate(rows):
        if i == 0 or r["pts"] != rows[i - 1]["pts"]:
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
          f"janela={len(fresh)} membros={len(members)}")


if __name__ == "__main__":
    main()
