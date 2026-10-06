import json
from odoo import models, fields, api
from odoo.tools import html2plaintext


class CrmLeadScoringReport(models.AbstractModel):
    _name = 'lead.scoring.dashboard'
    _description = 'Lead Scoring Dashboard Report'

    def _compute_bant_score(self, lead):
        score = {'budget': 0, 'authority': 0, 'need': 0, 'timeline': 0, 'total': 0, 'grade': 'D'}
        company = lead.partner_name or lead.name or ''
        contact = lead.contact_name or ''
        email = lead.email_from or ''
        phone = lead.phone or ''
        website = lead.website or ''
        desc = lead.description or ''
        has_email = bool(email and '@' in email)
        has_phone = bool(phone)
        has_website = bool(website)
        has_desc = bool(desc and len(desc) > 50)

        budget_signals = 0
        if has_email:
            budget_signals += 1
        if has_phone:
            budget_signals += 1
        if has_website:
            budget_signals += 1
        score['budget'] = min(budget_signals * 25, 100)

        if 'ceo' in (contact or '').lower() or 'director' in (contact or '').lower() or 'partner' in (contact or '').lower() or 'manager' in (contact or '').lower():
            score['authority'] = 100
        elif contact:
            score['authority'] = 50
        else:
            score['authority'] = 25

        if has_desc:
            desc_lower = desc.lower()
            need_indicators = ['digital', 'tech', 'software', 'crm', 'website', 'marketing', 'automation', 'platform', 'solution', 'growth', 'online', 'brokerage', 'real estate']
            found = sum(1 for ind in need_indicators if ind in desc_lower)
            score['need'] = min(found * 20 + 20, 100)
            if 'urgent' in desc_lower or 'immediately' in desc_lower or 'asap' in desc_lower:
                score['timeline'] = 100
            elif 'growing' in desc_lower or 'expand' in desc_lower or 'new' in desc_lower:
                score['timeline'] = 75
            else:
                score['timeline'] = 50
        else:
            score['need'] = 30
            score['timeline'] = 40

        if lead.stage_id:
            stage_seq = lead.stage_id.sequence if hasattr(lead.stage_id, 'sequence') else 0
            if stage_seq >= 4:
                score['timeline'] = max(score['timeline'], 80)
            elif stage_seq >= 2:
                score['timeline'] = max(score['timeline'], 60)

        score['total'] = (score['budget'] + score['authority'] + score['need'] + score['timeline']) / 4
        if score['total'] >= 80:
            score['grade'] = 'A'
        elif score['total'] >= 60:
            score['grade'] = 'B'
        elif score['total'] >= 40:
            score['grade'] = 'C'
        else:
            score['grade'] = 'D'
        return score

    def _compute_closing_probability(self, lead, ai_score, bant_score):
        ai_weight = 0.35
        bant_weight = 0.35
        stage_weight = 0.15
        revenue_weight = 0.15

        ai_component = (ai_score or 0) * ai_weight
        bant_component = bant_score['total'] * bant_weight

        if lead.stage_id:
            stage_seq = lead.stage_id.sequence if hasattr(lead.stage_id, 'sequence') else 0
            stage_factor = min(stage_seq * 20, 100) * stage_weight
        else:
            stage_factor = 10 * stage_weight
        has_expected_revenue = (lead.expected_revenue or 0) > 0
        revenue_factor = (80 if has_expected_revenue else 40) * revenue_weight

        closing_prob = ai_component + bant_component + stage_factor + revenue_factor
        return min(closing_prob, 100)

    def generate_dashboard(self):
        leads = self.env['crm.lead'].search([
            '|',
            ('ai_enrichment_status', 'in', ['scored', 'enriched']),
            ('ai_probability_score', '>', 0),
        ], order='ai_probability_score DESC', limit=50)
        if not leads:
            leads = self.env['crm.lead'].search([], order='id DESC', limit=20)

        rows = []
        for lead in leads:
            bant = self._compute_bant_score(lead)
            closing = self._compute_closing_probability(lead, lead.ai_probability_score, bant)
            play = lead.x_sales_play or ''
            territory = lead.x_territory or ''
            emirate = lead.x_emirate or ''
            industry_fit = lead.x_industry_fit or 'unknown'
            authority = lead.x_contact_authority or 'unknown'
            play_cls = 'hot' if play in ('Immediate Demo',) else ('warm' if 'Call' in play or 'Nurture' in play else 'cold')
            rows.append({
                'id': lead.id,
                'name': lead.name or 'Unnamed',
                'contact': lead.contact_name or '',
                'email': lead.email_from or '',
                'phone': lead.phone or '',
                'company': lead.partner_name or '',
                'website': lead.website or '',
                'stage': lead.stage_id.name or 'New',
                'ai_score': lead.ai_probability_score or 0,
                'completeness': lead.ai_completeness_score or 0,
                'clarity': lead.ai_clarity_score or 0,
                'engagement': lead.ai_engagement_score or 0,
                'bant_budget': bant['budget'],
                'bant_authority': bant['authority'],
                'bant_need': bant['need'],
                'bant_timeline': bant['timeline'],
                'bant_total': bant['total'],
                'bant_grade': bant['grade'],
                'closing_probability': round(closing, 0),
                'sales_play': play,
                'play_cls': play_cls,
                'territory': territory or 'Unknown',
                'emirate': emirate or 'Unknown',
                'industry_fit': industry_fit,
                'authority': authority,
            })

        n = len(rows)
        ai_avg = sum(r['ai_score'] for r in rows) / n if n else 0
        bant_avg = sum(r['bant_total'] for r in rows) / n if n else 0
        closing_avg = sum(r['closing_probability'] for r in rows) / n if n else 0

        high_count = sum(1 for r in rows if r['closing_probability'] >= 60)
        medium_count = sum(1 for r in rows if 40 <= r['closing_probability'] < 60)
        low_count = sum(1 for r in rows if r['closing_probability'] < 40)
        a_count = sum(1 for r in rows if r['bant_grade'] == 'A')
        comp_avg = sum(r['completeness'] for r in rows) / n if n else 0

        rows.sort(key=lambda x: x['closing_probability'], reverse=True)

        def sbar(val, w=160):
            pct = min(val * 100 / 100, 100)
            c = '#1a7f37' if val >= 70 else ('#e6a817' if val >= 40 else '#cf222e')
            return '<div style="background:#e8e8e8;border-radius:4px;width:{}px;height:14px;display:inline-block;vertical-align:middle"><div style="background:{};width:{}%;height:14px;border-radius:4px"></div></div>'.format(w, c, pct)

        def mcard(title, value, color, sub=''):
            return '<div style="flex:1;text-align:center;padding:16px 12px;background:white;border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,0.08)"><div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px">{}</div><div style="font-size:32px;font-weight:700;color:{}">{}</div><div style="font-size:11px;color:#999">{}</div></div>'.format(title, color, value, sub)

        plays_dist = {}
        for r in rows:
            p = r['sales_play'] or 'Uncategorized'
            plays_dist[p] = plays_dist.get(p, 0) + 1

        territories = {}
        for r in rows:
            t = r['territory'] or 'Unknown'
            territories[t] = territories.get(t, 0) + 1

        def cf(r):
            return r['company'] or r['name']

        pipe_rows = ''
        for r in rows:
            pct = r['closing_probability']
            c = '#1a7f37' if pct >= 60 else ('#e6a817' if pct >= 40 else '#cf222e')
            pipe_rows += '<div style="display:flex;align-items:center;margin:4px 0;gap:8px"><span style="min-width:180px;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{}</span><div style="flex:1;background:#e8e8e8;border-radius:4px;height:12px"><div style="background:{};width:{}%;height:12px;border-radius:4px"></div></div><span style="min-width:40px;text-align:right;font-size:12px;font-weight:600;color:{}">{}%</span></div>'.format(cf(r), c, pct, c, pct)

        play_rows = ''
        for play, count in sorted(plays_dist.items(), key=lambda x: -x[1]):
            cls = 'hot' if 'Demo' in play else ('warm' if 'Call' in play or 'Nurture' in play or 'Re-engagement' in play else 'cold')
            play_rows += '<div class="insight-item"><span class="tag-{}" style="padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">{}</span> <strong>{}</strong></div>'.format(cls, count, play)

        territory_rows = ''
        for t, count in sorted(territories.items(), key=lambda x: -x[1]):
            pct = count * 100 / n if n else 0
            territory_rows += '<div class="insight-item"><strong>{}</strong> <span style="float:right">{}/{} ({:.0f}%)</span></div>'.format(t, count, n, pct)

        table_rows = ''
        for r in rows:
            bgc = {'A': '#1a7f37', 'B': '#9a6700', 'C': '#cf222e', 'D': '#82071e'}.get(r['bant_grade'], '#888')
            contact = r['contact'] if r['contact'] else '<span style="color:#bbb">\u2014</span>'
            close_color = '#1a7f37' if r['closing_probability'] >= 60 else ('#9a6700' if r['closing_probability'] >= 40 else '#cf222e')
            play_badge = '<span class="tag-{}" style="padding:1px 6px;border-radius:3px;font-size:10px">{}</span>'.format(
                r['play_cls'] or 'cold', r['sales_play'][:20] if r['sales_play'] else '')
            table_rows += '<tr style="border-bottom:1px solid #eee"><td style="padding:8px 6px;font-weight:600;font-size:13px">{}</td><td style="padding:8px 6px;font-size:12px;color:#666">{}</td><td style="padding:8px 6px;font-size:12px">{}</td><td style="padding:8px 6px">{}</td><td style="padding:8px 6px">{}</td><td style="padding:8px 6px;text-align:center"><span style="background:{}20;color:{};padding:2px 8px;border-radius:4px;font-weight:700;font-size:13px">{}</span></td><td style="padding:8px 6px;text-align:center;font-weight:700;font-size:14px;color:{}">{}%</td><td style="padding:8px 6px;font-size:11px">{}</td></tr>'.format(
                cf(r), contact, r['stage'], sbar(r['ai_score'], 80), sbar(r['bant_total'], 80), bgc, bgc, r['bant_grade'], close_color, r['closing_probability'], play_badge)

        now = fields.Datetime.now().strftime('%Y-%m-%d %H:%M')

        html = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background: #f0f2f5; color: #222; }}
.dash-wrap {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
.header {{ margin-bottom: 24px; }}
.header h1 {{ font-size: 24px; font-weight: 700; margin: 0 0 4px 0; }}
.header .subtitle {{ font-size: 13px; color: #666; }}
.metrics-row {{ display: flex; gap: 12px; margin-bottom: 20px; }}
.two-col {{ display: flex; gap: 16px; margin-bottom: 20px; }}
.col {{ flex: 1; background: white; border-radius: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); padding: 16px; }}
.col h3 {{ font-size: 14px; font-weight: 600; margin: 0 0 12px 0; color: #333; text-transform: uppercase; letter-spacing: 0.3px; }}
.insight-item {{ padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 13px; line-height: 1.5; }}
.insight-item:last-child {{ border-bottom: none; }}
.insight-item strong {{ color: #333; }}
.tag-hot {{ background:#dafbe1; color:#1a7f37; }}
.tag-warm {{ background:#fff8c5; color:#9a6700; }}
.tag-cold {{ background:#ffe8e8; color:#cf222e; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ padding:8px 6px; text-align:left; font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.5px; border-bottom:2px solid #eee; }}
.rec-box {{ background:#f6f8fa; border-radius:8px; padding:12px; margin-top:8px; font-size:12px; line-height:1.5; }}
.rec-box strong {{ color:#333; }}
</style>
</head>
<body>
<div class="dash-wrap">

<div class="header">
<h1>AI Lead Scoring & Closing Dashboard</h1>
<div class="subtitle">Executive Summary &middot; {n} leads analyzed | Generated {now}</div>
</div>

<div class="metrics-row">
{mcard_ai}
{mcard_bant}
{mcard_close}
{mcard_count}
</div>

<div class="two-col">
<div class="col">
<h3>Pipeline Health</h3>
<div style="display:flex;gap:12px;margin-bottom:12px">
<div style="flex:1;text-align:center;padding:8px;background:#dafbe1;border-radius:8px"><div style="font-size:20px;font-weight:700;color:#1a7f37">{high}</div><div style="font-size:10px;color:#1a7f37;text-transform:uppercase">Hot (&ge;60%)</div></div>
<div style="flex:1;text-align:center;padding:8px;background:#fff8c5;border-radius:8px"><div style="font-size:20px;font-weight:700;color:#9a6700">{med}</div><div style="font-size:10px;color:#9a6700;text-transform:uppercase">Warm (40-60%)</div></div>
<div style="flex:1;text-align:center;padding:8px;background:#ffe8e8;border-radius:8px"><div style="font-size:20px;font-weight:700;color:#cf222e">{low}</div><div style="font-size:10px;color:#cf222e;text-transform:uppercase">Cold (&lt;40%)</div></div>
</div>
<h3>Lead Probability Breakdown</h3>
{pipe_rows}
</div>

<div class="col">
<h3>AI Score Distribution</h3>
<div style="display:flex;gap:12px;margin-bottom:12px">
<div style="flex:1;text-align:center;padding:8px;background:#dafbe1;border-radius:8px"><div style="font-size:20px;font-weight:700;color:#1a7f37">{ai_avg:.0f}</div><div style="font-size:10px;color:#1a7f37;text-transform:uppercase">Avg AI Score</div></div>
<div style="flex:1;text-align:center;padding:8px;background:#dafbe1;border-radius:8px"><div style="font-size:20px;font-weight:700;color:#1a7f37">{bant_avg:.0f}</div><div style="font-size:10px;color:#1a7f37;text-transform:uppercase">Avg BANT</div></div>
<div style="flex:1;text-align:center;padding:8px;background:#dafbe1;border-radius:8px"><div style="font-size:20px;font-weight:700;color:#1a7f37">{closing_avg:.0f}</div><div style="font-size:10px;color:#1a7f37;text-transform:uppercase">Avg Closing</div></div>
</div>

<h3>Key Takeaways for Sales Team</h3>
<div class="insight-item"><strong>Focus on Hot Leads:</strong> {high} leads show &ge;60% closing probability. Prioritize immediate outreach with personalized demos.</div>
<div class="insight-item"><strong>BANT Grade A</strong> leads ({a_count}) have clear budget signals and decision-maker contacts &mdash; these are ready for proposal.</div>
<div class="insight-item"><strong>Warm leads</strong> ({med}) need engagement reactivation. Send case studies and schedule discovery calls.</div>
<div class="insight-item"><strong>Completeness Gap:</strong> Avg completeness score is {comp_avg:.0f}%. Leads missing phone/description need enrichment before full scoring.</div>
<div class="insight-item"><strong>Recommended Action:</strong> Use "B2B Full Score" button on individual leads or batch enrichment for enriched scoring with location intelligence.</div>
</div>
</div>

<div class="two-col">
<div class="col" style="flex:0.8">
<h3>Territory Distribution</h3>
{territory_rows}
<h3 style="margin-top:16px">Recommended Sales Plays</h3>
{play_rows}
</div>

<div class="col" style="flex:1.6">
<h3>Lead Scoring Table</h3>
<table>
<thead><tr><th>Company</th><th>Contact</th><th>Stage</th><th>AI Score</th><th>BANT</th><th>Grade</th><th>Close Prob</th><th>Sales Play</th></tr></thead>
<tbody>
{table_rows}
</tbody>
</table>
</div>

<div class="col" style="flex:0.6">
<h3>BANT Framework Legend</h3>
<div style="font-size:12px;line-height:1.6;color:#555">
<p><strong>B</strong> &mdash; <strong>Budget</strong>: Email, phone, website signals indicate capacity to invest</p>
<p><strong>A</strong> &mdash; <strong>Authority</strong>: Contact role/title (CEO, Director, Partner, Manager)</p>
<p><strong>N</strong> &mdash; <strong>Need</strong>: Description contains need keywords (digital, tech, platform, etc.)</p>
<p><strong>T</strong> &mdash; <strong>Timeline</strong>: Urgency signals + pipeline stage progression</p>
<hr style="border:none;border-top:1px solid #eee;margin:12px 0">
<h4 style="font-size:12px;margin:8px 0">B2B Tech Investment Closing Checklist</h4>
<ul style="padding-left:16px;margin:4px 0">
<li>&#x2705; Digital maturity assessment</li>
<li>&#x2705; Tech stack audit &amp; compatibility</li>
<li>&#x2705; ROI projection &amp; business case</li>
<li>&#x2705; Decision-maker alignment</li>
<li>&#x2705; Budget verification</li>
<li>&#x2705; Implementation timeline</li>
<li>&#x2705; Competitive landscape review</li>
<li>&#x2705; Stakeholder buy-in confirmed</li>
<li>&#x2705; Contract &amp; legal review</li>
<li>&#x2705; Onboarding &amp; training plan</li>
</ul>
<hr style="border:none;border-top:1px solid #eee;margin:12px 0">
<h4 style="font-size:12px;margin:8px 0">Executive Insights</h4>
<div class="rec-box">
<strong>Pipeline Overview:</strong> {n} leads with avg closing prob {closing_avg:.0f}%. Top priority leads show strong digital presence signals (LinkedIn, Instagram, FB) indicating tech awareness and digital maturity.
</div>
</div>
</div>
</div>

</div>
</body>
</html>'''.format(
            n=n, now=now,
            mcard_ai=mcard('AI Score Avg', '{:.0f}%'.format(ai_avg), '#1a7f37', 'LLM-powered lead quality'),
            mcard_bant=mcard('BANT Score Avg', '{:.0f}%'.format(bant_avg), '#1a7f37', 'Budget-Authority-Need-Timeline'),
            mcard_close=mcard('Closing Prob Avg', '{:.0f}%'.format(closing_avg), '#1a7f37', 'Weighted composite score'),
            mcard_count=mcard('Leads Analyzed', str(n), '#0969da', 'In current pipeline'),
            high=high_count, med=medium_count, low=low_count, a_count=a_count,
            pipe_rows=pipe_rows, table_rows=table_rows, territory_rows=territory_rows, play_rows=play_rows,
            ai_avg=ai_avg, bant_avg=bant_avg, closing_avg=closing_avg, comp_avg=comp_avg,
        )

        return html
