# ABOUTME: Vérifie la cohérence de config.yaml : sujets filtrés décrits, flux store plafonnés.
# ABOUTME: Garantit aussi que le suivi des apps des constructeurs reste intact.

from pathlib import Path

import yaml

import veille

CFG = yaml.safe_load((Path(__file__).parent.parent / "config.yaml").read_text(encoding="utf-8"))


def test_every_new_veille_has_a_topic_description():
    for veille_name in ("Architecture", "IA locale"):
        assert veille.topic_for(CFG, veille_name)
        assert any(f["veille"] == veille_name for f in CFG["feeds"])


def test_store_news_feeds_are_capped_at_three():
    caps = {f["source"]: f.get("max") for f in CFG["feeds"]}
    assert caps["Apple Developer"] == 3
    assert caps["Android Developers"] == 3


def test_car_maker_apps_are_untouched():
    assert len(CFG["apps"]) == 24
