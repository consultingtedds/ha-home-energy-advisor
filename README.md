# Home Energy Advisor

A Home Assistant custom integration that explains the **financial impact** of
your energy usage, per device: what it actually cost to run, what it would
have cost without solar, and how much your solar saved.

> **Status: pre-alpha — produces live per-device cost figures.** The foundation
> (skeleton, CI, quality gates), the pure-Python accounting engine (delta
> extraction, interval ledger, battery stored-cost ledger, proportional
> allocation), the configuration flow (house-level setup + per-device
> subentries), the runtime wiring, and the per-device sensors are complete and
> tested. Each tracked device and the "Untracked" remainder now publish four
> figures — Energy Used, Actual Cost, Cost Without Solar, Cost Savings — that
> stay continuous across restarts. Still to come: automatic cycle totals
> (daily/monthly…), energy derivation for power-only devices, diagnostics and
> Repairs, and the Lovelace dashboards. See [docs/PLAN.md](docs/PLAN.md) for the
> delivery plan and [docs/](docs/) for the product vision, charter, PRD and ADRs.

Home Energy Advisor complements Home Assistant's Energy Dashboard: HA explains
energy flows; this integration explains money.

## Development

The test suite requires a Unix-like OS — Linux, macOS, or WSL on Windows —
because Home Assistant imports `fcntl`. Python ≥3.14.2.

```bash
pip install -r requirements_test.txt
pytest
```

## Licence

[MIT](LICENSE)
