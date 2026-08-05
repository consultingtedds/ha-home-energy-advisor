// Commit message rules. Replaces .commitlintrc.json, which could not express
// the `ignores` predicate below — that has to be a function, so the config has
// to be JavaScript.

export default {
  extends: ["@commitlint/config-conventional"],
  rules: {
    // Our convention is `type(HEA-nn): description`, but a scope is not
    // mandatory and HEA-nn is upper-case.
    "scope-empty": [0],
    "scope-case": [2, "always", ["upper-case", "lower-case"]],
  },
  // Dependabot writes its own bodies: compare URLs and an
  // `updated-dependencies:` block, neither of which survives a 100-character
  // wrap. Nobody can fix those messages, so linting them only ever produces a
  // red PR nobody can act on. We lint what humans write. Headers still follow
  // the convention (`chore(deps):`, `ci(deps):`) because dependabot.yml sets
  // the prefix explicitly. See HEA-71.
  ignores: [(message) => /^(chore|ci)\(deps(-dev)?\):/.test(message)],
};
