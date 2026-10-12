"""Veille automatique : RSS + App Store -> résumés Claude -> Notion -> digest Telegram."""

import datetime as dt
import html
import json
import os
import re
import time

import feedparser
import requests
import yaml
from anthropic import Anthropic

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_DB = os.environ["NOTION_DATABASE_ID"].replace("-", "")
TG_TOKEN = os.environ["TELEGRAM_TOKEN"]
TG_CHAT = os.environ["TELEGRAM_CHAT_ID"]
MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
MAX_AGE_DAYS = int(os.environ.get("MAX_AGE_DAYS", "8"))
DRY_RUN = os.environ.get("DRY_RUN") == "1"  # 1 = pas d'écriture Notion ni d'envoi

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}
UA = {"User-Agent": "Mozilla/5.0 (veille-bot)"}

THEMES = ["Flutter", "Archi", "IA / Agents", "Conférence Apple", "Conférence Google",
          "SDV", "Régulation", "Concurrence"]
CONCURRENTS = [
    "Tesla", "BYD", "BMW", "MINI", "Mercedes", "Volkswagen", "Audi", "Porsche", "Škoda", "Cupra",
    "Stellantis", "Peugeot", "Citroën", "Opel", "Toyota", "Hyundai / Kia", "Hyundai", "Kia",
    "Volvo", "Polestar", "Ford", "Nissan", "XPeng", "Zeekr", "Land Rover", "Rivian",
    "MG", "NIO", "Leapmotor", "Lucid",
]

CUTOFF = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=MAX_AGE_DAYS)
claude = Anthropic()


def clean(text: str, limit: int = 4000) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()[:limit]


# ---------- Collecte ----------

def collect_feeds(cfg: dict) -> list[dict]:
    items = []
    for feed in cfg.get("feeds") or []:
        try:
            resp = requests.get(feed["url"], headers=UA, timeout=20)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
        except Exception as ex:
            print(f"⚠️  Flux ignoré {feed['url']} : {ex}")
            continue
        for e in parsed.entries[: feed.get("max", 10)]:
            t = e.get("published_parsed") or e.get("updated_parsed")
            date = dt.datetime(*t[:6], tzinfo=dt.timezone.utc) if t else dt.datetime.now(dt.timezone.utc)
            if date < CUTOFF or not e.get("link"):
                continue
            body = e.content[0].value if e.get("content") else e.get("summary", "")
            items.append({
                "title": clean(e.get("title", "Sans titre"), 200),
                "link": e.link,
                "date": date,
                "source": feed["source"],
                "veille": feed["veille"],
                "text": clean(body),
                "concurrent": None,
            })
    return items


def collect_apps(cfg: dict) -> list[dict]:
    items = []
    for app in cfg.get("apps") or []:
        try:
            r = requests.get("https://itunes.apple.com/lookup",
                             params={"id": app["app_store_id"], "country": app.get("country", "fr")}, timeout=20)
            results = r.json().get("results") or []
        except Exception as ex:
            print(f"⚠️  App ignorée {app.get('name')} : {ex}")
            continue
        if not results:
            print(f"⚠️  App introuvable : {app.get('name')}")
            continue
        a = results[0]
        released = a.get("currentVersionReleaseDate")
        date = (dt.datetime.fromisoformat(released.replace("Z", "+00:00"))
                if released else dt.datetime.now(dt.timezone.utc))
        if date < CUTOFF:
            continue
        version = a.get("version", "?")
        items.append({
            "title": f"{app['name']} {version} (App Store)",
            "link": f"{a['trackViewUrl']}#v{version}",  # une URL unique par version
            "date": date,
            "source": "App Store / Play Store",
            "veille": "Auto connectée",
            "text": clean(f"Notes de version de l'app {app['name']} {version} : {a.get('releaseNotes', '')}"),
            "concurrent": app.get("concurrent"),
        })
    return items


# ---------- Notion ----------

def already_in_notion(link: str) -> bool:
    r = requests.post(f"https://api.notion.com/v1/databases/{NOTION_DB}/query",
                      headers=NOTION_HEADERS, timeout=20,
                      json={"filter": {"property": "Lien", "url": {"equals": link}}, "page_size": 1})
    r.raise_for_status()
    return bool(r.json()["results"])


def create_notion_page(item: dict) -> None:
    props = {
        "Titre": {"title": [{"text": {"content": item["title"][:200]}}]},
        "Résumé": {"rich_text": [{"text": {"content": item["resume"][:1900]}}]},
        "Lien": {"url": item["link"]},
        "Veille": {"select": {"name": item["veille"]}},
        "Thème": {"multi_select": [{"name": t} for t in item["themes"]]},
        "Source": {"select": {"name": item["source"]}},
        "Radar": {"select": {"name": "Surveiller"}},
        "Impact AppVengers": {"checkbox": item["impact"]},
        "Date": {"date": {"start": item["date"].date().isoformat()}},
    }
    if item["concurrent"]:
        props["Concurrent"] = {"select": {"name": item["concurrent"]}}
    r = requests.post("https://api.notion.com/v1/pages", headers=NOTION_HEADERS, timeout=20,
                      json={"parent": {"database_id": NOTION_DB}, "properties": props})
    r.raise_for_status()


# ---------- Résumé Claude ----------

PROMPT = """Tu fais la veille d'un architecte mobile Flutter senior qui travaille sur l'application \
compagnon d'un constructeur automobile.

Résume l'article ci-dessous en français, en 2 ou 3 phrases factuelles, sans formule d'introduction.
Réponds UNIQUEMENT avec un objet JSON, sans texte autour ni balises Markdown :
{"resume": "...", "themes": ["..."], "concurrent": null, "impact": false}

- themes : 1 à 3 valeurs parmi __THEMES__
- concurrent : une valeur parmi __CONCURRENTS__ si l'article porte sur ce constructeur, sinon null
- impact : true seulement si cela peut concrètement influencer l'architecture, les standards \
ou le produit d'une app mobile Flutter automobile

Titre : __TITLE__
Source : __SOURCE__
Contenu :
__TEXT__"""


def ask_claude_json(prompt: str) -> dict | None:
    """Interroge Claude et parse sa réponse JSON. Renvoie None si l'appel échoue."""
    try:
        msg = claude.messages.create(model=MODEL, max_tokens=500,
                                     messages=[{"role": "user", "content": prompt}])
        raw = "".join(b.text for b in msg.content if b.type == "text")
        return json.loads(re.sub(r"```(json)?", "", raw).strip())
    except Exception as ex:
        print(f"⚠️  Appel Claude impossible : {ex}")
        return None


def summarize(item: dict) -> dict:
    prompt = (PROMPT.replace("__THEMES__", json.dumps(THEMES, ensure_ascii=False))
              .replace("__CONCURRENTS__", json.dumps(CONCURRENTS, ensure_ascii=False))
              .replace("__TITLE__", item["title"])
              .replace("__SOURCE__", item["source"])
              .replace("__TEXT__", item["text"] or "(pas de contenu, résume à partir du titre)"))
    data = ask_claude_json(prompt)
    if data is None:
        print(f"⚠️  Résumé impossible pour « {item['title']} »")
        data = {"resume": item["text"][:300], "themes": [], "concurrent": None, "impact": False}

    item["resume"] = str(data.get("resume") or item["title"])
    item["themes"] = [t for t in data.get("themes") or [] if t in THEMES]
    if not item["concurrent"] and data.get("concurrent") in CONCURRENTS:
        item["concurrent"] = data["concurrent"]
    if item["concurrent"] and "Concurrence" not in item["themes"]:
        item["themes"].append("Concurrence")
    item["impact"] = bool(data.get("impact"))
    return item


# ---------- Offres d'emploi ----------

JOB_PROMPT = """Tu aides un développeur à faire sa veille d'offres d'emploi. Voici son profil :
__PROFILE__

Évalue l'offre ci-dessous par rapport à ce profil. Réponds UNIQUEMENT avec un objet JSON, \
sans texte autour ni balises Markdown :
{"fit": true, "resume": "...", "themes": ["Flutter"]}

- fit : true seulement si le poste correspond vraiment aux points forts du profil \
(séniorité, techno, langue parlée). false sinon.
- resume : 2 phrases en français — l'intitulé puis pourquoi ça colle (ou non) au profil, \
en précisant lieu, type de contrat et techno si l'offre les mentionne.
- themes : toujours ["Flutter"].

Titre : __TITLE__
Source : __SOURCE__
Contenu :
__TEXT__"""


def apply_job_result(item: dict, data: dict | None) -> bool:
    """Renseigne resume/themes/impact de l'offre et renvoie True s'il faut la garder.

    Si l'évaluation a échoué (data None), on garde l'offre en la signalant plutôt que de
    la perdre silencieusement."""
    item["impact"] = False
    item["themes"] = ["Flutter"]
    if data is None:
        print(f"⚠️  Évaluation du fit impossible pour « {item['title']} »")
        item["resume"] = f"⚠️ Évaluation du fit impossible, à vérifier manuellement : {item['title']}"
        return True
    item["resume"] = str(data.get("resume") or item["title"])
    item["themes"] = [t for t in data.get("themes") or [] if t in THEMES] or ["Flutter"]
    return bool(data.get("fit"))


def score_job(item: dict, profile: str) -> bool:
    prompt = (JOB_PROMPT.replace("__PROFILE__", profile)
              .replace("__TITLE__", item["title"])
              .replace("__SOURCE__", item["source"])
              .replace("__TEXT__", item["text"] or "(pas de contenu)"))
    return apply_job_result(item, ask_claude_json(prompt))


# ---------- Telegram ----------

def item_block(i: dict) -> str:
    star = " ⭐" if i.get("impact") else ""
    return (f'• <b><a href="{html.escape(i["link"], quote=True)}">{html.escape(i["title"])}</a></b>'
            f"{star}\n{html.escape(i['resume'])}")


def build_digest(items: list[dict]) -> list[str]:
    notion_url = f"https://www.notion.so/{NOTION_DB}"
    blocks = [f"📡 <b>Veille de la semaine</b> — {len(items)} nouveautés (⭐ = impact AppVengers)"
              if items else "📡 <b>Veille</b> : rien de nouveau cette semaine."]
    for veille, emoji in (("Tech / Archi / IA", "🧠"), ("Auto connectée", "🚗")):
        section = [i for i in items if i["veille"] == veille]
        if not section:
            continue
        blocks.append(f"\n{emoji} <b>{html.escape(veille)}</b>")
        blocks.extend(item_block(i) for i in section)

    # Section Jobs toujours affichée : « aucune offre » doit se distinguer d'un flux vide/cassé.
    jobs = [i for i in items if i["veille"] == "Jobs"]
    blocks.append("\n💼 <b>Jobs</b>")
    if jobs:
        blocks.extend(item_block(i) for i in jobs)
    else:
        blocks.append("Aucune offre correspondant à ton profil cette semaine.")

    blocks.append(f'\n🗂 <a href="{notion_url}">Ouvrir la base Notion</a>')
    return blocks


def send_telegram(items: list[dict]) -> None:
    blocks = build_digest(items)

    # Telegram limite un message à 4096 caractères : on découpe si besoin
    chunks, current = [], ""
    for block in blocks:
        if len(current) + len(block) + 2 > 3800:
            chunks.append(current)
            current = ""
        current += block + "\n\n"
    chunks.append(current)

    for chunk in chunks:
        r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", timeout=20,
                          json={"chat_id": TG_CHAT, "text": chunk, "parse_mode": "HTML",
                                "disable_web_page_preview": True})
        r.raise_for_status()


# ---------- Main ----------

def main() -> None:
    with open("config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    with open("profile.md", encoding="utf-8") as f:
        profile = f.read()

    candidates = sorted(collect_feeds(cfg) + collect_apps(cfg), key=lambda i: i["date"], reverse=True)
    print(f"{len(candidates)} éléments récents trouvés")

    seen, new_items = set(), []
    for item in candidates:
        if item["link"] in seen:
            continue
        seen.add(item["link"])
        try:
            if already_in_notion(item["link"]):
                continue
            if item["veille"] == "Jobs":
                if not score_job(item, profile):
                    print(f"⏭  Offre écartée : {item['title']}")
                    continue
            else:
                summarize(item)
            if not DRY_RUN:
                create_notion_page(item)
            new_items.append(item)
            print(f"✅ {item['title']}")
            time.sleep(0.4)  # rester sous la limite de l'API Notion (3 req/s)
        except Exception as ex:
            print(f"⚠️  Erreur sur « {item['title']} » : {ex}")

    if DRY_RUN:
        for i in new_items:
            print(f"\n[{i['veille']}] {i['title']}\n{i['resume']}\n{i['link']}")
    else:
        send_telegram(new_items)
    print(f"Terminé : {len(new_items)} nouveautés")


if __name__ == "__main__":
    main()