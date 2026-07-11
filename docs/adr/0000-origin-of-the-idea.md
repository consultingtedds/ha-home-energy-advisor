# ADR-0000: Origin of the Idea

## Status

Accepted

## Purpose

This document records the origin of Home Energy Advisor and the reasoning that led to the creation of the project.

Unlike other ADRs, this is not an architectural decision. It exists to preserve the original problem statement and the thought process that led to the product.

Future architectural decisions should always be considered in the context of the problem described here.

---

# The Original Problem

The project originated from a real Home Assistant installation with rooftop solar generation.

Home Assistant's Energy Dashboard already provides excellent visibility into:

* Energy imported from the grid
* Solar generation
* Household consumption
* Exported energy

In addition, a number of individual devices report their own electricity consumption through smart plugs and other energy monitoring devices.

Despite having access to all of this information, answering relatively simple financial questions remained surprisingly difficult.

For example:

* How much did the pool pump actually cost to run today?
* How much did running the dishwasher during solar generation save?
* Which devices are responsible for most of the electricity bill?
* How much would a device have cost if solar generation had not been available?

The information existed.

The answers did not.

---

# Initial Observation

Most existing dashboards focus on energy.

The missing piece is understanding money.

Users ultimately make decisions based on financial impact rather than kilowatt-hours.

The problem is therefore not collecting more data, but presenting existing data in a way that supports better decisions.

---

# The First Insight

The initial concept was not to replace Home Assistant's Energy Dashboard.

Instead, it should complement it.

Home Assistant explains energy flows.

Home Energy Advisor explains financial impact.

This distinction remains one of the fundamental principles of the product.

---

# The First Technical Challenge

Calculating the financial cost of an individual device is not straightforward.

At any point in time, a device may be powered by:

* locally generated energy;
* imported electricity;
* exported electricity that was no longer available for self-consumption; or
* a combination of these.

Multiple measurable devices may also be operating simultaneously.

This immediately raises an important accounting question:

**How should imported electricity be allocated between devices?**

The initial proposal was to allocate imported energy proportionally across measurable devices according to their consumption.

During discussion it became clear that different households may reasonably prefer different accounting models.

For example, some users may wish to prioritise discretionary loads such as pool pumps or EV charging, while treating essential appliances differently.

Rather than deciding this immediately, the product should be designed so that allocation strategies can evolve once real user feedback is available.

---

# The Turning Point

During the early discussions, the focus shifted away from calculations towards user outcomes.

The important question became:

> What decision does this help the user make?

This significantly influenced the direction of the project.

Rather than becoming another reporting tool, Home Energy Advisor should help users understand the financial consequences of their choices and make better energy decisions.

---

# MVP Thinking

A conscious decision was made to avoid building a feature-rich product from the outset.

The MVP should focus on answering three simple questions:

* What did this device actually cost to run?
* What would it have cost without local generation?
* How much money was saved through local generation?

If these questions can be answered accurately and clearly, the product already delivers meaningful value.

Recommendations, forecasting, optimisation and automation can then build upon this trusted accounting foundation.

---

# Documentation Philosophy

During the initial design discussions a clear documentation philosophy emerged.

Documentation should explain intent and significant decisions.

Code should explain implementation.

Tests should explain behaviour.

Documentation should only exist where it adds value beyond what can already be understood from the code and tests.

This philosophy will guide both the documentation and engineering practices of the project.

---

# Product Philosophy

The project deliberately avoids becoming a feature factory.

Features are not considered valuable simply because they are technically interesting.

Every significant enhancement should make it easier for users to make better energy decisions.

This principle is expected to guide future roadmap decisions.

---

# Looking Forward

This document captures the thinking at the start of the project.

It is intentionally preserved as a historical record.

Future ADRs should explain why the project evolved, but this document should continue to explain why the project exists in the first place.

