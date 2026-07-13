# SGC TECH AI - Odoo 19 Premium Theme

Version: `19.0.1.0.0`  
License: `LGPL-3`

## Overview

`sgc_theme_ai` is a production-ready Odoo 19 website theme for SGC TECH AI. It includes:

- branded marketing pages
- solution landing pages
- ROI calculator
- AI copilot widget
- website shop styling
- portal and login branding
- Odoo 19 manifest-based asset loading

## Production Status

This module has been validated on Odoo 19 in Docker with:

- clean install on a fresh database
- full install on the shared custom addons path
- post-install test run with `0 failed, 0 error(s)`

Validated review database:

- `sgc_theme_ai_fullpath_20260314_b`

## Installation

1. Place `sgc_theme_ai` inside your Odoo custom addons path.
2. Update the apps list.
3. Install `SGC TECH AI - Premium Theme`.

Local URL in the current Docker environment:

- `http://localhost:8069`

## Key Behaviors

- The default website homepage is redirected to `/home` through a post-init hook.
- `/solutions` and the linked solution pages are live and install-safe.
- The theme does not create a second website record on install.
- Frontend and backend assets are loaded through the Odoo 19 `assets` manifest.
- Core marketing pages use bundled local media instead of external Cloudinary dependencies.

## Structure

```text
sgc_theme_ai/
|-- __manifest__.py
|-- hooks.py
|-- controllers/
|-- models/
|-- security/
|-- static/
|-- tests/
`-- views/
```
