from odoo import _, api, fields, models
from odoo.exceptions import UserError

RESEARCH_DONE_STAGE_ID = 2  # BANT gate applies here, NOT to Valid Contact/Outreach
BANT_FIELDS = ('x_bant_budget', 'x_bant_authority', 'x_bant_need', 'x_bant_timeline')
BANT_MIN_LEN = 3  # reject placeholder junk like "x" or "."


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    outreach_mail_sent = fields.Boolean(
        string='Outreach Email Sent',
        copy=False,
    )

    def _bant_missing(self, vals=None):
        """Return labels of BANT fields still empty, considering pending vals."""
        self.ensure_one()
        vals = vals or {}
        missing = []
        for fname in BANT_FIELDS:
            value = vals[fname] if fname in vals else self[fname]
            if not value or len(str(value).strip()) < BANT_MIN_LEN:
                missing.append(self._fields[fname].get_description(self.env)['string'])
        return missing

    def _check_bant_gate(self, vals):
        # technical bypass for migrations/scripts: context skip_bant_check
        if self.env.context.get('skip_bant_check'):
            return
        for lead in self:
            if lead.stage_id.id == RESEARCH_DONE_STAGE_ID:
                continue  # already in Research Done, not a move into it
            missing = lead._bant_missing(vals)
            if missing:
                raise UserError(_(
                    'Cannot move "%(lead)s" to Research Done.\n\n'
                    'BANT qualification must be completed with real information first. '
                    'Missing or too short: %(fields)s',
                    lead=lead.name, fields=', '.join(missing)))

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        # gate leads created directly in Research Done as well
        if not self.env.context.get('skip_bant_check'):
            for lead in leads.filtered(
                    lambda l: l.stage_id.id == RESEARCH_DONE_STAGE_ID):
                missing = lead._bant_missing()
                if missing:
                    raise UserError(_(
                        'Cannot create "%(lead)s" directly in Research Done.\n\n'
                        'BANT qualification must be completed with real information first. '
                        'Missing or too short: %(fields)s',
                        lead=lead.name, fields=', '.join(missing)))
        return leads

    def write(self, vals):
        if vals.get('stage_id') == RESEARCH_DONE_STAGE_ID:
            self._check_bant_gate(vals)
        return super().write(vals)

    def action_open_outreach_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Send Outreach Email',
            'res_model': 'crm.outreach.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_lead_id': self.id},
        }
