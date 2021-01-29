from wikibaseintegrator import wbi_core


def test_item_engine():
    wbi_core.ItemEngine()
    wbi_core.ItemEngine(data=None)


def test_search_only():
    item = wbi_core.ItemEngine(item_id="Q2", search_only=True)

    assert item.get_label('en') == "Earth"
    descr = item.get_description('en')
    assert len(descr) > 3

    assert "Terra" in item.get_aliases()
    assert "planet" in item.get_description()

    assert item.get_label("es") == "Tierra"


def test_label():
    item = wbi_core.ItemEngine(item_id="Q2")

    assert item.get_label('en') == "Earth"
    descr = item.get_description('en')
    assert len(descr) > 3

    assert "Terra" in item.get_aliases()
    assert "planet" in item.get_description()

    assert item.get_label("es") == "Tierra"

    # set_description on already existing description
    item.set_description(descr)
    item.set_description("fghjkl")
    item.set_description("fghjkltest", lang='en', if_exists='KEEP')
    assert item.json_representation['descriptions']['en'] == {'language': 'en', 'value': 'fghjkl'}
    # set_description on empty desription
    item.set_description("")
    item.set_description("zaehjgreytret", lang='en', if_exists='KEEP')
    assert item.json_representation['descriptions']['en'] == {'language': 'en', 'value': 'zaehjgreytret'}

    item.set_label("Earth")
    item.set_label("xfgfdsg")
    item.set_label("xfgfdsgtest", lang='en', if_exists='KEEP')
    assert item.json_representation['labels']['en'] == {'language': 'en', 'value': 'xfgfdsg'}
    item.set_aliases(["fake alias"], if_exists='APPEND')
    assert {'language': 'en', 'value': 'fake alias'} in item.json_representation['aliases']['en']

    item.get_label("ak")
    item.get_description("ak")
    item.get_aliases("ak")
    item.set_label("label", lang='ak')
    item.set_description("d", lang='ak')
    item.set_aliases(["a"], lang='ak', if_exists='APPEND')
    assert item.get_aliases('ak') == ['a']
    item.set_aliases("b", lang='ak')
    assert item.get_aliases('ak') == ['a', 'b']
    item.set_aliases("b", lang='ak', if_exists='REPLACE')
    assert item.get_aliases('ak') == ['b']
    item.set_aliases(["c"], lang='ak', if_exists='REPLACE')
    assert item.get_aliases('ak') == ['c']
