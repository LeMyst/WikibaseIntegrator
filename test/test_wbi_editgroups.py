"""
Tests for wbi_editgroups: the batch link EditGroups expects at the end of the edit summary of a custom bot.
"""
import re

import pytest

from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.datatypes import String
from wikibaseintegrator.wbi_editgroups import MAX_SUMMARY_LENGTH, EditGroup

# The format required by EditGroups for custom bots (https://www.wikidata.org/wiki/Wikidata:Edit_groups/Adding_a_tool)
CUSTOM_BOT_LINK = re.compile(r'\(\[\[:toolforge:editgroups/b/CB/([0-9a-f]{4,32})\|details\]\]\)$')


class TestBatchId:
    def test_random_batch_id(self):
        editgroup = EditGroup()
        assert re.fullmatch(r'[0-9a-f]{12}', editgroup.batch_id)
        assert EditGroup().batch_id != editgroup.batch_id

    @pytest.mark.parametrize('batch_id', ['89ead4fe', 'abcd', '0' * 32])
    def test_custom_batch_id(self, batch_id):
        assert EditGroup(batch_id).batch_id == batch_id

    @pytest.mark.parametrize('batch_id', ['abc', '0' * 33, '89EAD4FE', 'not-hex', ''])
    def test_invalid_batch_id(self, batch_id):
        with pytest.raises(ValueError):
            EditGroup(batch_id)

    def test_str_and_url(self):
        editgroup = EditGroup('89ead4fe')
        assert str(editgroup) == '89ead4fe'
        assert editgroup.url == 'https://editgroups.toolforge.org/b/CB/89ead4fe/'


class TestSummary:
    def test_summary(self):
        assert EditGroup('89ead4fe').summary('Add the population') == 'Add the population ([[:toolforge:editgroups/b/CB/89ead4fe|details]])'

    @pytest.mark.parametrize('summary', [None, ''])
    def test_empty_summary(self, summary):
        assert EditGroup('89ead4fe').summary(summary) == '([[:toolforge:editgroups/b/CB/89ead4fe|details]])'

    def test_link_matches_the_editgroups_format(self):
        editgroup = EditGroup()
        match = CUSTOM_BOT_LINK.search(editgroup.summary('Some edit'))
        assert match is not None
        assert match.group(1) == editgroup.batch_id

    def test_long_summary_keeps_the_link(self):
        editgroup = EditGroup()
        summary = editgroup.summary('x' * 1000)

        assert len(summary) <= MAX_SUMMARY_LENGTH
        assert summary.endswith(f'… {editgroup.link}')
        assert CUSTOM_BOT_LINK.search(summary)

    def test_summary_at_the_limit_is_kept(self):
        editgroup = EditGroup()
        text = 'x' * (MAX_SUMMARY_LENGTH - len(editgroup.link) - 1)
        assert editgroup.summary(text) == f'{text} {editgroup.link}'


def test_write_with_editgroup(wikibase):
    editgroup = EditGroup('89ead4fe')
    item = WikibaseIntegrator().item.new()
    item.claims.add(String(value='abc', prop_nr='P1'))

    item.write(summary=editgroup.summary('Add a string'), allow_anonymous=True)

    assert wikibase.last_edit['params']['summary'] == 'Add a string ([[:toolforge:editgroups/b/CB/89ead4fe|details]])'
