# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ConstructionMaterialRequisition(models.Model):
    _name = 'construction.material.requisition'
    _description = 'Material Requisition'
    _inherit = ['mail.thread']
    company_id = fields.Many2one('res.company', index=True, string='Company', required=True, default=lambda self: self.env.company)

    name = fields.Char(required=True)
    ref = fields.Char(readonly=True, default='New')
    project_id = fields.Many2one('construction.project', index=True, required=True)
    wbs_id = fields.Many2one('construction.wbs', index=True, string='WBS Phase', domain="[('project_id','=',project_id)]")
    work_order_id = fields.Many2one('construction.work.order', index=True, domain="[('project_id','=',project_id)]")
    date_requested = fields.Date(default=lambda self: fields.Date.context_today(self))
    date_required = fields.Date()
    requested_by = fields.Many2one('res.users', index=True, default=lambda self: self.env.user)
    approved_by = fields.Many2one('res.users', index=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True)
    line_ids = fields.One2many('construction.material.requisition.line', 'requisition_id')
    total_estimated_cost = fields.Monetary(compute='_compute_total', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', index=True, related='project_id.currency_id')
    notes = fields.Text()
    purchase_order_ids = fields.One2many('construction.purchase.order', 'requisition_id',
                                         string='Purchase Orders')
    purchase_order_count = fields.Integer(compute='_compute_purchase_order_count')

    @api.depends('purchase_order_ids')
    def _compute_purchase_order_count(self):
        for rec in self:
            rec.purchase_order_count = len(rec.purchase_order_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('ref', 'New') == 'New':
                vals['ref'] = self.env['ir.sequence'].next_by_code('construction.material.requisition') or 'New'
        return super().create(vals_list)

    @api.depends('line_ids.subtotal')
    def _compute_total(self):
        for rec in self:
            rec.total_estimated_cost = sum(rec.line_ids.mapped('subtotal'))

    def action_submit(self):
        self.state = 'submitted'

    def action_approve(self):
        self.write({'state': 'approved', 'approved_by': self.env.user.id})

    def action_receive(self):
        self.state = 'received'

    def action_cancel(self):
        self.state = 'cancelled'

    def action_reset(self):
        self.state = 'draft'

    @api.onchange('work_order_id')
    def _onchange_work_order_id(self):
        if self.work_order_id and self.work_order_id.wbs_id:
            self.wbs_id = self.work_order_id.wbs_id

    def action_create_purchase(self):
        """Create a Purchase Order (RFQ/LPO) from this approved requisition."""
        self.ensure_one()
        if self.state not in ('approved', 'received'):
            raise ValidationError(_("You can only create a Purchase Order from an approved requisition."))
        if not self.line_ids:
            raise ValidationError(_("Add at least one material line before creating a Purchase Order."))
        po_lines = []
        for line in self.line_ids:
            qty = line.qty_approved or line.qty_requested
            po_lines.append((0, 0, {
                'product_id': line.product_id.id or False,
                'name': line.description or (line.product_id.display_name if line.product_id else ''),
                'uom_id': line.uom_id.id or False,
                'quantity': qty,
                'price_unit': line.unit_price,
            }))
        po = self.env['construction.purchase.order'].create({
            'name': self.name,
            'project_id': self.project_id.id,
            'wbs_id': self.wbs_id.id,
            'requisition_id': self.id,
            'order_date': fields.Date.context_today(self),
            'line_ids': po_lines,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Order'),
            'res_model': 'construction.purchase.order',
            'view_mode': 'form',
            'res_id': po.id,
        }

    def action_view_purchase_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'construction.purchase.order',
            'view_mode': 'list,form',
            'domain': [('requisition_id', '=', self.id)],
            'context': {'default_requisition_id': self.id, 'default_project_id': self.project_id.id},
        }


class ConstructionMaterialRequisitionLine(models.Model):
    _name = 'construction.material.requisition.line'
    _description = 'Material Requisition Line'

    @api.constrains('qty_requested', 'qty_approved', 'qty_received')
    def _check_quantities(self):
        for rec in self:
            if rec.qty_approved > rec.qty_requested:
                raise ValidationError(_("Approved quantity cannot be greater than requested quantity."))
            if rec.qty_received > rec.qty_approved:
                raise ValidationError(_("Received quantity cannot be greater than approved quantity."))

    requisition_id = fields.Many2one('construction.material.requisition', index=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', index=True, string='Material')
    description = fields.Char()
    uom_id = fields.Many2one('uom.uom', index=True, string='UOM')
    qty_requested = fields.Float(digits=(12, 3))
    qty_approved = fields.Float(digits=(12, 3))
    qty_received = fields.Float(digits=(12, 3))
    unit_price = fields.Monetary(currency_field='currency_id')
    subtotal = fields.Monetary(compute='_compute_subtotal', store=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', index=True, related='requisition_id.currency_id')

    @api.depends('qty_requested', 'unit_price')
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = rec.qty_requested * rec.unit_price

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.name
            self.uom_id = self.product_id.uom_id
            self.unit_price = self.product_id.standard_price
