"""
Interaction tests for ItemEntity against the simulated Wikibase instance:
retrieval, error handling and, most importantly, the exact payloads sent to
the wbeditentity API endpoint when writing.
"""
import json

import pytest

from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.datatypes import Item, String
from wikibaseintegrator.wbi_exceptions import ModificationFailed, MWApiError, NonExistentEntityError

wbi = WikibaseIntegrator()


class TestGet:
    def test_get_id_formats(self, item_q582):
        assert wbi.item.get('Q582').id == 'Q582'
        assert wbi.item.get('582').id == 'Q582'
        assert wbi.item.get(582).id == 'Q582'
        assert wbi.item.get('Item:Q582').id == 'Q582'

    def test_get_sends_expected_request(self, wikibase, item_q582):
        wbi.item.get('Q582')

        request = wikibase.last_request
        assert request['action'] == 'wbgetentities'
        assert request['ids'] == 'Q582'
        assert request['format'] == 'json'
        # No login was provided: the query must be anonymous.
        assert request['assert'] == 'anon'
        assert request['token'] == '+\\'

    def test_get_invalid_ids(self, wikibase):
        with pytest.raises(ValueError):
            wbi.item.get('L5')

        with pytest.raises(ValueError):
            wbi.item.get(0)

        with pytest.raises(ValueError):
            wbi.item.get(-1)

    def test_get_nonexistent_entity(self, wikibase):
        with pytest.raises(NonExistentEntityError):
            wbi.item.get('Q99999999999999')

    def test_get_json(self, item_q582):
        assert wbi.item.get('Q582').get_json()['labels']['fr']['value'] == 'Villeurbanne'

    def test_get_limited_props(self, wikibase, item_q582):
        item = wbi.item.get('Q582', props=['labels'])
        assert wikibase.last_request['props'] == 'labels|info'
        assert item.labels.get('fr').value == 'Villeurbanne'
        assert len(item.claims) == 0
        assert len(item.sitelinks) == 0
        assert len(item.aliases) == 0
        assert len(item.descriptions) == 0

        item = wbi.item.get('Q582', props=['aliases'])
        assert len(item.aliases) > 0
        assert len(item.labels) == 0


class TestEntityUrl:
    def test_entity_url(self):
        assert wbi.item.new(id='Q582').get_entity_url() == 'http://www.wikidata.org/entity/Q582'
        assert wbi.item.new(id='582').get_entity_url() == 'http://www.wikidata.org/entity/Q582'
        assert wbi.item.new(id=582).get_entity_url() == 'http://www.wikidata.org/entity/Q582'


class TestWrite:
    def test_write_edit_roundtrip(self, wikibase, item_q582):
        item = wbi.item.get('Q582')
        item.claims.add(Item(prop_nr='P1791', value='Q42'))
        written = item.write(allow_anonymous=True)

        # The API received exactly one wbeditentity call with the full payload.
        edit = wikibase.last_edit
        assert edit['params']['action'] == 'wbeditentity'
        assert edit['params']['id'] == 'Q582'
        assert edit['params']['maxlag'] == '5'
        assert edit['params']['assert'] == 'anon'

        payload = edit['data']
        assert payload['labels']['fr'] == {'language': 'fr', 'value': 'Villeurbanne'}
        assert payload['claims']['P1791'][0]['mainsnak']['datavalue']['value']['id'] == 'Q42'

        # The entity returned by the instance is deserialized back.
        assert written.id == 'Q582'
        assert written.claims.get('P1791')[0].mainsnak.datavalue['value']['id'] == 'Q42'
        assert written.claims.get('P1791')[0].id is not None
        assert written.lastrevid == item_q582['lastrevid'] + 1

    def test_write_new_item(self, wikibase):
        item = wbi.item.new()
        item.labels.set(language='en', value='A brand new item')
        item.claims.add(String(prop_nr='P828', value='new item claim'))
        written = item.write(allow_anonymous=True)

        edit = wikibase.last_edit
        assert edit['params']['new'] == 'item'
        assert 'id' not in edit['params']
        assert written.id.startswith('Q')
        assert written.labels.get('en') == 'A brand new item'

    def test_write_with_summary_and_bot_flag(self, wikibase, item_q582):
        item = wbi.item.get('Q582')
        item.write(allow_anonymous=True, summary='update item', is_bot=True)

        params = wikibase.last_edit['params']
        assert params['summary'] == 'update item'
        assert params['bot'] == ''

    def test_write_as_new(self, wikibase, item_q582):
        item = wbi.item.get('Q582')
        written = item.write(allow_anonymous=True, as_new=True)

        assert wikibase.last_edit['params']['new'] == 'item'
        assert written.id != 'Q582'

    def test_write_limited_claims(self, wikibase, item_q582):
        item = wbi.item.get('Q582')
        item.write(allow_anonymous=True, limit_claims=['P31'])

        payload = wikibase.last_edit['data']
        assert list(payload['claims'].keys()) == ['P31']

    def test_write_clear(self, wikibase, item_q582):
        item = wbi.item.get('Q582')
        item.clear(allow_anonymous=True)

        assert wikibase.last_edit['params']['clear'] == ''
        assert wikibase.last_edit['data'] == {}

    def test_write_baserevid(self, wikibase, item_q582):
        item = wbi.item.get('Q582')
        item.write(allow_anonymous=True, baserevid=item.lastrevid)

        assert wikibase.last_edit['params']['baserevid'] == str(item_q582['lastrevid'])

    def test_anonymous_write_refused_without_flag(self, wikibase, item_q582):
        item = wbi.item.get('Q582')
        with pytest.raises(ValueError):
            item.write()

    def test_write_modification_failed(self, wikibase, item_q582):
        item = wbi.item.get('Q582')
        wikibase.fail_next(code='modification-failed', info='Item already has label...', messages=[{'name': 'wikibase-validator-label-with-description-conflict'}])

        with pytest.raises(ModificationFailed):
            item.write(allow_anonymous=True)

    def test_write_generic_api_error(self, wikibase, item_q582):
        item = wbi.item.get('Q582')
        wikibase.fail_next(code='badtoken', info='Invalid CSRF token.')

        with pytest.raises(MWApiError):
            item.write(allow_anonymous=True)

    def test_write_invalid_json_response(self, wikibase, requests_mock, item_q582):
        item = wbi.item.get('Q582')
        requests_mock.post(wikibase.mediawiki_api_url, text='<html>this is not JSON</html>')

        with pytest.raises(json.JSONDecodeError):
            item.write(allow_anonymous=True)


class TestWriteWithLogin:
    def test_write_uses_edit_token_and_login_session(self, wikibase, item_q582):
        from wikibaseintegrator import wbi_login

        wikibase.valid_credentials['BotUser@pytest'] = 'botpassword'
        login = wbi_login.Login(user='BotUser@pytest', password='botpassword', mediawiki_api_url=wikibase.mediawiki_api_url)

        authenticated_wbi = WikibaseIntegrator(login=login)
        item = authenticated_wbi.item.get('Q582')
        item.labels.set(language='en', value='Modified label')
        item.write()

        params = wikibase.last_edit['params']
        assert params['token'] == wikibase.csrf_token
        assert params['assert'] == 'user'
