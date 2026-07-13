# -*- coding: utf-8 -*-
import base64
import hashlib
import logging
import time

import requests

from odoo import _, exceptions, models

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Primary  : Hugging Face Inference Router — FLUX.1-schnell (free account)
# Fallback : Pexels stock photo search (free API key)
# Docs HF  : https://huggingface.co/docs/api-inference
# Docs Pex : https://www.pexels.com/api/documentation/
# ---------------------------------------------------------------------------
_HF_ENDPOINT = (
    "https://router.huggingface.co/hf-inference/models/"
    "black-forest-labs/FLUX.1-schnell"
)
_PEXELS_ENDPOINT = "https://api.pexels.com/v1/search"
_CLOUDINARY_UPLOAD = "https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"

# ─────────────────────────────────────────────────────────────────────────
# Secondary : Google GenSpark API — Advanced AI image generation
# Docs Vertex AI : https://cloud.google.com/vertex-ai/docs/reference/rest
# ─────────────────────────────────────────────────────────────────────────
_GENSPARK_ENDPOINT = "https://aiplatform.googleapis.com/v1/projects/{project}/locations/us-central1/imageGenerationModels/imagen-3-0-fast-generate:generateImages"


class ProductTemplateAIImage(models.Model):
    _inherit = "product.template"

    # ------------------------------------------------------------------
    # Public action — called from "Generate AI Image" button
    # ------------------------------------------------------------------
    def action_generate_ai_images(self):
        """Generate a product image for each selected product that has no
        extra images yet.

        Strategy (in order):
        1. Hugging Face FLUX.1-schnell — real AI generation (free account).
        2. Pexels stock photo search    — fallback when HF is unavailable.

        Both services are 100 % free with a free account / API key.
        """
        ICP = self.env["ir.config_parameter"].sudo()
        hf_token         = ICP.get_param("website_sgctech_ai.hf_token", "").strip()
        genspark_api_url = ICP.get_param("website_sgctech_ai.genspark_api_url", "").strip()
        genspark_api_secret = ICP.get_param("website_sgctech_ai.genspark_api_secret", "").strip()
        genspark_model   = ICP.get_param("website_sgctech_ai.genspark_model", "imagen4").strip() or "imagen4"
        pexels_api_key   = ICP.get_param("website_sgctech_ai.pexels_api_key", "").strip()
        cloudinary_cloud = ICP.get_param("website_sgctech_ai.cloudinary_cloud_name", "").strip()
        cloudinary_key   = ICP.get_param("website_sgctech_ai.cloudinary_api_key", "").strip()
        cloudinary_secret= ICP.get_param("website_sgctech_ai.cloudinary_api_secret", "").strip()

        if not hf_token and not (genspark_api_url and genspark_api_secret) and not pexels_api_key:
            raise exceptions.UserError(
                _(
                    "No image source configured.\n\n"
                    "Go to Settings → SGC TECH AI → AI Image Generation and add:\n"
                    "• Hugging Face token (free at huggingface.co)  — AI generated images\n"
                    "• GenSpark bridge URL + API secret            — SGC branded image generation\n"
                    "• Pexels API key (free at pexels.com/api)      — stock photo fallback"
                )
            )

        use_cloudinary = bool(cloudinary_cloud and cloudinary_key and cloudinary_secret)
        generated = skipped = 0
        errors = []

        for product in self:
            needs_avatar  = not product.image_1920
            needs_gallery = not product.product_template_image_ids

            if not needs_avatar and not needs_gallery:
                skipped += 1
                continue

            name = product.name or "product"

            # ── Two distinct prompts for two distinct images ──────────────
            # Avatar  — clean isolated product shot on white
            prompt_avatar = (
                f"Professional product photography of '{name}', "
                "isolated on a pure white background, centered composition, "
                "soft studio lighting, sharp focus, photorealistic, high resolution, "
                "no shadows, no text, e-commerce ready."
            )
            # Gallery — lifestyle/context scene showing the product in use
            prompt_gallery = (
                f"Lifestyle scene featuring '{name}', "
                "modern workspace or office environment, natural light, "
                "cinematic composition, high resolution, photorealistic, "
                "professional digital product showcase, no text."
            )

            img_avatar  = None
            img_gallery = None
            source_used = ""

            def _fetch(prompt, label):
                """Try HF first, then the GenSpark bridge, then Pexels."""
                img = None
                src = ""
                if hf_token:
                    try:
                        img = self._generate_with_huggingface(hf_token, prompt, use_raw_prompt=True)
                        src = "HF FLUX"
                    except Exception as exc:
                        _logger.warning(
                            "HF failed for [%s] %s (%s), trying next provider: %s",
                            product.id, name, label, exc,
                        )
                if img is None and genspark_api_url and genspark_api_secret:
                    try:
                        from .genspark_integration import GenSparkImageGenerator

                        img = GenSparkImageGenerator.generate_image(
                            api_url=genspark_api_url,
                            api_secret=genspark_api_secret,
                            prompt=prompt,
                            model=genspark_model,
                        )
                        src = f"GenSpark {genspark_model}"
                    except Exception as exc:
                        _logger.warning(
                            "GenSpark failed for [%s] %s (%s), trying Pexels: %s",
                            product.id, name, label, exc,
                        )
                if img is None and pexels_api_key:
                    try:
                        img = self._fetch_pexels_image(pexels_api_key, name)
                        src = "Pexels"
                    except Exception as exc:
                        _logger.error(
                            "Pexels also failed for [%s] %s (%s): %s",
                            product.id, name, label, exc,
                        )
                return img, src

            if needs_avatar:
                img_avatar, source_used = _fetch(prompt_avatar, "avatar")

            if needs_gallery:
                img_gallery, source_used = _fetch(prompt_gallery, "gallery")

            if img_avatar is None and img_gallery is None:
                errors.append(name)
                continue

            # ── Optional Cloudinary CDN upload ───────────────────────────
            if use_cloudinary and img_gallery:
                try:
                    self._upload_to_cloudinary(
                        img_gallery, cloudinary_key, cloudinary_secret,
                        cloudinary_cloud, public_id=f"odoo_product_{product.id}",
                    )
                except Exception as exc:
                    _logger.warning(
                        "Cloudinary upload failed for [%s] %s (storing locally): %s",
                        product.id, name, exc,
                    )

            # ── Save avatar (main product image) ─────────────────────────
            if img_avatar:
                product.write({"image_1920": base64.b64encode(img_avatar)})
                _logger.info("Avatar set for product [%s] %s via %s", product.id, name, source_used)

            # ── Save gallery image ────────────────────────────────────────
            if img_gallery:
                self.env["product.image"].create({
                    "name": name,
                    "product_tmpl_id": product.id,
                    "image_1920": base64.b64encode(img_gallery),
                })
                _logger.info("Gallery image added for product [%s] %s via %s", product.id, name, source_used)

            generated += 1

        lines = [_("%d image(s) generated successfully.") % generated]
        if skipped:
            lines.append(_("%d product(s) skipped (already have images).") % skipped)
        if errors:
            lines.append(_("Failed for: %s") % ", ".join(errors))

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("AI Image Generation"),
                "message": " ".join(lines),
                "type": "success" if generated else ("warning" if skipped else "danger"),
                "sticky": bool(errors),
            },
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _generate_with_huggingface(self, token: str, product_name: str, use_raw_prompt: bool = False) -> bytes:
        """Call HF Inference Router (FLUX.1-schnell) and return raw image bytes.

        Free tier: ~unlimited requests with a free HF account token.
        Get token: https://huggingface.co/settings/tokens

        Args:
            token: HF bearer token.
            product_name: Used as the prompt when use_raw_prompt=False,
                          or passed directly as the full prompt when True.
            use_raw_prompt: When True, product_name is used as-is as the prompt.
        """
        prompt = product_name if use_raw_prompt else (
            f"Professional product photography of '{product_name}', "
            "clean white studio background, soft even lighting, sharp focus, "
            "photorealistic, high resolution, e-commerce ready, no text."
        )
        response = requests.post(
            _HF_ENDPOINT,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"inputs": prompt},
            timeout=120,
        )

        if response.status_code == 401:
            raise exceptions.UserError(
                _("Invalid Hugging Face token. Check Settings → SGC TECH AI.")
            )
        if response.status_code == 503:
            raise RuntimeError("HF model is loading, will retry via fallback.")

        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "image" not in content_type:
            raise ValueError(
                f"HF did not return an image. Content-Type: {content_type}"
            )
        return response.content

    def _fetch_pexels_image(self, api_key: str, product_name: str) -> bytes:
        """Search Pexels for a stock photo matching the product name.

        Free tier: 200 requests/hour, 20,000/month — more than enough.
        Get key: https://www.pexels.com/api/
        """
        # Use product name as search query; fall back to generic term
        query = product_name.strip() or "product"

        search = requests.get(
            _PEXELS_ENDPOINT,
            headers={"Authorization": api_key},
            params={
                "query": query,
                "per_page": 1,
                "orientation": "square",
                "size": "large",
            },
            timeout=30,
        )

        if search.status_code == 401:
            raise exceptions.UserError(
                _("Invalid Pexels API key. Check Settings → SGC TECH AI.")
            )
        search.raise_for_status()

        photos = search.json().get("photos", [])
        if not photos:
            # Broaden search to 'product' if nothing found for the specific name
            search2 = requests.get(
                _PEXELS_ENDPOINT,
                headers={"Authorization": api_key},
                params={"query": "product", "per_page": 1, "orientation": "square"},
                timeout=30,
            )
            search2.raise_for_status()
            photos = search2.json().get("photos", [])

        if not photos:
            raise ValueError("Pexels returned no photos for this product.")

        # Download the large2x version (1880px wide max)
        image_url = photos[0]["src"].get("large2x") or photos[0]["src"]["original"]
        img = requests.get(image_url, timeout=60)
        img.raise_for_status()
        return img.content

    def _upload_to_cloudinary(
        self,
        image_bytes: bytes,
        api_key: str,
        api_secret: str,
        cloud_name: str,
        public_id: str = "",
    ) -> str:
        """Upload image to Cloudinary using signed upload, return secure URL."""
        timestamp = int(time.time())
        params = {"timestamp": timestamp}
        if public_id:
            params["public_id"] = public_id

        params_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        signature = hashlib.sha1(
            f"{params_str}{api_secret}".encode("utf-8")
        ).hexdigest()

        response = requests.post(
            _CLOUDINARY_UPLOAD.format(cloud_name=cloud_name),
            files={"file": ("product_image.jpg", image_bytes, "image/jpeg")},
            data={
                "api_key": api_key,
                "timestamp": timestamp,
                "signature": signature,
                **({k: v for k, v in params.items() if k != "timestamp"}),
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json().get("secure_url", "")
