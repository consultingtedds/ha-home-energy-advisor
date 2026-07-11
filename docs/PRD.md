# Product Requirements Document (PRD)

> **Home Energy Advisor** *(working title)*

## Purpose

This document defines the product requirements for Home Energy Advisor.

It describes the user outcomes the product aims to achieve, the scope of the Minimum Viable Product (MVP) and the principles used to prioritise future development.

Implementation details, architectural decisions and engineering rationale are intentionally documented elsewhere.

---

# Problem Statement

Home Assistant provides excellent visibility into household energy usage, generation and storage.

However, users still struggle to answer relatively simple financial questions about their energy consumption.

Examples include:

* How much did my pool pump cost to run today?
* How much money did my solar panels save by running the dishwasher this afternoon?
* Which devices are responsible for most of my electricity bill?
* Which devices would benefit most from being scheduled differently?

Answering these questions typically requires users to combine information from multiple dashboards and perform manual calculations.

Home Energy Advisor exists to make those answers easy to obtain and easy to understand.

---

# Product Goal

Enable users to make better energy decisions by providing meaningful financial insight into household energy consumption.

The product should explain where money is being spent, where savings are being achieved and where opportunities exist to improve.

---

# Target Users

The initial product is intended for Home Assistant users who:

* monitor household energy consumption;
* generate electricity locally (such as solar);
* use static, dynamic or time-of-use electricity tariffs; or
* measure the energy consumption of one or more individual devices.

The product should remain useful for simpler installations while naturally supporting more advanced energy systems.

---

# User Outcomes

A successful release should enable users to achieve one or more of the following:

* Understand what an individual device actually costs to operate.
* Understand how local energy generation affects those costs.
* Identify devices responsible for the highest running costs.
* Understand where changes in behaviour could reduce energy costs.
* Build confidence in the financial information presented by the product.

---

# Minimum Viable Product

The MVP focuses on one core capability:

**Provide accurate financial accounting for measurable household devices.**

The MVP should allow users to:

* view the actual running cost of monitored devices;
* view the estimated running cost without local generation;
* understand the financial benefit provided by local generation;
* compare devices by running cost;
* present this information within Home Assistant using a clear and intuitive dashboard.

The MVP deliberately excludes forecasting, optimisation, automation and scheduling recommendations.

---

# Success Criteria

The MVP is considered successful if a typical Home Assistant user can install the integration and quickly answer questions such as:

* What did this device cost me today?
* How much money did solar save on this device?
* Which monitored devices cost the most to operate?

without requiring manual calculations or external tools.

---

# Constraints

The MVP should:

* integrate naturally with Home Assistant;
* operate locally wherever practical;
* produce transparent calculations that users can understand and trust;
* favour correctness and clarity over feature count.

---

# Out of Scope

The following are intentionally excluded from the MVP:

* automation;
* predictive scheduling;
* weather forecasting;
* battery optimisation;
* electric vehicle optimisation;
* machine learning or AI-driven recommendations;
* complex simulation or forecasting.

These capabilities may be considered in future releases once the accounting foundation is proven.

---

# Future Evolution

Future development should build upon the accounting engine rather than replace it.

Potential future capabilities include recommendations, optimisation and automation, but only where they improve user outcomes and build upon a trusted financial model.

The roadmap should evolve through user feedback and practical experience rather than speculative feature planning.

