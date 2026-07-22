from odoo import models, api, fields
from datetime import datetime, timedelta
from collections import OrderedDict


class CRMDashboard(models.AbstractModel):
    _name = "crm.dashboard"
    _description = "CRM Dashboard"

    @api.model
    def _is_admin(self):
        """Check if current user has admin/manager access."""
        user = self.env.user
        admin_groups = [
            self.env.ref("base.group_system", raise_if_not_found=False),
            self.env.ref("sales_team.group_sale_manager", raise_if_not_found=False),
        ]
        for g in admin_groups:
            if g and g in user.group_ids:
                return True
        # Fallback: check for common admin group names
        cr = self.env.cr
        cr.execute("""
            SELECT 1 FROM res_groups_users_rel ug
            JOIN res_groups g ON g.id = ug.gid
            WHERE ug.uid = %s AND (
                g.id IN (SELECT id FROM res_groups WHERE name->>'en_US' IN ('Administrator', 'Admin', 'Role / Administrator'))
            )
            LIMIT 1
        """, (user.id,))
        return cr.fetchone() is not None

    @api.model
    def get_dashboard_data(self, user_id=None):
        lead = self.env["crm.lead"]
        order = self.env["sale.order"]
        team = self.env["crm.team"]
        is_admin = self._is_admin()
        current_user = self.env.user

        # Determine which users to show
        if user_id:
            target_users = self.env["res.users"].browse(user_id)
        elif is_admin:
            target_users = self.env["res.users"].search([("id", ">", 2)])
        else:
            target_users = current_user

        target_ids = target_users.ids

        # KPIs scoped to target users
        lead_domain_base = [("user_id", "in", target_ids)] if not user_id and not is_admin else []
        if user_id:
            lead_domain_base = [("user_id", "=", user_id)]

        # Get won stage ids dynamically from CRM stages
        won_stage_ids = self.env["crm.stage"].search([("is_won", "=", True)]).ids
        won_stage_condition = f"l.stage_id IN ({','.join(map(str, won_stage_ids))})" if won_stage_ids else "1=0"

        total_leads = lead.search_count(lead_domain_base or [])
        pipeline = lead.search_count((lead_domain_base or []) + [("active", "=", True), ("probability", ">", 0), ("probability", "<", 100)])
        won = lead.search_count((lead_domain_base or []) + [("stage_id", "in", won_stage_ids)])
        lost = lead.search_count((lead_domain_base or []) + ["|", ("active", "=", False), ("probability", "=", 0)])

        cr = self.env.cr
        fu_user_filter, fu_params = "", []
        if user_id:
            fu_user_filter, fu_params = "AND l.user_id = %s", [user_id]
        elif not is_admin:
            fu_user_filter, fu_params = "AND l.user_id IN %s", [tuple(target_ids)]

        # Follow Up: active leads in "Follow Up" stage (stage_id = 6)
        cr.execute(f"""
            SELECT COUNT(*)
            FROM crm_lead l
            WHERE l.active = true AND l.stage_id = 6
              {fu_user_filter}
        """, fu_params)
        follow_up = cr.fetchone()[0] or 0

        # Research Done: active leads in "Research Done" stage (stage_id = 2)
        cr.execute(f"""
            SELECT COUNT(*)
            FROM crm_lead l
            WHERE l.active = true AND l.stage_id = 2
              {fu_user_filter}
        """, fu_params)
        research_done = cr.fetchone()[0] or 0

        # Outreach Email: active leads in "Valid Contact/Email Outreach" stage (stage_id = 10)
        cr.execute(f"""
            SELECT COUNT(*)
            FROM crm_lead l
            WHERE l.active = true AND l.stage_id = 10
              {fu_user_filter}
        """, fu_params)
        outreach_email = cr.fetchone()[0] or 0

        # Proposal: active leads in "Proposal" stage (stage_id = 9)
        cr.execute(f"""
            SELECT COUNT(*)
            FROM crm_lead l
            WHERE l.active = true AND l.stage_id = 9
              {fu_user_filter}
        """, fu_params)
        proposal = cr.fetchone()[0] or 0

        # New to Moved: leads moved out of "New" stage (old_value_integer = 1) today
        mt_fu_filter, mt_fu_params = "", []
        if user_id:
            mt_fu_filter, mt_fu_params = "AND mtv.create_uid = %s", [user_id]
        elif not is_admin:
            mt_fu_filter, mt_fu_params = "AND mtv.create_uid IN %s", [tuple(target_ids)]
        cr.execute(f"""
            SELECT COUNT(*)
            FROM mail_tracking_value mtv
            JOIN ir_model_fields imf ON imf.id = mtv.field_id_id
            WHERE imf.model = 'crm.lead'
              AND imf.name = 'stage_id'
              AND mtv.create_date::date = CURRENT_DATE
              AND mtv.old_value_integer = 1
              {mt_fu_filter}
        """, mt_fu_params)
        new_to_moved = cr.fetchone()[0] or 0

        # Objection Ranking: count of objections per objection name
        cr.execute(f"""
            SELECT o.name->>'en_US' as objection, COUNT(l.id) as count
            FROM crm_lead l
            JOIN crm_lead_objection_rel rel ON rel.lead_id = l.id
            JOIN crm_objection o ON o.id = rel.objection_id
            WHERE l.active = true
              {fu_user_filter}
            GROUP BY o.name
            ORDER BY count DESC
        """, fu_params)
        objection_ranking = [{"objection": r[0], "count": r[1]} for r in cr.fetchall()]

        # Meeting Booked: active leads in "Meeting Booked" stage (stage_id = 3)
        cr.execute(f"""
            SELECT COUNT(*)
            FROM crm_lead l
            WHERE l.active = true AND l.stage_id = 3
              {fu_user_filter}
        """, fu_params)
        booked = cr.fetchone()[0] or 0

        # Daily Activity: leads with any real activity today
        # (write_date change OR mail_message OR activity done OR stage change)
        cr.execute(f"""
            SELECT COUNT(DISTINCT l.id)
            FROM crm_lead l
            LEFT JOIN mail_message m ON m.res_id = l.id AND m.model = 'crm.lead'
                AND m.date::date = CURRENT_DATE
            LEFT JOIN mail_activity a ON a.res_id = l.id AND a.res_model = 'crm.lead'
                AND a.date_done::date = CURRENT_DATE
            LEFT JOIN mail_tracking_value tv ON tv.mail_message_id IN (
                SELECT id FROM mail_message WHERE res_id = l.id AND model = 'crm.lead'
            ) AND tv.create_date::date = CURRENT_DATE
            WHERE (l.write_date::date = CURRENT_DATE OR m.id IS NOT NULL OR a.id IS NOT NULL OR tv.id IS NOT NULL)
              {fu_user_filter}
        """, fu_params)
        daily_activity = cr.fetchone()[0] or 0

        total_orders = order.search_count([])
        confirmed_orders = order.search_count([("state", "=", "sale")])
        confirmed_revenue = 0
        for o in order.search([("state", "=", "sale")]):
            confirmed_revenue += o.amount_total

        # Funnel: ordered stages
        funnel_stages = []
        for s in self.env["crm.stage"].search([], order="sequence"):
            f_domain = [("stage_id", "=", s.id)]
            if user_id:
                f_domain.append(("user_id", "=", user_id))
            elif not is_admin:
                f_domain.append(("user_id", "in", target_ids))
            stage_leads = lead.search_count(f_domain)
            funnel_stages.append({"name": s.name, "count": stage_leads})

        # Pipeline stages (active only)
        stages = []
        for s in self.env["crm.stage"].search([], order="sequence"):
            s_domain = [("stage_id", "=", s.id), ("active", "=", True)]
            if user_id:
                s_domain.append(("user_id", "=", user_id))
            elif not is_admin:
                s_domain.append(("user_id", "in", target_ids))
            stage_leads = lead.search_count(s_domain)
            if stage_leads > 0:
                stages.append({"name": s.name, "count": stage_leads})

        # Per-salesperson summary with days-since-booking
        cr = self.env.cr
        user_filter = ""
        params = []
        if user_id:
            user_filter = "AND l.user_id = %s"
            params = [user_id]
        elif not is_admin:
            user_filter = "AND l.user_id = %s"
            params = [current_user.id]

        won_stage_ids_sql = ",".join(map(str, won_stage_ids)) if won_stage_ids else "0"

        cr.execute(f"""
            SELECT
                u.id as user_id,
                COALESCE(p.name, u.login) as name,
                count(l.id) as total,
                SUM(CASE WHEN l.active=true AND l.stage_id IN ({won_stage_ids_sql}) THEN 1 ELSE 0 END) as won,
                SUM(CASE WHEN l.active=false OR (l.active=true AND l.probability=0) THEN 1 ELSE 0 END) as lost,
                MAX(CASE WHEN l.active=true AND l.stage_id IN ({won_stage_ids_sql}) THEN l.date_closed END) as last_win_date,
                MAX(l.write_date) as last_activity_date,
                SUM(CASE WHEN l.create_date >= NOW() - INTERVAL '30 days' THEN 1 ELSE 0 END) as last_30d,
                SUM(CASE WHEN l.create_date >= NOW() - INTERVAL '7 days' THEN 1 ELSE 0 END) as last_7d
            FROM crm_lead l
            JOIN res_users u ON l.user_id = u.id
            LEFT JOIN res_partner p ON u.partner_id = p.id
            WHERE u.active = true AND u.id > 2 {user_filter}
            GROUP BY u.id, p.name, u.login
            ORDER BY total DESC
        """, params)
        salesperson_data = []
        for r in cr.dictfetchall():
            last_win = r["last_win_date"]
            last_act = r["last_activity_date"]
            now = datetime.now()
            if last_win:
                days_since_win = (now - last_win.replace(tzinfo=None)).days
            else:
                days_since_win = None
            if last_act:
                days_since_act = (now - last_act.replace(tzinfo=None)).days
            else:
                days_since_act = None
            # "Days without booking" = days since last win; if no wins, days since last activity
            days_without_booking = days_since_win if days_since_win is not None else days_since_act
            salesperson_data.append({
                "id": r["user_id"],
                "name": r["name"],
                "leads": r["total"],
                "won": r["won"],
                "lost": r["lost"],
                "last_30d": r["last_30d"],
                "last_7d": r["last_7d"],
                "days_since_win": days_since_win,
                "days_since_activity": days_since_act,
                "days_without_booking": days_without_booking,
            })

        # Monthly trend
        monthly = []
        now = datetime.now()
        months = OrderedDict()
        for i in range(11, -1, -1):
            d = now - timedelta(days=30 * i)
            key = d.strftime("%Y-%m")
            months[key] = {"new": 0, "won": 0}

        month_domain = [("create_date", ">=", (now - timedelta(days=365)).strftime("%Y-%m-%d"))]
        if user_id:
            month_domain.append(("user_id", "=", user_id))
        elif not is_admin:
            month_domain.append(("user_id", "in", target_ids))

        for l in lead.search(month_domain):
            m = l.create_date.strftime("%Y-%m") if l.create_date else False
            if m and m in months:
                months[m]["new"] += 1
                if l.active and l.stage_id in won_stage_ids:
                    months[m]["won"] += 1
        for k, v in months.items():
            monthly.append({"month": k, "new": v["new"], "won": v["won"]})

        # Teams
        teams = []
        for t in team.search([("active", "=", True)]):
            t_domain = [("team_id", "=", t.id)]
            t_leads = lead.search_count(t_domain)
            t_won = lead.search_count(t_domain + [("stage_id", "in", won_stage_ids)])
            teams.append({
                "name": t.name,
                "leads": t_leads,
                "won": t_won,
                "target": t.dashboard_target_revenue or 0,
            })

        # All users for filter dropdown (admin only, exclude inactive)
        all_users = []
        if is_admin:
            for u in self.env["res.users"].search([("id", ">", 2), ("active", "=", True)]):
                all_users.append({"id": u.id, "name": u.partner_id.name or u.login})

        return {
            "is_admin": is_admin,
            "current_user_id": current_user.id,
            "all_users": all_users,
            "selected_user_id": user_id,
            "kpi": {
                "total_leads": total_leads,
                "pipeline": pipeline,
                "won": won,
                "lost": lost,
                "follow_up": follow_up,
                "research_done": research_done,
                "outreach_email": outreach_email,
                "proposal": proposal,
                "new_to_moved": new_to_moved,
                "booked": booked,
                "daily_activity": daily_activity,
                "total_orders": total_orders,
                "confirmed_orders": confirmed_orders,
                "confirmed_revenue": confirmed_revenue,
            },
            "objection_ranking": objection_ranking,
            "funnel": funnel_stages,
            "stages": stages,
            "salesperson": salesperson_data[:10] if is_admin and not user_id else salesperson_data,
            "monthly": monthly,
            "teams": teams,
        }

    @api.model
    def get_salesperson_detail(self, user_id):
        """Return detailed productivity data for a single salesperson."""
        cr = self.env.cr

        won_stage_ids = self.env["crm.stage"].search([("is_won", "=", True)]).ids
        won_stage_ids_sql = ",".join(map(str, won_stage_ids)) if won_stage_ids else "0"
        cr.execute(f"""
            SELECT
                count(*) as total,
                SUM(CASE WHEN active=true AND stage_id IN ({won_stage_ids_sql}) THEN 1 ELSE 0 END) as won,
                SUM(CASE WHEN active=false OR (active=true AND probability=0) THEN 1 ELSE 0 END) as lost,
                SUM(CASE WHEN create_date >= NOW() - INTERVAL '30 days' THEN 1 ELSE 0 END) as last_30d,
                SUM(CASE WHEN create_date >= NOW() - INTERVAL '7 days' THEN 1 ELSE 0 END) as last_7d,
                SUM(CASE WHEN date_open IS NOT NULL THEN 1 ELSE 0 END) as accepted,
                SUM(CASE WHEN day_open IS NOT NULL THEN day_open ELSE 0 END)::float /
                    NULLIF(SUM(CASE WHEN day_open IS NOT NULL THEN 1 ELSE 0 END), 0) as avg_days_to_close,
                MAX(CASE WHEN active=true AND stage_id IN ({won_stage_ids_sql}) THEN date_closed END) as last_win_date,
                MAX(write_date) as last_activity_date
            FROM crm_lead WHERE user_id = %s
        """, (user_id,))
        row = cr.dictfetchone()

        now = datetime.now()
        last_win = row["last_win_date"]
        last_act = row["last_activity_date"]
        days_since_win = (now - last_win.replace(tzinfo=None)).days if last_win else None
        days_since_act = (now - last_act.replace(tzinfo=None)).days if last_act else None

        # Stage breakdown
        lang = self.env.user.lang or 'en_US'
        cr.execute("""
            SELECT s.name->>%s as stage, count(*) as count
            FROM crm_lead l
            JOIN crm_stage s ON l.stage_id = s.id
            WHERE l.user_id = %s AND l.active = true
            GROUP BY s.name, s.sequence ORDER BY s.sequence
        """, (lang, user_id,))
        user_stages = [{"name": r["stage"], "count": r["count"]} for r in cr.dictfetchall()]

        # Activities
        cr.execute("""
            SELECT
                count(*) as total,
                SUM(CASE WHEN date_done IS NOT NULL THEN 1 ELSE 0 END) as done,
                SUM(CASE WHEN date_done IS NULL AND date_deadline < CURRENT_DATE THEN 1 ELSE 0 END) as overdue,
                SUM(CASE WHEN date_done IS NULL AND date_deadline >= CURRENT_DATE THEN 1 ELSE 0 END) as pending
            FROM mail_activity
            WHERE user_id = %s AND res_model = 'crm.lead'
        """, (user_id,))
        act = cr.dictfetchone()

        # Activity types breakdown
        cr.execute("""
            SELECT at.name->>%s as type, count(*) as total,
                SUM(CASE WHEN a.date_done IS NOT NULL THEN 1 ELSE 0 END) as done
            FROM mail_activity a
            JOIN mail_activity_type at ON a.activity_type_id = at.id
            WHERE a.user_id = %s AND a.res_model = 'crm.lead'
            GROUP BY at.name ORDER BY total DESC
        """, (lang, user_id,))
        act_types = [{"type": r["type"], "total": r["total"], "done": r["done"]} for r in cr.dictfetchall()]

        # Recent leads
        cr.execute("""
            SELECT l.name, l.create_date, l.probability, l.active,
                s.name->>%s as stage
            FROM crm_lead l
            LEFT JOIN crm_stage s ON l.stage_id = s.id
            WHERE l.user_id = %s
            ORDER BY l.create_date DESC LIMIT 10
        """, (lang, user_id,))
        recent_leads = [{
            "name": r["name"] or "Unnamed",
            "create_date": r["create_date"].strftime("%Y-%m-%d") if r["create_date"] else "",
            "probability": r["probability"] or 0,
            "active": r["active"],
            "stage": r["stage"] or "Unassigned",
        } for r in cr.dictfetchall()]

        return {
            "leads": {
                "total": row["total"] or 0,
                "won": row["won"] or 0,
                "lost": row["lost"] or 0,
                "last_30d": row["last_30d"] or 0,
                "last_7d": row["last_7d"] or 0,
                "accepted": row["accepted"] or 0,
                "avg_days_to_close": round(row["avg_days_to_close"] or 0, 1),
                "days_since_win": days_since_win,
                "days_since_activity": days_since_act,
                "days_without_booking": days_since_win if days_since_win is not None else days_since_act,
            },
            "stages": user_stages,
            "activities": {
                "total": act["total"] or 0,
                "done": act["done"] or 0,
                "overdue": act["overdue"] or 0,
                "pending": act["pending"] or 0,
            },
            "activity_types": act_types,
            "recent_leads": recent_leads,
        }

    @api.model
    def get_moved_today_leads(self, user_id=None):
        """Return IDs of leads that moved out of New stage (stage_id=1) today."""
        cr = self.env.cr
        fu_user_filter = ""
        fu_params = []
        if user_id:
            fu_user_filter = "AND mtv.create_uid = %s"
            fu_params = [user_id]
        cr.execute(f""" 
            SELECT DISTINCT mtv.res_id
            FROM mail_tracking_value mtv
            JOIN ir_model_fields imf ON imf.id = mtv.field_id
            WHERE imf.model = 'crm.lead'
              AND imf.name = 'stage_id'
              AND mtv.create_date::date = CURRENT_DATE
              AND mtv.old_value_integer = 1
              {fu_user_filter}
            ORDER BY mtv.res_id
        """, fu_params)
        return [r[0] for r in cr.fetchall()]

