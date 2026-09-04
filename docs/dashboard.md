# The dashboard

Home Energy Advisor ships its own Lovelace cards, and the integration serves
them. There is no HACS resource to add, no file to copy, and no device to name:
every card reads the tracked-device list from the integration, so adding or
removing a device changes what you see without you editing anything.

## Getting it

Three routes, depending on how much of your dashboard you want it to be.

### A dashboard of its own

**Settings → Dashboards → Add dashboard → Home Energy Advisor**, under
*Community dashboards*. The title, icon and url are filled in; press **Create**.

That gives you every card, laid out, over your own devices. It is generated each
time the page loads rather than saved, so a device you add next month appears
without you touching it, and an upgrade brings the current layout with it.

If you later want to change something, use Home Assistant's own **Take control**
(⋮ → Edit dashboard → ⋮ → Take control). That converts the generated layout into
ordinary cards which are then yours: rearrange, delete, mix with anything else.
Nothing is lost and nothing is locked.

### A page inside a dashboard you already have

Add a view, open **⋮ → Edit in YAML** on it, and replace its contents with:

```yaml
strategy:
  type: custom:hea
```

Same page, same generated layout, living inside your dashboard. Home Assistant
has no picker for view strategies yet, which is the only reason this one needs
YAML at all.

### Individual cards, anywhere

Every card is in the card picker under **Home Energy Advisor**. Add whichever
ones you want to any view you already have. Nothing needs configuring: a card
with no options shows every tracked device for whatever period the page's date
picker is set to.

Two of them are worth adding together with the rest:

- an **Energy date selection** card (Home Assistant's own) sets the period every
  HEA card on the page reads. Without one they fall back to the last 30 days.
- **Home Energy Advisor: Filter** narrows the whole page to a room, a floor, a
  label or a single device.

### If your dashboards are YAML files

None of the above applies: a dashboard defined by a file is edited as a file.
Add the cards, or the `strategy:` block above, to that file by hand.
[`dashboard-template.yaml`](dashboard-template.yaml) is a complete working
example to copy from.

## The cards

Every option is optional. Left alone, each card shows all tracked devices for
the page's selected period.

| Card | Shows | Options |
| --- | --- | --- |
| Totals | Paid, Would have paid, Saved for the period | |
| Devices | Per-device table with energy, money and rate | `sort_by`: `actual_cost` (default), `cost_at_grid_price`, `cost_savings`, `energy_used` |
| Device costs (chart) | What each device cost, dearest first | `layout`: `auto` (default), `horizontal`, `vertical` |
| Cost over time | The period's cost as it accumulated | |
| Energy sources | Where the energy came from, per device | `sort_by`: `energy_used` (default), `energy_from_grid`, `energy_from_generation`, `energy_from_battery` |
| Cost distribution | Where the cost went, by floor, room and device | `metric`: `cost` (default), `energy`; `layout`: `auto`, `horizontal`, `vertical` |
| Self-sufficiency | What share ran on your own generation | |
| Filter | Narrows the page by room, floor, label or device | |

Two options every card accepts:

- `title` replaces the card's heading. Leave it out and the card names itself in
  your own language; set it to an empty string for no heading at all.
- `devices` limits the card to a list of device keys. Leave it out for all of
  them, which is almost always what you want, since the page filter is a better
  way to narrow things.

## The sensors behind it

Each tracked device exposes four figures, named after the device:

| Sensor | Unit | Meaning |
| --- | --- | --- |
| `<device> Energy Used` | kWh | Energy the device used |
| `<device> Actual Cost` | currency | What it actually cost, after solar and battery |
| `<device> Cost at Grid Price` | currency | What it would have cost bought off the meter as used |
| `<device> Cost Savings` | currency | The difference between the two |

The cards say **Paid**, **Would have paid** and **Saved** for those three
figures. The sensors keep the longer names because an entity name has to stand
alone in a template where a column heading does not (ADR-0018).

The three `total_increasing` figures also have daily and monthly variants. The
remainder pseudo-device, **Untracked Energy Devices**, carries the same set and
is what makes the shares add up to your whole bill.

Three more sensors name no device: `Unreconciled Energy`, and the whole-home
`Lowest Possible Cost` and `Highest Possible Cost`.

## What the figures do not know

The cards say this where it matters rather than hiding it here, but in one
place:

- **Paid (min-max) is a bound, not an error bar.** A meter that reports every 30
  to 90 minutes used its energy somewhere inside that span, and nothing in the
  data says where, so the cost is knowable only to a range. What is shown is the
  widest those readings allow, which is not a typical error (ADR-0016).
- **Saved can be negative, and that is real.** Battery energy stored when
  electricity was expensive and used when it was cheap costs more than buying at
  the time. It is shown as a loss rather than floored at zero (ADR-0003).
- **Saved is optimistic.** The model does not yet price the export revenue given
  up by using your own generation, so savings are knowingly on the high side.
- **Today's cost catches up rather than going backwards.** Energy your devices
  report before the house meter has accounted for it is held until its real
  price is known, so a figure read mid-hour can sit slightly low and rise later.
  It never falls (ADR-0006).
- **Unreconciled Energy should read zero.** It counts energy published that your
  house meter never accounted for. Any other reading is worth looking at, which
  is exactly what makes zero the useful default (ADR-0015).
- **Untracked Energy Devices is not a device.** It is everything the house used
  that no tracked device claimed, derived per interval rather than measured.
