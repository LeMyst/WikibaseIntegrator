import copy


class JsonParser:
    references = []
    qualifiers = []
    final = False
    current_type = None

    def __init__(self, f):
        self.f = f

    def __call__(self, *args):
        self.json_representation = args[1]

        if self.final:
            self.final = False
            return self.f(cls=self.current_type, jsn=self.json_representation)

        if 'mainsnak' in self.json_representation:
            self.mainsnak = None
            self.references = []
            self.qualifiers = []
            json_representation = self.json_representation

            if 'references' in json_representation:
                self.references.extend([[] for _ in json_representation['references']])
                for count, ref_block in enumerate(json_representation['references']):
                    ref_hash = ''
                    if 'hash' in ref_block:
                        ref_hash = ref_block['hash']
                    for prop in ref_block['snaks-order']:
                        jsn = ref_block['snaks'][prop]

                        for prop_ref in jsn:
                            ref_class = self.get_class_representation(prop_ref)
                            ref_class.is_reference = True
                            ref_class.snak_type = prop_ref['snaktype']
                            ref_class.set_hash(ref_hash)

                            self.references[count].append(copy.deepcopy(ref_class))

                            # print(self.references)
            if 'qualifiers' in json_representation:
                for prop in json_representation['qualifiers-order']:
                    for qual in json_representation['qualifiers'][prop]:
                        qual_hash = ''
                        if 'hash' in qual:
                            qual_hash = qual['hash']

                        qual_class = self.get_class_representation(qual)
                        qual_class.is_qualifier = True
                        qual_class.snak_type = qual['snaktype']
                        qual_class.set_hash(qual_hash)
                        self.qualifiers.append(qual_class)

                        # print(self.qualifiers)
            mainsnak = self.get_class_representation(json_representation['mainsnak'])
            mainsnak.set_references(self.references)
            mainsnak.set_qualifiers(self.qualifiers)
            if 'id' in json_representation:
                mainsnak.set_id(json_representation['id'])
            if 'rank' in json_representation:
                mainsnak.set_rank(json_representation['rank'])
            mainsnak.snak_type = json_representation['mainsnak']['snaktype']

            return mainsnak

        elif 'property' in self.json_representation:
            return self.get_class_representation(jsn=self.json_representation)

    def get_class_representation(self, jsn):
        from wikibaseintegrator.wbi_datatype import BaseDataType
        data_type = [x for x in BaseDataType.__subclasses__() if x.DTYPE == jsn['datatype']][0]
        self.final = True
        self.current_type = data_type
        return data_type.from_json(jsn)
