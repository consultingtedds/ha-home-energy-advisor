import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // The integration is Python; JavaScript exists only for the shipped
    // Lovelace cards (HEA-50), so keep the runner out of everything else.
    include: ["frontend/**/*.test.js"],
    coverage: {
      provider: "v8",
      include: ["frontend/**/*.js"],
      exclude: ["frontend/test/**"],
      reporter: ["text", "lcov"],
      reportsDirectory: "coverage-frontend",
    },
  },
});
