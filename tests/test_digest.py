# ABOUTME: Teste le rendu du digest Telegram, en particulier la section Jobs.
# ABOUTME: La section Jobs doit toujours apparaître, même vide (aucune donnée ≠ bug).

import veille


def _job(title="Senior Flutter Engineer"):
    return {"veille": "Jobs", "title": title, "resume": "Super fit",
            "link": "https://example.com/1", "impact": False,
            "themes": ["Flutter"], "concurrent": None}


def _article():
    return {"veille": "Tech / Archi / IA", "title": "Un article",
            "resume": "résumé", "link": "https://example.com/a", "impact": False,
            "themes": ["Flutter"], "concurrent": None}


def test_jobs_section_states_explicitly_when_empty():
    text = "\n".join(veille.build_digest([_article()]))
    assert "💼" in text
    assert "Aucune offre" in text


def test_jobs_section_states_empty_even_when_nothing_new():
    text = "\n".join(veille.build_digest([]))
    assert "Aucune offre" in text


def test_jobs_section_lists_matched_offer():
    text = "\n".join(veille.build_digest([_job()]))
    assert "Senior Flutter Engineer" in text
    assert "Aucune offre" not in text
