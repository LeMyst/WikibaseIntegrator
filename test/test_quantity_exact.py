import pytest

from wikibaseintegrator.datatypes import Quantity
from wikibaseintegrator.datatypes.quantity import format_amount


class TestBoundsOfZero:
    def test_upper_bound_of_zero(self):
        value = Quantity(amount=-5, upper_bound=0, lower_bound=-10, prop_nr='P1').mainsnak.datavalue['value']

        # The upper bound used to be dropped, leaving a single bound that Wikibase rejects
        assert value == {'amount': '-5', 'unit': '1', 'upperBound': '+0', 'lowerBound': '-10'}

    def test_lower_bound_of_zero(self):
        value = Quantity(amount=0.5, upper_bound=1, lower_bound=0, prop_nr='P1').mainsnak.datavalue['value']

        assert value == {'amount': '+0.5', 'unit': '1', 'upperBound': '+1', 'lowerBound': '+0'}

    def test_amount_of_zero_with_bounds_of_zero(self):
        value = Quantity(amount=0, upper_bound='0', lower_bound=0.0, prop_nr='P1').mainsnak.datavalue['value']

        assert value == {'amount': '+0', 'unit': '1', 'upperBound': '+0', 'lowerBound': '+0'}

    def test_bound_of_zero_is_checked(self):
        with pytest.raises(ValueError, match='Upper bound too small'):
            Quantity(amount=5, upper_bound=0, lower_bound=-1, prop_nr='P1')

    def test_no_bound(self):
        assert Quantity(amount=5, upper_bound=None, lower_bound='', prop_nr='P1').mainsnak.datavalue['value'] == {'amount': '+5', 'unit': '1'}
        assert Quantity(amount=5, upper_bound='', lower_bound=None, prop_nr='P1').mainsnak.datavalue['value'] == {'amount': '+5', 'unit': '1'}


class TestExactAmounts:
    @pytest.mark.parametrize('amount,expected', [
        # Large integers used to be rounded by float()
        ('12345678901234567890', '+12345678901234567890'),
        ('602214076000000000000000', '+602214076000000000000000'),
        (12345678901234567890, '+12345678901234567890'),
        ('-98765432109876543210', '-98765432109876543210'),
        # Digits beyond the precision of a float
        ('1.00000000000000001', '+1.00000000000000001'),
        # Exponents, which Wikibase rejects, are written as digits
        (0.00001, '+0.00001'),
        ('1.5e-5', '+0.000015'),
        ('6.02214076E23', '+602214076000000000000000'),
        (1e16, '+10000000000000000'),
        # Unchanged formatting
        (42, '+42'), (-42, '-42'), (42.0, '+42'), (42.5, '+42.5'), ('42', '+42'), ('+42', '+42'), ('42.50', '+42.50'),
        (0, '+0'), ('-0.0', '+0'), ('007', '+7'), (0.1, '+0.1'), (-0.5, '-0.5'),
    ])
    def test_format_amount(self, amount, expected):
        assert format_amount(amount) == expected

    @pytest.mark.parametrize('amount', ['nan', float('nan'), float('inf'), '-inf', 'Infinity', '', ' 0.5', '0.5 ', '1,5', 'abc', '1e', True])
    def test_not_a_finite_number(self, amount):
        with pytest.raises(ValueError):
            format_amount(amount)

    @pytest.mark.parametrize('amount', ['nan', float('inf'), ' 0.5', '0.5 '])
    def test_quantity_refuses_what_wikibase_refuses(self, amount):
        with pytest.raises(ValueError, match='must parse as integers or float'):
            Quantity(amount=amount, prop_nr='P1')

    def test_sparql_value_of_a_large_amount(self):
        quantity = Quantity(prop_nr='P1').from_json({'mainsnak': {'snaktype': 'value', 'property': 'P1', 'datatype': 'quantity',
                                                                  'datavalue': {'value': {'amount': '+12345678901234567890', 'unit': '1'}, 'type': 'quantity'}},
                                                     'type': 'statement', 'id': 'Q1$abc', 'rank': 'normal'})

        # The key compared by fastrun with the value of the Query Service
        assert quantity.get_sparql_value() == '"+12345678901234567890"^^xsd:decimal'

    def test_bounds_compared_without_float_rounding(self):
        # As floats, the three values are equal
        value = Quantity(amount='10000000000000000001', upper_bound='10000000000000000002', lower_bound='10000000000000000000', prop_nr='P1').mainsnak.datavalue['value']
        assert value['upperBound'] == '+10000000000000000002'

        with pytest.raises(ValueError, match='Upper bound too small'):
            Quantity(amount='10000000000000000001', upper_bound='10000000000000000000', prop_nr='P1')
