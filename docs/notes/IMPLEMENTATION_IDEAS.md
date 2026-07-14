# Implementation Ideas

> Working notes captured during early product exploration.
>
> These are ideas, not decisions. They exist so we don't lose useful thinking while the product evolves.

---

## Overall Architecture

Current thinking:

```
Home Assistant
        │
        ▼
 Energy Sources
 (Energy Dashboard, Devices, Tariffs)
        │
        ▼
 Accounting Engine
        │
        ▼
 Financial Model
        │
        ├── Home Assistant Entities
        ├── Native Dashboard
        └── Optional Grafana Dashboard
```

Keep financial calculations independent of presentation.

---

## Native Home Assistant Integration

Preferred initial direction.

Reasons:

* Native entities
* Config Flow
* Repairs
* Diagnostics
* Recorder
* Long-term statistics

Alternative discussed:

* Spring Boot service with HA integration.

---

## Dashboard Strategy

Default:

* Native Lovelace dashboard.

Optional:

* Grafana dashboards for advanced users.

---

## Device Cost Model

Every measurable device should eventually expose concepts similar to:

* Actual Cost
* Cost Without Solar
* Solar Saving
* Energy Used

Entity names intentionally left undecided.

---

## Cost Allocation

Ideas discussed:

* Proportional allocation
* Weighted allocation
* Configurable allocation strategies

No decision made.

---

## Device Categories

Possible future categories:

* Essential
* Flexible
* Background

These are accounting concepts rather than Home Assistant concepts.

---

## Technology

Current assumptions:

* Python
* Native Home Assistant integration
* pytest
* ruff
* mypy
* pre-commit
* GitHub Actions

Subject to change.
