from typing import Any, Dict, List


class MWApiError(Exception):
    """
    Base class for MediaWiki API error handling
    """
    code: str
    info: Dict[str, Any]
    messages: List[Dict[str, Any]]
    messages_names: List[str]

    @property
    def get_conflicting_entity_id(self) -> str:
        """
        :return: Returns the QID string of the item which has the same label and description as the one which should
         be set.
        """
        entity_string = ""
        if self.code == 'failed-save':
            # The first message has empty list as parameters so we use the second
            entity_string = self.messages[1]['parameters'][2]
        else:
            # TODO test with DataValueCorrupt wikibase response
            if not self.info == "Data value corrupt:":
                try:
                    entity_string = self.messages[0]['parameters'][2]
                except IndexError:
                    raise IndexError(self.error_dict)
            else:
                raise DataValueCorrupt(self.error_dict)
        if entity_string:
            return entity_string.split('|')[0][2:].replace("Property:", "")

    @property
    def get_language(self) -> str:
        """
        :return: Returns a 2 letter language string, indicating the language which triggered the error
        """
        if self.code == 'failed-save':
            # The first message has empty list as parameters so we use the second
            return self.messages[1]['parameters'][1]
        else:
            if not self.info == "Data value corrupt:":
                if "not found" in self.info:
                    raise NonExistentEntityError(self.error_dict)
                try:
                    return self.messages[0]['parameters'][1]
                except IndexError:
                    raise IndexError(self.error_dict)
            else:
                raise DataValueCorrupt(self.error_dict)

    def __init__(self, error_dict: Dict[str, Any]):
        super().__init__(error_dict['info'])
        self.code = error_dict['code']
        self.error_dict = error_dict
        self.info = error_dict['info']
        self.messages = error_dict['messages']
        self.messages_names = [message['name'] for message in error_dict['messages']]

    def __str__(self):
        return repr(self.info)

    def __repr__(self):
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(  # pylint: disable=consider-using-f-string
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs="\r\n\t ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )


class ModificationFailed(MWApiError):
    """
    When the API return a 'modification-failed' error
    """
    pass


class SaveFailed(MWApiError):
    """
    When the API return a 'save-failed' error
    """

    def __init__(self, error_dict: Dict[str, Any]):
        super().__init__(error_dict)


class NonExistentEntityError(MWApiError):
    pass


class MaxRetriesReachedException(Exception):
    pass


class MissingEntityException(Exception):
    pass


class SearchError(Exception):
    pass


class DataValueCorrupt(Exception):
    pass
