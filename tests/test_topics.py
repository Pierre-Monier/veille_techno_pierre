# ABOUTME: Teste le filtre de pertinence des veilles décrites dans « topics » (config.yaml).
# ABOUTME: Vérifie le prompt envoyé à Claude et la décision garder/écarter selon sa réponse.

import veille

TOPIC = "Clean Architecture et DDD"


def _item(text=""):
    return {"veille": "Architecture", "title": "Un article", "source": "S", "text": text,
            "resume": "", "themes": [], "concurrent": None}


def test_relevant_item_is_kept():
    item = _item()
    keep = veille.apply_summary(item, {"pertinent": True, "resume": "r", "themes": ["DDD"],
                                       "concurrent": None, "impact": False}, TOPIC)
    assert keep is True
    assert item["themes"] == ["DDD"]
    assert item["resume"] == "r"


def test_off_topic_item_is_dropped():
    keep = veille.apply_summary(_item(), {"pertinent": False, "resume": "r", "themes": []}, TOPIC)
    assert keep is False


def test_missing_pertinent_field_drops_filtered_item():
    assert veille.apply_summary(_item(), {"resume": "r", "themes": []}, TOPIC) is False


def test_claude_failure_drops_filtered_item(capsys):
    assert veille.apply_summary(_item(), None, TOPIC) is False
    assert "Résumé impossible pour « Un article »" in capsys.readouterr().out


def test_unfiltered_item_kept_without_pertinent_field():
    assert veille.apply_summary(_item(), {"resume": "r", "themes": []}, None) is True


def test_claude_failure_keeps_unfiltered_item_with_fallback_summary(capsys):
    item = _item(text="texte brut")
    assert veille.apply_summary(item, None, None) is True
    assert item["resume"] == "texte brut"
    assert "Résumé impossible" in capsys.readouterr().out


def test_prompt_includes_topic_and_pertinent_field_when_filtered():
    prompt = veille.build_summary_prompt(_item(), TOPIC)
    assert TOPIC in prompt
    assert '"pertinent"' in prompt


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


def test_prompt_json_example_shows_pertinent_when_filtered():
    prompt = veille.build_summary_prompt(_item(), TOPIC)
    assert '{"pertinent": true, "resume": "..."' in prompt
