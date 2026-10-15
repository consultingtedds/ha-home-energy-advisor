"""Reading the house-level inputs out of a config entry's data."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


def house_entities(data: Mapping[str, Any], key: str) -> tuple[str, ...]:
    """The meters configured under one house input, none if it is unset.

    Generation holds a list - Home Assistant's Energy Dashboard takes any number
    of solar sources, so a household with two arrays has two meters (HEA-219) -
    and every other input holds one entity id. Reading both through here means
    no caller has to know which is which.
    """
    value = data.get(key)
    if not value:
        return ()
    return (value,) if isinstance(value, str) else tuple(value)
