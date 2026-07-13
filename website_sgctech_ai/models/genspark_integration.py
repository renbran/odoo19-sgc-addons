# -*- coding: utf-8 -*-
"""
GenSpark2API bridge integration.
Uses the same plain-text prompt contract as the SGC n8n and image platform build.
"""
import logging
import requests

from odoo import _, exceptions

_logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "imagen4"
_DEFAULT_SIZE = "1024x1024"


class GenSparkImageGenerator:
    """Handles requests to the self-hosted Genspark2API bridge."""

    @staticmethod
    def generate_image(
        api_url: str,
        api_secret: str,
        prompt: str,
        model: str = _DEFAULT_MODEL,
        size: str = _DEFAULT_SIZE,
        num_images: int = 1,
    ) -> bytes:
        """
        Generate an image through the self-hosted Genspark2API bridge.

        Args:
            api_url: Base URL for the bridge, e.g. http://143.244.130.74:7055
            api_secret: Bearer token used by the bridge
            prompt: Plain text prompt passed directly to the model
            model: Model name exposed by the bridge
            size: Requested image size
            num_images: Number of images to generate (default: 1)

        Returns:
            Raw image bytes downloaded from the returned image URL.

        Raises:
            exceptions.UserError: If authentication fails
            RuntimeError: If API call fails
        """
        endpoint = f"{api_url.rstrip('/')}/v1/images/generations"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_secret}",
        }
        payload = {
            "model": model or _DEFAULT_MODEL,
            "prompt": prompt,
            "n": num_images,
            "size": size or _DEFAULT_SIZE,
        }

        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=180)

            if response.status_code == 401:
                raise exceptions.UserError(
                    _("Invalid GenSpark API secret. Check Settings → SGC TECH AI Settings.")
                )

            response.raise_for_status()

            result = response.json()
            image_rows = result.get("data", [])
            image_url = image_rows[0].get("url") if image_rows else ""
            if not image_url:
                raise ValueError("GenSpark bridge did not return an image URL.")

            image_response = requests.get(image_url, timeout=180)
            image_response.raise_for_status()
            return image_response.content

        except requests.RequestException as e:
            _logger.warning("GenSpark request failed: %s", e)
            raise RuntimeError(f"GenSpark API unavailable: {str(e)}")

    @staticmethod
    def is_configured(config_params) -> bool:
        """Check if GenSpark API is properly configured.

        Args:
            config_params: ir.config_parameter lookup dict

        Returns:
            True if API key is present and not empty
        """
        api_url = config_params.get("website_sgctech_ai.genspark_api_url", "").strip()
        api_secret = config_params.get("website_sgctech_ai.genspark_api_secret", "").strip()
        return bool(api_url and api_secret)
