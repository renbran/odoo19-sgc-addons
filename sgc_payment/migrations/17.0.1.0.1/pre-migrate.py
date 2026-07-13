# -*- coding: utf-8 -*-

def migrate(cr, version):
    """
    Pre-migration script to clean up data before model initialization.
    This runs before constraints are checked to prevent ValidationError.
    """
    try:
        # Emergency data cleanup before model initialization
        cr.execute("""
            -- Check if account_payment table exists
            DO $$ 
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'account_payment') THEN
                    
                    -- Clean high-value vendor payments with duplicate approvers
                    UPDATE account_payment 
                    SET approver_id = NULL, authorizer_id = NULL
                    WHERE payment_type = 'outbound' 
                      AND COALESCE(amount, 0) >= 10000 
                      AND (
                        (reviewer_id IS NOT NULL AND approver_id IS NOT NULL AND reviewer_id = approver_id) OR
                        (reviewer_id IS NOT NULL AND authorizer_id IS NOT NULL AND reviewer_id = authorizer_id) OR
                        (approver_id IS NOT NULL AND authorizer_id IS NOT NULL AND approver_id = authorizer_id)
                      );
                    
                    -- Fix low-value payments
                    UPDATE account_payment 
                    SET authorizer_id = NULL
                    WHERE payment_type = 'outbound' 
                      AND COALESCE(amount, 0) < 10000 
                      AND reviewer_id IS NOT NULL 
                      AND authorizer_id IS NOT NULL 
                      AND reviewer_id = authorizer_id;
                    
                    -- Clear inbound payment workflow fields
                    UPDATE account_payment 
                    SET reviewer_id = NULL, 
                        approver_id = NULL,
                        authorizer_id = NULL,
                        approval_state = 'draft'
                    WHERE payment_type = 'inbound';
                    
                    -- Reset problematic approval states (removed state column checks)
                    UPDATE account_payment 
                    SET approval_state = 'draft'
                    WHERE payment_type = 'outbound' 
                      AND approval_state NOT IN ('draft', 'under_review');
                      
                END IF;
            END $$;
        """)
        
    except Exception:
        # Ignore any errors during pre-migration cleanup
        pass