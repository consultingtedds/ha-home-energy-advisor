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
already includes another, so the same energy is counted twice - for example, a
smart plug and the appliance plugged into it both tracked. A house-level input
measuring the wrong circuit does the same.

The **Unreconciled Energy** figure on the Home Energy Advisor device shows how
much energy is involved.

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

If a device pauses and *stays* paused for longer than a day, its counter has
probably settled at the new scale and is now permanently out of step with the
rest of your setup. Please open an issue - that case is not yet handled
automatically, and it is worth us knowing which device and which integration.

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
