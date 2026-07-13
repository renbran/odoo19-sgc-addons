/** @odoo-module */
// (c) SGC TECH — Finance. Systems. Technology. — https://sgctech.ai
// Tier-b KPI count-up: animates a number from 0 to its target when scrolled
// into view. Under prefers-reduced-motion the final value is shown at once.

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class SgcStatCounter extends Interaction {
    static selector = ".s_sgc_stat_value";

    setup() {
        this.reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        // Respect the snippet's "Animate count-up" option (data-sgc-animate on
        // the section). Missing/"false" => show the final value immediately.
        const section = this.el.closest(".s_sgc_stats");
        const flag = section ? section.dataset.sgcAnimate : undefined;
        this.animateEnabled = flag !== undefined && flag !== "false";
        const raw = this.el.dataset.sgcTarget || this.el.textContent || "0";
        this.target = parseFloat(raw.replace(/[^0-9.\-]/g, "")) || 0;
        this.prefix = this.el.dataset.sgcPrefix || "";
        this.suffix = this.el.dataset.sgcSuffix || "";
        this.duration = parseInt(this.el.dataset.sgcDuration || "1600", 10);
        this.decimals = (String(this.target).split(".")[1] || "").length;
    }

    start() {
        this.render(this.reduced ? this.target : 0);
        if (this.reduced || !this.animateEnabled || !("IntersectionObserver" in window)) {
            this.render(this.target);
            return;
        }
        this.observer = new IntersectionObserver(
            (entries) => {
                if (entries.some((e) => e.isIntersecting)) {
                    this.observer.disconnect();
                    this.animate();
                }
            },
            { threshold: 0.4 }
        );
        this.observer.observe(this.el);
        this.registerCleanup(() => this.observer && this.observer.disconnect());
    }

    animate() {
        const startTs = performance.now();
        const step = (now) => {
            const p = Math.min(1, (now - startTs) / this.duration);
            const eased = 1 - Math.pow(1 - p, 3); // easeOutCubic
            this.render(this.target * eased);
            if (p < 1) {
                this.raf = requestAnimationFrame(step);
            }
        };
        this.raf = requestAnimationFrame(step);
        this.registerCleanup(() => this.raf && cancelAnimationFrame(this.raf));
    }

    render(value) {
        this.el.textContent = `${this.prefix}${value.toFixed(this.decimals)}${this.suffix}`;
    }
}

registry
    .category("public.interactions")
    .add("sgc_theme_website.stat_counter", SgcStatCounter);
