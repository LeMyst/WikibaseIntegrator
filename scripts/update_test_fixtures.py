#!/usr/bin/env python3
"""
Refresh the JSON fixtures in test/fixtures/ from the live Wikidata/Wikimedia
Commons APIs.

The fixtures are deliberately *pruned* copies of real entities: only the
languages, claims and sitelinks actually used by the test suite are kept, so
the files stay small, readable and stable. Volatile fields (lastrevid,
modified) are normalized to fixed values to avoid meaningless diffs.

The script also validates the structural invariants the test suite relies on
(e.g. "Q582 has a P443 claim qualified with P407 = Q150"). If upstream data
changed in a way that breaks an invariant, the script fails with an explicit
message: update the corresponding test together with the fixture.

Usage:
    python scripts/update_test_fixtures.py             # refresh all fixtures
    python scripts/update_test_fixtures.py --check     # exit 1 if a refresh would change files
    python scripts/update_test_fixtures.py --only item_Q582

After refreshing, always run `pytest` to make sure the suite still passes.
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

import requests

WIKIDATA_API = 'https://www.wikidata.org/w/api.php'
COMMONS_API = 'https://commons.wikimedia.org/w/api.php'
USER_AGENT = 'WikibaseIntegrator-fixture-updater/1.0 (https://github.com/LeMyst/WikibaseIntegrator)'
FIXTURE_DIR = Path(__file__).resolve().parent.parent / 'test' / 'fixtures'

# Normalized values for volatile fields, so that a refresh only produces a
# diff when the *content* of the entity changed.
MODIFIED_PLACEHOLDER = '2025-01-01T00:00:00Z'
LASTREVID_PLACEHOLDERS = {
    'Q582': 2211855070,
    'P50': 2183770174,
    'L5': 1685575043,
    'M75908279': 725401355,
}

session = requests.Session()
session.headers.update({'User-Agent': USER_AGENT})

problems: list[str] = []


def require(condition: bool, message: str) -> None:
    """Record a violated invariant instead of failing at the first one."""
    if not condition:
        problems.append(message)


def fetch_entity(api_url: str, entity_id: str) -> dict:
    response = session.get(api_url, params={'action': 'wbgetentities', 'ids': entity_id, 'format': 'json'}, timeout=60)
    response.raise_for_status()
    payload = response.json()
    if 'error' in payload:
        raise RuntimeError(f"API error while fetching {entity_id}: {payload['error']}")
    return payload['entities'][entity_id]


def base_info(entity: dict) -> dict:
    """Common header fields, with volatile values normalized."""
    info = {key: entity[key] for key in ('pageid', 'ns', 'title') if key in entity}
    info['lastrevid'] = LASTREVID_PLACEHOLDERS.get(entity['id'], entity.get('lastrevid', 1))
    info['modified'] = MODIFIED_PLACEHOLDER
    info['type'] = entity['type']
    return info


def keep_languages(section: dict, languages: tuple[str, ...]) -> dict:
    return {language: deepcopy(value) for language, value in section.items() if language in languages}


def prune_item_q582(entity: dict) -> dict:
    claims = entity.get('claims', {})
    p31 = deepcopy(claims.get('P31', [])[:2])
    p443 = deepcopy([claim for claim in claims.get('P443', []) if 'P407' in claim.get('qualifiers', {})][:1])
    p2581 = deepcopy([claim for claim in claims.get('P2581', []) if claim.get('references')][:1])

    result = {
        **base_info(entity),
        'id': 'Q582',
        'labels': keep_languages(entity['labels'], ('en', 'fr', 'es')),
        'descriptions': keep_languages(entity['descriptions'], ('en', 'fr')),
        # The test suite needs an entity with aliases and Q582 has none upstream:
        # stable synthetic ones are injected instead.
        'aliases': {
            'fr': [{'language': 'fr', 'value': 'Villeurbanne (Rhône)'}],
            'en': [{'language': 'en', 'value': 'Villeurbanne, France'}],
        },
        'claims': {'P31': p31, 'P443': p443, 'P2581': p2581},
        'sitelinks': {site: deepcopy(entity['sitelinks'][site]) for site in ('enwiki', 'frwiki') if site in entity.get('sitelinks', {})},
    }

    # Invariants relied upon by the test suite (test_models.py, test_entity_item.py)
    require(result['labels'].get('fr', {}).get('value') == 'Villeurbanne', "Q582: French label is no longer 'Villeurbanne'")
    require('es' in result['labels'], 'Q582: Spanish label is missing')
    require('commune' in result['descriptions'].get('en', {}).get('value', ''), "Q582: English description no longer contains 'commune'")
    require(len(p31) == 2, 'Q582: needs at least two P31 claims')
    require(any(claim['mainsnak']['datavalue']['value']['id'] == 'Q484170' for claim in p31), 'Q582: P31 no longer contains Q484170 (commune of France)')
    require(bool(p443), 'Q582: needs a P443 claim with a P407 qualifier')
    if p443:
        qualifier_value = p443[0]['qualifiers']['P407'][0].get('datavalue', {}).get('value', {}).get('id')
        require(qualifier_value == 'Q150', f"Q582: P443 qualifier P407 is no longer Q150 (got {qualifier_value})")
    require(bool(p2581), 'Q582: needs a P2581 claim with at least one reference')
    require('enwiki' in result['sitelinks'], 'Q582: enwiki sitelink is missing')

    return result


def prune_property_p50(entity: dict) -> dict:
    result = {
        **base_info(entity),
        'datatype': entity['datatype'],
        'id': 'P50',
        'labels': keep_languages(entity['labels'], ('en', 'fr')),
        'descriptions': keep_languages(entity['descriptions'], ('en',)),
        'aliases': keep_languages(entity.get('aliases', {}), ('en',)),
        'claims': {},
    }

    require(result['datatype'] == 'wikibase-item', 'P50: datatype is no longer wikibase-item')
    require(result['labels'].get('fr', {}).get('value') == 'auteur ou autrice', "P50: French label is no longer 'auteur ou autrice' (update test_entity_property.py)")

    return result


def prune_lexeme_l5(entity: dict) -> dict:
    claims = entity.get('claims', {})
    kept_claims = {}
    if 'P5185' in claims:
        kept_claims['P5185'] = deepcopy(claims['P5185'][:1])

    forms = []
    for form in entity.get('forms', []):
        forms.append({
            'id': form['id'],
            'representations': deepcopy(form['representations']),
            'grammaticalFeatures': deepcopy(form['grammaticalFeatures']),
            'claims': {},
        })

    senses = []
    for sense in entity.get('senses', [])[:1]:
        senses.append({
            'id': sense['id'],
            'glosses': keep_languages(sense['glosses'], ('es', 'en')),
            'claims': {},
        })

    result = {
        **base_info(entity),
        'id': 'L5',
        'lemmas': deepcopy(entity['lemmas']),
        'lexicalCategory': entity['lexicalCategory'],
        'language': entity['language'],
        'claims': kept_claims,
        'forms': forms,
        'senses': senses,
    }

    require(result['lemmas'].get('es', {}).get('value') == 'pino', "L5: Spanish lemma is no longer 'pino'")
    require(len(forms) >= 2, 'L5: needs at least two forms')
    es_representations = {form['representations'].get('es', {}).get('value') for form in forms}
    require({'pino', 'pinos'} <= es_representations, f"L5: forms no longer include 'pino' and 'pinos' (got {es_representations})")
    require(bool(senses) and senses[0]['glosses'].get('en', {}).get('value') == 'pine tree',
            "L5: first sense English gloss is no longer 'pine tree' (update test_entity_lexeme.py)")

    return result


def prune_mediainfo_budapest(entity: dict) -> dict:
    statements = entity.get('statements', {})
    p180 = deepcopy(statements.get('P180', [])[:1])

    result = {
        **base_info(entity),
        'id': 'M75908279',
        'labels': keep_languages(entity.get('labels', {}), ('en',)),
        'descriptions': {},
        'statements': {'P180': p180},
    }

    require(result['title'] == 'File:2018-07-05-budapest-buda-hill.jpg', 'M75908279: file title changed (update test_entity_mediainfo.py)')
    require(bool(p180), 'M75908279: needs at least one P180 statement')

    return result


FIXTURES = {
    'item_Q582': (WIKIDATA_API, 'Q582', prune_item_q582),
    'property_P50': (WIKIDATA_API, 'P50', prune_property_p50),
    'lexeme_L5': (WIKIDATA_API, 'L5', prune_lexeme_l5),
    'mediainfo_M75908279': (COMMONS_API, 'M75908279', prune_mediainfo_budapest),
}


def render(data: dict) -> str:
    return json.dumps(data, indent=4, ensure_ascii=False) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true', help='do not write anything, exit 1 if a refresh would change files')
    parser.add_argument('--only', choices=sorted(FIXTURES), help='refresh a single fixture')
    args = parser.parse_args()

    names = [args.only] if args.only else sorted(FIXTURES)
    changed = []

    for name in names:
        api_url, entity_id, prune = FIXTURES[name]
        print(f'Fetching {entity_id} from {api_url}...')
        entity = fetch_entity(api_url, entity_id)
        new_content = render(prune(entity))

        path = FIXTURE_DIR / f'{name}.json'
        old_content = path.read_text(encoding='utf-8') if path.exists() else ''

        if new_content == old_content:
            print(f'  {path.name}: up to date')
            continue

        changed.append(name)
        if args.check:
            print(f'  {path.name}: OUTDATED')
        else:
            path.write_text(new_content, encoding='utf-8', newline='\n')
            print(f'  {path.name}: updated')

    if problems:
        print('\nUpstream data no longer matches the invariants expected by the test suite:', file=sys.stderr)
        for problem in problems:
            print(f'  - {problem}', file=sys.stderr)
        print('Fix the corresponding tests together with the fixtures.', file=sys.stderr)
        return 2

    if changed:
        print(f"\n{len(changed)} fixture(s) {'need a refresh' if args.check else 'refreshed'}: {', '.join(changed)}")
        print('Run `pytest` to make sure the test suite still passes.')
        return 1 if args.check else 0

    print('\nAll fixtures are up to date.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
