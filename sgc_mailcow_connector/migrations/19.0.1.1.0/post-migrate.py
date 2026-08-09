def migrate(cr, version):
    # The 3 report actions were created with noupdate="1" data, so the XML
    # repoint to sgc.employee.document does not apply on upgrade — apply it here.
    cr.execute("""
        UPDATE ir_act_report_xml ar
        SET model = 'sgc.employee.document',
            binding_model_id = (SELECT id FROM ir_model WHERE model = 'sgc.employee.document')
        WHERE ar.id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'sgc_mailcow_connector'
              AND name IN ('action_report_nda', 'action_report_warning_letter',
                           'action_report_company_asset_handover')
        )
    """)
