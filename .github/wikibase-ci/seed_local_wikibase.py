import json
import os
from typing import Any

import requests

API_URL = os.getenv('WBI_MEDIAWIKI_API_URL', 'http://127.0.0.1:8181/w/api.php')
USERNAME = os.getenv('WBI_TEST_USERNAME', 'Admin')
PASSWORD = os.getenv('WBI_TEST_PASSWORD', 'adminpass')


def api_post(session: requests.Session, data: dict[str, Any]) -> dict[str, Any]:
    payload = {'format': 'json'}
    payload.update(data)
    response = session.post(API_URL, data=payload, timeout=30)
    response.raise_for_status()
    output = response.json()
    if 'error' in output:
        raise RuntimeError(f"MediaWiki API error: {output['error']}")
    return output


def get_token(session: requests.Session, token_type: str) -> str:
    result = api_post(session, {'action': 'query', 'meta': 'tokens', 'type': token_type})
    return result['query']['tokens'][f'{token_type}token']


def login(session: requests.Session) -> None:
    login_token = get_token(session, 'login')
    result = api_post(session, {
        'action': 'clientlogin',
        'username': USERNAME,
        'password': PASSWORD,
        'logintoken': login_token,
        'loginreturnurl': 'http://127.0.0.1/'
    })
    status = result.get('clientlogin', {}).get('status')
    if status != 'PASS':
        raise RuntimeError(f'Failed to login to local Wikibase: {result}')


def create_property(session: requests.Session, csrf_token: str, label_en: str, datatype: str) -> str:
    data = {
        'labels': {'en': {'language': 'en', 'value': label_en}, 'fr': {'language': 'fr', 'value': label_en}}
    }
    result = api_post(session, {
        'action': 'wbeditentity',
        'new': 'property',
        'data': json.dumps(data),
        'datatype': datatype,
        'token': csrf_token
    })
    return result['entity']['id']


def create_item(session: requests.Session, csrf_token: str) -> str:
    entity_data = {
        'labels': {
            'en': {'language': 'en', 'value': 'Villeurbanne test seed'},
            'fr': {'language': 'fr', 'value': 'Villeurbanne'}
        },
        'descriptions': {
            'en': {'language': 'en', 'value': 'city used for local integration tests'}
        },
        'aliases': {
            'fr': [{'language': 'fr', 'value': 'Villeurbanne alias'}],
            'en': [{'language': 'en', 'value': 'Villeurbanne alias en'}]
        }
    }
    result = api_post(session, {
        'action': 'wbeditentity',
        'new': 'item',
        'data': json.dumps(entity_data),
        'token': csrf_token
    })
    return result['entity']['id']


def create_lexeme(session: requests.Session, csrf_token: str, language_qid: str, category_qid: str) -> str:
    lexeme_data = {
        'lemmas': {'en': {'language': 'en', 'value': 'pino'}},
        'language': language_qid,
        'lexicalCategory': category_qid
    }
    result = api_post(session, {
        'action': 'wbeditentity',
        'new': 'lexeme',
        'data': json.dumps(lexeme_data),
        'token': csrf_token
    })
    lexeme_id = result['entity']['id']

    form_data = {
        'representations': {'es': {'language': 'es', 'value': 'pinos'}}
    }
    api_post(session, {
        'action': 'wbladdform',
        'lexemeId': lexeme_id,
        'data': json.dumps(form_data),
        'token': csrf_token
    })

    return lexeme_id


def main() -> None:
    session = requests.Session()
    login(session)
    csrf_token = get_token(session, 'csrf')

    created_properties = [
        create_property(session, csrf_token, 'author', 'string'),
        create_property(session, csrf_token, 'test qualifier property', 'wikibase-item'),
        create_property(session, csrf_token, 'test reference property', 'external-id')
    ]

    city_qid = create_item(session, csrf_token)
    lexeme_id = create_lexeme(session, csrf_token, city_qid, city_qid)

    print(f'Created properties: {created_properties}')
    print(f'Created item: {city_qid}')
    print(f'Created lexeme: {lexeme_id}')


if __name__ == '__main__':
    main()

