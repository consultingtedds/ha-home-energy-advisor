import { defineConfig } from "vitest/config";

// The cards ship inside the integration: that is the directory HACS copies and
// the one the integration serves from.
const CARDS = "custom_components/home_energy_advisor/frontend";

export default defineConfig({
  test: {
    // The integration is Python; JavaScript exists only for the shipped
    // Lovelace cards (HEA-50), so keep the runner out of everything else.
    include: [`${CARDS}/**/*.test.js`],
    coverage: {
      provider: "v8",
      include: [`${CARDS}/**/*.js`],
      exclude: [`${CARDS}/test/**`],
      reporter: ["text", "lcov"],
      reportsDirectory: "coverage-frontend",
    },
  },
});
