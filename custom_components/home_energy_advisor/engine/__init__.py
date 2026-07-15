"""Accounting engine: the financial core, independent of Home Assistant.

Nothing in this package may import ``homeassistant``. The integration layer
adapts Home Assistant state into engine inputs and publishes engine results back
to entities, which keeps the money and energy arithmetic fully unit-testable
without a running instance.
"""

from __future__ import annotations
