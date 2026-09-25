# Troubleshooting

Most things that look wrong in Home Energy Advisor have an explanation here.
Find the entry that matches what you are seeing.

If yours is not here, see
[Getting help](https://github.com/consultingtedds/ha-home-energy-advisor#troubleshooting-and-help)
in the README.

## Nothing shows up after setting it up

This is expected, and it takes a while.

- **The sensors read zero for about twenty minutes.** Home Energy Advisor only
  counts a stretch of time once it is twenty minutes old, because some device
  sensors report their energy late and it waits for them. While it waits, each
  figure carries a `warming_up` attribute. After that, every figure runs about
  twenty minutes behind the clock, all the time.
- **The dashboard can stay empty for up to about an hour and a half.** Its cards
  read Home Assistant's hourly statistics, which are only written once each hour
  has finished. So the first figures reach the dashboard at the first hour
  boundary after the twenty-minute wait.

If the sensors still read zero after an hour, look for a notification from Home
Energy Advisor, or see the next entry.

## A device stays at zero

- **It may simply not have run.** A heater in summer, or an appliance that has
  been off all day, reads zero, and that is correct.
- **A notification says the device "is tracked by a sensor that has never
  reported".** The sensor you chose has never produced a reading. Until it does,
  that device's share is counted under Untracked instead. Choose a different
  sensor for the device, or check the integration that provides it.
- **A notification says the device "is reporting more energy than the whole
  house".** That sensor is faulty, so Home Energy Advisor has stopped counting it
  to protect your other figures. It starts again by itself once the readings make
  sense. If the device offers another energy sensor, choose that one instead.
- **Its sensor does not say what unit it is in.** Home Energy Advisor counts in
  kWh and Wh. A sensor reporting something else - MWh, or no unit at all - is
  left uncounted rather than guessed at, because a number whose size is unknown
  is worse than no number. Its energy goes to Untracked, so your house total
  stays right. Choose a sensor that reports in kWh or Wh.
- **It is a power-only device and the integration behind it has stopped.** Where
  a device is tracked by a power sensor, Home Energy Advisor builds its energy
  from that sensor. An integration that reports zero watts when it has actually
  lost contact - a cloud device that needs signing in again, say - looks exactly
  like a device that is switched off. Check whether that integration is asking
  you to reauthenticate.

## A device's figures have stopped moving

Every device has a **Last Reading** sensor, under Diagnostic on its device page.
It says when the sensor you chose for that device last reported something Home
Energy Advisor could count, which is the first thing to look at when a device
looks stuck.

If it says **Unavailable**, that sensor has reported nothing for at least half an
hour - it has gone unavailable itself, or it has left Home Assistant altogether.

**An old time on its own is not a fault.** Many sensors report only when their
reading changes, so a device switched off at the wall sends nothing at all, and
this can read hours or days old while nothing whatever is wrong. On a device
like that the time often reflects the last Home Assistant restart rather than
anything the device did. Read it as when that device's figures last moved, and
treat **Unavailable** as the signal that nobody is counting.

- **The cost figures stay exactly as they are.** They are not wrong: they are what
  that device has cost so far, and they are still counted in your house totals and
  your history. Only this one diagnostic entity is withdrawn.
- **Nothing is raised and nothing needs dismissing.** A heater unplugged for the
  summer will sit like this until you plug it back in, and it will not ask you
  anything in the meantime.
- **Your house totals stay right.** While the device is silent, the energy it uses
  - if it is using any - is counted under Untracked instead.
- **A device switched off does not do this.** A plug that is still reporting, at
  zero watts, is reporting. This only happens when the sensor itself has nothing
  to say.

If you watch for unavailable entities with Spook or a similar add-on, these
sensors are how a failed device sensor reaches it: the cost figures never go
unavailable, so they can never be flagged. Watchman only reports on entities you
reference in your own YAML or dashboards, so add the Last Reading sensors to it
if you want them covered there.

To fix it, check the integration that provides the sensor - it may need
reauthenticating, or the device may be off the network.

## Notifications about a unit changing to your currency

For example:

```
The unit of 'Tumble Dryer Cost at Grid Price Daily' changed to 'EUR' which
can't be converted to the previously stored unit, ''.
```

These are harmless and safe to accept. The README's
[Known issues](https://github.com/consultingtedds/ha-home-energy-advisor#known-issues)
explains why they appear and what to choose.

## A notification says the totals no longer add up to your meter

Your device sensors are reporting more energy than your house meter recorded,
and it is not correcting itself. The usual cause is one device sensor that
already includes another, so the same energy is counted twice - a smart plug and
the appliance plugged into it, or a circuit and an appliance on that circuit. A
house-level input measuring the wrong circuit does the same.

The **Unreconciled Energy** figure on the Home Energy Advisor device shows how
much energy is involved.

### If one device really is inside another

This is common on houses metered at the breaker: a clamp on a circuit measures
everything downstream of it, so an appliance you also track separately is inside
both counters.

Tell Home Assistant, and Home Energy Advisor follows it:

1. **Settings** > **Dashboards** > **Energy**
2. Edit the **inner** device - the appliance, not the circuit
3. Set the device that already includes it

Nothing to configure here, and no restart. Your figures start accounting for it
from the next interval; figures already recorded are not rewritten.

Depth does not matter. A breaker containing a sub-circuit containing a plug
containing an appliance works the same way - each one names the device directly
above it.

### What we cannot see

**If you do not record it, nothing detects it.** The notification above only
appears when the double count pushes your tracked devices past what your house
meter read. A circuit and its appliances that together stay *under* your house
total raise nothing at all, because nothing has overflowed - the two figures are
simply too high, and no check we have can tell.

So it is worth setting, even if nothing appears to be wrong.

## A notification says an energy input or the price has been unavailable

Home Energy Advisor carries on, but it cannot measure what it cannot see. Energy
used while an input was down is missing from the totals, and while the price is
unavailable it keeps using the last price it saw. Check the integration that
provides that sensor.

## Setup says a house input must be a total-increasing counter

Choose the cumulative energy meter, measured in kWh - not a power sensor in
watts, and not a sensor whose value goes up and down. The Energy Dashboard's grid
meter is the right kind, and if you have set that up the field is usually filled
in for you.

## My figures are far higher than my meter, or Untracked is enormous

Almost always a source sensor that was **replaced** rather than a fault in your
house. A new sensor starts its counter at a different number, and the jump from
the old one is not energy anybody used.

Home Energy Advisor refuses a reading that implies more power than a house can
draw, and raises a notification naming the input when it does. Figures that were
already wrong before that refusal stay wrong: they are part of the running
totals, and only starting those again clears them.

To clear them, once your sensors have settled: **Settings** > **Devices &
services** > **Home Energy Advisor**, three-dot menu, **Reset all totals**. That
zeroes every figure and clears the history behind them, which is what you want
here, because that history is what holds the wrong numbers. It cannot be undone.

If your figures are wrong and you have not changed a sensor, the diagnostics
download says what every reading was counted as - attach it to an issue.

## A notification says an energy input jumped by more than any house could use

The counter behind that sensor leapt, which is what replacing or rescaling a
sensor looks like from here, so the jump was not counted as energy. Accounting
carries on from the new counter's position and nothing needs putting right.

The limit is 100 kW of continuous draw, which is about 1.4 times the largest
domestic supply. If your site genuinely draws more than that, please open an
issue: the figure is fixed today and can be made adjustable.

## A device paused after its firmware updated

A firmware update can change what a device's counter counts in without changing
what it calls it - the same energy written as a number ten or a thousand times
larger, still labelled kWh. From the outside that is indistinguishable from a
device that has suddenly used a great deal of energy, or, if the number goes
down, from a counter that has restarted.

Home Energy Advisor compares each reading against what your house meter says the
whole house used over the same period. A device cannot use more than the house
it sits in, so a reading that claims to is not counted, and the device pauses.
You may get the "reporting more energy than the whole house" notification while
that lasts.

**It recovers on its own**, usually within the hour, and carries on counting
from wherever the counter now stands. Its energy for that period is not lost
from your house total - it goes to Untracked instead, so the totals still add
up. What is lost is knowing which device used it.

You may also get a notification saying **"An energy input's counter changed the
scale it reports in"**, naming the device and the factor - ten, a hundred or a
thousand. That is the same event, measured: the two sides of the jump differ by
a clean power of ten, which energy never does but a change of unit always does.

### Correcting it, if the counter does not put itself right

**First, work out which way is wrong.** This is the part nobody can do for you,
and it is why the notification does not offer to fix it. A counter that changed
by ten might have been broken by an update, or *repaired* by one - both have
happened here, four days apart, and they look identical from the outside.

Compare the device against itself:

- What is the appliance rated at? A 2 kW heater running half an hour is about
  1 kWh. If its counter moved by 10 kWh, the counter is reading ten times high.
- Does the device publish its own power sensor? Watch it while the appliance
  runs. Power in watts, over the hours it ran, should roughly equal the energy
  its counter gained.
- What did it read before the update? If you know it was sensible then, the
  side that matches it is the right one.

**Only once you are sure**, create a template sensor that scales the reading and
point Home Energy Advisor at that instead. Read this rather than copying it: the
`/ 10` below is an example, and using the wrong operator or the wrong factor
leaves you further out than you started.

```yaml
template:
  - sensor:
      - name: Corrected Plug Energy
        unique_id: corrected_plug_energy
        state: "{{ states('sensor.YOUR_SENSOR') | float(0) / 10 }}"
        unit_of_measurement: kWh
        device_class: energy
        state_class: total_increasing
```

Three things that matter more than they look:

- **`/ 10` is a guess until you have checked.** Multiply instead if the counter
  is reading low, and use the factor the notification named, not this one.
- **Keep all three of `unit_of_measurement`, `device_class` and
  `state_class`.** Without them the sensor will be refused when you choose it.
- **`state_class: total_increasing` must stay**, because the original is a
  counter that only climbs. A corrected sensor that reports a measurement
  instead would be misread as energy on every reading.

Then repoint the device: **Settings > Devices & services > Home Energy Advisor**,
the device, **Configure**. Counting restarts from the new sensor's position;
figures already recorded are not rewritten.

**This fixes our figures only.** Your Energy Dashboard, and anything else using
the original sensor, is still reading the uncorrected one - so repoint those too
if you rely on them.

**Please open an issue either way.** A counter that settles permanently at a new
scale is worth us knowing about: which device, which integration, and which
direction it went.

## Untracked is a large share of the bill

Untracked is everything in the house you have not added as a device, so on most
homes it starts out large. It is what makes the figures add up to what the house
really used, so it is doing its job.

To shrink it, track more devices. **Discover devices to track**, in the
integration's settings menu, lists the energy and power sensors that are not
tracked yet.

## The total does not match my electricity bill

Home Energy Advisor counts what the metered energy cost at the price at the time.
Standing charges and payment for exported energy are not included, so the total
is usually lower than the bill. See
[What Actual Cost does not include](https://github.com/consultingtedds/ha-home-energy-advisor#what-actual-cost-does-not-include).

## My figures disagree with the Energy Dashboard

Over a day they agree. Inside the current hour they cannot, and that is the
twenty-minute wait doing its job: Home Energy Advisor holds an interval open so
that a meter reporting every half hour has its reading placed in the hour it
belongs to, while the Energy Dashboard settles on the hour.

On the cost-over-time chart the interval still being counted is drawn faded,
with a note saying so, so a bar that looks short is one that is still filling
rather than a figure to compare.

## HACS is not offering the update yet

HACS checks repositories it does not carry in its own store - which is all
custom repositories, including this one - about **every two days**. A new release
can therefore exist for a while before your instance is told about it, and
**Check for updates** under Settings > System will not change that, because it
asks HACS rather than GitHub.

To fetch it now: **HACS** > **Home Energy Advisor** > three-dot menu > **Update
information**.

## The dashboard is missing after installing or updating

Restart Home Assistant after installing or updating, then reload the page in your
browser. The dashboard appears under **Add dashboard** once the integration has
loaded.
