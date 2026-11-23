# Refonte des sujets de la veille — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Réduire Apple/Android Developers et ajouter deux veilles filtrées par Claude, *Architecture* et *IA locale*.

**Architecture:** Les descriptions de sujet vivent dans `config.yaml` (`topics:`). Un item dont la veille a une description est résumé avec cette description et un champ `pertinent` demandé dans le même appel Claude ; s'il n'est pas pertinent, il est écarté comme une offre d'emploi rejetée. `summarize` est découpé en fonctions pures testables (prompt, application du verdict).

**Tech Stack:** Python 3.12, feedparser, anthropic, pytest.

**Spec:** `docs/superpowers/specs/2026-11-23-refresh-radar-topics-design.md`

## Global Constraints

- Ne pas toucher à la liste `apps:` ni à la section 🚗 Auto connectée.
- Code, logs, prompts et commentaires en français, comme le reste de `veille.py`.
- Chaque fichier de test commence par deux lignes `# ABOUTME: `.
- Lancer les tests avec `python -m pytest -q` depuis la racine (`tests/conftest.py` fournit des variables d'env factices).

## Review Focus

- Échec de l'appel Claude sur un item filtré : l'item est écarté et loggé, jamais publié avec un résumé brut (test dans la tâche 1).
- Échec de l'appel Claude sur un item non filtré : comportement actuel inchangé (résumé de repli, item gardé) (test dans la tâche 1).
- Claude omet `pertinent` dans sa réponse pour un item filtré : traité comme non pertinent (test dans la tâche 1).
- `config.yaml` sans clé `topics` : aucune veille filtrée, pas de crash (test dans la tâche 1, via `topic_for`).
- Une veille filtrée sans aucun item retenu : sa section n'apparaît pas dans le digest (test dans la tâche 2).

---

### Task 1: Filtre de pertinence par sujet

**Files:**
- Modify: `veille.py` (bloc « Résumé Claude », `THEMES`, `main`)
- Test: `tests/test_topics.py` (créer)

**Interfaces:**
- Produces:
  - `topic_for(cfg: dict, veille: str) -> str | None` : description du sujet ou `None`.
  - `build_summary_prompt(item: dict, topic: str | None) -> str`
  - `apply_summary(item: dict, data: dict | None, topic: str | None) -> bool` : remplit `resume`, `themes`, `concurrent`, `impact` ; renvoie `True` s'il faut garder l'item.
  - `summarize(item: dict, topic: str | None = None) -> bool` : compose les trois ci-dessus avec `ask_claude_json`.
  - `THEMES` contient en plus `"Clean Archi"`, `"DDD"`, `"IA locale"`.

- [ ] **Step 1: Écrire les tests qui échouent** dans `tests/test_topics.py`

```python
TOPIC = "Clean Architecture et DDD"

def test_relevant_item_is_kept():
    item = _item()
    keep = veille.apply_summary(item, {"pertinent": True, "resume": "r", "themes": ["DDD"],
                                       "concurrent": None, "impact": False}, TOPIC)
    assert keep is True and item["themes"] == ["DDD"]

def test_off_topic_item_is_dropped():
    assert veille.apply_summary(_item(), {"pertinent": False, "resume": "r", "themes": []}, TOPIC) is False

def test_missing_pertinent_field_drops_filtered_item():
    assert veille.apply_summary(_item(), {"resume": "r", "themes": []}, TOPIC) is False

def test_claude_failure_drops_filtered_item():
    assert veille.apply_summary(_item(), None, TOPIC) is False

def test_unfiltered_item_kept_without_pertinent_field():
    assert veille.apply_summary(_item(), {"resume": "r", "themes": []}, None) is True

def test_claude_failure_keeps_unfiltered_item_with_fallback_summary():
    item = _item(text="texte brut")
    assert veille.apply_summary(item, None, None) is True
    assert item["resume"] == "texte brut"

def test_prompt_includes_topic_and_pertinent_field_when_filtered():
    p = veille.build_summary_prompt(_item(), TOPIC)
    assert TOPIC in p and '"pertinent"' in p

def test_prompt_has_no_pertinent_field_when_unfiltered():
    assert '"pertinent"' not in veille.build_summary_prompt(_item(), None)

def test_topic_for_reads_config_and_tolerates_missing_key():
    assert veille.topic_for({"topics": {"Architecture": TOPIC}}, "Architecture") == TOPIC
    assert veille.topic_for({"topics": {"Architecture": TOPIC}}, "Jobs") is None
    assert veille.topic_for({}, "Architecture") is None

def test_new_themes_are_accepted():
    item = _item()
    veille.apply_summary(item, {"pertinent": True, "resume": "r",
                                "themes": ["Clean Archi", "IA locale"]}, TOPIC)
    assert item["themes"] == ["Clean Archi", "IA locale"]
```

`_item(text="")` renvoie `{"veille": "Architecture", "title": "Un article", "source": "S", "text": text, "resume": "", "themes": [], "concurrent": None}`.

- [ ] **Step 2: Vérifier l'échec** — `python -m pytest tests/test_topics.py -q` → échecs `AttributeError: module 'veille' has no attribute 'apply_summary'`.

- [ ] **Step 3: Implémenter**
  - Ajouter les trois thèmes à `THEMES`.
  - Ajouter au `PROMPT` un marqueur `__TOPIC__` placé avant le titre. `build_summary_prompt` le remplace par un paragraphe qui donne le sujet et demande `"pertinent": true|false` (true seulement si l'article traite vraiment du sujet) quand `topic` existe, et par une chaîne vide sinon. Le JSON d'exemple existant ne contient pas `pertinent`.
  - `apply_summary` reprend la logique actuelle de `summarize`. Item filtré : renvoie `False` si `data is None` (log « ⚠️ Résumé impossible ») ou si `data.get("pertinent")` est falsy. Item non filtré : renvoie toujours `True`, avec le repli actuel.
  - `main` : pour les veilles autres que Jobs, remplacer `summarize(item)` par `if not summarize(item, topic_for(cfg, item["veille"])): print(f"⏭  Hors sujet : {item['title']}"); continue`.

- [ ] **Step 4: Vérifier** — `python -m pytest -q` → tout passe, y compris `test_jobs.py` et `test_digest.py`.

- [ ] **Step 5: Commit** — `git add veille.py tests/test_topics.py && git commit -m "Filtre les articles hors sujet pour les veilles décrites dans topics"`

### Task 2: Sections Architecture et IA locale dans le digest

**Files:**
- Modify: `veille.py` (`build_digest`)
- Test: `tests/test_digest.py`

**Interfaces:**
- Consumes: rien de la tâche 1.
- Produces: `build_digest` rend les sections dans cet ordre : 🧠 Tech / Archi / IA, 🏛 Architecture, 🖥 IA locale, 🚗 Auto connectée, puis 💼 Jobs.

- [ ] **Step 1: Écrire les tests qui échouent** dans `tests/test_digest.py`

```python
def test_architecture_and_local_ai_sections_are_rendered_in_order():
    items = [_article(), _in("Architecture", "Hexa"), _in("IA locale", "Quad 3090")]
    text = "\n".join(veille.build_digest(items))
    assert text.index("🧠") < text.index("🏛 <b>Architecture</b>") < text.index("🖥 <b>IA locale</b>")
    assert "Hexa" in text and "Quad 3090" in text

def test_empty_new_sections_are_hidden():
    text = "\n".join(veille.build_digest([_article()]))
    assert "🏛" not in text and "🖥" not in text
```

`_in(veille, title)` copie `_article()` avec ces deux champs remplacés.

- [ ] **Step 2: Vérifier l'échec** — `python -m pytest tests/test_digest.py -q` → `ValueError: substring not found`.
- [ ] **Step 3: Implémenter** — ajouter `("Architecture", "🏛")` et `("IA locale", "🖥")` au tuple de la boucle de `build_digest`, entre Tech et Auto connectée.
- [ ] **Step 4: Vérifier** — `python -m pytest -q` → tout passe.
- [ ] **Step 5: Commit** — `git add veille.py tests/test_digest.py && git commit -m "Ajoute les sections Architecture et IA locale au digest"`

### Task 3: Sources et descriptions de sujet dans config.yaml

**Files:**
- Modify: `config.yaml`, `README.md` (section « Personnaliser »)
- Test: `tests/test_config.py` (créer)

**Interfaces:**
- Consumes: `topic_for` (tâche 1).

- [ ] **Step 1: Écrire les tests qui échouent** dans `tests/test_config.py` (charger `config.yaml` avec `yaml.safe_load`)

```python
def test_every_new_veille_has_a_topic_description():
    for veille_name in ("Architecture", "IA locale"):
        assert veille.topic_for(CFG, veille_name)
        assert any(f["veille"] == veille_name for f in CFG["feeds"])

def test_store_news_feeds_are_capped_at_three():
    caps = {f["source"]: f.get("max") for f in CFG["feeds"]}
    assert caps["Apple Developer"] == 3 and caps["Android Developers"] == 3

def test_car_maker_apps_are_untouched():
    assert len(CFG["apps"]) == 24
```

- [ ] **Step 2: Vérifier l'échec** — `python -m pytest tests/test_config.py -q` → échec sur `topic_for` / `max`.
- [ ] **Step 3: Éditer `config.yaml`**
  - `max: 3` sur Apple Developer et Android Developers.
  - Bloc `topics:` avec les deux descriptions mot pour mot depuis la spec, précédé d'un commentaire disant qu'elles sont éditables et servent au filtre Claude.
  - Section `# --- Architecture ---` (`veille: Architecture`) :
    - Architecture Weekly : `https://www.architecture-weekly.com/feed`
    - Mathias Verraes : `https://verraes.net/feed.atom`
    - Vlad Khononov : `https://vladikk.com/index.xml`
    - Khalil Stemmler : `https://khalilstemmler.com/rss.xml`
    - Mark Seemann : `https://blog.ploeh.dk/rss.xml`
    - Martin Fowler : `https://martinfowler.com/feed.atom`
    - Medium flutter-architecture : `https://medium.com/feed/tag/flutter-architecture`
    - Medium clean-architecture : `https://medium.com/feed/tag/clean-architecture`
    - Medium hexagonal-architecture : `https://medium.com/feed/tag/hexagonal-architecture`
    - Medium domain-driven-design : `https://medium.com/feed/tag/domain-driven-design`
    - dev.to cleanarchitecture : `https://dev.to/feed/tag/cleanarchitecture`
    - dev.to hexagonalarchitecture : `https://dev.to/feed/tag/hexagonalarchitecture`
    - dev.to domaindrivendesign : `https://dev.to/feed/tag/domaindrivendesign`
  - Section `# --- IA locale ---` (`veille: IA locale`) :
    - Digital Spaceport : `https://digitalspaceport.com/feed/`
    - Pedro Alonso : `https://www.pedroalonso.net/rss.xml`
    - Patshead : `https://blog.patshead.com/atom.xml`
    - bmdpat : `https://bmdpat.com/blog/rss.xml` avec `max: 30` (74 posts en 3 mois, le filtre trie)
    - Simon Willison (local LLMs) : `https://simonwillison.net/tags/local-llms.atom`
    - dev.to localllm : `https://dev.to/feed/tag/localllm`
    - Medium local-llm : `https://medium.com/feed/tag/local-llm`
    - Medium homelab : `https://medium.com/feed/tag/homelab`
  - README, « Personnaliser » : une ligne sur `topics:` (« décrit ce qui est gardé dans les veilles filtrées par Claude »).
- [ ] **Step 4: Vérifier** — `python -m pytest -q` → tout passe.
- [ ] **Step 5: Vérifier la collecte réelle (sans Notion, Telegram ni Claude)** — `python -c "import tests.conftest, veille, yaml; c=yaml.safe_load(open('config.yaml')); from collections import Counter; print(Counter(i['veille'] for i in veille.collect_feeds(c)))"`. Attendu : aucun `⚠️ Flux ignoré`, et des compteurs non nuls pour Architecture et IA locale.
- [ ] **Step 6: Commit** — `git add config.yaml README.md tests/test_config.py && git commit -m "Réduit les flux store et ajoute les sources Architecture et IA locale"`
