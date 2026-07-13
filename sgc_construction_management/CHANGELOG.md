# Changelog

All notable changes to SGC Construction Management are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [19.0.1.0.0] - 2026-06-24

### Changed
- Renamed internal module references from `aos_construction_management` to
  `sgc_construction_management` to match the directory name and the SGC TECH
  marketplace `sgc_*` naming convention. All 31 internal references updated
  across 11 files.
- Corrected `__manifest__.py` `assets` paths: removed the bogus
  `aos_construction_management/` prefix that was preventing dashboard assets,
  Leaflet library, CSS, JS, and XML templates from loading.
- Updated `index.html` security group count from 3 to 5 to match actual module.

### Added
- `README.md` - proper module README with features, install steps, dependencies, security roles.
- `LICENSE` - LGPL-3 license text.
- `CHANGELOG.md` - this file.

### Removed
- Dev-only folders: `.omc/`, `.omo/`, `.playwright-mcp/`, `token-optimizer/`,
  `models/.omc/`, `models/.claude/`, root `.claude/`.
- Python bytecode cache: `models/__pycache__/`.
- Backup file: `.claude/settings.local.json.bak`.

## Pre-1.0.0

Earlier history predates the SGC TECH marketplace adoption. The module was
originally developed as `aos_construction_management` for an internal deployment
and ported to the SGC TECH marketplace under `sgc_construction_management`.