import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // The integration is Python; JavaScript exists only for the shipped
    // Lovelace cards (HEA-50), so keep the runner out of everything else.
    include: ["frontend/**/*.test.js"],
    coverage: {
      provider: "v8",
      include: ["frontend/**/*.js"],
      // The period probe is throwaway spike code (HEA-50) whose output was a
      // finding, not a feature. It is deleted once the cards exist, and holding
      // it to a coverage bar would only invite tests nobody should write.
      exclude: ["frontend/test/**", "frontend/hea-period-probe.js"],
      reporter: ["text", "lcov"],
      reportsDirectory: "coverage-frontend",
    },
  },
});
