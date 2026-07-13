import base64
import logging

_logger = logging.getLogger(__name__)

ACK_HTML = """<div style="background-color: #F5F1E8; padding: 30px 20px; font-family: Arial, Helvetica, sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto;">
<tr><td style="background-color: #B89968; height: 4px; font-size: 0; line-height: 0; border-radius: 4px 4px 0 0;">&nbsp;</td></tr>
<tr>
<td style="background-color: #FFFFFF; border: 1px solid #B89968; border-top: none; padding: 30px; border-radius: 0 0 4px 4px; color: #1A1A1A; font-size: 14px; line-height: 1.6;">
Hello,<br/><br/>
We confirm we successfully received your application for the job
"<a t-att-href="hasattr(object.job_id, 'website_url') and object.job_id.website_url or ''" style="color: #B89968; text-decoration: none;"><strong t-out="object.job_id.name or ''">Experienced Developer</strong></a>" at <strong t-out="object.company_id.name or ''">YourCompany</strong>.<br/><br/>
We will come back to you shortly.
<div t-if="'website_url' in object.job_id and object.job_id.website_url" style="padding: 16px 8px 16px 8px;">
<a t-att-href="object.job_id.website_url" style="background-color: #B89968; text-decoration: none; color: #FFFFFF; padding: 10px 24px; border-radius: 4px; display: inline-block; font-size: 14px;">Job Description</a>
</div>
<hr style="border: none; border-top: 1px solid #EDE8DD; margin: 24px 0;"/>
<t t-if="object.user_id">
<h3 style="color: #B89968; font-size: 15px; margin: 0 0 8px 0;"><strong>Your Contact:</strong></h3>
<p style="margin: 0; color: #4A4A4A;">
<strong style="color: #1A1A1A;" t-out="object.user_id.name or ''">Mitchell Admin</strong><br/>
Email: <t t-out="object.user_id.email or ''">admin@yourcompany.example.com</t><br/>
Phone: <t t-out="object.user_id.phone or ''">+1 650-123-4567</t>
</p>
<hr style="border: none; border-top: 1px solid #EDE8DD; margin: 24px 0;"/>
</t>
<h3 style="color: #B89968; font-size: 15px; margin: 0 0 8px 0;"><strong>What is the next step?</strong></h3>
We usually <strong>answer applications within a few days.</strong><br/><br/>
Feel free to <strong>contact us if you want a faster feedback</strong> or if you don't get news from us quickly enough (just reply to this email).
<hr style="border: none; border-top: 1px solid #EDE8DD; margin: 24px 0;"/>
<table cellpadding="0" cellspacing="0" style="color: #4A4A4A; font-size: 13px;">
<t t-if="object.job_id.address_id.name"><tr><td><strong style="color: #1A1A1A;" t-out="object.job_id.address_id.name or ''">Teksa SpA</strong></td></tr></t>
<t t-if="object.job_id.address_id.street"><tr><td t-out="object.job_id.address_id.street or ''">Puerto Madero 9710</td></tr></t>
<t t-if="object.job_id.address_id.street2"><tr><td t-out="object.job_id.address_id.street2 or ''">Of A15, Santiago (RM)</td></tr></t>
<t t-if="object.job_id.address_id.city or object.job_id.address_id.state_id.name or object.job_id.address_id.zip"><tr><td><t t-out="object.job_id.address_id.city or ''">Pudahuel</t><t t-if="object.job_id.address_id.city and (object.job_id.address_id.state_id.name or object.job_id.address_id.zip)">,</t> <t t-out="object.job_id.address_id.state_id.name or ''">C1</t> <t t-out="object.job_id.address_id.zip or ''">98450</t></td></tr></t>
<t t-if="object.job_id.address_id.country_id.name"><tr><td t-out="object.job_id.address_id.country_id.name or ''">Argentina</td></tr></t>
</table>
</td>
</tr>
<tr>
<td style="text-align: center; padding-top: 16px; color: #757575; font-size: 12px; line-height: 1.5;">
<t t-out="object.company_id.name or ''">Scholarix Global Consulting</t><br/>
This email was sent regarding your job application.<br/>
Powered by <a href="https://sgctech.ai" style="color: #B89968; text-decoration: none;">SGC Tech AI</a>
</td>
</tr>
</table>
</div>"""

INTEREST_HTML = """<div style="background-color: #F5F1E8; padding: 30px 20px; font-family: Arial, Helvetica, sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto;">
<tr><td style="background-color: #B89968; height: 4px; font-size: 0; line-height: 0; border-radius: 4px 4px 0 0;">&nbsp;</td></tr>
<tr>
<td style="background-color: #FFFFFF; border: 1px solid #B89968; border-top: none; padding: 30px; border-radius: 0 0 4px 4px; color: #1A1A1A; font-size: 14px; line-height: 1.6;">
<div style="text-align: center; padding-bottom: 8px;">
<h2 style="color: #B89968; margin: 0 0 4px 0; font-size: 22px;">Congratulations!</h2>
<div style="color: #4A4A4A;">Your resume has been positively reviewed.</div>
</div>
We just reviewed your resume, and it caught our attention. As we think you might be great for the position, your application has been short listed for a call or an interview.<br/><br/>
<div t-if="'website_url' in object.job_id and object.job_id.website_url" style="padding: 16px 8px 16px 8px; text-align: center;">
<a t-att-href="object.job_id.website_url" style="background-color: #B89968; text-decoration: none; color: #FFFFFF; padding: 10px 24px; border-radius: 4px; display: inline-block; font-size: 14px;">Job Description</a>
</div>
<t t-if="object.user_id">
<p style="color: #4A4A4A;">
You will soon be contacted by:<br/>
<strong style="color: #1A1A1A;" t-out="object.user_id.name or ''">Mitchell Admin</strong><br/>
<span>Email: <t t-out="object.user_id.email or ''">admin@yourcompany.example.com</t></span><br/>
<span>Phone: <t t-out="object.user_id.phone or ''">+1 650-123-4567</t></span>
</p><br/>
</t>
See you soon,
<div style="font-size: 12px; color: #757575;">
-- <br/>
The HR Team
<t t-if="'website_url' in object.job_id and hasattr(object.job_id, 'website_url') and object.job_id.website_url">
<br/>Discover <a href="/jobs" style="text-decoration: none; color: #B89968;">all our jobs</a>.
</t>
</div>
<hr style="border: none; border-top: 1px solid #EDE8DD; margin: 24px 0;"/>
<h3 style="color: #B89968; font-size: 15px; margin: 0 0 8px 0;"><strong>What is the next step?</strong></h3>
We usually <strong>answer applications within a few days</strong>.<br/><br/>
The next step is either a call or a meeting in our offices.<br/><br/>
Feel free to <strong>contact us if you want a faster feedback</strong> or if you don't get news from us quickly enough (just reply to this email).
<hr style="border: none; border-top: 1px solid #EDE8DD; margin: 24px 0;"/>
<table cellpadding="0" cellspacing="0" style="color: #4A4A4A; font-size: 13px;">
<t t-set="location" t-value=""/>
<t t-if="object.job_id.address_id.name"><tr><td><strong style="color: #1A1A1A;" t-out="object.job_id.address_id.name or ''">Teksa SpA</strong></td></tr></t>
<t t-if="object.job_id.address_id.street"><tr><td t-out="object.job_id.address_id.street or ''">Puerto Madero 9710</td></tr></t>
<t t-if="object.job_id.address_id.street2"><tr><td t-out="object.job_id.address_id.street2 or ''">Of A15, Santiago (RM)</td></tr></t>
<t t-if="object.job_id.address_id.city or object.job_id.address_id.state_id.name or object.job_id.address_id.zip"><tr><td><t t-out="object.job_id.address_id.city or ''">Pudahuel</t><t t-if="object.job_id.address_id.city and (object.job_id.address_id.state_id.name or object.job_id.address_id.zip)">,</t> <t t-out="object.job_id.address_id.state_id.name or ''">C1</t> <t t-out="object.job_id.address_id.zip or ''">98450</t></td></tr></t>
<t t-if="object.job_id.address_id.country_id.name"><tr><td t-out="object.job_id.address_id.country_id.name or ''">Argentina</td></tr></t>
</table>
</td>
</tr>
<tr>
<td style="text-align: center; padding-top: 16px; color: #757575; font-size: 12px; line-height: 1.5;">
<t t-out="object.company_id.name or ''">Scholarix Global Consulting</t><br/>
This email was sent regarding your job application.<br/>
Powered by <a href="https://sgctech.ai" style="color: #B89968; text-decoration: none;">SGC Tech AI</a>
</td>
</tr>
</table>
</div>"""

REFUSE_HTML = """<div style="background-color: #F5F1E8; padding: 30px 20px; font-family: Arial, Helvetica, sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto;">
<tr><td style="background-color: #B89968; height: 4px; font-size: 0; line-height: 0; border-radius: 4px 4px 0 0;">&nbsp;</td></tr>
<tr>
<td style="background-color: #FFFFFF; border: 1px solid #B89968; border-top: none; padding: 30px; border-radius: 0 0 4px 4px; color: #1A1A1A; font-size: 14px; line-height: 1.6;">
Hello,<br/><br/>
Thank you for your interest in joining the
<b><t t-out="object.company_id.name or ''">YourCompany</t></b> team. We wanted to let you know that, although your resume is competitive, our hiring team reviewed your application and <b>did not select it for further consideration</b>.<br/><br/>
Please note that recruiting is hard, and we can make mistakes. Do not hesitate to reply to this email if you think we made a mistake, or if you want more information about our decision.<br/><br/>
We will, however, keep your resume on record and get in touch with you about future opportunities that may be a better fit for your skills and experience.<br/><br/>
We wish you all the best in your job search and hope we will have the chance to consider you for another role in the future.<br/><br/>
Thank you,
<div style="font-size: 12px; color: #757575;">
<t t-if="object.user_id">
-- <br/>
<strong style="color: #1A1A1A;" t-out="object.user_id.name or ''">Mitchell Admin</strong><br/>
Email: <t t-out="object.user_id.email or ''">admin@yourcompany.example.com</t><br/>
Phone: <t t-out="object.user_id.phone or ''">+1 650-123-4567</t>
</t>
<t t-else="">
-- <br/>
<t t-out="object.company_id.name or ''">YourCompany</t><br/>
The HR Team
</t>
</div>
</td>
</tr>
<tr>
<td style="text-align: center; padding-top: 16px; color: #757575; font-size: 12px; line-height: 1.5;">
<t t-out="object.company_id.name or ''">Scholarix Global Consulting</t><br/>
This email was sent regarding your job application.<br/>
Powered by <a href="https://sgctech.ai" style="color: #B89968; text-decoration: none;">SGC Tech AI</a>
</td>
</tr>
</table>
</div>"""

NOT_INTERESTED_HTML = """<div style="background-color: #F5F1E8; padding: 30px 20px; font-family: Arial, Helvetica, sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto;">
<tr><td style="background-color: #B89968; height: 4px; font-size: 0; line-height: 0; border-radius: 4px 4px 0 0;">&nbsp;</td></tr>
<tr>
<td style="background-color: #FFFFFF; border: 1px solid #B89968; border-top: none; padding: 30px; border-radius: 0 0 4px 4px; color: #1A1A1A; font-size: 14px; line-height: 1.6;">
Dear,<br/><br/>
We would like to thank you for your interest and your time.<br/>
We wish you all the best in your future endeavors.<br/><br/>
Best,<br/>
<div style="font-size: 12px; color: #757575;">
<t t-if="object.user_id">
-- <br/>
<strong style="color: #1A1A1A;" t-out="object.user_id.name or ''">Marc Demo</strong><br/>
Email: <t t-out="object.user_id.email or ''">mark.brown23@example.com</t><br/>
Phone: <t t-out="object.user_id.phone or ''">+1 650-123-4567</t>
</t>
<t t-else="">
-- <br/>
<t t-out="object.company_id.name or ''">YourCompany</t><br/>
The HR Team
</t>
</div>
</td>
</tr>
<tr>
<td style="text-align: center; padding-top: 16px; color: #757575; font-size: 12px; line-height: 1.5;">
<t t-out="object.company_id.name or ''">Scholarix Global Consulting</t><br/>
This email was sent regarding your job application.<br/>
Powered by <a href="https://sgctech.ai" style="color: #B89968; text-decoration: none;">SGC Tech AI</a>
</td>
</tr>
</table>
</div>"""

AVATAR_SVG = base64.b64encode(
    b'<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192">'
    b'<circle cx="96" cy="96" r="96" fill="#B89968"/>'
    b'<text x="96" y="106" font-family="Arial,Helvetica,sans-serif" font-size="48" font-weight="bold" fill="#FFFFFF" text-anchor="middle" dominant-baseline="central">AIRA</text>'
    b'</svg>'
).decode()

TEMPLATE_BODIES = {
    "email_template_data_applicant_congratulations": ACK_HTML,
    "email_template_data_applicant_interest": INTEREST_HTML,
    "email_template_data_applicant_refuse": REFUSE_HTML,
    "email_template_data_applicant_not_interested": NOT_INTERESTED_HTML,
}


def post_init_hook(cr, registry):
    """Run after module install/upgrade to apply branding changes."""
    # 1. Rename OdooBot partner to AIRA SGC TECH
    cr.execute(
        "UPDATE res_partner SET name = 'AIRA SGC TECH' WHERE id = 2 AND name = 'OdooBot'"
    )
    if cr.rowcount:
        _logger.info("Renamed OdooBot partner → AIRA SGC TECH")

    # 2. Set avatar on the bot partner
    cr.execute(
        "UPDATE res_partner SET image_1920 = %s WHERE id = 2",
        [AVATAR_SVG],
    )
    if cr.rowcount:
        _logger.info("Set avatar for AIRA SGC TECH")

    # 3. Update recruitment email template bodies with branded HTML
    for xml_name, body_html in TEMPLATE_BODIES.items():
        cr.execute(
            """UPDATE mail_template mt
               SET body_html = %s
               FROM ir_model_data imd
               WHERE imd.model = 'mail.template'
                 AND imd.module = 'hr_recruitment'
                 AND imd.name = %s
                 AND imd.res_id = mt.id""",
            [body_html, xml_name],
        )
        if cr.rowcount:
            _logger.info("Updated mail template %s", xml_name)
