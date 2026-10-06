/**
 * Guard jQuery.find() against undefined/null selectors to avoid Sizzle crashes
 * that can occur when upstream code passes an empty selector. Returns an empty
 * jQuery set in those cases instead of throwing.
 */
(function guardJQueryFind() {
    'use strict';

    const $ = window.jQuery || window.$;
    if (!$ || !$.fn || !$.fn.find) {
        return;
    }

    const originalFind = $.fn.find;
    $.fn.find = function (selector) {
        try {
            // Protect Sizzle from null/undefined/non-string selectors.
            if (selector === undefined || selector === null || selector === '') {
                return this.pushStack([]);
            }
            const isNode = selector && selector.nodeType !== undefined;
            const hasLength = selector && selector.length !== undefined;
            const isString = typeof selector === 'string';
            if (!isString && !isNode && !hasLength) {
                return this.pushStack([]);
            }
            return originalFind.call(this, selector);
        } catch (err) {
            return this.pushStack([]);
        }
    };
})();
