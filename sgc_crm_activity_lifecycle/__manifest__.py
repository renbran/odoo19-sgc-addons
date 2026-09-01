{
    'name': 'SGC CRM Activity Lifecycle',
    'version': '19.0.1.0.0',
    'category': 'CRM',
    'summary': 'Auto-cancel overdue CRM activities and clear stale activities on opportunity reassignment',
    'description': """
        SGC CRM Activity Lifecycle
        ==========================

        Two automated lifecycle rules for CRM activities:

        1. **Reassignment cleanup**: When an opportunity's owner (user_id) changes,
           all non-done activities on that lead are unlinked. This prevents stale
           tasks from cluttering the new salesperson's activity list.

        2. **Auto-cancel overdue**: A daily cron job cancels any CRM activity that
           has been overdue for 14+ days. Uses action_cancel() to properly record
           the cancellation with feedback.
    """,
    'author': 'SGC Tech AI',
    'license': 'LGPL-3',
    'depends': ['crm', 'mail'],
    'data': [
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
