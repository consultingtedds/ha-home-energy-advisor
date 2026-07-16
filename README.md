# Home Energy Advisor

A Home Assistant custom integration that explains the **financial impact** of
your energy usage, per device: what it actually cost to run, what it would
have cost without solar, and how much your solar saved.

> **Status: pre-alpha — not yet installable.** The foundation (skeleton, CI,
> quality gates) and the pure-Python accounting engine (delta extraction,
> interval ledger, battery stored-cost ledger, proportional allocation) are
> complete and fully unit-tested. The Home Assistant integration layer — config
> flow, entities, dashboards — is not built yet, so there is nothing to install.
> See [docs/PLAN.md](docs/PLAN.md) for the delivery plan and [docs/](docs/) for
> the product vision, charter, PRD and ADRs.

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
