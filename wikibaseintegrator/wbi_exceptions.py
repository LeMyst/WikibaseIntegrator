class MWApiError(Exception):
    """
    Base class for Mediawiki API error handling

    :param error_message: The JSON returned by the Mediawiki API containing the error message
    :type error_message: dict
    """

    def __init__(self, error_message):
        self.error_msg = error_message

    def __str__(self):
        return repr(self.error_msg)


class NonUniqueLabelDescriptionPairError(MWApiError):
    """
    This class handles errors returned from the API due to an attempt to create an item which has the same label and description as an existing item in a certain language.

    :param value: An API error message containing 'wikibase-validator-label-with-description-conflict' as the message name.
    :type value: dict
    """

    def __init__(self, value):
        self.value = value

    def get_language(self):
        """
        :return: Returns a 2 letter language string, indicating the language which triggered the error
        """
        return self.value['error']['messages'][0]['parameters'][1]

    def get_conflicting_item_qid(self):
        """
        :return: Returns the QID string of the item which has the same label and description as the one which should be set.
        """
        qid_string = self.value['error']['messages'][0]['parameters'][2]

        return qid_string.split('|')[0][2:]

    def __str__(self):
        return repr(self.value)


class IDMissingError(ValueError):
    """Raised when trying to create an item with a given ID

    :param error_message: The error message to pass with the exception
    :type error_message: str
    """

    def __init__(self, error_message):
        self.error_message = error_message

    def __str__(self):
        return repr(self.error_message)


class SearchError(MWApiError):
    """Raised when there is an error during a search request

    :param error_message: The error message to pass with the exception
    :type error_message: str
    """

    def __init__(self, error_message):
        self.error_message = error_message

    def __str__(self):
        return repr(self.error_message)


class ManualInterventionReqException(Exception):
    def __init__(self, value, property_string, item_list):
        self.value = value + ' Property: {}, items affected: {}'.format(property_string, item_list)

    def __str__(self):
        return repr(self.value)


class CorePropIntegrityException(Exception):
    """
    :param error_message: The error message to pass with the exception
    :type error_message: str
    """

    def __init__(self, error_message):
        self.error_message = error_message

    def __str__(self):
        return repr(self.error_message)


class SearchOnlyError(Exception):
    """Raised when the ItemEngine is in search_only mode"""
    pass
