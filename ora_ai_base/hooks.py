def _uninstall_cleanup(env):
    """Clean up all module artifacts on uninstall."""
    env.cr.execute("""
        -- Remove our custom models
        DELETE FROM ir_model
        WHERE model IN ('ora.ai', 'ora.file', 'ora.language',
                        'provider.model', 'transcriber.model');

        -- Drop tables
        DROP TABLE IF EXISTS ora_ai CASCADE;
        DROP TABLE IF EXISTS ora_file CASCADE;
        DROP TABLE IF EXISTS ora_language CASCADE;
        DROP TABLE IF EXISTS provider_model CASCADE;
        DROP TABLE IF EXISTS transcriber_model CASCADE;
        DROP TABLE IF EXISTS ora_ai_ora_file_rel CASCADE;
        DROP TABLE IF EXISTS ora_ai_ora_language_rel CASCADE;
    """)
