# -*- coding: utf-8 -*-
"""CES identity, manager resolution and safe configuration lookups.

Nothing in this module hard-codes a production record id.  Every reference to
a live record (the CES ``hr.job``, the CRM proposal/won/dead-end stages) is
resolved through ``ir.config_parameter`` first, then through an XML-ID lookup,
then through a case-insensitive name lookup, and finally degrades to an empty
result.  This mirrors the pattern already used by ``sgc_sales_playbook``.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ir.config_parameter keys owned by this module
# ---------------------------------------------------------------------------
PARAM_CES_JOB_ID = "sgc_ces_kpi_banner.ces_job_id"
PARAM_CES_JOB_NAME = "sgc_ces_kpi_banner.ces_job_name"
PARAM_PROPOSAL_STAGE_ID = "sgc_ces_kpi_banner.proposal_stage_id"
PARAM_WON_STAGE_ID = "sgc_ces_kpi_banner.won_stage_id"
PARAM_EXCLUDED_STAGE_IDS = "sgc_ces_kpi_banner.excluded_stage_ids"
PARAM_BANNER_ENABLED = "sgc_ces_kpi_banner.banner_enabled"
PARAM_CACHE_SECONDS = "sgc_ces_kpi_banner.cache_seconds"
PARAM_EMAIL_ENABLED = "sgc_ces_kpi_banner.review_email_enabled"

DEFAULT_CES_JOB_NAME = "Telesales/Client Engagement Specialist"


def _int_list(raw):
    """Parse a comma separated integer list without eval()."""
    out = []
    for chunk in (raw or "").replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            out.append(int(chunk))
        except (TypeError, ValueError):
            _logger.warning("sgc_ces_kpi_banner: ignoring non-integer id %r", chunk)
    return out


class SgcCesIdentity(models.AbstractModel):
    """Stateless helper model. All lookups are read-only and sudo-safe."""

    _name = "sgc.ces.identity"
    _description = "SGC CES Identity & Configuration Resolution"

    # -- generic parameter access -------------------------------------------
    @api.model
    def _param(self, key, default=None):
        value = self.env["ir.config_parameter"].sudo().get_param(key)
        return value if value not in (None, False, "") else default

    @api.model
    def _param_int(self, key, default=None):
        raw = self._param(key)
        if raw is None:
            return default
        try:
            return int(raw)
        except (TypeError, ValueError):
            _logger.warning("sgc_ces_kpi_banner: parameter %s is not an integer (%r)", key, raw)
            return default

    @api.model
    def _param_bool(self, key, default=False):
        raw = self._param(key)
        if raw is None:
            return default
        return str(raw).strip().lower() in ("1", "true", "yes", "on")

    # -- CES job -------------------------------------------------------------
    @api.model
    def _resolve_ces_job(self):
        """Return the CES ``hr.job`` recordset (possibly empty). Never raises."""
        Job = self.env["hr.job"].sudo()
        job_id = self._param_int(PARAM_CES_JOB_ID)
        if job_id:
            job = Job.browse(job_id).exists()
            if job:
                return job
            _logger.warning("sgc_ces_kpi_banner: configured CES job id %s no longer exists", job_id)
        # XML-ID escape hatch, so a customer can ship their own job record.
        job = self.env.ref("sgc_ces_kpi_banner.ces_job_override", raise_if_not_found=False)
        if job and job._name == "hr.job":
            return job.sudo()
        name = self._param(PARAM_CES_JOB_NAME, DEFAULT_CES_JOB_NAME)
        job = Job.search([("name", "=ilike", name)], limit=1)
        if job:
            return job
        job = Job.search([("name", "ilike", "Engagement Specialist")], limit=1)
        if job:
            return job
        _logger.info("sgc_ces_kpi_banner: no CES hr.job could be resolved (looked for %r)", name)
        return Job.browse()

    # -- hr.version current row ---------------------------------------------
    @api.model
    def _current_version(self, employee):
        """Return the current ``hr.version`` for an employee.

        Odoo 19 has no boolean "current" flag on ``hr.version``; the current
        row is ``MAX(date_version) WHERE date_version <= today``.  If every
        version is in the future (data entry error) we fall back to the
        earliest row so the employee is not silently invisible.
        """
        employee = employee.sudo()
        if not employee:
            return self.env["hr.version"].sudo().browse()
        Version = self.env["hr.version"].sudo()
        today = fields.Date.context_today(self)
        version = Version.search(
            [("employee_id", "=", employee.id), ("date_version", "<=", today)],
            order="date_version desc, id desc",
            limit=1,
        )
        if version:
            return version
        return Version.search(
            [("employee_id", "=", employee.id)], order="date_version asc, id asc", limit=1
        )

    @api.model
    def _employee_for_user(self, user):
        user = user.sudo()
        if not user:
            return self.env["hr.employee"].sudo().browse()
        return self.env["hr.employee"].sudo().search(
            [("user_id", "=", user.id)], order="active desc, id asc", limit=1
        )

    @api.model
    def is_ces_user(self, user=None):
        """True when ``user`` currently holds the CES job."""
        user = (user or self.env.user).sudo()
        job = self._resolve_ces_job()
        if not job:
            return False
        employee = self._employee_for_user(user)
        if not employee:
            return False
        version = self._current_version(employee)
        return bool(version and version.job_id and version.job_id.id == job.id)

    @api.model
    def ces_employees(self):
        """All employees currently holding the CES job."""
        job = self._resolve_ces_job()
        if not job:
            return self.env["hr.employee"].sudo().browse()
        Employee = self.env["hr.employee"].sudo()
        candidates = Employee.search(
            [("id", "in", self.env["hr.version"].sudo()
              .search([("job_id", "=", job.id)]).mapped("employee_id").ids)]
        )
        return candidates.filtered(
            lambda e: self._current_version(e).job_id.id == job.id
        )

    # -- CES start date ------------------------------------------------------
    @api.model
    def ces_start_date(self, employee, strategy="auto"):
        """Resolve the date the employee entered the CES role.

        ``auto``            first CES-job version date, else contract start,
                            else employee create date.
        ``role_entry``      earliest ``hr.version.date_version`` carrying the
                            CES job.
        ``contract_start``  ``hr.version.contract_date_start`` of the current
                            version.
        ``create_date``     ``hr.employee.create_date``.
        """
        employee = employee.sudo()
        if not employee:
            return False
        job = self._resolve_ces_job()
        role_entry = False
        if job:
            version = self.env["hr.version"].sudo().search(
                [("employee_id", "=", employee.id), ("job_id", "=", job.id)],
                order="date_version asc, id asc",
                limit=1,
            )
            role_entry = version.date_version if version else False
        current = self._current_version(employee)
        contract_start = current.contract_date_start if current else False
        created = fields.Date.to_date(employee.create_date) if employee.create_date else False

        if strategy == "role_entry":
            return role_entry or contract_start or created
        if strategy == "contract_start":
            return contract_start or role_entry or created
        if strategy == "create_date":
            return created
        return role_entry or contract_start or created

    # -- manager resolution --------------------------------------------------
    @api.model
    def resolve_manager(self, employee):
        """Resolution hierarchy, first hit wins, never raises.

        1. ``hr.version.hr_responsible_id`` of the current version
           (populated for 4/4 CES employees in the live data).
        2. ``hr.employee.parent_id.user_id``.
        3. ``hr.department.manager_id.user_id``.
        4. The configured fallback user (``sgc_ces_kpi_banner.fallback_manager_uid``).
        5. Empty recordset - callers must degrade gracefully.
        """
        employee = employee.sudo()
        Users = self.env["res.users"].sudo()
        if not employee:
            return Users.browse()
        version = self._current_version(employee)
        if version and version.hr_responsible_id:
            return version.hr_responsible_id
        if employee.parent_id and employee.parent_id.user_id:
            return employee.parent_id.user_id
        department = employee.department_id
        if department and department.manager_id and department.manager_id.user_id:
            return department.manager_id.user_id
        fallback = self._param_int("sgc_ces_kpi_banner.fallback_manager_uid")
        if fallback:
            user = Users.browse(fallback).exists()
            if user:
                return user
        return Users.browse()

    @api.model
    def resolve_manager_for_user(self, user):
        return self.resolve_manager(self._employee_for_user(user))

    @api.model
    def managed_user_ids(self, manager_user=None):
        """User ids of every CES employee whose resolved manager is ``manager_user``."""
        manager_user = (manager_user or self.env.user).sudo()
        result = []
        for employee in self.ces_employees():
            if not employee.user_id:
                continue
            manager = self.resolve_manager(employee)
            if manager and manager.id == manager_user.id:
                result.append(employee.user_id.id)
        return result

    # -- CRM stage resolution ------------------------------------------------
    @api.model
    def _resolve_stage(self, param_key, xml_id, name_candidates):
        Stage = self.env["crm.stage"].sudo()
        stage_id = self._param_int(param_key)
        if stage_id:
            stage = Stage.browse(stage_id).exists()
            if stage:
                return stage
        if xml_id:
            stage = self.env.ref(xml_id, raise_if_not_found=False)
            if stage and stage._name == "crm.stage":
                return stage.sudo()
        for candidate in name_candidates:
            stage = Stage.search([("name", "=ilike", candidate)], limit=1)
            if stage:
                return stage
        return Stage.browse()

    @api.model
    def proposal_stage(self):
        return self._resolve_stage(PARAM_PROPOSAL_STAGE_ID, None, ["Proposal", "Proposition"])

    @api.model
    def won_stage(self):
        stage = self._resolve_stage(PARAM_WON_STAGE_ID, None, ["Won", "Closed Won"])
        if stage:
            return stage
        return self.env["crm.stage"].sudo().search([("is_won", "=", True)], limit=1)

    @api.model
    def excluded_stage_ids(self):
        """Stages that never count as live pipeline (dead ends + won)."""
        raw = self._param(PARAM_EXCLUDED_STAGE_IDS)
        ids = _int_list(raw)
        if not ids:
            Stage = self.env["crm.stage"].sudo()
            dead = Stage.search([
                "|", "|",
                ("name", "ilike", "No Answer"),
                ("name", "ilike", "Not Interested"),
                ("name", "ilike", "Lost"),
            ])
            ids = dead.ids
        won = self.won_stage()
        if won and won.id not in ids:
            ids.append(won.id)
        return ids
