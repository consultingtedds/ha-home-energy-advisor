/**
 * Every Home Energy Advisor card, in one resource.
 *
 * A dashboard should not have to list a url per card: one entry registers the
 * family, and a card added later arrives without the user touching their
 * resource list. Each card registers itself on import.
 */

import "./hea-cost-over-time-card.js";
import "./hea-device-costs-card.js";
import "./hea-devices-card.js";
import "./hea-sources-card.js";
import "./hea-totals-card.js";
