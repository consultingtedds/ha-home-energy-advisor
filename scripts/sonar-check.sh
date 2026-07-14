#!/usr/bin/env bash
#
# Local SonarQube gate. Never wired into GitHub CI — external contributors have
# no server, and the pipeline must stay green without one.
#
#   ./scripts/sonar-check.sh scan          analyse, wait for the server, print measures
#   ./scripts/sonar-check.sh qualitygate   print the quality gate status
#
# Requires SONAR_TOKEN. SONAR_HOST_URL defaults to http://localhost:9000.
# `scan` requires coverage.xml — generate it first, in whatever environment runs
# your tests:
#
#   pytest --cov --cov-report=xml
#
set -euo pipefail

SONAR_HOST_URL="${SONAR_HOST_URL:-http://localhost:9000}"
PROJECT_KEY="$(sed -n 's/^sonar\.projectKey=//p' sonar-project.properties)"
REPORT_TASK=".scannerwork/report-task.txt"

die() {
  echo "error: $*" >&2
  exit 1
}

require_token() {
  [ -n "${SONAR_TOKEN:-}" ] || die "SONAR_TOKEN is not set"
}

api() {
  curl -sS -f -u "${SONAR_TOKEN}:" "${SONAR_HOST_URL}$1"
}

# Run this where the working tree natively lives. The scanner is a JVM process,
# and pointing it at a Windows working tree from inside WSL takes ~14 minutes
# against ~1.5 on the host — the filesystem boundary, not the analysis, is the
# cost.
run_scanner() {
  if command -v sonar-scanner >/dev/null 2>&1; then
    sonar-scanner
  elif command -v npx >/dev/null 2>&1; then
    npx --no -- sonarqube-scanner
  else
    die "no scanner found — run: npm install"
  fi
}

# The scanner returns as soon as the report is submitted; the server analyses it
# asynchronously. Measures read before the Compute Engine task finishes are the
# *previous* run's, which is how a local gate silently reports stale results.
await_compute_engine() {
  [ -f "$REPORT_TASK" ] || die "no $REPORT_TASK — did the scan run?"
  local task_id
  task_id="$(sed -n 's/^ceTaskId=//p' "$REPORT_TASK")"

  for _ in $(seq 1 60); do
    local status
    status="$(api "/api/ce/task?id=${task_id}" | python -c 'import json,sys; print(json.load(sys.stdin)["task"]["status"])')"
    case "$status" in
      SUCCESS) return 0 ;;
      FAILED | CANCELED) die "compute engine task $status" ;;
      *) sleep 2 ;;
    esac
  done
  die "timed out waiting for compute engine task ${task_id}"
}

print_measures() {
  local keys="bugs,vulnerabilities,code_smells,duplicated_lines_density,coverage,cognitive_complexity"
  api "/api/measures/component?component=${PROJECT_KEY}&metricKeys=${keys}" |
    python -c '
import json, sys
measures = json.load(sys.stdin)["component"]["measures"]
for m in sorted(measures, key=lambda entry: entry["metric"]):
    print("  %-28s %s" % (m["metric"], m["value"]))
'
}

cmd_scan() {
  require_token
  [ -f coverage.xml ] || die "coverage.xml not found — run: pytest --cov --cov-report=xml"

  SONAR_HOST_URL="$SONAR_HOST_URL" SONAR_TOKEN="$SONAR_TOKEN" run_scanner
  await_compute_engine

  echo
  echo "Measures for ${PROJECT_KEY}:"
  print_measures
}

cmd_qualitygate() {
  require_token
  api "/api/qualitygates/project_status?projectKey=${PROJECT_KEY}"
  echo
}

case "${1:-}" in
  scan) cmd_scan ;;
  qualitygate) cmd_qualitygate ;;
  *) die "usage: $0 {scan|qualitygate}" ;;
esac
