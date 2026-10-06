# SGC Multi-Persona Chatbot Assistant

A self-contained Odoo 19 module that adds 14 SGC persona assistants to a unified chat panel, reusing the existing `llm.thread` generation pipeline and `@llm_tool` framework.

## Design

- **Additive** — does NOT modify `ai_brain`, `odoo-llm`, or the orchestrator service
- **Coexists** — the existing `AiBrainPanel` remains untouched and functional
- **Extensible** — personas and their data tools are DB records + decorated methods; adding future personas needs no code changes
- **Namespaced** — all components use `sgc_*` / `o_sgc_*` prefixes to avoid collision

## Architecture

```
SgcChatPanel (Owl client action) → persona selector (dropdown)
   → /llm/thread/set_assistant  (existing controller)
   → /llm/thread/generate       (existing SSE endpoint)
   → llm.thread.generate()      (existing pipeline with advisory-lock, tool-looping)
   → orchestrator:8088/chat → LiteLLM → provider   (unchanged)
```

## Dependency Versions (verified)

| Dependency | Version | Status |
|---|---|---|
| Odoo | 19.0 Community | Confirmed |
| `llm_assistant` | 19.0 | Installed |
| `llm_thread` | 19.0 | Installed |
| `llm_tool` | 19.0 | Installed |

See `.claude/prds/DEPS_VERIFICATION.md` for full dependency verification report.

## 14 Personas

| # | Code | Data Scope |
|---|---|---|
| 1 | `finance_analyst` | account.move, account.bank.statement, account.journal |
| 2 | `aml_officer` | risk.assessment, kyc.application, transaction.monitoring |
| 3 | `hr_assistant` | hr.employee, hr.leave*, hr.payslip* |
| 4 | `sales_analyst` | crm.lead, sale.order, account.move |
| 5 | `operations_manager` | stock.move, stock.quant, mrp.production* |
| 6 | `inventory_specialist` | stock.quant, stock.move |
| 7 | `customer_support` | res.partner |
| 8 | `marketing_analyst` | crm.lead |
| 9 | `project_manager` | project.project* |
| 10 | `procurement_officer` | purchase.order* |
| 11 | `compliance_auditor` | mail.message |
| 12 | `executive_assistant` | cross-domain snapshot |
| 13 | `it_support` | res.users, ir.module.module |
| 14 | `data_analyst` | dynamic read_group on any accessible model |

*Optional models — tools degrade gracefully (error message) when the module is not installed.

> **Personas 6–14**: codes and data scopes are placeholders — confirm exact names and scope with the owner before delivery.

## Install Steps

1. Place `sgc_persona/` in your Odoo addons path
2. Activate the Developer Mode in Odoo
3. Go to Apps → Update Apps List
4. Search for "SGC Multi-Persona" and click Install

The module will create:
- 14 `llm.assistant` records (with stable XML IDs)
- 14 `llm.prompt` templates
- 14 `llm.tool` records (one per persona)
- 2 security groups (`sgc_persona.group_sgc_persona_admin`, `sgc_persona.group_sgc_persona_tool_manager`)
- A menu entry under "SGC AI → AI Assistant"

## Tests

Tests are written but **unexecuted by design** in the build phase. Run them after install:

```bash
docker exec odoo-prod odoo -d odoo19-sgc --test-tags sgc_persona --stop-after-init
```

Or to run a specific test:
```bash
docker exec odoo-prod odoo -d odoo19-sgc --test-tags /sgc_persona --test-enable --stop-after-init
```

## Orchestrator Routing (Future Task)

An optional `assistant_code` pass-through is gated behind config parameter `sgc_persona.enable_orchestrator_routing` (default `False`). When an admin enables it, the persona's `code` field will be included in the generation payload for orchestrator-side routing.

**Orchestrator-side contract** (not implemented here):
- `POST /chat` should accept an optional `assistant_code` field
- Map known codes to LiteLLM virtual model aliases:
  - `finance_analyst`, `aml_officer`, `compliance_auditor` → `task-analysis`
  - `hr_assistant`, `executive_assistant`, `customer_support` → `task-summary`
  - `data_analyst` → unspecialized (default model)

## License

LGPL-3 — matches upstream `odoo-llm` modules.
