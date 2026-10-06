/** @odoo-module **/

import { NavBar } from "@web/webclient/navbar/navbar";
import { patch } from "@web/core/utils/patch";

// Fix 4: Use existing state methods (_openAppMenuSidebar / _closeAppMenuSidebar)
// and existing state.isAppMenuSidebarOpened instead of parallel state management.
// No patch needed — the sidebar toggle button in apps_sidebar.xml now calls
// _openAppMenuSidebar directly, and the close button calls _closeAppMenuSidebar.
// The t-att-class binds to state.isAppMenuSidebarOpened which is already reactive.
