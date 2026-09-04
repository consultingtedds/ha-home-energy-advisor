// Bundle the Lovelace cards into the single module the integration serves.
//
// The sources under `frontend/` are plain ES modules and stay that way; only
// what ships is bundled. A browser fetched 25 files and 230 KB to render one
// dashboard, and paid it on any page, because the integration asks the frontend
// to load the cards everywhere. The bundle is one request of about 51 KB.
//
//   npm run build
//
// The output is committed, because HACS ships `custom_components/` and nothing
// builds on a household's machine. CI rebuilds and fails on a diff, so the
// artifact cannot drift from the sources it came from.

import { build } from "esbuild";

const ENTRY = "frontend/hea-cards.js";
const OUT = "custom_components/home_energy_advisor/frontend/hea-cards.js";

await build({
  entryPoints: [ENTRY],
  outfile: OUT,
  bundle: true,
  minify: true,
  format: "esm",
  // Home Assistant's own frontend targets modern browsers; matching it keeps
  // the bundle from carrying transpilation nothing asks for.
  target: "es2022",
  // Every line in the bundle is ours, so there is no third-party licence to
  // preserve - and this project comments heavily, which is most of the saving.
  legalComments: "none",
});

console.log(`built ${OUT} from ${ENTRY}`);
