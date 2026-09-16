"""What a figure was worth, when both of the stores that carry it are gone.

A published figure survives a restart on two stores: the engine's snapshot of
where every counter stood, and the sensor's own restored state. Both are delayed
writes, so a restart landing before either has been flushed finds neither, and
every figure starts again from zero. A household set up minutes earlier loses
the lot, silently.

Home Assistant kept them. The figures were recorded as statistics while they were
published, and those are written on their own schedule and survive what the two
stores did not. So a figure with nothing else to go on asks the recorder what it
last published, and carries on from there.

It reaches a household as the dashboard disagreeing with the device page: the
cards read statistics and the device page reads the sensor, so after such a
restart the cards are right and the sensors are low, for ever (HEA-134, GitHub
#20). Which is also why the recorder is the right place to ask - it held the
correct figure the whole time.

**Short-term statistics first.** Home Assistant compiles those every five
minutes and rolls them up into the hourly ones on the hour, so a household whose
first hour has not finished has only the short-term rows - and that household,
minutes from setting up and restarting, is exactly the one this is for.

Read only, and only ever for this integration's own entity ids.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from homeassistant.components.recorder.const import DOMAIN as RECORDER_DOMAIN
from homeassistant.components.recorder.statistics import (
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.helpers.recorder import get_instance
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

#: How far back to look for a five-minute row. Home Assistant keeps short-term
#: statistics for days; a figure older than this has hourly rows to be found in
#: instead, so the window only has to cover a restart, never a history.
_SHORT_TERM_WINDOW = timedelta(hours=6)


async def async_last_recorded(hass: HomeAssistant, entity_id: str) -> Decimal | None:
    """The last figure Home Assistant recorded for ``entity_id``, if any.

    ``None`` where there is nothing to recover: a first install, a household
    whose recorder excludes these sensors, or an instance running without one at
    all. Each is a household that never had a figure here rather than one that
    lost it, so each starts from zero exactly as before.
    """
    if RECORDER_DOMAIN not in hass.config.components:
        return None
    recorded = await get_instance(hass).async_add_executor_job(
        _last_recorded_state, hass, entity_id
    )
    return _as_decimal(recorded)


def _last_recorded_state(hass: HomeAssistant, entity_id: str) -> float | None:
    """The newest recorded state for ``entity_id``, short-term rows preferred.

    Runs in the recorder's own executor: both calls below are synchronous
    database reads.
    """
    recent = statistics_during_period(
        hass,
        dt_util.utcnow() - _SHORT_TERM_WINDOW,
        None,
        {entity_id},
        "5minute",
        None,
        {"state"},
    )
    rows = recent.get(entity_id) or []
    if not rows:
        hourly = get_last_statistics(
            hass, 1, entity_id, convert_units=True, types={"state"}
        )
        rows = hourly.get(entity_id) or []
    return rows[-1].get("state") if rows else None


def _as_decimal(recorded: float | None) -> Decimal | None:
    if recorded is None:
        return None
    try:
        # Through `str`: the recorder hands back a float, and a Decimal built
        # from one carries the binary representation's error into a figure every
        # later total is added to.
        return Decimal(str(recorded))
    except InvalidOperation:
        return None
