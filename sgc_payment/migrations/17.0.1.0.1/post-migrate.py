# -*- coding: utf-8 -*-

def migrate(cr, version):
    """
    Migration script to clean up existing payment records that might violate
    the new enhanced workflow validation constraints.
    
    This prevents ValidationError during module installation/upgrade.
    """
    try:
        # Check if account_payment table exists
        cr.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'account_payment'
            );
        """)
        
        table_exists = cr.fetchone()[0]
        if not table_exists:
            return
            
        # Check if the workflow columns exist before trying to update them
        cr.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'account_payment' 
              AND column_name IN ('reviewer_id', 'approver_id', 'authorizer_id', 'approval_state', 'payment_type');
        """)
        
        existing_columns = [row[0] for row in cr.fetchall()]
        
        # Only proceed if the workflow columns exist
        if 'reviewer_id' in existing_columns and 'approver_id' in existing_columns:
            
            # Clean up high-value vendor payments with duplicate approvers
            cr.execute("""
                UPDATE account_payment 
                SET approver_id = NULL, authorizer_id = NULL
                WHERE payment_type = 'outbound' 
                  AND COALESCE(amount, 0) >= 10000 
                  AND (
                    (reviewer_id IS NOT NULL AND approver_id IS NOT NULL AND reviewer_id = approver_id) OR
                    (reviewer_id IS NOT NULL AND authorizer_id IS NOT NULL AND reviewer_id = authorizer_id) OR
                    (approver_id IS NOT NULL AND authorizer_id IS NOT NULL AND approver_id = authorizer_id)
                  );
            """)
            
            # Fix low-value payments - clear authorizer if same as reviewer
            cr.execute("""
                UPDATE account_payment 
                SET authorizer_id = NULL
                WHERE payment_type = 'outbound' 
                  AND COALESCE(amount, 0) < 10000 
                  AND reviewer_id IS NOT NULL 
                  AND authorizer_id IS NOT NULL 
                  AND reviewer_id = authorizer_id;
            """)
            
            # Reset approval states for problematic records (if approval_state column exists)
            if 'approval_state' in existing_columns:
                # Reset vendor payments in inconsistent states (removed state column checks)
                cr.execute("""
                    UPDATE account_payment 
                    SET approval_state = 'draft'
                    WHERE payment_type = 'outbound' 
                      AND approval_state NOT IN ('draft', 'under_review');
                """)
            
            # Clear workflow fields for customer receipts (inbound payments)
            cr.execute("""
                UPDATE account_payment 
                SET reviewer_id = NULL, 
                    approver_id = NULL,
                    authorizer_id = NULL
                WHERE payment_type = 'inbound' 
                  AND (reviewer_id IS NOT NULL OR approver_id IS NOT NULL OR authorizer_id IS NOT NULL);
            """)
            
            # Reset approval_state for inbound payments if column exists
            if 'approval_state' in existing_columns:
                cr.execute("""
                    UPDATE account_payment 
                    SET approval_state = 'draft'
                    WHERE payment_type = 'inbound' 
                      AND approval_state != 'draft';
                """)
                
    except Exception as e:
        # Log the error but don't fail the migration
        # This ensures the module can still be installed even if data cleanup fails
        import logging
        _logger = logging.getLogger(__name__)
        _logger.warning("Payment data cleanup during migration failed: %s", str(e))
        pass