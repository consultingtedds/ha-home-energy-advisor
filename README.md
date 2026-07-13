# Home Energy Advisor

A Home Assistant custom integration that explains the **financial impact** of
your energy usage, per device: what it actually cost to run, what it would
have cost without solar, and how much your solar saved.

> **Status: pre-alpha — not yet installable.** The integration skeleton and CI
> pipeline are in place; the accounting engine and Home Assistant integration
> layer are not built yet. See [docs/PLAN.md](docs/PLAN.md) for the delivery
> plan and [docs/](docs/) for the product vision, charter, PRD and ADRs.

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
