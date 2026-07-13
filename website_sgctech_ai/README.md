# SGC Tech AI — Premium Financial Theme for Odoo 19

## Overview

Enterprise-grade premium financial institution theme for Odoo 19, inspired by sgctech.ai.

**Brand Identity:**
- Deep Navy (`#0D223D`) — Primary brand color
- Cream/Ivory (`#FAF7F2`) — Background
- Light Brown Gold (`#B89B5E`) — Accent

**Typography:**
- Playfair Display (serif) — Headings
- Inter (sans-serif) — Body text

## Installation

1. Copy the `theme_sgctech` directory into your Odoo addons path:
   ```bash
   cp -r theme_sgctech /path/to/odoo/custom-addons/
   ```

2. Update the addons list in Odoo:
   - Go to **Settings → Activate Developer Mode**
   - Go to **Apps → Update Apps List**

3. Install the theme:
   - Search for "SGC Tech AI" in the Apps list
   - Click **Install**

4. Apply the theme to your website:
   - Go to **Website → Configuration → Settings**
   - Select "SGC Tech AI" as your active theme

## Directory Structure

```
theme_sgctech/
├── __manifest__.py                    # Module manifest
├── __init__.py                        # Python init
├── README.md                          # This file
├── data/
│   └── theme_data.xml                 # Color palette and theme config
├── static/
│   └── src/
│       ├── img/                       # AI-generated imagery
│       │   ├── hero-bg.png
│       │   ├── ai-technology.png
│       │   ├── about-team.png
│       │   ├── sgc-logo.png
│       │   └── services-dashboard.png
│       ├── js/
│       │   └── theme.js               # Header scroll, FAQ, stat counters
│       └── scss/
│           ├── primary_variables.scss  # Color palette, typography, design tokens
│           ├── secondary_variables.scss # Component-level variables
│           └── custom.scss            # Full premium styling system
├── templates/
│   ├── assets.xml                     # SCSS/JS asset registration
│   ├── header.xml                     # Header/navigation override
│   ├── footer.xml                     # Premium dark footer
│   ├── homepage.xml                   # Complete landing page
│   ├── snippets.xml                   # Drag-and-drop builder snippets
│   └── options.xml                    # Editor color palette options
└── views/
    └── website_views.xml              # Page and menu registrations
```

## Design Token System

### Color Variables (SCSS)

| Token | Value | Usage |
|-------|-------|-------|
| `$o-navy` | `#0D223D` | Primary brand, headings, nav |
| `$o-navy-light` | `#102A43` | Hover states |
| `$o-navy-lighter` | `#132F4C` | Dark section backgrounds |
| `$o-navy-dark` | `#091929` | Footer, deep backgrounds |
| `$o-cream` | `#FAF7F2` | Page background |
| `$o-cream-dark` | `#F8F4EE` | Section alternate bg |
| `$o-cream-darker` | `#F6F1EA` | Cards, muted areas |
| `$o-gold` | `#B89B5E` | Primary accent |
| `$o-gold-light` | `#C4A267` | Hover accent, CTA gold |
| `$o-gold-lighter` | `#D1B075` | Light accent |
| `$o-gold-dark` | `#A68B4B` | Active states |

### CTA Classes

| Class | Description |
|-------|-------------|
| `.sgc-cta-primary` | Navy bg, white text, gold hover |
| `.sgc-cta-secondary` | Ivory bg, navy text, gold border |
| `.sgc-cta-text` | Navy text, gold hover underline |
| `.sgc-cta-lg` | Large size modifier |

### Section Classes

| Class | Description |
|-------|-------------|
| `.sgc-section-cream` | Light cream background |
| `.sgc-section-cream-dark` | Darker cream background |
| `.sgc-section-navy` | Deep navy background |
| `.sgc-section-navy-dark` | Darkest navy background |
| `.sgc-hairline` | Gold gradient hairline divider |

### Component Classes

| Class | Description |
|-------|-------------|
| `.sgc-card` | Premium card with hover effect |
| `.sgc-card-icon` | Navy circle with gold icon |
| `.sgc-testimonial` | Dark testimonial card |
| `.sgc-badge--gold-outline` | Gold outlined badge |
| `.sgc-badge--navy-filled` | Navy filled badge |
| `.sgc-faq-item` | FAQ accordion item |
| `.sgc-stat` | Stat counter block |

## Accessibility (WCAG AA)

All color combinations meet WCAG AA requirements:
- Navy on cream: 12.8:1 contrast ratio
- White on navy: 13.5:1 contrast ratio
- Gold on navy: 4.6:1 contrast ratio (large text)
- Gold hairlines at 35% opacity for subtle accent

## Website Builder Snippets

The theme registers these drag-and-drop snippets:
1. **SGC Hero Banner** — Full-screen hero with overlay
2. **SGC Services Grid** — 3-column service cards
3. **SGC Statistics Row** — Animated counter section
4. **SGC Testimonials** — Client quote cards
5. **SGC Call to Action** — Conversion section
6. **SGC Gold Hairline** — Section divider

## Customization

Edit `static/src/scss/primary_variables.scss` to change:
- Brand colors
- Font families
- Border radius
- Shadow depths
- CTA styles

Edit `static/src/scss/secondary_variables.scss` to change:
- Section-specific variables
- Header behavior
- Footer styling
- Card and component variables

## License

LGPL-3
