# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CrmLeadDedupMergeWizard(models.TransientModel):
    _name = 'crm.lead.dedup.merge.wizard'
    _description = 'CRM Lead Dedup - Approved Cluster Merge Runner'

    batch_size = fields.Integer(default=200, help="Clusters processed before an explicit commit.")
    dry_run = fields.Boolean(default=True, help="If set, only validates and reports; does not call _merge_opportunity.")
    log = fields.Text(readonly=True)

    def action_run_tier1_merge(self):
        """Merge every approved cluster, any tier.

        Originally Tier 1 (email/phone exact match) only; widened so any
        cluster a human has moved to state='approved' — including Tier 2/3
        company-identity/name-similarity clusters — is mergeable too. The
        SCOPE safety net below is what makes that safe to widen: it applies
        regardless of which strategy or tier flagged the cluster.

        - state='approved', quarantined=False.
        - SCOPE check per cluster (not just Tier 1's original detection-time
          check): at most one member may be past entry stage (stage_id=1),
          and no entry-stage member being absorbed may be won or linked to a
          sale.order. A cluster violating this is a human approving something
          this automation should not blindly consume — it is reverted to
          'pending_review' with a note instead of merged, and the batch
          continues.
        - Calls _merge_opportunity(auto_unlink=False, max_length=0) per
          cluster, so absorbed records are archived (active=False), never
          deleted, and cluster size never triggers the batch-size UserError
          (confirmed from source: max_length only guards that check, it does
          not cap the merge chatter, which always itemises every absorbed
          record via _merge_log_summary).
        - Commits every `batch_size` clusters. On any post-merge assertion
          failure, rolls back the *current uncommitted batch* and halts —
          already-committed batches stand.
        """
        self.ensure_one()
        Cluster = self.env['crm.lead.dedup.cluster']
        clusters = Cluster.search([
            ('state', '=', 'approved'),
            ('quarantined', '=', False),
        ], order='id')
        if not clusters:
            raise UserError("No clusters are in state 'approved'. Nothing to merge.")

        sale_linked_ids = set(self.env['sale.order'].search([('opportunity_id', '!=', False)]).mapped('opportunity_id.id'))

        lines = []
        processed_since_commit = 0
        for cluster in clusters:
            leads = cluster.line_ids.mapped('lead_id')
            if len(leads) < 2:
                lines.append(f"cluster {cluster.id}: SKIPPED, fewer than 2 live members")
                continue

            non_entry = leads.filtered(lambda l: l.stage_id.id != 1)
            entry_leads = leads - non_entry
            entry_blocked = entry_leads.filtered(lambda l: l.won_status == 'won' or l.id in sale_linked_ids)
            if len(non_entry) > 1 or entry_blocked:
                reason = (
                    f"{len(non_entry)} members past entry stage" if len(non_entry) > 1
                    else f"entry-stage member(s) {entry_blocked.ids} are won/sale-linked"
                )
                if self.dry_run:
                    lines.append(f"cluster {cluster.id} [{cluster.strategy}] DRY RUN would REVERT to pending_review: {reason}")
                else:
                    cluster.write({'state': 'pending_review', 'notes': f"SCOPE check failed at merge time: {reason}. Reverted to pending review."})
                    lines.append(f"cluster {cluster.id} [{cluster.strategy}]: REVERTED to pending_review, {reason}")
                continue

            pre_stage_ids = leads.mapped('stage_id.id')
            expected_max_sequence = max(leads.mapped('stage_id.sequence'))

            if self.dry_run:
                sorted_leads = leads._sort_by_confidence_level(reverse=True)
                master = sorted_leads[0]
                lines.append(
                    f"cluster {cluster.id} [{cluster.strategy}] DRY RUN master={master.id} "
                    f"stage_seq={master.stage_id.sequence} members={leads.ids}"
                )
                continue

            master = leads._sort_by_confidence_level(reverse=True)[0]
            # Call the private method directly with max_length=0: the public
            # merge_opportunity() wrapper hardcodes max_length's default (5)
            # and cannot be told to allow larger clusters in one call.
            merged = leads.sudo()._merge_opportunity(auto_unlink=False, max_length=0)

            if merged.id != master.id:
                self.env.cr.rollback()
                raise UserError(
                    f"ASSERTION FAILED cluster {cluster.id}: expected master {master.id}, "
                    f"_merge_opportunity returned {merged.id}. Batch rolled back, halted."
                )
            if merged.stage_id.sequence != expected_max_sequence:
                self.env.cr.rollback()
                raise UserError(
                    f"ASSERTION FAILED cluster {cluster.id}: survivor stage sequence "
                    f"{merged.stage_id.sequence} != expected max {expected_max_sequence} "
                    f"(pre-merge stage ids {pre_stage_ids}). Batch rolled back, halted."
                )

            # _merge_opportunity(auto_unlink=False) leaves the tail records
            # completely untouched (confirmed empirically: active stays
            # True, no marker set). Archive them here so reversibility is
            # real: flip x_dedup_merged_into_id's active back to True to undo.
            absorbed = leads - merged
            absorbed.sudo().write({
                'active': False,
                'x_dedup_merged_into_id': merged.id,
                'x_dedup_merged_on': fields.Datetime.now(),
            })
            still_active = absorbed.filtered('active')
            if still_active:
                self.env.cr.rollback()
                raise UserError(
                    f"ASSERTION FAILED cluster {cluster.id}: absorbed leads "
                    f"{still_active.ids} did not archive after explicit write. "
                    f"Batch rolled back, halted."
                )

            cluster.write({
                'state': 'merged',
                'master_lead_id': merged.id,
                'merged_on': fields.Datetime.now(),
            })
            lines.append(f"cluster {cluster.id} [{cluster.strategy}] MERGED master={merged.id} absorbed={absorbed.ids}")

            processed_since_commit += 1
            if processed_since_commit >= self.batch_size:
                self.env.cr.commit()
                _logger.info("dedup merge: committed batch, %s clusters so far", processed_since_commit)
                processed_since_commit = 0

        if not self.dry_run and processed_since_commit:
            self.env.cr.commit()

        self.log = "\n".join(lines)
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
