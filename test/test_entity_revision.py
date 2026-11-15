"""
Loading an entity at a given revision with get(revision=...), from Special:EntityData, and the download_entity_data() helper.
"""
from copy import deepcopy
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.entities import ItemEntity, LexemeEntity, MediaInfoEntity, PropertyEntity
from wikibaseintegrator.wbi_exceptions import MissingEntityException
from wikibaseintegrator.wbi_helpers import download_entity_data, download_entity_ttl

wbi = WikibaseIntegrator()

OLD_REVISION = 1000


def query_string(url: str) -> dict[str, str]:
    """The parameters of a URL, with their case (requests_mock lowercases its qs)."""
    return {key: values[0] for key, values in parse_qs(urlparse(url).query).items()}


def add_old_revision(wikibase, entity_id: str) -> dict:
    """Register an old revision of an entity of the instance, with another first label or lemma."""
    old = deepcopy(wikibase.entities[entity_id])
    old['lastrevid'] = OLD_REVISION
    terms = old['lemmas'] if 'lemmas' in old else old['labels']
    language = next(iter(terms))
    terms[language]['value'] = 'old value'
    wikibase.old_revisions[(entity_id, OLD_REVISION)] = old
    return old


class TestGetRevision:
    @pytest.mark.parametrize(('getter', 'fixture', 'entity_id', 'entity_class'), [
        ('item', 'item_Q582', 'Q582', ItemEntity),
        ('property', 'property_P50', 'P50', PropertyEntity),
        ('lexeme', 'lexeme_L5', 'L5', LexemeEntity),
        ('mediainfo', 'mediainfo_M75908279', 'M75908279', MediaInfoEntity),
    ])
    def test_get_old_revision(self, wikibase, getter, fixture, entity_id, entity_class):
        wikibase.add_fixture(fixture)
        add_old_revision(wikibase, entity_id)

        entity = getattr(wbi, getter).get(entity_id, revision=OLD_REVISION)

        assert isinstance(entity, entity_class)
        assert entity.id == entity_id
        assert entity.lastrevid == OLD_REVISION
        assert entity.loaded_revision == OLD_REVISION
        terms = entity.lemmas if isinstance(entity, LexemeEntity) else entity.labels
        assert 'old value' in [term.value for term in terms]
        # Loaded from Special:EntityData, not from wbgetentities
        assert wikibase.requests == []
        assert wikibase.entity_data_requests == [{'title': f'Special:EntityData/{entity_id}.json', 'revision': str(OLD_REVISION)}]

    def test_get_latest_revision_by_id(self, wikibase, item_q582):
        entity = wbi.item.get('Q582', revision=item_q582['lastrevid'])

        assert entity.lastrevid == item_q582['lastrevid']
        assert entity.loaded_revision == item_q582['lastrevid']
        assert entity.labels.get('en').value == item_q582['labels']['en']['value']

    def test_get_without_revision(self, wikibase, item_q582):
        entity = wbi.item.get('Q582')

        assert entity.loaded_revision is None
        assert wikibase.last_request['action'] == 'wbgetentities'
        assert wikibase.entity_data_requests == []

    def test_reload_at_revision(self, wikibase, item_q582):
        add_old_revision(wikibase, 'Q582')

        entity = wbi.item.get('Q582').get(revision=OLD_REVISION)

        assert entity.loaded_revision == OLD_REVISION
        assert entity.labels.get('en').value == 'old value'

    def test_missing_revision(self, wikibase, item_q582):
        with pytest.raises(MissingEntityException, match="The revision 1234 of the entity Q582 doesn't exist") as excinfo:
            wbi.item.get('Q582', revision=1234)

        assert isinstance(excinfo.value.__cause__, requests.HTTPError)
        assert excinfo.value.__cause__.response.status_code == 404

    def test_revision_of_another_entity(self, wikibase, item_q582):
        add_old_revision(wikibase, 'Q582')
        wikibase.add_entity({**deepcopy(item_q582), 'id': 'Q583', 'title': 'Q583', 'lastrevid': 2000})

        with pytest.raises(MissingEntityException):
            wbi.item.get('Q583', revision=OLD_REVISION)

    def test_other_error_is_raised(self, wikibase, requests_mock):
        requests_mock.get(wikibase.mediawiki_index_url, status_code=400, text='<html><body><h1>Bad Request</h1><p>Invalid ID: Q582.</p></body></html>')

        with pytest.raises(requests.HTTPError) as excinfo:
            wbi.item.get('Q582', revision=OLD_REVISION)

        assert excinfo.value.response.status_code == 400
        assert requests_mock.call_count == 1  # A client error isn't retried

    def test_server_error_is_retried(self, wikibase, item_q582, requests_mock):
        add_old_revision(wikibase, 'Q582')
        index = wikibase.mediawiki_index_url
        requests_mock.get(index, [{'status_code': 503, 'text': 'Service Unavailable'}, {'text': wikibase._handle_entity_data}])  # pylint: disable=protected-access

        entity = wbi.item.get('Q582', revision=OLD_REVISION)

        assert entity.labels.get('en').value == 'old value'
        assert requests_mock.call_count == 2

    def test_mediawiki_api_url(self, wikibase, requests_mock):
        other = 'https://other.example.org/w/index.php'
        requests_mock.get(other, json={'entities': {'Q1': {'id': 'Q1', 'type': 'item', 'lastrevid': 7, 'labels': {}, 'descriptions': {}, 'aliases': {}, 'claims': {}}}})

        entity = wbi.item.get('Q1', revision=7, mediawiki_api_url='https://other.example.org/w/api.php', user_agent='MyTool/1.0')

        assert entity.lastrevid == 7
        assert requests_mock.last_request.url.startswith(other + '?')
        assert requests_mock.last_request.headers['User-Agent'].startswith('MyTool/1.0 WikibaseIntegrator/')


class TestWriteLoadedRevision:
    def test_write_is_refused(self, wikibase, item_q582):
        add_old_revision(wikibase, 'Q582')
        entity = wbi.item.get('Q582', revision=OLD_REVISION)

        with pytest.raises(ValueError, match='was loaded at its revision 1000'):
            entity.write(allow_anonymous=True)
        with pytest.raises(ValueError, match='was loaded at its revision 1000'):
            entity.clear(allow_anonymous=True)

        assert wikibase.edits == []

    def test_write_after_reset(self, wikibase, item_q582):
        add_old_revision(wikibase, 'Q582')
        entity = wbi.item.get('Q582', revision=OLD_REVISION)

        entity.loaded_revision = None
        entity.write(allow_anonymous=True)

        assert wikibase.last_edit['data']['labels']['en']['value'] == 'old value'

    def test_new_entity_can_be_written(self, wikibase):
        entity = wbi.item.new()
        entity.labels.set('en', 'new item')

        assert entity.loaded_revision is None
        assert entity.write(allow_anonymous=True).id is not None


class TestDownloadEntityData:
    def test_default_json(self, wikibase, item_q582):
        data = download_entity_data('Q582')

        assert '"Q582"' in data
        assert wikibase.entity_data_requests == [{'title': 'Special:EntityData/Q582.json'}]

    def test_format_flavor_revision(self, wikibase, requests_mock):
        requests_mock.get(wikibase.mediawiki_index_url, text='<https://wikibase.example.org/entity/Q582> a <http://wikiba.se/ontology#Item> .\n')

        data = download_entity_data('Q582', format='nt', flavor='dump', revision=12)

        assert data.startswith('<https://wikibase.example.org/entity/Q582>')
        assert query_string(requests_mock.last_request.url) == {'title': 'Special:EntityData/Q582.nt', 'flavor': 'dump', 'revision': '12'}

    def test_unsupported_format(self, wikibase, item_q582):
        with pytest.raises(requests.HTTPError) as excinfo:
            download_entity_data('Q582', format='php')

        assert excinfo.value.response.status_code == 415

    def test_login_session(self, wikibase, requests_mock):
        requests_mock.get(wikibase.mediawiki_index_url, text='{}')
        session = requests.Session()
        session.headers['X-Session'] = 'login'

        class FakeLogin:
            def get_session(self):
                return session

        download_entity_data('Q582', login=FakeLogin())

        # The request went through the session of the login, with its headers (and its cookies or OAuth signature)
        assert requests_mock.last_request.headers['X-Session'] == 'login'


class TestDownloadEntityTtl:
    def test_flavor_revision(self, wikibase, requests_mock):
        requests_mock.get(f'{wikibase.base_url}/entity/Q582.ttl', text='@prefix wd: <https://wikibase.example.org/entity/> .')

        assert download_entity_ttl('Q582', flavor='simple', revision=12).startswith('@prefix')
        assert query_string(requests_mock.last_request.url) == {'flavor': 'simple', 'revision': '12'}

    def test_entity_method(self, wikibase, requests_mock):
        requests_mock.get(f'{wikibase.base_url}/entity/Q5.ttl', text='@prefix wd: <https://wikibase.example.org/entity/> .')

        wbi.item.new(id='Q5').download_entity_ttl(flavor='dump')

        assert query_string(requests_mock.last_request.url) == {'flavor': 'dump'}
