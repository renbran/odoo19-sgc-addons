# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Module Identity

`website_sgctech_ai` — Odoo 19 custom website theme module (version `19.0.1.1.2`).  
Technical name used in all XML IDs, `ir.config_parameter` keys, and asset bundle paths.

## Odoo Development Commands

All commands run from the repo root (where `odoo-bin` or `docker-compose.yml` lives).

```bash
# Install / upgrade the module (use -u after any Python/XML change)
python odoo-bin -u website_sgctech_ai -d <DB>

# Upgrade inside Docker
docker compose exec odoo python odoo-bin -u website_sgctech_ai -d <DB>

# Clear frontend asset cache after CSS/JS edits (Odoo 19)
# Settings → Technical → Clear Assets Cache  OR  append ?debug=assets to the URL

# Run Odoo tests for this module
python odoo-bin -u website_sgctech_ai --test-enable --stop-after-init -d <DB>
```

There is no separate JS/CSS build step — Odoo bundles `static/src/` automatically on upgrade.

## Architecture

### Python Layer

| File | Role |
|---|---|
| `models/res_config_settings.py` | Adds AI API key fields to Settings (stored as `ir.config_parameter` under `website_sgctech_ai.*`) |
| `models/product_template_gemini_image.py` | Extends `product.template` — "Generate AI Image" button logic with a three-provider fallback chain |
| `models/genspark_integration.py` | Standalone helper class `GenSparkImageGenerator` (no ORM inheritance) |
| `controllers/main.py` | `SGCTechWebsite` controller — `/sgctech/stats` JSON, `/tools/odoo-roi-calculator` UI, and `/tools/odoo-roi-calculator/lead` CRM capture |
| `hooks.py` | Intentionally empty placeholder |
| `migrations/19.0.1.1.1/pre-migrate.py` | Adds missing `res_config_settings` varchar columns for AI API keys |

**AI image provider chain** (tried in order per product):
1. Hugging Face FLUX.1-schnell (`website_sgctech_ai.hf_token`)
2. Self-hosted GenSpark2API bridge (`website_sgctech_ai.genspark_api_url` + `genspark_api_secret`)
3. Pexels stock photo (`website_sgctech_ai.pexels_api_key`)

Optional Cloudinary CDN upload runs after a successful generation if all three Cloudinary keys are configured.

### XML / Template Layer

| File | What it registers |
|---|---|
| `views/website_templates.xml` | Inherits `website.layout` — injects `.sgc-theme` on `#wrapwrap`, global background canvas elements, Google Fonts `<link>`, analytics scripts |
| `views/homepage.xml` | Full 10-section homepage at `/sgctech-home` |
| `views/pages.xml` | Static informational pages |
| `views/tools_templates.xml` | ROI Calculator page (`website_sgctech_ai.sgc_odoo_roi_calculator`) |
| `views/snippets.xml` | 5 drag-and-drop Website Builder snippets |
| `views/store_templates.xml` | eCommerce overrides |
| `views/auth_templates.xml` | Custom signup / password reset pages |
| `views/res_config_settings_views.xml` | Settings UI for AI API keys |
| `views/product_template_gemini_image_button.xml` | "Generate AI Image" button on product form |
| `views/generate_primary_template.xml` | Primary template generation views |
| `data/utm_data.xml` | Seed UTM source / campaign records for the ROI lead |

### Frontend Assets (`static/src/`)

**CSS load order is strict** (numbered in the asset bundle):

```
01_variables.css        ← CSS custom properties / design tokens
02_base.css             ← reset & typography
03_layout.css           ← navbar & footer
04_hero.css             ← hero section
05_sections.css         ← all content sections
06_components.css       ← cards, buttons, badges
07_animations.css       ← keyframes
08_responsive.css       ← breakpoints (480–1400 px)
09_ecommerce.css        ← shop overrides
09_store.css            ← legacy store styles (if present)
10_auth.css             ← authentication pages
10_roi_calculator.css   ← ROI calculator styles
11_background_paths.css ← animated path renderer
particle_text_effect.css
sgc_particle_hero.css
```

**JS files** (all vanilla ES5/ES6, no bundler, no framework):

| File | Purpose |
|---|---|
| `sgctech.js` | Main theme engine — navbar scroll-hide, 90-particle canvas network, typewriter (`[data-typewriter]`), scroll-reveal (IntersectionObserver), animated counters (`[data-count]`), magnetic buttons, scroll-spy, parallax orbs, tech ticker, pricing toggle, 3D tilt cards |
| `particle_text_effect.js` | Canvas particle text animation; reads phrases from `website_sgctech_ai.particle_words` (homepage) and `particle_words_about` (about page) via a `<div data-particle-words>` element |
| `background_paths.js` | Animated cubic-bezier path renderer on `#sgc-bg-paths` / `#sgc-bg-paths-global` (72 curves, 36 path pairs) |
| `aura_core.js` | WebGL shader pulse on `#sgc-aura-core-global` for non-home pages |
| `roi_calculator.js` | ROI Calculator front-end interactions |
| `neon_flow.js` | Neon flow animation effect |

**Critical JS guard pattern** — every JS file checks for `.sgc-theme` on `#wrapwrap` before running. This class is injected by `sgctech_body_class` in `website_templates.xml`. Background canvas elements are only rendered on non-home pages; the homepage hero has its own dedicated canvas.

## Settings / Config Parameters

All runtime settings are stored as `ir.config_parameter` records with the prefix `website_sgctech_ai.`:

| Key | UI label |
|---|---|
| `website_sgctech_ai.hf_token` | Hugging Face Token |
| `website_sgctech_ai.genspark_api_url` | GenSpark Bridge URL |
| `website_sgctech_ai.genspark_api_secret` | GenSpark API Secret |
| `website_sgctech_ai.genspark_model` | GenSpark Model (default: `imagen4`) |
| `website_sgctech_ai.pexels_api_key` | Pexels API Key |
| `website_sgctech_ai.cloudinary_cloud_name` | Cloudinary Cloud Name |
| `website_sgctech_ai.cloudinary_api_key` | Cloudinary API Key |
| `website_sgctech_ai.cloudinary_api_secret` | Cloudinary API Secret |
| `website_sgctech_ai.particle_words` | Homepage particle phrases (`phrase1\|phrase2::r,g,b:r,g,b:angle:holdMs`) |
| `website_sgctech_ai.particle_words_about` | About page particle phrases (same format) |

## Key Conventions

- **XML IDs**: always prefixed `website_sgctech_ai.` or `sgctech_*`
- **CSS classes**: always prefixed `sgc-` (e.g. `sgc-btn-primary`, `sgc-reveal`, `sgc-parallax-orb`)
- **JS data attributes**: `data-typewriter`, `data-count`, `data-suffix`, `data-price-monthly`, `data-tilt`, `data-speed`, `data-particle-words`, `data-particle-text-effect`
- **New migrations**: go in `migrations/19.0.X.Y.Z/pre-migrate.py`; always use `ADD COLUMN IF NOT EXISTS`
- **Controller**: does NOT inherit `website.HomePage` to avoid hijacking Odoo's own routes (`/shop`, `/page`, `/blog`, etc.)
