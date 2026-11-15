from typing import Any

from wikibaseintegrator.wbi_enums import ActionIfExists


def _add_with_action(items: list, item: Any, action_if_exists: ActionIfExists) -> None:
    """
    Add an item to a list following action_if_exists, with the semantics of Claims.add().

    The snaks and the references are the same when they are equal (==). The forms and the senses, which have an id and
    can be marked for removal:

    - are the same when they have the same id, or, when one of them has no id yet, the same content;
    - replace the one with the same id (APPEND_OR_REPLACE, REPLACE_ALL, MERGE_REFS_OR_APPEND), or cancel the removal of
      the one with the same content;
    - are marked for removal instead of being deleted from the list (REPLACE_ALL), and don't count as existing for KEEP
      when they are marked for removal.

    :param items: The list of the items, e.g. the qualifiers of a property or the senses of a lexeme.
    :param item: The item to add.
    :param action_if_exists: What to do when the item already exists.
    """
    if not isinstance(action_if_exists, ActionIfExists):
        raise ValueError(f'{action_if_exists} is not a valid action_if_exists value. Use the enum ActionIfExists')

    if action_if_exists == ActionIfExists.FORCE_APPEND:
        items.append(item)
        return

    sub_entity = hasattr(item, 'removed')

    def same(existing: Any) -> bool:
        if sub_entity and existing.id is not None and item.id is not None:
            return bool(existing.id == item.id)
        return bool(existing == item)

    if action_if_exists == ActionIfExists.KEEP and any(not getattr(existing, 'removed', False) for existing in items):
        return

    if action_if_exists == ActionIfExists.REPLACE_ALL:
        if sub_entity:
            for existing in items:
                if not same(existing):
                    existing.removed = True
        else:
            items[:] = [existing for existing in items if same(existing)]

    # Like Claims._find_equal(): the one that isn't marked for removal first
    matches = [position for position, existing in enumerate(items) if same(existing)]
    match = next((position for position in matches if not getattr(items[position], 'removed', False)), matches[0] if matches else None)
    if match is None:
        items.append(item)
    elif sub_entity and item.id is not None:
        items[match] = item
    elif sub_entity:
        items[match].removed = False


class BaseModel:
    def __repr__(self) -> str:
        """A mixin implementing a simple __repr__."""
        return "<{klass} @{id:x} {attrs}>".format(  # pylint: disable=consider-using-f-string
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join(f"{k}={v!r}" for k, v in self.__dict__.items()),
        )
