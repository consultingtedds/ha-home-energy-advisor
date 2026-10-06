import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // The integration is Python; JavaScript exists only for the shipped
    // Lovelace cards (HEA-50), so keep the runner out of everything else. The
    // sources are here; what ships is the bundle built from them.
    // `demo/` is throwaway tooling and not shipped, so it stays out of the
    // coverage target below. Its *messages* are tested, because a wait that
    // reported progress while a house was stalled sent a diagnosis the wrong way
    // twice, and a message is the one part of a harness a test can pin (HEA-193).
    include: ["frontend/**/*.test.js", "demo/**/*.test.js"],
    coverage: {
      provider: "v8",
      include: ["frontend/**/*.js"],
      exclude: ["frontend/test/**"],
      reporter: ["text", "lcov"],
      reportsDirectory: "coverage-frontend",
    },
  },
});
