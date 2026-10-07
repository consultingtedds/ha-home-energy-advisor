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
