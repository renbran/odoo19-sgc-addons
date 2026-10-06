def _uninstall_cleanup(env):
    """Clean up all module artifacts on uninstall."""
    env.cr.execute("""
        -- Remove our custom models
        DELETE FROM ir_model
        WHERE model IN ('vapi.inbound.call', 'vapi.squad', 'squad.members.line');

        -- Drop tables
        DROP TABLE IF EXISTS vapi_inbound_call CASCADE;
        DROP TABLE IF EXISTS vapi_squad CASCADE;
        DROP TABLE IF EXISTS squad_members_line CASCADE;
    """)
