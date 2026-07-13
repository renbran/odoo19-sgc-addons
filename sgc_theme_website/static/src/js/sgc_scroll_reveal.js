/** @odoo-module */
// (c) SGC TECH — Finance. Systems. Technology. — https://sgctech.ai
// Tier-b scroll reveal: fade/slide elements in as they enter the viewport.
// Fully skipped (final state shown immediately) under prefers-reduced-motion.

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class SgcScrollReveal extends Interaction {
    static selector = ".sgc-reveal";

    setup() {
        this.reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    }

    start() {
        // Under reduced motion the CSS already renders the final state; make it
        // explicit and do nothing else.
        if (this.reduced || !("IntersectionObserver" in window)) {
            this.el.classList.add("sgc-in");
            return;
        }
        this.observer = new IntersectionObserver(
            (entries) => {
                for (const entry of entries) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("sgc-in");
                        this.observer.unobserve(entry.target);
                    }
                }
            },
            { threshold: 0.15, rootMargin: "0px 0px -10% 0px" }
        );
        this.observer.observe(this.el);
        this.registerCleanup(() => this.observer && this.observer.disconnect());
    }
}

registry
    .category("public.interactions")
    .add("sgc_theme_website.scroll_reveal", SgcScrollReveal);
