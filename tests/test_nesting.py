from __future__ import annotations

from custom_components.home_energy_advisor.nesting import (
    Nesting,
    SkippedPair,
    SkipReason,
    nesting_of,
)

# What we read for each tracked device, by subentry id: a breaker's clamp and
# the aircon on it.
_READ = {"sensor.circuit_energy": "circuit", "sensor.aircon_energy": "aircon"}
# The aircon's Home Assistant device also carries a yearly counter.
_ON_OUR_DEVICES = {"sensor.aircon_energy_year": "aircon"}


def _prefs(*pairs: tuple[str, str | None]) -> dict[str, object]:
    return {
        "device_consumption": [
            {"stat_consumption": entity}
            | ({"included_in_stat": inside} if inside is not None else {})
            for entity, inside in pairs
        ]
    }


def _nesting(*pairs: tuple[str, str | None]) -> Nesting:
    return nesting_of(_prefs(*pairs), _READ, _ON_OUR_DEVICES.get)


def test_a_pair_named_by_the_sensors_we_read_is_applied() -> None:
    # Given / When - the aircon inside the circuit, by the sensors we read
    nesting = _nesting(
        ("sensor.circuit_energy", None),
        ("sensor.aircon_energy", "sensor.circuit_energy"),
    )

    # Then - the aircon nets against the circuit, and nothing is skipped
    assert nesting == Nesting({"aircon": "circuit"}, (), {})


def test_a_pair_named_by_another_sensor_of_our_device_is_skipped_and_named() -> None:
    # Given / When - the Energy Dashboard names the aircon by its yearly counter
    nesting = _nesting(("sensor.aircon_energy_year", "sensor.circuit_energy"))

    # Then - nothing nets, since the two counters we read were never declared
    # to contain each other, but the aircon is named with the sensor the
    # Energy Dashboard used, because the household can fix this one
    assert nesting == Nesting(
        {},
        (
            SkippedPair(
                "sensor.aircon_energy_year",
                "sensor.circuit_energy",
                SkipReason.ANOTHER_SENSOR,
                "aircon",
                "circuit",
            ),
        ),
        {"aircon": "sensor.aircon_energy_year"},
    )


def test_a_device_we_do_not_track_is_skipped_without_a_repair() -> None:
    # Given / When - a plug we do not track inside the circuit, and the aircon
    # inside a sub-board we do not track
    nesting = _nesting(
        ("sensor.plug_energy", "sensor.circuit_energy"),
        ("sensor.aircon_energy", "sensor.sub_board_energy"),
    )

    # Then - each is skipped for its own reason, and neither is a double count
    # within our figures, so neither is put to the household
    assert [(pair.reason, pair.device, pair.parent) for pair in nesting.skipped] == [
        (SkipReason.NOT_TRACKED, None, "circuit"),
        (SkipReason.PARENT_NOT_TRACKED, "aircon", None),
    ]
    assert nesting.applied == {}
    assert nesting.misread == {}


def test_a_device_declared_inside_itself_is_skipped() -> None:
    # Given / When - the aircon's yearly counter inside its lifetime one, which
    # is one device inside itself
    nesting = _nesting(("sensor.aircon_energy_year", "sensor.aircon_energy"))

    # Then - netting it would erase the aircon, so it is not applied, and there
    # is no sensor to repoint
    assert [pair.reason for pair in nesting.skipped] == [SkipReason.INSIDE_ITSELF]
    assert nesting.applied == {}
    assert nesting.misread == {}


def test_no_energy_dashboard_nests_nothing() -> None:
    # Given / When - no preferences at all, as before the Energy Dashboard is set up
    nesting = nesting_of(None, _READ, _ON_OUR_DEVICES.get)

    # Then - an empty nesting, not an error
    assert nesting == Nesting()
