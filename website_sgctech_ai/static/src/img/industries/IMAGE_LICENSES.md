# Industry card imagery — sources and licences

All eight homepage industry photographs were replaced on **2026-08-03** with
high-definition open-licence photography sourced from [Unsplash](https://unsplash.com).

**Licence:** [Unsplash Licence](https://unsplash.com/license) — free to use for
commercial and non-commercial purposes, no permission or attribution required.
Attribution is recorded here anyway, as good practice and so the originals can
be re-fetched at a larger size later if needed.

Each source was downloaded at **3840 px** on its long edge, then cropped and
re-encoded locally (no upscaling at any point):

| Variant | Dimensions | Used by |
|---|---|---|
| `<name>.avif` / `.webp` / `.jpg` | 1536 × 2048 (3:4) | homepage industry cards — matches `.sgc-industry-card` `aspect-ratio: 9/12` |
| `<name>_lg.avif` / `.webp` / `.jpg` | 2688 × 1536 (7:4) | `views/pages.xml` industry pages — 2× the previous 1344 × 768 |

Delivery is AVIF → WebP → JPEG via `image-set()` in
`static/src/css/05_sections.css`. The eight card AVIFs total **1 276 KB**, below
the **1 533 KB** the eight previous JPEGs cost.

| Industry | Unsplash photo | Photographer | Why it fits |
|---|---|---|---|
| Real Estate | [`9n7rZJLWY7o`](https://unsplash.com/photos/9n7rZJLWY7o) | see photo page | Burj Khalifa and the Dubai skyline at sunset — the exact market SGC's RERA/property pack serves |
| Construction | [`UxYEwaanctE`](https://unsplash.com/photos/UxYEwaanctE) | Robin Irfan | Tower cranes silhouetted over an active site at dusk; shot in Dubai, UAE |
| Trading & Distribution | [`duKI9Bhd2zc`](https://unsplash.com/photos/duKI9Bhd2zc) | Wolfgang Weiser | Gantry crane loading stacked containers — import/export and multi-warehouse work made literal |
| Retail & E-commerce | [`hMMbIptXPjI`](https://unsplash.com/photos/hMMbIptXPjI) | see photo page | Upscale mall interior with escalators and storefronts — POS/omnichannel context |
| Hospitality | [`pt0nGH-NvoA`](https://unsplash.com/photos/pt0nGH-NvoA) | see photo page | Marble reception lobby with warm wood and pendant lighting — hotel front-of-house |
| Manufacturing | [`WjOWazUPAss`](https://unsplash.com/photos/WjOWazUPAss) | see photo page | Engineers working an assembly floor — production line with people, not empty machinery |
| Healthcare | [`e7MJLM5VGjY`](https://unsplash.com/photos/e7MJLM5VGjY) | see photo page | Bright, modern clinical treatment room |
| Education | [`gMsnXqILjp4`](https://unsplash.com/photos/gMsnXqILjp4) | see photo page | Corporate training session with laptops — matches SGC's e-learning/enablement positioning better than a school classroom |

## Notes

- The Trading image contains incidental shipping-line branding (EVERGREEN, COSCO)
  visible on the containers. This is normal editorial stock photography and is
  permitted under the Unsplash Licence, but swap the source if a brand-free frame
  is preferred.
- `logistics.*` and `professional_services.*` were **not** replaced — they appear
  only on `views/pages.xml`, not on the homepage, and were out of scope for this
  pass. They remain the previous AI-generated art at 864 × 1152.
- Reproduce the crops/encodes with `scratchpad/encode.py`: per-image quality is
  stepped down until each variant meets its budget (AVIF ≤ 180 KB, WebP ≤ 260 KB,
  JPEG ≤ 400 KB).
