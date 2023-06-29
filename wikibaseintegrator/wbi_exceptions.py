from typing import Any, Dict, List


class MWApiError(Exception):
    """
    Base class for MediaWiki API error handling
    """
    error_dict: Dict[str, Any]
    code: str
    info: str
    messages: List[Dict[str, Any]]
    messages_names: List[str]

    @property
    def get_conflicting_entity_ids(self) -> List[str]:
        """
        Compute the list of conflicting entities from the error messages.

        :return: A list of conflicting entities or an empty list
        """

        return list(
            {
                message['parameters'][2].split('|')[0][2:].replace("Property:", "") for message in self.messages
                if message['name'].endswith('-conflict')
            }
        )

    @property
    def get_languages(self) -> List[str]:
        """
        Compute a list of language identifiers from the error messages. Indicating the language which triggered the error.

        :return: A list of language identifiers or an empty list
        """

        return list(
            {
                message['parameters'][1] for message in self.messages
                if message['name'].endswith('-conflict')
            }
        )

    def __init__(self, error_dict: Dict[str, Any]):
        self.error_dict = error_dict

        if 'info' in self.error_dict:
            self.info = self.error_dict['info']
        else:
            self.info = 'MWApiError'
        super().__init__(self.info)
        self.code = self.error_dict['code'] if 'code' in error_dict else 'wikibaseintegrator-missing-error-code'
        if 'messages' in self.error_dict:
            self.messages = self.error_dict['messages']
            self.messages_names = [message['name'] for message in self.error_dict['messages']]
        else:
            self.messages = [{'html': {'*': 'WikibaseIntegrator: missing message from HTML return.'}, 'name': 'wikibaseintegrator-missing-messages'}]
            self.messages_names = ['wikibaseintegrator-missing-messages']

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


class TtlDownloadError(BaseException):
    pass


class EntitySchemaDownloadError(BaseException):
    pass
