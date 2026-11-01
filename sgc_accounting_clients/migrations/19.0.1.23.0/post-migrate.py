# -*- coding: utf-8 -*-
"""A Chart of Accounts file that changed nothing goes back to its owner for
approval (since 19.0.1.23.0), instead of staying failed."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE sgc_accounting_upload upload
           SET booking_state = 'approval', approved_by_id = NULL, approved_sha256 = NULL
         WHERE upload.doc_type = 'chart_of_accounts'
           AND upload.booking_state = 'failed'
           AND EXISTS (SELECT 1 FROM sgc_accounting_upload_log log
                        WHERE log.upload_id = upload.id AND log.event = 'failed'
                          AND log.message LIKE 'Nothing was changed%%')
           AND NOT EXISTS (SELECT 1 FROM sgc_accounting_upload_log log
                            WHERE log.upload_id = upload.id AND log.event = 'applied')
        """
    )
