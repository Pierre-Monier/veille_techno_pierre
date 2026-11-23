# Refonte des sujets de la veille — design

## Intention

Le digest du lundi contient trop d'actualités store génériques (Apple Developer,
Android Developers) et rien sur deux sujets que Pierre veut apprendre :

- **Architecture** : Clean Architecture, architecture hexagonale, DDD.
- **IA locale** : héberger des modèles sur son propre matériel, à la maison, via des
  particuliers qui documentent concrètement ce qu'ils font (pas de blogs de
  fournisseurs ou d'applis).

## Objectifs / non-objectifs

- Réduire Apple Developer et Android Developers. **Garder intact** le suivi des apps
  des constructeurs (section 🚗 Auto connectée).
- Ajouter deux veilles, *Architecture* et *IA locale*, avec leur propre section
  Telegram et leur valeur « Veille » dans Notion.
- Non-objectif : plafonner le volume des nouvelles sections (à réévaluer après 2-3
  lundis).
- Anti-objectif : remplir ces sections de tutos débutants, de spam des tags
  Medium/dev.to ou d'annonces produit.

## Constat sur les sources (vérifié le 2026-11-23)

Aucun blog actif n'est dédié à la Clean Architecture : les auteurs de référence sont
dormants (Uncle Bob, Khorikov depuis 2023, Graça depuis 2020) et les actifs ont
dérivé vers l'IA. Les seules sources précises sont les tags Medium/dev.to, bruités.
D'où un filtre de pertinence par Claude.

## Approches considérées

1. **Config seule** (flux ajoutés à « Tech / Archi / IA ») : zéro code, mais sujets
   noyés et bruit des tags non filtré.
2. **Deux sections dédiées, sans filtre** : lisible, mais impossible d'utiliser les
   tags bruités, donc presque rien sur la Clean Archi.
3. **Deux sections + filtre Claude (retenue)** : permet une liste large de sources
   tout en ne gardant que ce qui colle au sujet. Coût : quelques centimes/semaine.

## Design

### config.yaml

- `max: 3` sur Apple Developer et Android Developers.
- Description de chaque sujet filtré, éditable par Pierre :

  ```yaml
  topics:
    Architecture: >
      Clean Architecture, architecture hexagonale (ports & adapters), DDD,
      modélisation du domaine, découpage modulaire. Pas de tuto débutant,
      pas d'article .NET/Java centré sur un framework plutôt que sur le design.
    IA locale: >
      Retour d'expérience concret d'une personne qui fait tourner des modèles
      d'IA sur son propre matériel (GPU, Mac, homelab) : config, perfs, coûts.
      Pas de tuto d'installation générique, pas d'annonce produit.
  ```

- Flux `veille: Architecture` : Architecture Weekly, Verraes, Khononov
  (vladikk.com/index.xml), Khalil Stemmler, Mark Seemann, Martin Fowler ; tags
  Medium `flutter-architecture`, `clean-architecture`, `hexagonal-architecture`,
  `domain-driven-design` ; tags dev.to `cleanarchitecture`,
  `hexagonalarchitecture`, `domaindrivendesign`.
- Flux `veille: IA locale` : Digital Spaceport, Pedro Alonso, Patshead, bmdpat,
  Simon Willison (tag local-llms) ; tags dev.to `localllm`, Medium `local-llm`,
  Medium `homelab`.

### veille.py

- Un item dont la veille figure dans `topics` passe par le résumé habituel, avec en
  plus la description du sujet et un champ `"pertinent": bool` demandé à Claude
  (même appel, pas d'appel supplémentaire). `pertinent == false` → item écarté
  et loggé (« ⏭ Hors sujet : … »), comme les offres d'emploi.
- Si l'appel Claude échoue pour un item filtré : on l'écarte en le loggant (choix
  du builder, à confirmer : contrairement aux offres, perdre un article n'a pas de
  coût).
- Nouveaux `THEMES` : `Clean Archi`, `DDD`, `IA locale`.
- `build_digest` : sections 🏛 Architecture et 🖥 IA locale après 🧠 Tech et avant
  🚗 Auto connectée (affichées seulement si non vides).

### Tests (TDD)

- Décision de garde/rejet selon `pertinent` et en cas d'échec Claude.
- Le prompt inclut la description du sujet pour les veilles filtrées, et pas pour
  les autres.
- `build_digest` affiche les deux nouvelles sections.

## Laissé au builder

Formulation exacte des prompts, ordre des flux dans `config.yaml`, valeurs `max`
pour les tags (défaut 10 suffit : ces flux ne contiennent que 10-12 entrées).
