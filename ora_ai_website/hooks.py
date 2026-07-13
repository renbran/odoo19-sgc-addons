def _uninstall_cleanup(env):
    """Clean up all module artifacts on uninstall."""
    env.cr.execute("""
        -- Clean up model fields added to res.config.settings
        DELETE FROM ir_model_fields
        WHERE model = 'res.config.settings'
          AND name IN ('is_website_assistant', 'website_assistant_id');

        -- Drop orphan columns
        ALTER TABLE res_config_settings
          DROP COLUMN IF EXISTS is_website_assistant,
          DROP COLUMN IF EXISTS website_assistant_id;
    """)
