/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Wysiwyg } from "@html_editor/wysiwyg";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";

patch(Wysiwyg.prototype, {
    setup() {
        super.setup();
        // Ensure we have the RPC route available
        if (!this.sgc_ai_initialized) {
            this._initSgcAI();
            this.sgc_ai_initialized = true;
        }
    },

    _initSgcAI() {
        // Store original methods
        this._originalGetConfig = this.getConfig || function() {};
        this._originalDestroy = this.destroy || function() {};
        
        // Override getConfig to inject our powerbox items
        this.getConfig = function() {
            const config = this._originalGetConfig.call(this) || {};
            
            // Initialize arrays if they don't exist
            config.powerbox_items = config.powerbox_items || [];
            config.powerbox_categories = config.powerbox_categories || [];
            config.user_commands = config.user_commands || [];
            
            // Check if already added to avoid duplicates
            const hasSgcaiCategory = config.powerbox_categories.some(cat => 
                cat.id === 'sgc_ai');
            if (!hasSgcaiCategory) {
                config.powerbox_categories.push({
                    id: 'sgc_ai',
                    name: _t('SGC AI'),
                    sequence: 80  // Place it after standard categories
                });
            }
            
            const hasSgcaiItem = config.powerbox_items.some(item => 
                item.categoryId === 'sgc_ai' && item.commandId === 'sgc_ai_cmd');
            if (!hasSgcaiItem) {
                config.powerbox_items.push({
                    categoryId: 'sgc_ai',
                    commandId: 'sgc_ai_cmd',
                    icon: 'fa-robot',
                    // For backwards compatibility with older powerbox systems
                    title: _t('Ask SGC AI'),
                    description: _t('Send selected text to SGC AI and insert the response')
                });
            }
            
            const hasSgcaiUserCmd = config.user_commands.some(cmd => 
                cmd.id === 'sgc_ai_cmd');
            if (!hasSgcaiUserCmd) {
                // We'll handle the actual execution via RPC in the powerbox item handler
                config.user_commands.push({
                    id: 'sgc_ai_cmd',
                    label: _t('Ask SGC AI'),
                    // This will be handled by our custom powerbox item logic below
                });
            }
            
            return config;
        };
        
        // Override destroy to clean up
        this.destroy = function() {
            // Restore original methods if needed
            if (this._originalGetConfig) {
                this.getConfig = this._originalGetConfig;
            }
            if (this._originalDestroy) {
                this.destroy = this._originalDestroy;
            }
            return this._originalDestroy.call(this);
        };
    }
});

// Global handler for powerbox item execution
// This gets called when the powerbox item is selected
window.sgc_ai_powerbox_execute = function() {
    // Get the current editor instance
    const editor = document.querySelector('.o_editor:not(.o_hidden)')?.['__editor__'] ||
                  document.querySelector('.o_field_widget[widget="html"] .o_editor:not(.o_hidden)')?.['__editor__'] ||
                  document.querySelector('.o_field_html_editor .o_editor:not(.o_hidden)')?.['__editor__'];
    
    if (!editor || !editor.getSelectedRange) {
        console.warn('SGC AI: Could not find active editor');
        return;
    }
    
    const range = editor.getSelectedRange();
    if (!range) {
        editor._notify ? editor._notify('Select some text first, then type /sgcai.') : 
                         alert('Select some text first, then type /sgcai.');
        return;
    }
    
    const selectedText = editor.getSelectedText ? editor.getSelectedText() : 
                        (range.toString ? range.toString() : '');
    
    if (!selectedText || !selectedText.trim()) {
        editor._notify ? editor._notify('Selected text is empty.') : 
                         alert('Selected text is empty.');
        return;
    }
    
    // Show loading state
    editor._replaceRange ? editor._replaceRange(range, '🌀 Thinking...') : 
                          console.log('Would replace with thinking...');
    
    // Call our backend
    rpc({
        url: '/sgc_ai_powerbox/get_response',
        params: { 
            pad: selectedText.trim()
        }
    }).then(function(result) {
        if (result.error) {
            editor._replaceRange ? 
                editor._replaceRange(range, '⚠️ Error: ' + result.error) :
                console.error('SGC AI Error:', result.error);
        } else {
            editor._replaceRange ? 
                editor._replaceRange(range, result.response) :
                console.log('Would replace with:', result.response);
        }
    }).catch(function(error) {
        console.error('SGC AJAX Error:', error);
    });
};