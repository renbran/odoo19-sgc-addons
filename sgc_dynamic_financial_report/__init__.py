# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from . import controllers
from . import models
from . import reports
from . import hooks

# post_init_hook is resolved via getattr(module, name) on this package's
# top-level namespace (Odoo does not resolve dotted paths), so it must be
# imported here under the exact name referenced in __manifest__.py.
from .hooks.post_init_hook import post_init_hook_function