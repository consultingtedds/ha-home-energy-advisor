# The demo instance - running it, and retaking the screenshots (2026-09-10)

> A throwaway Home Assistant in a container, holding an invented household, used
> to photograph the product for the README and to break things somewhere that is
> not the maintainer's home. Built under HEA-80. Everything lives in `demo/`.

## Why it exists

The README needs pictures, and a picture of the reference instance is the one
artefact this project must never publish: a week of per-device energy is an
occupancy trace whatever the labels say. Doctoring real screenshots fails twice
over - every leak has to be caught by hand, and the numbers themselves are the
disclosure. So nothing real is ever in frame. The house comes from
`demo/house.mjs` and the figures from `demo/seed.mjs`, and neither has ever met
the reference instance.

It has turned out to be worth more than the screenshots. Three defects were
found here in a day: HEA-117, HEA-119, and the real cause of HEA-114, whose
previous fix had shipped green against an inference that the demo disproved in
minutes.

## What it cannot answer

The integration here is real, installed and configured through its own flow. The
**figures are not**. `demo/seed.mjs` writes the week straight into long-term
statistics with `recorder/import_statistics`, so nothing in a screenshot was
computed by the accounting engine, and no statistic here was compiled from
recorded states.

That is the right trade for pictures and for anything the frontend does, and it
rules out a whole class of question. Nothing that depends on Home Assistant
compiling statistics *from states* can be asked here - reset behaviour and the
long-term statistics compiler among them (HEA-122 was settled against the real
recorder in `tests/test_reset_statistics.py` instead). Running `reset_totals` on
the demo would clear the seeded week and prove nothing.

What this instance tests well is setup, discovery, the flows, the dashboard and
the cards.

## Running it

Docker Desktop has to be running. Nothing else is needed.

```bash
node demo/run-e2e.mjs      # build a house, assert against it, repeat in Spanish
node demo/reset.mjs        # throw the house away, leave a container ready
node demo/setup.mjs        # onboard, build the rooms, fill in the Energy Dashboard
node demo/screenshots.mjs  # drive the flows, seed a week, photograph everything
node demo/cold-load.mjs 10 # load the dashboard cold N times and count what renders
```

`screenshots.mjs` seeds as it goes, so it is the only one to run for a rebuild.
`seed.mjs` can be run alone when only the figures need changing.

## The end-to-end checks

```bash
node demo/run-e2e.mjs         # both languages, then tear the container down
node demo/run-e2e.mjs es      # one language
node demo/run-e2e.mjs --keep  # leave the instance up to poke at
node demo/e2e.mjs             # assert against a house that already exists
```

Ten minutes or so, because each language rebuilds the instance from nothing.

**They are not one of the five gates**, deliberately. They are slow, they need
Docker, and Home Assistant ships monthly and will break them periodically. Run
them when the answer matters: before a release, or after a change to the cards.

### What they are for

The card unit tests mount a card against a double written from the same belief
as the card, and a double like that cannot disagree - HEA-84 shipped broken past
501 green tests. These load the real dashboard in a real Home Assistant and read
what a household would see, which makes them the only tests here that can tell
us we were wrong.

They assert **figures, never pixels**. A screenshot comparison rots against
Home Assistant's own UI within a release or two, and then everyone learns to
ignore it.

### Why the Spanish pass rebuilds the instance

Home Assistant builds an entity id from the entity's translated name, and it
does that once, when the entity is first registered. The registry then keeps
that id forever, keyed by `unique_id`: deleting the integration and adding it
back restores the ids it had before. So a Spanish pass cannot be a language
switch on a running house - it needs an instance whose language was Spanish
before the integration created anything.

Only the *instance* language changes. The account stays English, so the browser
automation keeps meeting English menus while the ids underneath it are Spanish.

That pass earned its cost immediately. It found that every card rendered "No
devices are being tracked yet." on a Spanish instance with nine tracked devices,
because `hea-devices.js` hardcoded the English entity id of the sensor that
lists them - five lines below its own comment explaining why that is wrong
(HEA-126). Three places in this harness had the same bug.

### What they still do not cover

Everything in *What it cannot answer* above, and one thing more: anything a
chart draws to a canvas is invisible to them. The figures they read are the ones
in the DOM, which is roughly what a screen reader would reach.

## Retaking the screenshots

Most of them can be retaken at any time: run `node demo/screenshots.mjs` and the
images in `docs/images/` are overwritten.

**The two setup shots are the exception.** They photograph a flow that exists
only on an instance that has not been through it, so retaking those means
`reset.mjs` and `setup.mjs` first. The script notices an instance that is
already configured and says so rather than failing.

## Changing what the pictures show

`demo/house.mjs` is the whole household in one file: floors, rooms, devices,
which sensor each device reads, how much energy it uses, when it runs, and how
its energy splits across grid, generation and battery. Change it and rerun.

A device's saving comes mostly from **when** it runs, not from its shares.
Generation is worth something only while the sun is up, so a midday timer saves
most of its cost and the same device run at eight in the evening saves nearly
none. That is what produces the range on the cards, and it is the argument the
README makes in words.

## Things that cost an afternoon to learn

- **Names go through the privacy checker before they land.** `scripts/privacy_check.py`
  refuses a room word joined to another word, and compares against the local
  list of the maintainer's real hardware. Two device names picked for the demo
  came back as real ones. Images are the one thing the checker cannot read, so
  the guarantee comes from everything in them being generated from a file that
  it can.
- **Statistics imports do not replace what is already there.** A reseed over an
  existing week silently keeps the old figures and reports success. The seed
  clears each statistic before writing it.
- **Home Assistant rejects an imported statistic dated in the future**, and
  rejects the whole series rather than the offending rows. So the week stops at
  the current hour, which leaves today part-finished, and the screenshot run
  steps the picker back to the last complete day rather than photographing a
  morning where half the house has not run yet.
- **The recorder commits on its own schedule.** Counting the imports that were
  made says nothing about what is readable; the seed reads every statistic back
  before reporting success.
- **A device added through the flow is not immediately in the devices sensor.**
  Its entities exist within a second, but the sensor that names them catches up
  on its own refresh, which has taken over half a minute.
- **Entity pickers are search dialogs, not combo boxes.** They focus their own
  search box, so the value is typed rather than filled, and a click that misses
  lands on the dialog's scroll lock. Forcing a click past Playwright's
  actionability check puts it through at coordinates the results overlay is
  covering: the row highlights, the dialog closes, and the field stays empty.
- **Verify, never count.** Every step that reports success checks the thing it
  claims to have done. The first version of the device loop cheerfully reported
  adding nine devices having created none.
