# Copyright 2026 Park Group
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError


class BufferMutationError(UserError):
    """A typed Buffer mutation error that must fail only its publication."""
