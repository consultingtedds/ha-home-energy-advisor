# Upgrading

What a release has to tell a household that no commit subject had room for: a
figure that will read differently afterwards, a setting worth checking, a
reading that is correct and looks like a fault.

The release notes are otherwise built from the commit subjects, which is right -
they cannot then disagree with the version about what shipped - but a subject
says what was changed rather than what somebody will see.

## How this file is used

Write the paragraph under a heading spelled exactly `## Unreleased`, in the same
commit as the change it describes. The release prints it under **Upgrading** in
the GitHub release body, which is what Home Assistant shows in the update
notification, and then replaces the heading with the version it cut. So the
sections below are an archive, not a list to tidy up.

The heading carries no version while it waits, deliberately. The version comes
from the commits at release time, and a paragraph filed under a number somebody
predicted is one that disappears the day the prediction is wrong.

Most releases need nothing here. A paragraph a household did not need teaches
them that this section is not worth reading, which is the one thing it cannot
survive.

Releases before 0.7.0 carry their notes on the
[releases page](https://github.com/consultingtedds/ha-home-energy-advisor/releases)
only; this file began with the mechanism that writes it.

**Everything above is for whoever writes here. Nothing but version sections goes
below**, because a pending section ends at the next one - so prose after the last
section is read as part of it and printed to a household.

## Unreleased

**If something charges your battery from the grid while the sun is up, say
so.** The house settings now ask **How your battery charges**, in place of
0.12.0's question about which the panels feed first. The preset has changed: it
now assumes the battery charges mainly from solar the house doesn't need, which
is true of most batteries. So in the minutes when the battery charges while the
house is also using the grid, the battery is now taken to hold solar and the
house to have run on the grid. If a cheap rate, a forced charge or an app such
as Predbat charges your battery from the grid during the day, open
**Reconfigure** and choose **From the grid as well**. If grid charging is turned
off, choose **Only from solar**. Whatever you chose in 0.12.0 is replaced by the
preset, and figures already recorded stay as they are.

**Your battery now has an entry of its own**, under the integration beside your
devices, and its meters, level and capacity have moved there from the house
settings. Nothing about it changes, and its figures carry on. To change it,
open it and choose **Edit battery**.

**If you have two batteries summed with a Group helper, you can enter each one
now.** Several batteries are counted as one, as the Energy Dashboard counts
them, and with two or more each gets its own Battery Losses. If your Energy
Dashboard already lists them, a notice in **Settings** > **Repairs** offers to
take them in place of the summed one. Your figures carry on either way.

**You may see that notice even with one battery.** It appears whenever the
batteries or grid meters in your Energy Dashboard differ from the ones here. If
you chose different meters here on purpose, choose **Keep mine**, and you will
not be asked again until the Energy Dashboard changes.

**If you filled in your battery's capacity, check it is in kWh.** The field now
refuses anything above 200, because no home battery holds that much and the
figure is almost always watt-hours: a 1500 Wh battery is 1.5. A capacity saved
before this release is not checked until you next edit the battery, so if yours
reads in the hundreds or thousands, change it there.

**If your battery stores solar, Battery Losses now shows what it could have
earned.** It read nothing under Could have earned before. The lost energy is
now valued at what export paid when it was stored, and Whole Home's Could have
earned rises by the same amount. Paid does not change. The new figure counts
from this release, so read it over a period that starts after the update.

**Your grid meter now has an entry of its own**, under the integration beside
your devices and batteries, and its import meter, price and export meter have
moved there from the house settings. Nothing about it changes, and your figures
carry on. To change it, open it and choose **Edit grid meter**.

**If your meter has a day and a night rate, you can enter each register now.**
Choose **Add grid meter** and give the second register its own price: a sensor,
or simply the rate. Each register's energy is then priced at its own rate. If
you had added the two together with a helper, replace it with the two
registers. A price can now be typed in as a number, so a fixed rate no longer
needs a Number helper.

**If you have a battery, the self-sufficiency card now counts the solar it
stored.** Its headline used to leave the battery out, because nothing said what
had charged it. Now the solar your battery gave back counts as your own, and
what it was charged with from the grid is shown on its own as **From battery
(grid)**. Each device gains **Energy From Battery (Solar)**, switched off if you
have no battery. It counts from this release: energy already in the battery, and
any period from before the update, count as charged from the grid, so read it
over a period that starts after the update.

## 0.12.0

**If you were told a device "is reporting more energy than the whole house",
check whether its energy sensor only updates every hour or two.** Such a sensor
could be set aside wrongly when one of its steps covered more than an hour,
which moved that device's energy into Untracked for a while. It is now weighed
against the hour each part of the step belongs to. Your totals were never
affected, so there is nothing to reset; the notification now says what it was
judged on and what to check.

**If your inverter charges the battery from solar first and runs the house from
the grid, say so.** There is a new choice on the house settings, below the
battery's meters: open the integration, choose **Reconfigure**, and pick
**Solar charges the battery first**. Until then your battery's stored energy is
priced as if it came from the grid in the minutes it charged while you were
also importing, which makes the devices it later runs look dearer than they
were. Nothing changes for anyone who leaves it alone, and figures already
recorded stay as they are.

## 0.11.0

**If you export, Cost by device leads with what you paid again.** Its main
column had been adding what your generation could have earned to what you
paid, under the heading Cost of use, so it disagreed with every other card. It
now shows **Paid**, matching the summary above it, with a separate **Could have
earned** column beside Saved. No figure has changed; they are just no longer
added together, and the setting that chose between the two readings has gone.

On the generated dashboard the summary and the table now span the full width
of a large screen, with the charts beneath them, and the table uses the room:
the range of what each device could have cost is its own **Paid (min-max)**
column there. On a phone the table is reduced instead - the range goes back
behind a tap on Paid and Could have earned is left out. If you chose a layout
for the range in the card's settings, that choice still holds.

The colour that shows how well each device did - green where it paid little of
what the grid would have charged, red where it paid more - has moved from Would
have paid onto **Paid**, the figure it is judging. Would have paid and Could
have earned are now grey, because neither is money anyone paid.

## 0.10.0

**If your generation comes from more than one sensor, you can now choose them
all.** Open **Settings** > **Devices & services** > **Home Energy Advisor** >
three-dot menu > **Reconfigure**, and pick every generation sensor you have. If
you had chosen only one of several, your generation was being undercounted, and
from then on it is counted in full; figures already recorded stay as they are.
A Group helper you set up to add them together keeps working, so there is
nothing to change if you have one.

**This update changes how the settings are stored, so an older version will not
load them.** Going back to an earlier release after this one means restoring a
backup taken before the update.

## 0.9.0

**If you have a home battery, Battery Losses should now read much lower, and a
day behind.** Two things let it run well above what your battery's own meters
allow: a limit that small mismatches between meters could slip past, and a
battery level that drifts during the day and catches up when it charges. One
household's figure was more than six times what their battery could have lost.

A loss is now published only once your meters have shown it for a whole day, so
today's loss appears tomorrow. **After updating, Battery Losses holds still for a
day** before it moves again. Your whole-home total includes this figure and moves
with it; nothing else changes.

As before, what is already recorded does not correct itself.

**If you export and the cost column reads Cost of use, its rollover now explains
it.** It showed the range for what you paid under a figure that also counts what
your generation could have earned, so the range could sit entirely below the
figure. It now breaks the figure down into those two parts, with the range on
what you paid, and the note under the table says which is which. No figure has
changed.

**Its total is back, too:** the totals row showed a dash under Cost of use. And
if you show the range as its own column, a Forgone export column now sits beside
it, so the two parts of Cost of use can be read across the row.

**The diagnostics download says more about prices and batteries.** It now shows
the import and export rate in force and since when, so you can tell a new rate
has taken without waiting for sunshine. And for a battery, it shows the level and
capacity you set, what the level has read over the last couple of days, and where
the loss measurement stands - which is what we otherwise have to ask you to
export by hand. One field is renamed: `loss_refused_kwh` is now
`meter_disagreement`, with a sentence beside the figure saying what it means.

## 0.8.1

**If you took 0.8.0 and have solar, update again.** The new Forgone Export
figure was reading your *import* price instead of your export price, so it
valued your own generation at what you pay for electricity rather than at what
you are paid for selling it - several times too high for most tariffs, and not
zero even for a household who are paid nothing for export.

Home Assistant stores a grid source two ways and the newer one, which most
installations are on, names the export price differently. We read the wrong key
and fell back onto the import price sitting next to it.

Cost by device adds this figure to the cost column by default, so the overstated
amount was on the headline. **What was already recorded does not correct itself**
- these figures only count upwards - so if the column looks high after taking
0.8.0, that is why, and it stops growing from this release. Reset totals will
clear it if you would rather start the figure again.

If you never installed 0.8.0, nothing here affects you.

## 0.8.0

**If you have solar panels and you export, Cost by device now counts what your
own generation could have earned.** Energy your panels made and your house used
was priced at nothing, which is right about your bank account and wrong about
what it was worth: that unit could have been exported and paid you. The table's
cost column now includes it, and says so by changing its heading - the figure is
no longer what you paid, so it is no longer called Paid.

**Including the sunshine that went through your battery.** Generation stored and
used later carries what it gave up at the moment it was stored - not whatever
export pays when the battery is emptied, which is a rate you were never offered
for that energy.

The rate comes from the export price you already told the Energy Dashboard. There
is nothing new to configure, and if you do not export, or have no panels, nothing
changes for you at all.

**Your sensors have not moved.** Actual Cost is still exactly what you paid, and
every total still adds up the way it did. The new figure is published beside it
as **Forgone Export**, per device, and the card simply chooses to show the two
together. If you would rather see only what you paid, the card's own settings
have a switch for it.

**If you have a home battery, this is the release where 0.7.2's Battery Losses
fix actually reaches you.** That release added a limit based on your battery's
own charge and discharge meters, and it only ever switched itself on for somebody
installing the integration for the first time. On an existing installation it
waited for a starting point it was never given, so it did nothing at all - and
the figure carried on reading as high as before. One household updated, saw no
change, and was right to say so.

It is on now. Energy going into a battery has to come out, stay in, or be lost,
and the figure can no longer exceed what your own meters say is possible.

**Reset totals now clears Battery Losses too.** It was clearing an older version
of that figure and leaving the one on your dashboard untouched, so a household
who reset everything found this single sensor still carrying its whole history.
If you reset before and that sensor stayed where it was, resetting again will
now take it to zero with the rest.

As before, what is already recorded does not correct itself - these figures only
count upwards, so an overstatement stops growing rather than being undone.

## 0.7.2

**If you have a home battery, Battery Losses may stop climbing as quickly.** It
could read far too high. The figure is worked out from what your house meters
cannot account for, less what your battery's level gained - which assumes nothing
about your hardware, but means any disagreement between your meters was being
published as battery loss. One household saw four times what their battery could
physically have lost, because their generation is metered on the far side of
their inverter.

Your battery's own charge and discharge meters put a limit on this: energy going
in has to come out, stay in, or be lost, so the loss can never exceed what went in
less what came out and what the battery gained. That limit now applies.

**Figures already recorded are not rewritten.** Battery Losses is a running total
and cannot go backwards, so the overstatement stops accruing rather than being
corrected - the same reason any published total here is only ever put right going
forwards. If the history matters more to you than keeping the rest, **Reset all
totals** in the integration's menu clears every figure and the history behind it,
and cannot be undone.

Nothing to configure, and no other figure changes.

**The cost range on Cost by device is now narrower, and it has moved.** Two
changes to the same thing.

It was far too wide. A device whose counter reports once an hour could have used
that energy in any of twelve five-minute slices, and the range priced all of it at
the cheapest slice and at the dearest - which included slices where your house
barely used anything at all, so the energy could not have been there. One device
read "paid 0.39, range 0.04 to 0.86". The range now covers only where the energy
can actually have been, which on that device lifts the bottom of the range by
roughly ninety times.

**And it is a rollover on Paid rather than a column.** 0.7.1 made the column
appear for the first time, and a column puts the range at the same weight as the
figure it qualifies, which reads as a second headline. Hover over a Paid figure,
or tap it on a phone, and the range appears beside it. If you preferred the
column, it is still there: edit the card and set **Show the cost range as** to
**Its own column**.

Only the range moved. What you paid is unchanged.

## 0.7.1

**If you turned on per-device cost ranges, the "Paid (min-max)" column will
appear on Cost by device.** It should have been there since the option existed
and never was: the table waited for every row to carry a range, and two rows
never can - the Untracked remainder and the battery both have an exact cost with
no span to be uncertain about, so there is nothing to bracket.

Those two now show a dash in that column, which is what "no range" looks like,
and they still count towards the total's range at their exact cost. No figure has
changed, and if you have not turned the option on you will not see the column.

## 0.7.0

**If any of Home Energy Advisor's figures are switched off, you will now be told.**
A warning appears saying how many, and where the setting that usually causes it
lives. Nothing has broken by the update: those figures were already recording
nothing, and this is the first release able to say so.

It counts only figures the integration asked to be enabled. On a home with no
generation and no battery the by-source and battery figures are disabled on
purpose, because they could only ever read zero, and they are not reported here -
nor is anything you switched off yourself.

**If you have told the Energy Dashboard that one device sits inside another, the
cards now show it.** A circuit you meter appears with the devices on it grouped
underneath, and a row for the part of it nothing else accounts for:

```
Kitchen Circuit                 20 kWh
  Dishwasher                     5 kWh
  Washing Machine                2 kWh
  Kitchen Circuit Untracked     13 kWh
```

The circuit's own row is what its clamp reads - the whole 20 - so it is the figure
on your breaker rather than a number you have to assemble. The rows under it add
up to it, and they are what the rest of your totals are built from, so nothing is
counted twice.

No figure has changed. **If you have not described your wiring in the Energy
Dashboard, nothing changes at all** - and nothing asks you to describe it.

**And a tracked device that has no figures at all is now named.** This is rarer
and stranger: the device is configured, nothing was ever published for it, and
your totals stay right the whole time because its energy counts in Untracked
instead. It has been seen after adding several devices one after another in quick
succession. Removing that device and adding it again fixes it, and the warning
says so. If you meet it, a report with a diagnostics download would be genuinely
useful - the cause is not understood yet, and it has only been seen once.
