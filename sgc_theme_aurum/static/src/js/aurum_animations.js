/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.AurumAnimations = publicWidget.Widget.extend({
    selector: "#wrapwrap",
    disabledInEditableMode: false,

    start() {
        this.prefersReducedMotion = window.matchMedia
            && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        this._setupReveal();
        this._setupNavbar();
        this._setupCounters();
        this._setupStagger();
        this._setupFormValidation();
        this._setupTimeline();
        if (!this.prefersReducedMotion) {
            this._setupParallax();
        }
        return this._super(...arguments);
    },

    _setupReveal() {
        const targets = this.el.querySelectorAll(".aurum-reveal");
        if (!targets.length) {
            return;
        }
        if (!("IntersectionObserver" in window)) {
            targets.forEach((t) => t.classList.add("aurum-in"));
            return;
        }
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("aurum-in");
                        observer.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.15 }
        );
        targets.forEach((t) => observer.observe(t));
    },

    _setupFormValidation() {
        const form = this.el.querySelector("#contact-form");
        if (!form) return;
        const btn = form.querySelector('button[type="submit"], input[type="submit"]');
        const inputs = form.querySelectorAll("input, textarea, select");
        inputs.forEach((input) => {
            const checkValid = () => {
                if (input.hasAttribute("required") && !input.value.trim()) {
                    input.style.borderColor = "#dc3545";
                } else {
                    input.style.borderColor = "";
                }
            };
            input.addEventListener("blur", checkValid);
            input.addEventListener("input", () => {
                if (input.value.trim()) input.style.borderColor = "";
            });
        });
        if (btn) {
            btn.addEventListener("click", (e) => {
                let valid = true;
                inputs.forEach((input) => {
                    if (input.hasAttribute("required") && !input.value.trim()) {
                        input.style.borderColor = "#dc3545";
                        if (!input.nextElementSibling || !input.nextElementSibling.classList.contains("aurum-field-error")) {
                            const err = document.createElement("div");
                            err.className = "aurum-field-error";
                            err.style.cssText = "color:#dc3545;font-size:.75rem;margin-top:.25rem;";
                            err.textContent = "This field is required";
                            input.parentNode.insertBefore(err, input.nextSibling);
                        }
                        valid = false;
                    }
                });
                if (!valid) {
                    e.preventDefault();
                    const firstErr = form.querySelector('[style*="border-color: rgb(220, 53, 69)"]');
                    if (firstErr) firstErr.focus();
                } else {
                    const success = document.createElement("div");
                    success.className = "alert alert-success mt-3";
                    success.setAttribute("role", "alert");
                    success.textContent = "Thank you. We'll be in touch within 24 hours.";
                    form.querySelector(".btn-aurum-gold, [type='submit']").closest("div, p")?.after(success);
                }
            });
        }
    },

    _setupTimeline() {
        if (this.prefersReducedMotion) return;
        const phases = this.el.querySelectorAll(".aurum-timeline-phase");
        if (!phases.length || !("IntersectionObserver" in window)) return;
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        entry.target.style.opacity = "1";
                        entry.target.style.transform = "translateY(0)";
                        observer.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.2 }
        );
        phases.forEach((p) => {
            p.style.opacity = "0";
            p.style.transform = "translateY(20px)";
            p.style.transition = "opacity .6s ease, transform .6s ease";
            observer.observe(p);
        });
    },

    _setupNavbar() {
        const header = this.el.querySelector("header#top");
        if (!header) {
            return;
        }
        header.classList.add("aurum-navbar");
        const onScroll = () => {
            if (window.scrollY > 60) {
                header.classList.add("aurum-scrolled");
            } else {
                header.classList.remove("aurum-scrolled");
            }
        };
        onScroll();
        window.addEventListener("scroll", onScroll, { passive: true });
    },

    _setupCounters() {
        const counters = this.el.querySelectorAll("[data-aurum-count]");
        if (!counters.length || !("IntersectionObserver" in window)) {
            return;
        }
        const animate = (el) => {
            const target = parseFloat(el.getAttribute("data-aurum-count")) || 0;
            const suffix = el.getAttribute("data-aurum-suffix") || "";
            if (this.prefersReducedMotion) {
                el.textContent = target + suffix;
                return;
            }
            const duration = 1400;
            const start = performance.now();
            const step = (now) => {
                const progress = Math.min((now - start) / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                el.textContent = Math.round(eased * target) + suffix;
                if (progress < 1) {
                    requestAnimationFrame(step);
                }
            };
            requestAnimationFrame(step);
        };
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        const statNum = entry.target.closest(".aurum-stat-num");
                        if (statNum) statNum.classList.add("aurum-in");
                        animate(entry.target);
                        observer.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.4 }
        );
        counters.forEach((c) => observer.observe(c));
    },

    _setupStagger() {
        const groups = this.el.querySelectorAll(".aurum-stagger");
        if (!groups.length || !("IntersectionObserver" in window)) return;
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("aurum-in");
                        observer.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.15 }
        );
        groups.forEach((g) => observer.observe(g));
    },

    _setupParallax() {
        const orbit = this.el.querySelector(".aurum-hero-orbit");
        if (!orbit) {
            return;
        }
        const onScroll = () => {
            const y = Math.min(window.scrollY, 600);
            orbit.style.transform = `translateY(calc(-50% + ${y * 0.15}px)) rotate(${y * 0.05}deg)`;
        };
        window.addEventListener("scroll", onScroll, { passive: true });
    },
});

export default publicWidget.registry.AurumAnimations;
