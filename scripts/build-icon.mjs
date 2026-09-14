/**
 * Render the integration's brand icon (HEA-32).
 *
 *   node scripts/build-icon.mjs
 *
 * Writes `brand/icon.png` (256) and `brand/icon@2x.png` (512), which is what
 * HACS looks for and what a `home-assistant/brands` submission needs.
 *
 * ## Why this is a script and not an exported file
 *
 * The icon is one Material Design Icons glyph, `home-lightning-bolt` - the same
 * one the dashboard strategy already sets, so what a household sees in the
 * sidebar and what they see on the integration page are the same mark rather
 * than two things that happen to resemble each other.
 *
 * Keeping it as a script means changing the glyph or the colour is a one-line
 * edit and a rerun, by somebody who does not draw. It also means the PNGs in
 * the repository can be regenerated and checked, rather than being artefacts
 * whose origin nobody remembers.
 *
 * Rendered through Playwright because it is already a dev dependency here for
 * the demo, so this needs nothing new installed. A headless browser rasterises
 * an SVG path at an exact size with a transparent background, which is the
 * whole job.
 *
 * MDI is Apache-2.0 licensed, which permits this use.
 */

import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";

const HERE = dirname(fileURLToPath(import.meta.url));
const BRAND = join(HERE, "..", "brand");

/**
 * `mdi:home-lightning-bolt`, on a 24x24 grid, copied from
 * Templarian/MaterialDesign-SVG. Embedded rather than fetched so the build
 * works offline and produces the same bytes in a year.
 */
const GLYPH =
  "M12 3L2 12H5V20H19V12H22L12 3M11.5 18V14H9L12.5 7V11H15L11.5 18Z";

/**
 * One flat colour, no background.
 *
 * Amber for electricity, and a mid tone deliberately: Home Assistant shows an
 * integration icon on a white card in the light theme and a dark one at night,
 * and a single file has to stay legible on both. A near-black would vanish in
 * the dark theme and a pale tint would vanish in the light one.
 *
 * Change this line to change the icon. Not Home Assistant's own brand blue -
 * the brands guidance asks custom integrations not to borrow its branding.
 */
const COLOUR = "#F0A330";

/** What `home-assistant/brands` asks for: 1:1, PNG, transparent. */
const SIZES = [
  { file: "icon.png", px: 256 },
  { file: "icon@2x.png", px: 512 },
];

/**
 * The glyph's own bounds, so the icon can be trimmed to them.
 *
 * The 24x24 grid has empty space around this path - two units either side, and
 * more above and below - and the brands guidance asks for "the minimum amount
 * of empty space on the edges". Measured in the browser rather than read off
 * the path by eye, because `getBBox` is exact and arithmetic done by hand here
 * would be a guess that looks like a measurement.
 */
async function measure(page) {
  return page.evaluate((d) => {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    const path = document.createElementNS(ns, "path");
    path.setAttribute("d", d);
    svg.appendChild(path);
    document.body.appendChild(svg);
    const { x, y, width, height } = path.getBBox();
    svg.remove();
    return { x, y, width, height };
  }, GLYPH);
}

/**
 * A square viewBox around the glyph, tight on its longer side.
 *
 * Square because the aspect ratio has to be 1:1, and centred on the glyph so
 * the trimming takes the empty space off rather than off-centring the mark.
 */
function squareViewBox({ x, y, width, height }) {
  const side = Math.max(width, height);
  const left = x - (side - width) / 2;
  const top = y - (side - height) / 2;
  return `${left} ${top} ${side} ${side}`;
}

async function main() {
  mkdirSync(BRAND, { recursive: true });
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.setContent("<body style='margin:0'></body>");
    const viewBox = squareViewBox(await measure(page));

    for (const { file, px } of SIZES) {
      await page.setViewportSize({ width: px, height: px });
      await page.setContent(
        `<body style="margin:0">
           <svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}"
                width="${px}" height="${px}">
             <path d="${GLYPH}" fill="${COLOUR}" />
           </svg>
         </body>`,
      );
      // `omitBackground` is what makes it transparent rather than white. The
      // brands guidance prefers transparency, and a white square would sit
      // visibly on the dark theme's card.
      await page.screenshot({
        path: join(BRAND, file),
        omitBackground: true,
        clip: { x: 0, y: 0, width: px, height: px },
      });
      console.log(`  brand/${file}  ${px}x${px}`);
    }
  } finally {
    await browser.close();
  }
}

await main();
