#!/usr/bin/env bash
# Copy the Lovelace cards into a timestamped folder under Home Assistant's www.
#
# This is the fallback, not the route: the integration serves the cards itself,
# so deploying it deploys them. Use this to push a card change without
# redeploying the integration, or to roll back to a previous stamp. Anything it
# serves loads *in addition* to the integration's own copy, so remove the
# Lovelace resource once you are done with it.
#
# Home Assistant serves /local/ with `Cache-Control: max-age=2678400` - 31 days.
# Overwriting a card in place therefore does nothing for anyone whose browser
# already fetched it, and a `?v=` on the dashboard resource url does not help:
# the cards are ES modules, and a relative `import "./hea-format.js"` does not
# inherit the query string. The entry point busts; its imports do not.
#
# A browser left holding one stale module fails the whole import - ES modules
# fail as a unit - so *no* card registers and every HEA card on the dashboard
# renders as an unknown element. Observed on a live instance (2026-08-10).
#
# Stamping the *folder* fixes it: every relative import resolves under the new
# prefix, so one url change re-fetches the whole set atomically.
#
#   ./scripts/deploy-frontend.sh /path/to/config/www
#
# Home Assistant's `www` is often a network share rather than a local path.
# Windows-style arguments are accepted and converted, so a drive mapped in
# Windows can be given as `Z:\www`, `Z:/www` or `/z/www`, and a UNC share as
# `\\homeassistant\config\www` - run it from Git Bash, where the mapping
# exists. WSL cannot see a Windows-mapped drive unless it is mounted there
# too, so prefer the Windows shell for this one.
#
# Prints the resource url to set on the dashboard. Old folders are left in
# place - they cost a few KB and let a bad release be rolled back by pointing
# the resource at the previous stamp.

set -euo pipefail

die() {
  echo "error: $*" >&2
  exit 1
}

# `Z:\www` -> `/z/www`, `\\host\share` -> `//host/share`; anything already
# usable is returned untouched.
to_shell_path() {
  local path="${1//\\//}"
  [ -d "$path" ] && { printf '%s' "$path"; return; }
  if [[ "$path" =~ ^([A-Za-z]):/(.*)$ ]]; then
    local drive="${BASH_REMATCH[1]}"
    local rest="${BASH_REMATCH[2]}"
    printf '/%s/%s' "$(printf '%s' "$drive" | tr '[:upper:]' '[:lower:]')" "$rest"
    return
  fi
  printf '%s' "$path"
}

cards="custom_components/home_energy_advisor/frontend"

[ -d frontend ] || die "run this from the repository root"
[ -f "$cards/hea-cards.js" ] || die "no bundle at $cards - run 'npm run build'"

[ -n "${1:-}" ] || die "usage: $0 <path-to-config/www> [stamp]"
www="$(to_shell_path "$1")"
[ -d "$www" ] || die "no such directory: $www (from '$1')
  a Windows-mapped drive is only visible from Git Bash, not from WSL"

stamp="${2:-$(date +%Y%m%d-%H%M%S)}"
target="$www/home-energy-advisor/$stamp"

mkdir -p "$target"
cp "$cards"/*.js "$target/"

echo "Copied $(ls -1 "$cards"/*.js | wc -l | tr -d ' ') files to $target"
echo
echo "Set the dashboard resource to:"
echo "  /local/home-energy-advisor/$stamp/hea-cards.js"
