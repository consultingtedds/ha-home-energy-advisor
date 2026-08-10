#!/usr/bin/env bash
# Copy the Lovelace cards into a timestamped folder under Home Assistant's www.
#
# Home Assistant serves /local/ with `Cache-Control: max-age=2678400` — 31 days.
# Overwriting a card in place therefore does nothing for anyone whose browser
# already fetched it, and a `?v=` on the dashboard resource url does not help:
# the cards are ES modules, and a relative `import "./hea-format.js"` does not
# inherit the query string. The entry point busts; its imports do not.
#
# A browser left holding one stale module fails the whole import — ES modules
# fail as a unit — so *no* card registers and every HEA card on the dashboard
# renders as an unknown element. Observed on a live instance (2026-08-10).
#
# Stamping the *folder* fixes it: every relative import resolves under the new
# prefix, so one url change re-fetches the whole set atomically.
#
#   ./scripts/deploy-frontend.sh /path/to/config/www
#
# Prints the resource url to set on the dashboard. Old folders are left in
# place — they cost a few KB and let a bad release be rolled back by pointing
# the resource at the previous stamp.

set -euo pipefail

die() {
  echo "error: $*" >&2
  exit 1
}

[ -f frontend/hea-cards.js ] || die "run this from the repository root"

www="${1:-}"
[ -n "$www" ] || die "usage: $0 <path-to-config/www> [stamp]"
[ -d "$www" ] || die "no such directory: $www"

stamp="${2:-$(date +%Y%m%d-%H%M%S)}"
target="$www/home-energy-advisor/$stamp"

mkdir -p "$target"
cp frontend/*.js "$target/"

echo "Copied $(ls -1 frontend/*.js | wc -l | tr -d ' ') files to $target"
echo
echo "Set the dashboard resource to:"
echo "  /local/home-energy-advisor/$stamp/hea-cards.js"
