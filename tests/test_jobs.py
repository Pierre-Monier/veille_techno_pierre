# ABOUTME: Teste la décision garder/écarter d'une offre à partir du verdict de Claude.
# ABOUTME: Vérifie aussi qu'un échec d'évaluation ne fait pas disparaître l'offre.

import veille


def _item():
    return {"veille": "Jobs", "title": "Lead Flutter Dev", "resume": "",
            "themes": [], "concurrent": None}


def test_strong_fit_is_kept():
    item = _item()
    keep = veille.apply_job_result(
        item, {"fit": True, "resume": "Rôle Flutter senior", "themes": ["Flutter"]})
    assert keep is True
    assert item["resume"] == "Rôle Flutter senior"
    assert item["themes"] == ["Flutter"]


def test_weak_fit_is_dropped():
    item = _item()
    keep = veille.apply_job_result(
        item, {"fit": False, "resume": "Poste purement backend", "themes": []})
    assert keep is False


def test_unknown_theme_is_filtered_out():
    item = _item()
    veille.apply_job_result(
        item, {"fit": True, "resume": "ok", "themes": ["Flutter", "Inexistant"]})
    assert item["themes"] == ["Flutter"]


def test_scoring_failure_surfaces_the_offer():
    item = _item()
    keep = veille.apply_job_result(item, None)
    assert keep is True  # on ne perd pas silencieusement une offre non évaluée
    assert "impossible" in item["resume"].lower()
    assert item["themes"] == ["Flutter"]
