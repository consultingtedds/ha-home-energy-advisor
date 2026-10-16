# ADR-0029: Every card leads with what was paid

## Status

Accepted

Revises ADR-0026 decision 4, which let the device table fold forgone export
into its cost column by default. The rest of ADR-0026 stands: forgone export is
still published beside the cost and never inside it.

## Context

The product answers one question first: what did that device cost you. The
answer is the money that left the household's bank account for it - `Actual
Cost`, shown on the cards as **Paid** (HEA-88 settled the vocabulary: Paid,
Would have paid, Saved, on every card).

ADR-0026 added a second, honest reading beside it: what the generation a device
used could have earned had it been exported instead. It kept that figure out of
the sensors, and then let the device table add it into its cost column, renamed
Cost of use, **by default** for every household that exports. A card option
therefore decided what the main column of the main card meant.

On the reference dashboard after 0.10.0 the cost summary read Paid €0.78 and the
table directly beneath it totalled €1.24. Within a row the figures stopped adding
up as they read: Untracked showed Cost of use €1.09 and Would have paid €2.28,
€1.19 apart, beside a Saved of €1.52, because Saved and the rate per kWh were
still worked out from Paid. HEA-214 and HEA-201 had added a breakdown and a
column to explain the merged figure rather than separating it again.

## Decision

**The headline money figure on every card is what the household paid, and it
always means that.** Four things follow.

1. **Everything else is an add-on.** Would have paid, Saved, the cost range,
   forgone export, and anything HEA-97 adds (export earnings, standing charges)
   is shown beside Paid under its own name, and never folded into it.
2. **Configuration may add or remove an add-on; it never changes what a column
   means.** A heading names one figure, whatever the card's settings.
3. **A household-level figure is never a device column.** Export earnings and a
   standing charge belong to no device, so they can only appear where the whole
   household is shown.
4. **Forgone export is a column of its own on the device table, headed "Could
   have earned"**, shown wherever any row forwent something. The heading is
   chosen so it cannot be read as money received for exporting, which is a
   different figure (HEA-97). The sensor keeps its name, Forgone Export, because
   entity names are permanent (ADR-0003).

### Rejected

- **Keeping the merged column as an opt-in.** It is the same problem made
  optional: a household who chose it would see a table that disagrees with every
  other card, and nothing on the page would say why.
- **A page-wide switch in the footer that folds the add-on in.** It would make
  every card agree, but Paid would mean something else while it was ticked, a
  figure read later or quoted in an issue would carry no record of which reading
  it was, and the footer's job is which devices are shown, not which money.
  Considered by the maintainer and rejected as more confusing than distinct
  columns.

## Consequences

- The table's Paid total equals the summary's Paid, and on every row Would have
  paid less Paid is the Saved beside it.
- A household who left the table on its default sees Paid return as the headline
  and the forgone figure move into its own column. One who had chosen to show
  only what they paid sees the new column appear; the stored option is ignored.
- The table needs more room, so the generated dashboard gives it the full width
  of a large screen.
- Every future figure is checked against this before it reaches a card: if it is
  not what was paid, it is an add-on with a name of its own.
