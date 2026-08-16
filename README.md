# Home Energy Advisor

A Home Assistant custom integration that explains the **financial impact** of
your energy usage, per device: what it actually cost to run, what it would
have cost at grid prices, and how much you saved.

> **Status: pre-alpha - the full integration is installable and produces live
> per-device cost figures.** Complete and tested: the foundation (skeleton, CI,
> quality gates); the pure-Python accounting engine (delta extraction, interval
> ledger, battery stored-cost ledger, proportional allocation); the configuration
> flow (house-level setup + per-device subentries) and options flow; the runtime
> wiring; the per-device and "Untracked" sensors (Energy Used, Actual Cost, Cost
> at Grid Price, Cost Savings, continuous across restarts); automatic cycle totals
> (daily/monthly, with weekly/quarterly/yearly opt-in) via native `utility_meter`
> helpers; energy derivation for power-only devices via native Integral helpers; a
> redacted diagnostics download and Repairs for degraded inputs; guided device
> discovery (scan for untracked energy/power sensors and choose which to add -
> manual add via "Add device" remains); a disclosure layer that states what the
> figures cannot know - how far your own meters disagree with each other, and the
> cost range a device's reporting interval permits, because a counter that reports
> once an hour used that energy *somewhere* inside the hour and nothing in the data
> says where; and English + Spanish translations. Costs are published only once
> they are known rather than estimated and corrected, so "spent so far today" is a
> figure that catches up rather than one that goes backwards. It
> now runs live on a real instance. Still to come: the Lovelace dashboards, a full
> install README, wider dogfooding, and the HACS release (historical backfill is
> deferred - see [docs/PLAN.md](docs/PLAN.md) → Epic 7). See
> [docs/PLAN.md](docs/PLAN.md) for the delivery plan and [docs/](docs/) for the
> product vision, charter, PRD and ADRs.

Home Energy Advisor complements Home Assistant's Energy Dashboard: HA explains
energy flows; this integration explains money.

## Development

The test suite requires a Unix-like OS - Linux, macOS, or WSL on Windows -
because Home Assistant imports `fcntl`. Python ≥3.14.2.

```bash
pip install -r requirements_test.txt
pytest
```

Contributions are welcome - see [CONTRIBUTING.md](CONTRIBUTING.md) for the
commit conventions, why some tests skip, and what the `HEA-nn` references in the
history mean (short version: a private tracker you do not need access to).

## Licence

[MIT](LICENSE)
