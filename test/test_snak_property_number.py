import pytest

from wikibaseintegrator import wbi_fastrun
from wikibaseintegrator.datatypes import BaseDataType, String
from wikibaseintegrator.models import Claims, Qualifiers, Reference, Snak, Snaks


class TestWithoutPropertyNumber:
    """A snak is stored under its property: without a property number it used to be stored under None, and sent as such."""

    def test_snaks(self):
        with pytest.raises(ValueError, match='no property number'):
            Snaks().add(Snak())

    def test_reference(self):
        with pytest.raises(ValueError, match='no property number'):
            Reference().add(String(value='x'))

    def test_qualifiers(self):
        with pytest.raises(ValueError, match='no property number'):
            Qualifiers().add(String(value='x'))

    def test_removing_a_qualifier_without_property_does_nothing(self):
        qualifiers = Qualifiers().add(String(prop_nr='P1', value='x'))

        qualifiers.remove(String(value='x'))

        assert list(qualifiers.get_json()) == ['P1']

    def test_claims_are_checked_before_any_change(self):
        claims = Claims().add(String(prop_nr='P1', value='x'))

        with pytest.raises(ValueError, match='no property number'):
            claims.add([String(prop_nr='P2', value='y'), String(value='z')])

        # Nothing was added
        assert list(claims.get_json()) == ['P1']

    def test_fastrun(self, wikibase):
        frc = wbi_fastrun.FastRunContainer(base_data_type=BaseDataType, base_filter=[BaseDataType(prop_nr='P1')])

        with pytest.raises(ValueError, match='no property number'):
            frc.load_statements(claims=String(value='x'))


def test_datavalue_is_always_a_dict():
    snak = Snak(property_number='P1')
    snak.datavalue = None

    # No value is an empty dict, like a snak created without one
    assert snak.datavalue == {}
    assert Snak(property_number='P1').datavalue == {}
