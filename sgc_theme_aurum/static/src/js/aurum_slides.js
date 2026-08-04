/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.AurumSlides = publicWidget.Widget.extend({
    selector: ".stage",
    disabledInEditableMode: false,

    start() {
        this._initDeck();
        return this._super(...arguments);
    },

    _initDeck() {
        const stage = this.el;
        const slides = Array.from(stage.querySelectorAll(".slide"));
        if (!slides.length) {
            return;
        }
        const nav = stage.querySelector(".nav");
        const dotsContainer = stage.querySelector(".dots");
        const prevBtn = nav ? nav.querySelector("button:first-child") : null;
        const nextBtn = nav ? nav.querySelector("button:last-child") : null;
        let current = Math.max(0, slides.findIndex((s) => s.classList.contains("active")));
        if (current < 0) {
            current = 0;
        }

        const render = () => {
            slides.forEach((slide, i) => {
                slide.classList.toggle("active", i === current);
            });
            if (dotsContainer) {
                dotsContainer.innerHTML = "";
                slides.forEach((slide, i) => {
                    const dot = document.createElement("span");
                    dot.className = "dot" + (i === current ? " active" : "");
                    dot.setAttribute("role", "tab");
                    dot.setAttribute("aria-label", "Go to slide " + (i + 1));
                    dot.addEventListener("click", () => {
                        current = i;
                        render();
                    });
                    dotsContainer.appendChild(dot);
                });
            }
        };

        const prev = () => {
            current = (current - 1 + slides.length) % slides.length;
            render();
        };
        const next = () => {
            current = (current + 1) % slides.length;
            render();
        };

        if (prevBtn) {
            prevBtn.addEventListener("click", prev);
        }
        if (nextBtn) {
            nextBtn.addEventListener("click", next);
        }
        stage.setAttribute("tabindex", "0");
        stage.addEventListener("keydown", (ev) => {
            if (ev.key === "ArrowLeft") {
                prev();
            } else if (ev.key === "ArrowRight") {
                next();
            }
        });

        let touchStartX = null;
        stage.addEventListener("touchstart", (ev) => {
            touchStartX = ev.touches[0].clientX;
        }, { passive: true });
        stage.addEventListener("touchend", (ev) => {
            if (touchStartX === null) {
                return;
            }
            const delta = ev.changedTouches[0].clientX - touchStartX;
            if (Math.abs(delta) > 40) {
                if (delta < 0) {
                    next();
                } else {
                    prev();
                }
            }
            touchStartX = null;
        }, { passive: true });

        render();
    },
});
