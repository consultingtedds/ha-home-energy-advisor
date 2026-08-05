"""Ask the recorder whether a source has ever produced a reading (HEA-69).

A source that is silent right now proves nothing: a seasonal device is
legitimately off for months, and HEA-24 settled that device silence must never
raise a Repair. The question worth asking is narrower — has this sensor *ever*
reported? — and the recorder is the only thing that can answer it for a source
that was already configured before the integration started watching.

The probe runs at most once per source, only for one that has stayed silent past
the grace period, so on a healthy household it never runs at all.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.components.recorder import history
from homeassistant.components.recorder.const import DOMAIN as RECORDER_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.recorder import get_instance
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant, State

_NO_READING = {STATE_UNAVAILABLE, STATE_UNKNOWN}


async def async_has_ever_reported(hass: HomeAssistant, entity_id: str) -> bool | None:
    """Whether the recorder holds any real reading for ``entity_id``.

    Returns ``None`` when the question cannot be answered — there is no recorder,
    so there is no history to consult. That is not the same as ``False``, and the
    caller must treat it as "say nothing": accusing a working sensor of being
    dead costs more than staying quiet about a dead one.
    """
    if RECORDER_DOMAIN not in hass.config.components:
        return None
    recorder = get_instance(hass)
    start = dt_util.utcnow() - timedelta(days=recorder.keep_days)
    changes = await recorder.async_add_executor_job(
        _recorded_states, hass, start, entity_id
    )
    return any(
        state.state not in _NO_READING
        for states in changes.values()
        for state in states
    )


def _recorded_states(
    hass: HomeAssistant, start: datetime, entity_id: str
) -> dict[str, list[State]]:
    """Every recorded state for the sensor since ``start``, run on the DB thread.

    ``include_start_time_state`` matters more than it looks: a counter belonging
    to a device that has been switched off for months holds its last total rather
    than changing, so the state at the window's start is often the only evidence
    that the sensor ever worked.
    """
    return history.state_changes_during_period(
        hass,
        start,
        entity_id=entity_id,
        no_attributes=True,
        include_start_time_state=True,
    )
