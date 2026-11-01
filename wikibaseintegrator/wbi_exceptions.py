import re
from typing import Any

# An entity link of the parameters of an error message, e.g. [[Q42|Q42]] or [[Property:P50|P50]]
ENTITY_LINK_PATTERN = re.compile(r'^\[\[([^|\]]+)\|[^\]]*\]\]$')


class WikibaseIntegratorError(Exception):
    """
    Base class of the exceptions raised by WikibaseIntegrator: catch it to handle any of them, e.g. around a bot run.

    The exceptions that report an invalid value, like EmptyValueError, are also ValueError.
    """


class MWApiError(WikibaseIntegratorError):
    """
    Base class for MediaWiki API error handling
    """
    error_dict: dict[str, Any]
    code: str
    info: str
    messages: list[dict[str, Any]]
    messages_names: list[str]
    response: dict[str, Any] | None

    @property
    def get_conflicting_entity_ids(self) -> list[str]:
        """
        Compute the list of conflicting entities from the error messages: the entities which already have the label and
        description, or the sitelink. A sitelink conflict with an unknown item names no entity.

        :return: A list of conflicting entities or an empty list
        """

        entity_ids = set()
        for message in self._conflict_messages():
            # The entity is the last parameter: [label, language, entity] or [sitelink, entity]
            match = ENTITY_LINK_PATTERN.match(str(message['parameters'][-1]))
            if match:
                # Without the namespace of the page, e.g. Property:P50
                entity_ids.add(match.group(1).rsplit(':', 1)[-1])
        return list(entity_ids)

    @property
    def get_languages(self) -> list[str]:
        """
        Compute a list of language identifiers from the error messages. Indicating the language which triggered the error.
        Only the label and description conflicts have a language, not the sitelink conflicts.

        :return: A list of language identifiers or an empty list
        """

        return list(
            {
                message['parameters'][1] for message in self._conflict_messages()
                if not message['name'].startswith('wikibase-validator-sitelink-conflict') and len(message['parameters']) > 2
            }
        )

    def _conflict_messages(self) -> list[dict[str, Any]]:
        """
        The conflict messages with parameters, e.g. wikibase-validator-label-conflict or wikibase-validator-sitelink-conflict.
        The sitelink conflicts also have the -redirects-supported (when redirect badges are configured) and -unknown variants.
        """
        return [message for message in self.messages if '-conflict' in message.get('name', '') and message.get('parameters')]

    def __init__(self, error_dict: dict[str, Any], response: dict[str, Any] | None = None) -> None:
        """
        :param error_dict: The 'error' part of the API response
        :param response: The whole API response, which can contain more than the error (e.g. the results of the values parsed by wbparsevalue)
        """
        self.error_dict = error_dict
        self.response = response

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

    def __str__(self) -> str:
        return repr(self.info)

    def __repr__(self) -> str:
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


class SaveFailed(MWApiError):
    """
    When the API return a 'failed-save' error
    """

    def __init__(self, error_dict: dict[str, Any], response: dict[str, Any] | None = None) -> None:
        super().__init__(error_dict, response=response)


class NonExistentEntityError(MWApiError):
    """
    When the API return a 'no-such-entity' error: the entity doesn't exist on the Wikibase instance, or its entity type
    doesn't exist there.
    """


class MissingExtensionError(NonExistentEntityError):
    """
    Raised when a request needs a MediaWiki extension the Wikibase instance doesn't provide, e.g. the lexemes of the
    WikibaseLexeme extension. The extension is either not installed or installed without its repository part.

    It inherits from NonExistentEntityError: the requested entity type doesn't exist on the instance.
    """
    extension: str

    def __init__(self, error_dict: dict[str, Any], extension: str, response: dict[str, Any] | None = None) -> None:
        super().__init__(error_dict, response=response)
        self.extension = extension
        self.info = (f"This request needs the {extension} extension, which is not installed or not enabled on the Wikibase instance "
                     f"(https://www.mediawiki.org/wiki/Extension:{extension}). API error: {error_dict.get('info', self.code)}")
        self.args = (self.info,)


class EmptyValueError(WikibaseIntegratorError, ValueError):
    """
    Raised before a write when a claim, a qualifier or a reference has no value, while its snak type states that it has
    one. A datatype created with None or an empty string as value has no value, and the Wikibase instance would reject
    it with a less explicit error.

    Set a value, or use the WikibaseSnakType.NO_VALUE or WikibaseSnakType.UNKNOWN_VALUE snak type.
    """


class UnknownDatatypeError(WikibaseIntegratorError, ValueError):
    """
    Raised when no data type class handles a datatype, like one added to the Wikibase instance by an extension that
    WikibaseIntegrator doesn't support. The message lists the supported datatypes.

    Reading an entity doesn't raise it: a claim of an unknown datatype is kept as a BaseDataType.
    """

    def __init__(self, datatype: str, supported: list[str]) -> None:
        super().__init__(f"Unknown datatype '{datatype}'. Supported datatypes: {', '.join(supported)}")
        self.datatype = datatype
        self.supported = supported


class WCQSAuthenticationError(WikibaseIntegratorError):
    """
    Raised when the Wikimedia Commons Query Service doesn't accept the wcqsOauth cookie given to wbi_login.WCQSAuth:
    it answers with the HTML login page of Wikimedia Commons instead of the query results. The cookie is invalid, or was
    revoked. It is not retried, as retrying with the same cookie cannot succeed.
    """


class MaxRetriesReachedException(WikibaseIntegratorError):
    """
    Raised when a request still fails after all its retries: the last failure is its cause (``__cause__``).
    """


class MissingEntityException(WikibaseIntegratorError):
    """
    Raised when an entity read from the Wikibase instance is missing, e.g. deleted, or when a MediaInfo title is not found.
    """


class SearchError(WikibaseIntegratorError):
    """
    Raised when the wbsearchentities API answers without success.
    """


class LoginError(WikibaseIntegratorError):
    """Raised when there is an issue with the login"""


class AnonymousEditNotAllowedError(WikibaseIntegratorError):
    """
    Raised when an anonymous edit is attempted while it is not explicitly allowed.

    Set ``allow_anonymous=True`` or provide a valid ``login`` object to edit the MediaWiki instance.
    """
