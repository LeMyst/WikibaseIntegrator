"""
The paths of the entities (BaseEntity, Item, Property, Lexeme, MediaInfo) and of the package __init__ not covered by the
other tests: the type checks of the setters, the optional parts of the entity JSON, the props of wbgetentities, the
Lexeme fields of fields_to_update, limit_claims, the property-path base filter of write_required(), the TTL download,
and the version and lazy attributes of the package.
"""
import importlib.metadata
from copy import deepcopy
from pathlib import Path

import pytest

import wikibaseintegrator
from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.datatypes import BaseDataType, Item, String
from wikibaseintegrator.entities import ItemEntity, LexemeEntity, MediaInfoEntity, PropertyEntity
from wikibaseintegrator.models import Claims
from wikibaseintegrator.wbi_enums import EntityField, WikibaseDatatype
from wikibaseintegrator.wbi_exceptions import MissingEntityException

from .conftest import load_fixture, uri

wbi = WikibaseIntegrator()

PACKAGE_ROOT = Path(wikibaseintegrator.__file__).parent.parent


@pytest.fixture
def lexeme_l5(wikibase):
    return wikibase.add_fixture('lexeme_L5')


class TestBaseEntity:
    def test_api_must_be_a_wikibaseintegrator(self):
        with pytest.raises(TypeError):
            ItemEntity(api='not a WikibaseIntegrator')

    def test_claims_setter(self):
        item = wbi.item.new()
        claim = String(value='foo', prop_nr='P1')

        # A single Claim is wrapped in a Claims object
        item.claims = claim
        assert isinstance(item.claims, Claims)
        assert item.claims.get('P1') == [claim]

        with pytest.raises(TypeError):
            item.claims = 'not a claim'

        with pytest.raises(TypeError):
            item.claims = [claim]

    def test_terms_setters_type_checks(self):
        item = wbi.item.new()
        with pytest.raises(TypeError):
            item.descriptions = {}
        with pytest.raises(TypeError):
            item.aliases = {}

    def test_missing_entity(self, wikibase):
        # wbgetentities answers {'id': ..., 'missing': ''} for a deleted entity
        wikibase.deleted_entities.add('Q1')
        with pytest.raises(MissingEntityException):
            wbi.item.get('Q1')

        with pytest.raises(MissingEntityException):
            ItemEntity().from_json({'id': 'Q1', 'missing': ''})

    def test_get_props_string(self, wikibase, item_q582):
        item = wbi.item.get('Q582', props='labels')
        # 'info' is added: from_json() needs the lastrevid, the type and the id
        assert wikibase.last_request['props'] == 'labels|info'
        assert item.id == 'Q582'
        assert item.labels.get('fr') is not None
        assert len(item.claims) == 0

    def test_get_props_list_with_info(self, wikibase, item_q582):
        item = wbi.item.get('Q582', props=['labels', 'info'])
        assert wikibase.last_request['props'] == 'labels|info'
        assert item.lastrevid is not None
        assert len(item.claims) == 0

    def test_get_props_list_without_info(self, wikibase, item_q582):
        wbi.item.get('Q582', props=['claims', 'labels'])
        assert wikibase.last_request['props'] == 'claims|labels|info'

    def test_fields_to_update_drops_the_lexeme_fields(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')
        assert lexeme.lexical_category  # sent by get_json(), so dropped below

        lexeme.write(allow_anonymous=True, fields_to_update=EntityField.CLAIMS)

        sent = wikibase.last_edit['data']
        assert 'claims' in sent
        for field in ('lemmas', 'lexicalCategory', 'language', 'forms', 'senses'):
            assert field not in sent

    def test_fields_to_update_keeps_the_lexeme_fields(self, wikibase, lexeme_l5):
        lexeme = wbi.lexeme.get('L5')

        lexeme.write(allow_anonymous=True, fields_to_update=[EntityField.LEMMAS, EntityField.LEXICAL_CATEGORY, EntityField.LANGUAGE, EntityField.FORMS, EntityField.SENSES])

        sent = wikibase.last_edit['data']
        assert 'claims' not in sent
        assert sent['lexicalCategory'] == 'Q1084'
        assert sent['language'] == 'Q1321'
        for field in ('lemmas', 'forms', 'senses'):
            assert field in sent

    def test_limit_claims_single_value(self, wikibase, item_q582):
        item = wbi.item.get('Q582')

        item.write(allow_anonymous=True, limit_claims='P443')

        assert set(wikibase.last_edit['data']['claims']) == {'P443'}

    def test_limit_claims_property_numbers_and_unknown_properties(self, wikibase, item_q582):
        item = wbi.item.get('Q582')

        # An int is a property number, a property without claims is skipped
        item.write(allow_anonymous=True, limit_claims=[31, 'P999999'])

        assert set(wikibase.last_edit['data']['claims']) == {'P31'}

    def test_get_entity_url(self, wikibase):
        assert wbi.item.new(id='Q5').get_entity_url() == f'{wikibase.base_url}/entity/Q5'
        assert wbi.item.new(id='Q5').get_entity_url('https://other.example.org') == 'https://other.example.org/entity/Q5'

        with pytest.raises(ValueError):
            wbi.item.new().get_entity_url()

    def test_download_entity_ttl(self, wikibase, requests_mock):
        ttl = '<https://wikibase.example.org/entity/Q5> a <http://wikiba.se/ontology#Item> .\n'
        requests_mock.get(f'{wikibase.base_url}/entity/Q5.ttl', text=ttl)

        assert wbi.item.new(id='Q5').download_entity_ttl() == ttl
        assert requests_mock.last_request.url == f'{wikibase.base_url}/entity/Q5.ttl'

    def test_download_entity_ttl_without_id(self, wikibase):
        with pytest.raises(ValueError):
            wbi.item.new().download_entity_ttl()


class TestWriteRequiredPropertyPath:
    """write_required() with a base filter in the property-path form: [anchor property, path property]."""

    @staticmethod
    def _serve(wikibase, value: str) -> None:
        """Serve one P31 statement of Q99 holding the value."""

        def dispatch(query: str) -> list[dict]:
            if 'wbi_fastrun.load_statements' in query and '/prop/P31> ?sid' in query:
                return [{
                    'entity': uri(f'{wikibase.base_url}/entity/Q99'),
                    'sid': uri(f'{wikibase.base_url}/entity/statement/Q99-P31-0'),
                    'value': uri(f'{wikibase.base_url}/entity/{value}'),
                    'property_type': uri('http://wikiba.se/ontology#WikibaseItem'),
                }]
            return []

        wikibase.sparql_bindings = dispatch

    @staticmethod
    def _item() -> ItemEntity:
        item = wbi.item.new(id='Q99')
        item.claims.add(Item(value='Q5', prop_nr='P31'))
        item.claims.add(String(value='not in the base filter', prop_nr='P1'))
        return item

    def test_not_required(self, wikibase):
        self._serve(wikibase, 'Q5')

        assert self._item().write_required(base_filter=[[Item(value='Q5', prop_nr='P31'), BaseDataType(prop_nr='P279')]]) is False

        # The anchor property of the path is the property checked, the path is in the query
        query = next(query for query in wikibase.sparql_queries if 'wbi_fastrun.load_statements' in query)
        assert '/prop/P31> ?sid' in query
        assert f'<{wikibase.base_url}/prop/direct/P31>/<{wikibase.base_url}/prop/direct/P279>*' in query
        assert all('/prop/P1> ?sid' not in query for query in wikibase.sparql_queries)

    def test_required(self, wikibase):
        self._serve(wikibase, 'Q6')

        assert self._item().write_required(base_filter=[[Item(value='Q5', prop_nr='P31'), BaseDataType(prop_nr='P279')]]) is True


class TestItem:
    def test_invalid_ids(self):
        item = wbi.item.new()
        with pytest.raises(ValueError):
            item.id = 'P5'
        with pytest.raises(ValueError):
            item.id = 5.0

    def test_sitelinks_type_check(self):
        with pytest.raises(TypeError):
            wbi.item.new().sitelinks = {}


class TestProperty:
    def test_invalid_ids(self):
        prop = wbi.property.new()
        with pytest.raises(ValueError):
            prop.id = 'Q5'
        with pytest.raises(ValueError):
            prop.id = 5.0

    def test_get_json_without_datatype(self):
        prop = PropertyEntity()
        assert prop.datatype is None
        assert 'datatype' not in prop.get_json()

    def test_from_json_without_datatype_keeps_it(self):
        prop = PropertyEntity(datatype=WikibaseDatatype.STRING).from_json({'id': 'P5', 'type': 'property', 'lastrevid': 1})
        assert prop.id == 'P5'
        assert prop.datatype == WikibaseDatatype.STRING


class TestLexeme:
    def test_invalid_ids(self):
        lexeme = wbi.lexeme.new()
        with pytest.raises(ValueError):
            lexeme.id = 'Q5'
        with pytest.raises(ValueError):
            lexeme.id = 5.0

    def test_type_checks(self):
        lexeme = wbi.lexeme.new()
        for attribute in ('lemmas', 'forms', 'senses'):
            with pytest.raises(TypeError):
                setattr(lexeme, attribute, {})

    def test_language(self):
        lexeme = wbi.lexeme.new()

        lexeme.language = 5
        assert lexeme.language == 'Q5'

        lexeme.language = None
        assert lexeme.language is None

        with pytest.raises(ValueError):
            lexeme.language = 'L5'
        with pytest.raises(ValueError):
            lexeme.language = 5.0

    def test_minimal_json(self, preserve_config):
        # Without the optional parts, the default values are kept
        lexeme = LexemeEntity().from_json({'id': 'L1', 'type': 'lexeme', 'lastrevid': 1})
        assert lexeme.id == 'L1'
        assert lexeme.lexical_category is None
        assert lexeme.language == preserve_config['DEFAULT_LEXEME_LANGUAGE']
        assert len(lexeme.lemmas) == 0
        assert len(lexeme.forms.forms) == 0
        assert len(lexeme.senses.senses) == 0

        json_data = lexeme.get_json()
        assert 'lexicalCategory' not in json_data
        assert json_data['language'] == preserve_config['DEFAULT_LEXEME_LANGUAGE']


class TestMediaInfo:
    def test_invalid_ids(self):
        mediainfo = wbi.mediainfo.new()
        with pytest.raises(ValueError):
            mediainfo.id = 'Q5'
        with pytest.raises(ValueError):
            mediainfo.id = 5.0

    def test_get_by_title_more_than_one_entity(self, wikibase):
        first = wikibase.add_fixture('mediainfo_M75908279')
        second = deepcopy(load_fixture('mediainfo_M75908279'))
        second.update({'id': 'M1', 'pageid': 1, 'title': 'File:Other.jpg'})
        wikibase.add_entity(second)

        with pytest.raises(ValueError, match='More than one element'):
            wbi.mediainfo.get_by_title([first['title'], second['title']])

        assert wikibase.last_request['titles'] == f"{first['title']}|File:Other.jpg"

    def test_get_json_statements_without_datatype(self):
        mediainfo = MediaInfoEntity()
        mediainfo.claims.add(String(value='foo', prop_nr='P180'))
        assert mediainfo.claims.get('P180')[0].mainsnak.get_json()['datatype'] == 'string'

        json_data = mediainfo.get_json()
        assert 'claims' not in json_data
        assert 'datatype' not in json_data['statements']['P180'][0]['mainsnak']


class TestPackage:
    def test_dir(self):
        names = dir(wikibaseintegrator)
        assert names == sorted(names)
        assert {'WikibaseIntegrator', '__version__', 'entities', 'wbi_helpers', '_version'} <= set(names)

    def test_lazy_attributes(self):
        assert wikibaseintegrator.WikibaseIntegrator is WikibaseIntegrator
        assert wikibaseintegrator.wbi_enums.EntityField is EntityField

        with pytest.raises(AttributeError, match='no_such_attribute'):
            getattr(wikibaseintegrator, 'no_such_attribute')


class TestVersion:
    """_version() of a package without metadata, imported from a checkout: the version is read from its pyproject.toml."""

    @pytest.fixture
    def without_metadata(self, monkeypatch):
        def version(name):
            raise importlib.metadata.PackageNotFoundError(name)

        monkeypatch.setattr(importlib.metadata, 'version', version)

    @pytest.fixture
    def checkout(self, monkeypatch, tmp_path, without_metadata):
        """A checkout in tmp_path: return the path of its pyproject.toml, to write."""
        monkeypatch.setattr(wikibaseintegrator, '__file__', str(tmp_path / 'wikibaseintegrator' / '__init__.py'))
        return tmp_path / 'pyproject.toml'

    def test_from_the_metadata(self, monkeypatch):
        monkeypatch.setattr(importlib.metadata, 'version', lambda name: '9.8.7' if name == 'wikibaseintegrator' else None)
        assert wikibaseintegrator._version() == '9.8.7'

    def test_this_checkout(self, without_metadata):
        with open(PACKAGE_ROOT / 'pyproject.toml', 'rb') as file:
            content = file.read().decode('utf-8')
        expected = next(line.split('"')[1] for line in content.splitlines() if line.startswith('version = '))

        assert wikibaseintegrator._version() == expected

    def test_poetry_version(self, checkout):
        checkout.write_text('[tool.poetry]\nname = "wikibaseintegrator"\nversion = "1.2.3"\n', encoding='utf-8')
        assert wikibaseintegrator._version() == '1.2.3'

    def test_project_version(self, checkout):
        checkout.write_text('[project]\nname = "wikibaseintegrator"\nversion = "2.0.0"\n\n[tool.poetry]\nversion = "1.2.3"\n', encoding='utf-8')
        assert wikibaseintegrator._version() == '2.0.0'

    def test_no_version(self, checkout):
        checkout.write_text('[project]\nname = "wikibaseintegrator"\ndynamic = ["version"]\n', encoding='utf-8')
        assert wikibaseintegrator._version() == '0.0.0+unknown'

    def test_invalid_toml(self, checkout):
        checkout.write_text('[project\nversion = \n', encoding='utf-8')
        assert wikibaseintegrator._version() == '0.0.0+unknown'

    def test_no_pyproject(self, checkout):
        assert not checkout.exists()
        assert wikibaseintegrator._version() == '0.0.0+unknown'
