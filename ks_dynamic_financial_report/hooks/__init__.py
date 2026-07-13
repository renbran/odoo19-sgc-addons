# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Hooks module for ks_dynamic_financial_report installation/upgrade lifecycle."""

from .pre_init_hook import pre_init_hook
from .post_init_hook import post_init_hook
from .uninstall_hook import uninstall_hook

__all__ = ['pre_init_hook', 'post_init_hook', 'uninstall_hook']
