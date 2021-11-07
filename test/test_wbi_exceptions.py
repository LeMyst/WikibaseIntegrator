from wikibaseintegrator.wbi_exceptions import (CorePropIntegrityException, IDMissingError, ManualInterventionReqException, MergeError, MWApiError,
                                               NonUniqueLabelDescriptionPairError, SearchError)


def test_mwapierror():
    assert str(MWApiError('MWApiError')) == 'MWApiError'


def test_nonuniquelabeldescriptionpairerror():
    json_data = {
        'error': {
            'messages': [
                {
                    'parameters': [
                        'first',
                        'second',
                        'third|test'
                    ]
                }
            ]
        }
    }

    assert NonUniqueLabelDescriptionPairError(json_data).get_language() == 'second'
    assert NonUniqueLabelDescriptionPairError(json_data).get_conflicting_item_qid() == 'ird'


def test_idmissingerror():
    assert str(IDMissingError('IDMissingError')) == 'IDMissingError'


def test_searcherror():
    assert str(SearchError('SearchError')) == 'SearchError'


def test_manualinterventionreqexception():
    assert ManualInterventionReqException(value='value', property_string='property_string',
                                          item_list='item_list').value == 'value Property: property_string, items affected: item_list'


def test_corepropintegrityexception():
    assert str(CorePropIntegrityException('CorePropIntegrityException')) == 'CorePropIntegrityException'


def test_mergeerror():
    assert str(MergeError('MergeError')) == 'MergeError'
