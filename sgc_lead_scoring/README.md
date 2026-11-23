# SGC - Lead Scoring

![Version](https://img.shields.io/badge/version-19.0.1.0.0-blue.svg)
![Odoo](https://img.shields.io/badge/Odoo-19.0-714B67.svg)
![License](https://img.shields.io/badge/license-LGPL-3-green.svg)
![Module](https://img.shields.io/badge/type-Module-lightgrey.svg)

## Overview

**SGC - Lead Scoring** — AI-Powered Lead Scoring with Multi-LLM Support

Part of the **SGC TECH AI** Odoo 19 module suite for enterprise real estate, HR, CRM, and productivity workflows.

## Key Features

- **Multi-LLM Provider Support** — OpenAI, Groq, HuggingFace, Anthropic, and custom endpoints
- **Automated Research** — Pull publicly available data on lead company/contact
- **AI Scoring Algorithm** — Considers form completeness, requirement clarity, and activity
- **Probability Score** — 0-100 lead grade displayed on CRM kanban
- **Enrichment Notes** — AI insights written to lead chatter automatically
- **Scheduled & Real-Time** — Cron-based or on-demand enrichment
- **Customizable Prompts** — Edit scoring criteria per business vertical

## Installation

1. Copy the `sgc_lead_scoring` folder into your Odoo `addons` directory
2. Update the apps list: **Apps > Update Apps List**
3. Search for "SGC - Lead Scoring"
4. Click **Install**

### Dependencies

`base`, `crm`, `mail`

## Configuration

After installation:

1. Set up user access rights in **Settings > Users & Companies > Users**
2. Assign the relevant SGC security groups to your users
3. Configure module-specific parameters as needed

## Usage

CRM > Leads. New leads auto-enrich; manually re-score from the Lead Scoring wizard.

## Module Information

| Field | Value |
|-------|-------|
| **Technical Name** | `sgc_lead_scoring` |
| **Version** | `19.0.1.0.0` |
| **Category** | CRM |
| **Author** | SGC TECH AI |
| **License** | LGPL-3 |
| **Odoo Version** | 19.0 |
| **Application** | No |

## Architecture

- **Models**: Located in `models/`
- **Views**: Located in `views/`
- **Security**: ACL and record rules in `security/`
- **Controllers**: HTTP routes in `controllers/`
- **Static Assets**: Branding and descriptions in `static/`
- **Reports**: QWeb templates in `reports/`
- **Wizards**: Interactive wizards in `wizard/` or `wizards/`

## Security

This module implements:

- **Access Control Lists** (`security/ir.model.access.csv`) — model-level permissions
- **Record Rules** — row-level access where applicable
- **Security Groups** — role-based access via `res.groups`
- **Public/Portal Routes** — token-based authentication where exposed

## Support

For issues, feature requests, or integration support, contact the SGC TECH AI team.

## License

This module is licensed under LGPL-3.

---

**Maintained by**: SGC TECH AI
**Odoo Version**: 19.0
