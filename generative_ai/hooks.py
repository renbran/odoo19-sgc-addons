def _uninstall_cleanup(env):
    """Ensure complete cleanup of all module artifacts on uninstall."""
    env.cr.execute("""
        -- Views, menus, and actions are cleaned by Odoo's uninstall mechanism.
        -- This hook handles edge cases where ORM-level cleanup may be partial.

        -- Clean up model fields added to res.config.settings
        DELETE FROM ir_model_fields
        WHERE model = 'res.config.settings'
          AND name IN ('generative_ai_systems', 'api_key', 'max_token',
                       'model_id', 'openrouter_model_id');

        -- Drop orphan columns
        ALTER TABLE res_config_settings
          DROP COLUMN IF EXISTS generative_ai_systems,
          DROP COLUMN IF EXISTS api_key,
          DROP COLUMN IF EXISTS max_token,
          DROP COLUMN IF EXISTS model_id,
          DROP COLUMN IF EXISTS openrouter_model_id;

        -- Remove our custom models
        DELETE FROM ir_model WHERE model = 'website.snippet.data';
        DROP TABLE IF EXISTS website_snippet_data CASCADE;
    """)
