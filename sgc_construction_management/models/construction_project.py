# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ConstructionProject(models.Model):
    _name = 'construction.project'
    _description = 'Construction Project'
    _inherit = ['mail.thread', 'image.mixin', 'portal.mixin']

    name = fields.Char(required=True, tracking=True)
    ref = fields.Char('Project Code', readonly=True, default='New')
    client_id = fields.Many2one('res.partner', index=True, string='Client', tracking=True)
    site_manager_id = fields.Many2one('res.users', index=True, string='Site Manager')
    project_manager_id = fields.Many2one('res.users', index=True, string='Project Manager')
    start_date = fields.Date()
    end_date = fields.Date()
    contract_value = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', index=True, default=lambda self: self.env.company.currency_id)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True)
    location = fields.Char()
    latitude = fields.Float(digits=(10, 7))
    longitude = fields.Float(digits=(10, 7))
    emirate = fields.Selection([
        ('abu_dhabi', 'Abu Dhabi'),
        ('dubai', 'Dubai'),
        ('sharjah', 'Sharjah'),
        ('ajman', 'Ajman'),
        ('umm_al_quwain', 'Umm Al Quwain'),
        ('ras_al_khaimah', 'Ras Al Khaimah'),
        ('fujairah', 'Fujairah'),
    ], string='Emirate', tracking=True)
    description = fields.Text()
    analytic_account_id = fields.Many2one('account.analytic.account', index=True, string='Analytic Account', copy=False)
    company_id = fields.Many2one('res.company', index=True, string='Company', required=True, default=lambda self: self.env.company)

    # Smart button counts
    boq_count = fields.Integer(compute='_compute_counts')
    wbs_count = fields.Integer(compute='_compute_counts')
    work_order_count = fields.Integer(compute='_compute_counts')
    material_requisition_count = fields.Integer(compute='_compute_counts')
    subcontract_count = fields.Integer(compute='_compute_counts')
    billing_count = fields.Integer(compute='_compute_counts')
    quality_check_count = fields.Integer(compute='_compute_counts')
    expense_count = fields.Integer(compute='_compute_counts')
    invoice_count = fields.Integer(compute='_compute_financials', store=True)
    vendor_bill_count = fields.Integer(compute='_compute_financials', store=True)

    total_billed = fields.Monetary(compute='_compute_financials', currency_field='currency_id', store=True)
    total_expenses = fields.Monetary(compute='_compute_financials', currency_field='currency_id', store=True)
    margin_percent = fields.Float(compute='_compute_financials', string='Margin %', store=True)
    billing_percent = fields.Float(compute='_compute_financials', string='Billing %', store=True,
        help="Percentage of contract value billed to client")
    expense_vs_billed_percent = fields.Float(compute='_compute_financials', string='Expense vs Billed %', store=True,
        help="Percentage of billed amount consumed by expenses")
    total_received = fields.Monetary(compute='_compute_financials', currency_field='currency_id', store=True)
    receipt_percent = fields.Float(compute='_compute_financials', string='Receipt %', store=True,
        help="Percentage of actual receipt against billed invoices")
    planned_progress = fields.Float(compute='_compute_progress', string='Planned Progress %')
    progress = fields.Float(compute='_compute_progress', string='Actual Progress %')
    budget_consumed = fields.Float(compute='_compute_financials', string='Budget Consumed %', store=True)
    rag_status = fields.Selection([
        ('green', 'Healthy'),
        ('amber', 'Attention'),
        ('orange', 'At Risk'),
        ('red', 'Critical')
    ], compute='_compute_rag_status', string='RAG Status')
    open_ncr_count = fields.Integer(compute='_compute_counts', string='Open NCRs')
    document_count = fields.Integer(compute='_compute_counts')
    vo_count = fields.Integer(compute='_compute_counts', string='Variation Orders')
    weather_status = fields.Char(default='Clear', string='Site Weather')
    last_site_diary = fields.Date(string='Last Site Diary')
    photo_ids = fields.One2many('construction.project.photo', 'project_id', string='Site Photos')

    @api.depends('progress', 'planned_progress', 'budget_consumed')
    def _compute_rag_status(self):
        for rec in self:
            # Simple RAG logic
            if rec.progress < rec.planned_progress - 15 or rec.budget_consumed > 105:
                rec.rag_status = 'red'
            elif rec.progress < rec.planned_progress - 10 or rec.budget_consumed > 100:
                rec.rag_status = 'orange'
            elif rec.progress < rec.planned_progress - 5:
                rec.rag_status = 'amber'
            else:
                rec.rag_status = 'green'

    def _compute_access_url(self):
        super()._compute_access_url()
        for project in self:
            project.access_url = '/my/construction-projects/%s' % project.id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('ref', 'New') == 'New':
                vals['ref'] = self.env['ir.sequence'].next_by_code('construction.project') or 'New'
        projects = super().create(vals_list)
        for project in projects:
            project._create_analytic_account()
            project._create_default_folders()
        return projects

    def _create_analytic_account(self):
        plan = self.env.ref('%s.analytic_plan_construction' % self._module, raise_if_not_found=False)
        for rec in self:
            if not rec.analytic_account_id:
                vals = {
                    'name': rec.name,
                    'plan_id': plan.id if plan else False,
                    'company_id': rec.env.company.id,
                }
                rec.analytic_account_id = self.env['account.analytic.account'].create(vals)

    def _create_default_folders(self):
        default_folders = [
            ('01', 'Contract Documents'),
            ('02', 'Drawings'),
            ('03', 'BOQ'),
            ('04', 'VO / Change Orders'),
            ('05', 'RFIs'),
            ('06', 'Submittals'),
            ('07', 'Material Approvals'),
            ('08', 'Method Statements'),
            ('09', 'Inspection Requests'),
            ('10', 'NCR'),
            ('11', 'Site Diary'),
            ('12', 'Progress Reports'),
            ('13', 'Billing'),
            ('14', 'Invoices'),
            ('15', 'Payments'),
            ('16', 'Procurement'),
            ('17', 'Purchase Orders'),
            ('18', 'Vendor Documents'),
            ('19', 'HSE'),
            ('20', 'QAQC'),
            ('21', 'Equipment'),
            ('22', 'Labor'),
            ('23', 'Timesheets'),
            ('24', 'Photos'),
            ('25', 'Correspondence'),
        ]
        for seq, name in default_folders:
            self.env['construction.document.folder'].create({
                'name': name,
                'project_id': self.id,
                'sequence': int(seq),
            })

    def _compute_counts(self):
        # Optimized counts using _read_group (Odoo 17+ style)
        boq_data = self.env['construction.boq']._read_group([('project_id', 'in', self.ids)], ['project_id'], ['__count'])
        boq_counts = {project.id: count for project, count in boq_data}

        wbs_data = self.env['construction.wbs']._read_group([('project_id', 'in', self.ids)], ['project_id'], ['__count'])
        wbs_counts = {project.id: count for project, count in wbs_data}

        wo_data = self.env['construction.work.order']._read_group([('project_id', 'in', self.ids)], ['project_id'], ['__count'])
        wo_counts = {project.id: count for project, count in wo_data}

        req_data = self.env['construction.material.requisition']._read_group([('project_id', 'in', self.ids)], ['project_id'], ['__count'])
        req_counts = {project.id: count for project, count in req_data}

        sub_data = self.env['construction.subcontract']._read_group([('project_id', 'in', self.ids)], ['project_id'], ['__count'])
        sub_counts = {project.id: count for project, count in sub_data}

        bill_data = self.env['construction.ra.billing']._read_group([('project_id', 'in', self.ids)], ['project_id'], ['__count'])
        bill_counts = {project.id: count for project, count in bill_data}

        qc_data = self.env['construction.quality.check']._read_group([('project_id', 'in', self.ids)], ['project_id'], ['__count'])
        qc_counts = {project.id: count for project, count in qc_data}

        ncr_data = self.env['construction.quality.check']._read_group(
            [('project_id', 'in', self.ids), ('state', 'in', ['draft', 'in_progress', 'failed'])],
            ['project_id'], ['__count']
        )
        ncr_counts = {project.id: count for project, count in ncr_data}

        exp_data = self.env['construction.expense']._read_group([('project_id', 'in', self.ids)], ['project_id'], ['__count'])
        exp_counts = {project.id: count for project, count in exp_data}

        doc_data = self.env['construction.document']._read_group([('project_id', 'in', self.ids)], ['project_id'], ['__count'])
        doc_counts = {project.id: count for project, count in doc_data}

        vo_data = self.env['construction.document']._read_group([('project_id', 'in', self.ids), ('category', '=', 'VO')], ['project_id'], ['__count'])
        vo_counts = {project.id: count for project, count in vo_data}

        for rec in self:
            rec.boq_count = boq_counts.get(rec.id, 0)
            rec.wbs_count = wbs_counts.get(rec.id, 0)
            rec.work_order_count = wo_counts.get(rec.id, 0)
            rec.material_requisition_count = req_counts.get(rec.id, 0)
            rec.subcontract_count = sub_counts.get(rec.id, 0)
            rec.billing_count = bill_counts.get(rec.id, 0)
            rec.quality_check_count = qc_counts.get(rec.id, 0)
            rec.open_ncr_count = ncr_counts.get(rec.id, 0)
            rec.expense_count = exp_counts.get(rec.id, 0)
            rec.document_count = doc_counts.get(rec.id, 0)
            rec.vo_count = vo_counts.get(rec.id, 0)

    @api.depends('analytic_account_id')
    def _compute_financials(self):
        # Optimized financials using batch search to avoid N+1 query storms
        # Since analytic_distribution is JSON, we fetch all relevant posted lines for all analytic accounts in one go.
        analytic_accounts = self.mapped('analytic_account_id')
        if not analytic_accounts:
            for rec in self:
                rec.total_billed = rec.total_expenses = rec.budget_consumed = rec.margin_percent = 0.0
                rec.invoice_count = rec.vendor_bill_count = 0
                rec.total_received = rec.receipt_percent = 0.0
            return

        # Fetch all move lines for all projects in one go.
        # Note: analytic_distribution is a JSON field in Odoo 19 and does NOT
        # support 'like' (raises "Operation not supported"). 'in' with a list of
        # analytic account ids already matches a line whose distribution contains
        # ANY of them - the analytic mixin translates this to the correct JSON
        # query, so no manual OR-domain construction is needed.
        analytic_ids = analytic_accounts.ids
        domain = [
            ('parent_state', '=', 'posted'),
            ('analytic_distribution', 'in', analytic_ids),
        ]

        all_lines = self.env['account.move.line'].search(domain)

        # Pre-filter lines into groups for each project to optimize loop
        for project in self:
            if not project.analytic_account_id:
                project.total_billed = project.total_expenses = project.budget_consumed = project.margin_percent = 0.0
                project.invoice_count = project.vendor_bill_count = 0
                project.total_received = project.receipt_percent = 0.0
                continue

            # In-memory filtering (faster than database round-trip in loop).
            # analytic_distribution reads back as a dict (e.g. {'24': 100.0}),
            # not a raw JSON string, so membership is a dict-key check.
            p_id_str = str(project.analytic_account_id.id)
            p_lines = all_lines.filtered(lambda l: p_id_str in (l.analytic_distribution or {}))

            out_lines = p_lines.filtered(lambda l: l.move_id.move_type == 'out_invoice')
            in_lines = p_lines.filtered(lambda l: l.move_id.move_type == 'in_invoice')

            project.total_billed = sum(out_lines.mapped('credit')) - sum(out_lines.mapped('debit'))
            project.total_expenses = sum(in_lines.mapped('debit')) - sum(in_lines.mapped('credit'))
            project.invoice_count = len(out_lines.mapped('move_id'))
            project.vendor_bill_count = len(in_lines.mapped('move_id'))

            # Calculate new billing percentages
            if project.contract_value > 0:
                project.billing_percent = (project.total_billed / project.contract_value) * 100
            else:
                project.billing_percent = 0.0

            if project.total_billed > 0:
                project.expense_vs_billed_percent = (project.total_expenses / project.total_billed) * 100
            else:
                project.expense_vs_billed_percent = 0.0

            if project.contract_value > 0:
                project.budget_consumed = (project.total_expenses / project.contract_value) * 100
            else:
                project.budget_consumed = 0.0

            if project.progress < project.planned_progress - 15 or project.budget_consumed > 105:
                project.rag_status = 'red'
            elif project.progress < project.planned_progress - 10 or project.budget_consumed > 100:
                project.rag_status = 'orange'
            elif project.progress < project.planned_progress - 5:
                project.rag_status = 'amber'
            else:
                project.rag_status = 'green'

            # Actual receipts: prorate each invoice's payment progress (a gross,
            # tax-inclusive ratio from core's amount_total_signed/amount_residual_signed,
            # both positive for out_invoice and shrinking toward 0 as payments reconcile)
            # onto this project's own net/untaxed billed amount for that invoice - matching
            # total_billed's basis. Without this, a fully-paid invoice would show ~105%
            # received (the VAT rider) instead of 100%, since tax lines carry no analytic
            # distribution and are excluded from total_billed.
            net_billed_by_move = {}
            for line in out_lines:
                net_billed_by_move[line.move_id] = net_billed_by_move.get(line.move_id, 0.0) + line.credit - line.debit

            total_received = 0.0
            for move, move_net_billed in net_billed_by_move.items():
                if move.amount_total_signed:
                    paid_ratio = (move.amount_total_signed - move.amount_residual_signed) / move.amount_total_signed
                    total_received += move_net_billed * paid_ratio
            project.total_received = total_received

            # Calculate new billing percentages
            if project.contract_value > 0:
                project.billing_percent = (project.total_billed / project.contract_value) * 100
            else:
                project.billing_percent = 0.0

            if project.total_billed > 0:
                project.expense_vs_billed_percent = (project.total_expenses / project.total_billed) * 100
            else:
                project.expense_vs_billed_percent = 0.0

            if project.contract_value > 0:
                project.budget_consumed = (project.total_expenses / project.contract_value) * 100
            else:
                project.budget_consumed = 0.0

            if project.total_billed > 0:
                project.margin_percent = ((project.total_billed - project.total_expenses) / project.total_billed) * 100
            else:
                project.margin_percent = 0.0

            if project.total_billed > 0:
                project.receipt_percent = (project.total_received / project.total_billed) * 100
            else:
                project.receipt_percent = 0.0

    def _compute_progress(self):
        wbs_data = self.env['construction.wbs']._read_group(
            [('project_id', 'in', self.ids)],
            ['project_id'],
            ['progress:avg']
        )
        progress_map = {project.id: progress_avg for project, progress_avg in wbs_data}

        for rec in self:
            rec.progress = progress_map.get(rec.id, 0.0)

            # Simple planned progress logic based on dates
            if rec.start_date and rec.end_date:
                total_days = (rec.end_date - rec.start_date).days
                elapsed_days = (fields.Date.context_today(rec) - rec.start_date).days
                if total_days > 0:
                    rec.planned_progress = min(max(elapsed_days / total_days * 100, 0), 100)
                else:
                    rec.planned_progress = 0.0
            else:
                rec.planned_progress = 0.0

    def action_activate(self):
        self.state = 'active'

    def action_hold(self):
        self.state = 'on_hold'

    def action_complete(self):
        self.state = 'completed'

    def action_cancel(self):
        self.state = 'cancelled'

    def action_reset(self):
        self.state = 'draft'

    def action_view_boq(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'BOQ',
            'res_model': 'construction.boq',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_export_wip_xlsx(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/sgc_construction_management/xlsx/wip/%s' % self.id,
            'target': 'self',
        }

    def action_view_documents(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Documents',
            'res_model': 'construction.document',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_variation_orders(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Variation Orders',
            'res_model': 'construction.document',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id), ('category', '=', 'VO')],
            'context': {'default_project_id': self.id, 'default_category': 'VO'},
        }

    def action_view_invoices(self):
        if not self.analytic_account_id:
            return
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('line_ids.analytic_distribution', 'in', [self.analytic_account_id.id])
        ]
        context = {
            'default_move_type': 'out_invoice',
            'form_view_ref': 'account.view_move_form'
        }
        tree_view = self.env.ref('account.view_out_invoice_tree')
        search_view = self.env.ref('account.view_account_invoice_filter')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoices',
            'res_model': 'account.move',
            'views': [(tree_view.id, 'list'), (False, 'form')],
            'search_view_id': search_view.id,
            'domain': domain,
            'context': context,
        }

    def action_view_vendor_bills(self):
        if not self.analytic_account_id:
            return
        domain = [
            ('move_type', '=', 'in_invoice'),
            ('line_ids.analytic_distribution', 'in', [self.analytic_account_id.id])
        ]
        context = {
            'default_move_type': 'in_invoice',
            'form_view_ref': 'account.view_move_form'
        }
        tree_view = self.env.ref('account.view_in_invoice_bill_tree')
        search_view = self.env.ref('account.view_account_bill_filter')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vendor Bills',
            'res_model': 'account.move',
            'views': [(tree_view.id, 'list'), (False, 'form')],
            'search_view_id': search_view.id,
            'domain': domain,
            'context': context,
        }

    def action_view_wbs(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'WBS Phases',
            'res_model': 'construction.wbs',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_work_orders(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Work Orders',
            'res_model': 'construction.work.order',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_requisitions(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Material Requisitions',
            'res_model': 'construction.material.requisition',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_subcontracts(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Subcontracts',
            'res_model': 'construction.subcontract',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_billing(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'RA Billing',
            'res_model': 'construction.ra.billing',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_quality(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Quality Checks',
            'res_model': 'construction.quality.check',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_expenses(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Expenses',
            'res_model': 'construction.expense',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
