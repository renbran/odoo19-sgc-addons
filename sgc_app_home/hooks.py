import json
import logging

_logger = logging.getLogger(__name__)

_SNAPSHOT_PARAM = "sgc_app_home.action_id_snapshot"


def post_init_hook(env):
    """Make the SGC App Home the landing page for every internal user.

    Snapshots each user's prior Home Action first so uninstall_hook can put
    it back exactly as it was - this module never permanently overwrites
    that per-user setting.
    """
    action = env.ref("sgc_app_home.action_sgc_app_home", raise_if_not_found=False)
    if not action:
        _logger.warning("sgc_app_home: action_sgc_app_home not found, skipping home action setup")
        return

    users = env["res.users"].sudo().search([("share", "=", False)])
    snapshot = {str(user.id): user.action_id.id for user in users}
    env["ir.config_parameter"].sudo().set_param(_SNAPSHOT_PARAM, json.dumps(snapshot))

    users.write({"action_id": action.id})

    env["ir.default"].sudo().set(
        "res.users", "action_id", action.id, user_id=False, company_id=False
    )
    _logger.info("sgc_app_home: set Home Action for %d users and future-user default", len(users))


def uninstall_hook(env):
    """Restore each user's prior Home Action and remove the future-user default."""
    param = env["ir.config_parameter"].sudo().get_param(_SNAPSHOT_PARAM)
    if param:
        try:
            snapshot = json.loads(param)
        except ValueError:
            snapshot = {}
        for user_id_str, prior_action_id in snapshot.items():
            user = env["res.users"].sudo().browse(int(user_id_str))
            if user.exists():
                user.write({"action_id": prior_action_id or False})

    env["ir.default"].sudo().search([
        ("field_id.model", "=", "res.users"),
        ("field_id.name", "=", "action_id"),
    ]).unlink()

    env["ir.config_parameter"].sudo().search([("key", "=", _SNAPSHOT_PARAM)]).unlink()
    _logger.info("sgc_app_home: restored prior Home Action for all users")
