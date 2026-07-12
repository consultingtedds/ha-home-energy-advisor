# Documentation Standards — Home Energy Advisor

Documentation lives as close to the code as possible. No external wikis.
Adapted from the retirement platform's `DOCUMENTATION_STANDARDS.md`.

## Principles

- A reader should understand the project without leaving the repository
- Document the *why*, not the *what* — code explains what it does; docs
  explain constraints, trade-offs, and intent
- Documentation is part of the definition of done
- Code explains implementation; tests describe behaviour; docs capture intent
  (see `PRODUCT_CHARTER.md`)

## README.md

Must cover: purpose (one paragraph), install (HACS custom repo), configuration
walkthrough, entities table, a plain-language explanation of the accounting
model **including its known limitations** (export opportunity cost deferred,
interval approximation), and how to run tests. Transparency about the model is
a PRD constraint, not marketing copy to soften.

## Architecture Decision Records

Every significant technical decision gets an ADR in `docs/adr/`.

- Template: `docs/adr/TEMPLATE.md`
- Naming: `NNNN-short-title-in-kebab-case.md`
- **Append-only** — never edit an accepted ADR; supersede with a new one
  (`Status: Supersedes ADR-NNNN`)
- Statuses: `Proposed` → `Accepted` | `Deprecated` | `Superseded by ADR-NNNN`
- ADR-0000 (origin) is the permanent context for all future decisions

## Docstrings — Python

- Every module has a one-paragraph module docstring: its responsibility and
  place in the design
- Public functions and classes use **Google-style docstrings** — but only when
  they say something the signature and name don't. Restating the name is
  noise, not documentation
- A good docstring answers: what does this do that the name doesn't say? What
  are the constraints/preconditions? What related types matter?
- Private helpers (`_prefixed`) need docstrings only when non-obvious
- Default to no inline comments; add one line only when the *why* is
  non-obvious (a workaround, a hidden constraint, an invariant)
- Never reference tickets or PRs in code — that history belongs in git

```python
# BAD — restates the signature
def allocate(bucket: SourceBucket, draws: Mapping[DeviceId, Decimal]) -> Allocation:
    """Allocates the bucket across draws."""

# GOOD — documents the invariant and the edge behaviour
def allocate(bucket: SourceBucket, draws: Mapping[DeviceId, Decimal]) -> Allocation:
    """Splits one source bucket across devices in proportion to their draw.

    The returned allocations always sum exactly to ``bucket.energy_kwh`` —
    rounding residue is assigned to the largest share so the aggregate
    invariant holds at Decimal precision. Zero total draw allocates the
    entire bucket to the remainder.
    """
```

## Test documentation

Test names + Given/When/Then comments are the documentation — no docstrings on
individual tests. Test modules get a module docstring only when infrastructure
or fixtures need explanation.

## Diagrams — Mermaid

Use Mermaid (GitHub renders natively). Add a diagram when prose would take
more than two sentences and the diagram is clearer — never to fill space.
A heading immediately above every diagram; real entity IDs and names, not
"Sensor A". Keep diagrams narrow enough to avoid horizontal scrolling.

Likely homes: allocation data flow (README/ADR-0002), config-flow state
machine (ADR for the flow design), interval-ledger sequence (ADR-0002).

## Notes

Working notes and investigation write-ups go in `docs/notes/` with a date and
a provenance header (what instance, what window, what method) — see
`AIRCON_COST_EXPLORATION.md` and `DEVICE_SENSOR_SURVEY.md` as the pattern.
