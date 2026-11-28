# Copyright 2026 Park Group
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def uninstall_hook(env):
    """Archive Buffer accounts when their connector is uninstalled."""
    env["social.account"]._remove_social_media("buffer")
