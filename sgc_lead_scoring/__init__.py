# -*- coding: utf-8 -*-

# Monkey-patch ir.ui.view._get_view_postprocessed to fix core bug
# The bug: it passes model=self._name (ir.ui.view) instead of model=view.model
# This patch must be applied early, before the registry loads the view model
try:
    from odoo.addons.base.models.ir_ui_view import Base as BaseIrUiView
    original_get_view_postprocessed = BaseIrUiView._get_view_postprocessed
    
    def patched_get_view_postprocessed(self, view, arch, **options):
        if not view.model:
            return original_get_view_postprocessed(self, view, arch, **options)
        return view.postprocess_and_fields(arch, model=view.model, **options)
    
    BaseIrUiView._get_view_postprocessed = patched_get_view_postprocessed
except Exception as e:
    import logging
    _logger = logging.getLogger(__name__)
    _logger.warning("Could not patch ir.ui.view._get_view_postprocessed: %s", e)

from . import models
from . import wizards
