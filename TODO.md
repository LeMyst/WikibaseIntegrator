# TODO — Revue du projet (2026-07-27)

Fichier local, non versionné (ajouté au .gitignore). Issu de la revue complète du 27 juillet 2026.
État au moment de la revue : 203 tests OK (1,5 s), couverture 81 %, pylint 8.98/10, 41 issues ouvertes, dernière release 0.12.15 (21 déc. 2025).

## 1. Quick wins (à faire en premier)

- [x] **Fixer les 2 erreurs mypy sur master** — `wbi_login.py:339` et `wbi_login.py:428` :
      `session.headers.get()` renvoie `str | bytes`, incompatible avec `dict[str, str]` attendu par `_perform_login()`.
      Introduites par le bump mypy 2.3.0 (#1006). *(fait le 2026-07-27, garde `isinstance(…, str)`)*
- [x] **Corriger les `paths` de `.github/workflows/python-lint.yaml`** — ajouter `pyproject.toml` et `poetry.lock`
      (comme `python-pytest.yaml`), sinon les bumps de dépendances mergent sans passer le lint (cause racine du point précédent).
      *(fait le 2026-07-27)*
- [x] **Ajouter le marqueur `py.typed`** (PEP 561) — fichier vide `wikibaseintegrator/py.typed` + déclaration dans
      `pyproject.toml`. Sans lui, les type hints ne profitent pas aux utilisateurs en aval.
      *(fait le 2026-07-27, présence dans la wheel vérifiée via `poetry build`)*
- [x] **README** : supprimer/corriger la phrase « But WikibaseIntegrator lack the "fastrun" functionality »
      (contradictoire, `wbi_fastrun.py` existe). *(fait le 2026-07-27 — texte identique à celui de la PR #1001 pour éviter un conflit de merge)*
- [x] **AGENTS.md** : la version n'est plus « mirrored in `__init__.py` » (lecture via `importlib.metadata` désormais).
      *(fait le 2026-07-27)*

→ Reste à faire pour cette section : commit + push (non fait, en attente de validation).

## 2. Écluser la file d'attente (axe n° 1)

- [ ] **Merger les 5 PRs perso ouvertes** :
  - ~~#1001 — fix fastrun (`fix-wbi-fastrun`)~~ → **à fermer au profit de #333** (voir ci-dessous)
  - #983 — SPARQL en POST body
  - #982 — non-mutation des données passées en argument
  - #981 — supprimer les sessions requests module-level
  - #980 — AnonymousEditError + meilleure gestion d'erreurs
- [ ] **Publier la release 0.12.16** — 7 mois depuis 0.12.15, master contient déjà : récupération de session (#999),
      abandon de mwoauth (#998), `check_constraints()` (#997), refactor entités (#996).
- [x] **Décision fastrun (2026-07-28) : retenir #333 (`new-fastrun`), fermer #1001.**
      Vérifié : #333 = 235 tests, corrige le crash `wbi_fastrun.py:291` que #1001 laisse intact, et interroge SPARQL
      par statement au lieu de la requête unique sur tout le corpus (celle qui a enchaîné cinq 504 WDQS au benchmark).
      Coût : rebase nécessaire (conflits), rupture d'API fastrun (`get_items` → `get_entities`), donc changelog.
- [x] **Porter le meilleur de #1001 dans #333** → branche `port-1001-into-new-fastrun` (poussée, 253 tests).
      `BaseDataType.from_sparql_value()` générique + implémentations pour Property, Lexeme, Form, Sense, GeoShape,
      TabularData, CommonsMedia. Lève la limitation « datatypes non comparables » et corrige un faux appariement
      silencieux de CommonsMedia (stockait l'URL Commons entière).
- [x] **Rebaser `new-fastrun` sur master + intégrer le portage** (fait le 2026-07-28).
      PR #333 est passée de CONFLICTING à **MERGEABLE** : 6 commits, 0 de retard, 253 tests, mypy/isort/codespell/flynt
      clean (les 2 erreurs mypy héritées ont disparu avec #1010). Un seul conflit, sur la phrase fastrun du README
      (master via #1012 vs `new-fastrun`) — résolu en gardant celle de `new-fastrun`, plus précise.
      Sauvegarde d'avant rebase : branche locale `new-fastrun-bkp-20260728` (`195ee1d`).
- [x] **#1001 fermée** (2026-07-28) avec un commentaire renvoyant vers #333 et détaillant la raison
      (architecture de la requête en masse, crash `:291`, et ce qui a été porté). Branche `fix-wbi-fastrun` conservée.
- [x] **Branche `port-1001-into-new-fastrun` supprimée** (locale + distante) après vérification que son commit
      est intégré à l'identique dans #333.
- [ ] **Relire et merger #333** — dernière étape du chantier fastrun.
      Ne pas oublier : rupture d'API fastrun (`get_items` → `get_entities`, `write_required` gagne
      `entity_filter`/`property_filter`) → entrée de changelog + note de version.
      Après merge : supprimer la sauvegarde locale `new-fastrun-bkp-20260728` si tout va bien.
- [ ] **Grooming du backlog** (41 issues, les plus vieilles de 2023) : fermer l'obsolète, étiqueter le reste.
- [ ] **Bugs utilisateurs à prioriser** :
  - #953 — KeyError `'hash'` au parsing des références
  - #883 — erreur upload statement avec qualifier Time
  - #836 — impossible d'écrire dans un MediaInfo vide
- [ ] Traiter les PRs externes en attente : #917 (merge multi-items), #926 (draft, défaut `Claims.add()`), #834, #663 (draft).

## 3. Robustesse réseau

- [ ] **Retry bloquant** dans `wbi_helpers.mediawiki_api_call()` : `max_retries=100` × `sleep(60)` = jusqu'à ~100 min
      de blocage silencieux. Réduire les défauts + backoff progressif (le décorateur `wbi_backoff` ne couvre que SPARQL/login).
- [ ] **Lookups de datatypes fragiles** : le motif `[x for x in BaseDataType.subclasses if x.DTYPE == ...][0]`
      (models/claims.py:127, wbi_fastrun.py, wbi_helpers.py) lève une `IndexError` brute sur datatype inconnu.
      → registre avec message d'erreur explicite listant les datatypes supportés.
- [ ] (Long terme, si demande) API async via httpx pour les bots de masse.

## 4. Architecture / dette

- [ ] **Boilerplate propriétés** : centaines de getters/setters triviaux (baseentity.py, claims.py…).
      → dataclasses (cf. branche dormante `implement-pep557`) ou suppression des propriétés triviales.
- [ ] **Imports cycliques** (pylint R0401) : `wikibaseintegrator ↔ entities ↔ wbi_helpers ↔ wbi_login`,
      masqués par des imports locaux dans les fonctions.
- [ ] **État global restant** : dict `config` mutable sans validation, cache module-level `properties_dt`
      (format2wbi), liste globale `fastrun_store`. (#981/#982 traitent déjà les sessions et la mutation.)
- [ ] **`format2wbi` / `_json2datatype`** : expérimentaux, non testés, références non attachées.
      → finir ou sortir du module principal.

## 5. Tests

- [ ] **`wbi_helpers.py` à 69 %** : la logique de retry (rate limiting, readonly, maxlag) est en `pragma: no cover`
      alors qu'elle est testable offline avec requests-mock. Code critique pour un bot.
- [ ] Modules les moins couverts : monolingualtext (70 %), globecoordinate (72 %), baseentity (73 %), references (77 %).

## 6. Outillage / packaging

- [ ] **ruff** : remplacerait isort + flynt et une partie de pylint (une config, beaucoup plus rapide en CI).
- [ ] **pre-commit** : la branche `add-pre-commit` existe déjà, jamais mergée.
- [ ] **PEP 621** : migrer `[tool.poetry]` vers `[project]` (supporté par Poetry 2).
- [ ] **Couverture en CI + badge** (issue #895).
- [ ] Classifieurs `pyproject.toml` : `Python :: 3.15` déclaré alors que 3.15 n'est pas sorti ;
      `Development Status :: 4 - Beta` ne reflète plus la maturité.

## 7. Stratégique

- [ ] **API REST Wikibase** (issue #518) : direction poussée par Wikimedia. Au minimum une exploration de design
      (module `wbi_rest` parallèle plutôt que réécriture).
- [ ] **Ergonomie 0.13** (avec dépréciations propres) :
  - défaut `REPLACE_ALL` de `Claims.add()` (piège connu, cf. #926 / #841)
  - confusion `len(claims)` (nb propriétés) vs `count()` (nb claims)
  - supprimer la classe dépréciée `BColors`
- [ ] **Docs** : README de 35 Ko monolithique → déplacer les guides vers Sphinx/RTD, garder un README court.

## Ordre de priorité suggéré

1. Section 1 (quick wins) — ~1 h de travail, débloque la CI.
2. Section 2 — merges + release 0.12.16.
3. Bugs utilisateurs (#953, #883, #836) + grooming.
4. Sections 3–6 au fil de l'eau.
5. Section 7 ensuite.
