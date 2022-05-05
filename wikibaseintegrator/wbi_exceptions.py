class MWApiError(Exception):
    """
    Base class for MediaWiki API error handling
    """


class NonUniqueLabelDescriptionPairError(MWApiError):
    def __init__(self, error_message):
        """
        This class handles errors returned from the API due to an attempt to create an item which has the same label and description as an existing item in a certain language.

        :param error_message: An API error message containing 'wikibase-validator-label-with-description-conflict'
         as the message name.
        :type error_message: A Python json representation dictionary of the error message
        :return:
        """
        super().__init__(error_message)

        self.error_msg = error_message

    def get_language(self) -> str:
        """
        :return: Returns a 2 letter language string, indicating the language which triggered the error
        """
        return self.error_msg['error']['messages'][0]['parameters'][1]

    def get_conflicting_item_qid(self) -> str:
        """
        :return: Returns the QID string of the item which has the same label and description as the one which should be set.
        """
        qid_string = self.error_msg['error']['messages'][0]['parameters'][2]

        return qid_string.split('|')[0][2:]

    def __str__(self):
        return repr(self.error_msg)


class IDMissingError(Exception):
    pass


class SearchError(Exception):
    pass


class ManualInterventionReqException(Exception):
    def __init__(self, value, property_string, item_list):
        super().__init__()

        self.value = value + f' Property: {property_string}, items affected: {item_list}'

    def __str__(self):
        return repr(self.value)


class CorePropIntegrityException(Exception):
    pass


class MergeError(Exception):
    pass


class NonExistentEntityError(Exception):
    pass
