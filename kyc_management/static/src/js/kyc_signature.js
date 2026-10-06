/**
 * KYC Enhanced Module - Signature Canvas Widget
 * Handles digital signature capture with HTML5 Canvas API
 * 
 * Features:
 * - Mouse and touch support
 * - Draw, Clear, Submit functionality
 * - Base64 encoding for submission
 * - OSUS branding and styling
 */

(function() {
    'use strict';

    const SignaturePad = {
        // Canvas configuration
        canvas: null,
        ctx: null,
        isDrawing: false,
        lastX: 0,
        lastY: 0,
        
        // Color configuration
        strokeColor: '#800020',  // OSUS burgundy
        strokeWidth: 2,
        canvasWidth: 600,
        canvasHeight: 200,
        
        /**
         * Initialize the signature canvas
         */
        init: function() {
            this.canvas = document.getElementById('signature_pad');
            if (!this.canvas) {
                console.warn('Signature canvas not found');
                return;
            }
            
            this.ctx = this.canvas.getContext('2d');
            this.resizeCanvas();
            this.setupEventListeners();
            this.clearCanvas();
        },
        
        /**
         * Resize canvas to fit container.
         * The canvas may start inside a hidden panel (display:none) so
         * getBoundingClientRect() returns 0×0.  Fall back to CSS-defined
         * size or a sensible default so drawing always works.
         */
        resizeCanvas: function() {
            const rect = this.canvas.getBoundingClientRect();
            const dpr  = window.devicePixelRatio || 1;
            // Use rect dimensions if the element is currently visible; otherwise
            // fall back to offsetWidth / the closest scrollable parent width.
            let w = rect.width  || this.canvas.offsetWidth  || this.canvas.parentElement.offsetWidth  || 600;
            let h = rect.height || this.canvas.offsetHeight || 180;
            this.canvas.width  = Math.round(w * dpr);
            this.canvas.height = Math.round(h * dpr);
            this.ctx.scale(dpr, dpr);
            this.clearCanvas();
        },
        
        /**
         * Setup event listeners for mouse and touch
         */
        setupEventListeners: function() {
            // Mouse events
            this.canvas.addEventListener('mousedown', (e) => this.handleStart(e));
            this.canvas.addEventListener('mousemove', (e) => this.handleMove(e));
            this.canvas.addEventListener('mouseup', (e) => this.handleEnd(e));
            this.canvas.addEventListener('mouseout', (e) => this.handleEnd(e));
            
            // Touch events — must be non-passive to allow preventDefault()
            const touchOpts = { passive: false };
            this.canvas.addEventListener('touchstart', (e) => this.handleStart(e), touchOpts);
            this.canvas.addEventListener('touchmove', (e) => this.handleMove(e), touchOpts);
            this.canvas.addEventListener('touchend', (e) => this.handleEnd(e), touchOpts);
            this.canvas.addEventListener('touchcancel', (e) => this.handleEnd(e), touchOpts);
            
            // Button listeners
            const clearBtn = document.getElementById('clear_signature');
            if (clearBtn) {
                clearBtn.addEventListener('click', () => this.clearCanvas());
            }
            
            const submitBtn = document.getElementById('submit_kyc_form');
            if (submitBtn) {
                submitBtn.addEventListener('click', (e) => this.captureSignature(e));
            }
        },
        
        /**
         * Handle drawing start
         */
        handleStart: function(e) {
            e.preventDefault();
            this.isDrawing = true;
            const pos = this.getMousePos(e);
            this.lastX = pos.x;
            this.lastY = pos.y;
        },
        
        /**
         * Handle drawing move
         */
        handleMove: function(e) {
            if (!this.isDrawing) return;
            e.preventDefault();
            
            const pos = this.getMousePos(e);
            this.drawLine(this.lastX, this.lastY, pos.x, pos.y);
            this.lastX = pos.x;
            this.lastY = pos.y;
        },
        
        /**
         * Handle drawing end
         */
        handleEnd: function(e) {
            this.isDrawing = false;
            e.preventDefault();
        },
        
        /**
         * Get mouse position relative to canvas
         */
        getMousePos: function(e) {
            const rect = this.canvas.getBoundingClientRect();
            let x, y;
            
            if (e.touches) {
                x = e.touches[0].clientX - rect.left;
                y = e.touches[0].clientY - rect.top;
            } else {
                x = e.clientX - rect.left;
                y = e.clientY - rect.top;
            }
            
            return { x: x, y: y };
        },
        
        /**
         * Draw line on canvas
         */
        drawLine: function(x1, y1, x2, y2) {
            this.ctx.strokeStyle = this.strokeColor;
            this.ctx.lineWidth = this.strokeWidth;
            this.ctx.lineCap = 'round';
            this.ctx.lineJoin = 'round';
            this.ctx.beginPath();
            this.ctx.moveTo(x1, y1);
            this.ctx.lineTo(x2, y2);
            this.ctx.stroke();
        },
        
        /**
         * Clear the canvas
         */
        clearCanvas: function() {
            this.ctx.fillStyle = '#ffffff';
            this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
            this.ctx.strokeStyle = '#cccccc';
            this.ctx.lineWidth = 1;
            this.ctx.setLineDash([5, 5]);
            this.ctx.strokeRect(0, 0, this.canvas.width, this.canvas.height);
            this.ctx.setLineDash([]);
        },
        
        /**
         * Capture signature as base64 data
         */
        captureSignature: function(e) {
            const imageData = this.canvas.toDataURL('image/png');
            const input = document.getElementById('signature_data');
            if (input) {
                input.value = imageData;
                console.log('✓ Signature captured');
                return true;
            }
            return false;
        },
        
        /**
         * Check if canvas is empty (no ink drawn by user)
         * Compares pixel data against a freshly cleared reference canvas.
         */
        isCanvasEmpty: function() {
            const ref = document.createElement('canvas');
            ref.width = this.canvas.width;
            ref.height = this.canvas.height;
            const refCtx = ref.getContext('2d');
            // Reproduce the cleared state (white fill + dashed border)
            refCtx.fillStyle = '#ffffff';
            refCtx.fillRect(0, 0, ref.width, ref.height);
            refCtx.strokeStyle = '#cccccc';
            refCtx.lineWidth = 1;
            refCtx.setLineDash([5, 5]);
            refCtx.strokeRect(0, 0, ref.width, ref.height);
            const live = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height).data;
            const clean = refCtx.getImageData(0, 0, ref.width, ref.height).data;
            for (let i = 0; i < live.length; i++) {
                if (live[i] !== clean[i]) return false;
            }
            return true;
        },
        
        /**
         * Get signature as base64
         */
        getSignatureData: function() {
            return this.canvas.toDataURL('image/png');
        },
        
        /**
         * Validate has signature — shows an inline error instead of a blocking alert
         */
        validate: function() {
            if (this.isCanvasEmpty()) {
                // Prefer an inline error label over a blocking alert
                const errorEl = document.getElementById('signature_error');
                if (errorEl) {
                    errorEl.textContent = 'Please sign the document before submitting.';
                    errorEl.style.display = 'block';
                    this.canvas.scrollIntoView({ behavior: 'smooth', block: 'center' });
                } else {
                    alert('Please sign the document before submitting.');
                }
                return false;
            }
            const errorEl = document.getElementById('signature_error');
            if (errorEl) { errorEl.style.display = 'none'; }
            this.captureSignature();
            return true;
        }
    };
    
    // Initialize only on the KYC form page where the canvas exists
    function _maybeInit() {
        if (!document.getElementById('signature_pad')) {
            return;
        }
        SignaturePad.init();
        window.SignaturePad = SignaturePad;
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _maybeInit);
    } else {
        _maybeInit();
    }
    
})();
