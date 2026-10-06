# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    SaleAgreement = env['sale.agreement'].sudo()
    SaleOrder = env['sale.order'].sudo()

    orders = SaleOrder.search([('partner_id', '!=', False)])
    for order in orders:
        commercial_partner = order.partner_id.commercial_partner_id
        year = (order.agreement_date or order.create_date.date()).year
        existing = SaleAgreement.search([
            ('commercial_partner_id', '=', commercial_partner.id),
            ('agreement_year', '=', year),
            ('company_id', '=', order.company_id.id),
        ], limit=1)
        if existing:
            if not existing.sale_order_id:
                existing.sale_order_id = order.id
            continue

        SaleAgreement.create({
            'partner_id': commercial_partner.id,
            'agreement_year': year,
            'company_id': order.company_id.id,
            'sale_order_id': order.id,
            'agreement_date': order.agreement_date,
            'agreement_contact_person': order.agreement_contact_person,
            'agreement_job_title': order.agreement_job_title,
            'num_users': order.num_users or 1,
            'odoo_modules': order.odoo_modules,
            'date_start': order.project_start_date,
            'date_end': order.golive_date,
        })
