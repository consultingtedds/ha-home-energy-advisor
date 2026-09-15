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

## The dashboard is missing after installing or updating

Restart Home Assistant after installing or updating, then reload the page in your
browser. The dashboard appears under **Add dashboard** once the integration has
loaded.
