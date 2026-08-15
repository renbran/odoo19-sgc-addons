from odoo import fields, models


class CrmLeadFieldMapping(models.Model):
    _name = 'crm.lead.field.mapping'
    _description = 'CRM Lead Ingestion Field Mapping'

    source_config_id = fields.Many2one(
        'crm.lead.source.config', required=True, ondelete='cascade')
    source_key = fields.Char(
        required=True,
        help="Key/path in the provider's payload, e.g. 'full_name' or "
             "'user_column_data.EMAIL'.")
    target_field = fields.Char(
        required=True,
        help="Technical field name on crm.lead to write this value to, "
             "e.g. 'email_from'.")
