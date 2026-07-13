# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ── Hugging Face (primary — AI generation) ────────────────────────────
    hf_token = fields.Char(
        string="Hugging Face Token",
        config_parameter="website_sgctech_ai.hf_token",
        help="Free token from huggingface.co/settings/tokens — used for FLUX.1-schnell AI image generation.",
    )

    # ── GenSpark2API bridge (secondary AI generation) ─────────────────────
    genspark_api_url = fields.Char(
        string="GenSpark Bridge URL",
        config_parameter="website_sgctech_ai.genspark_api_url",
        help="Base URL of your self-hosted Genspark2API bridge, for example http://143.244.130.74:7055.",
    )
    genspark_api_secret = fields.Char(
        string="GenSpark API Secret",
        config_parameter="website_sgctech_ai.genspark_api_secret",
        help="Bearer secret used by your n8n and Genspark2API workflow.",
    )
    genspark_model = fields.Char(
        string="GenSpark Model",
        config_parameter="website_sgctech_ai.genspark_model",
        help="Image model exposed by your bridge. The current n8n workflow uses imagen4.",
    )

    # ── Pexels (fallback — stock photo) ───────────────────────────────────
    pexels_api_key = fields.Char(
        string="Pexels API Key",
        config_parameter="website_sgctech_ai.pexels_api_key",
        help="Free API key from pexels.com/api — used as fallback stock photo when HF is unavailable.",
    )

    # ── Cloudinary (optional CDN) ─────────────────────────────────────────
    cloudinary_cloud_name = fields.Char(
        string="Cloud Name",
        config_parameter="website_sgctech_ai.cloudinary_cloud_name",
        help="Cloudinary cloud name. Leave blank to store images directly in Odoo.",
    )
    cloudinary_api_key = fields.Char(
        string="Cloudinary API Key",
        config_parameter="website_sgctech_ai.cloudinary_api_key",
    )
    cloudinary_api_secret = fields.Char(
        string="Cloudinary API Secret",
        config_parameter="website_sgctech_ai.cloudinary_api_secret",
    )

    # ── Hero Particle Text ────────────────────────────────────────────────────
    particle_words = fields.Char(
        string="Homepage Phrases",
        config_parameter="website_sgctech_ai.particle_words",
        help=(
            "Phrases displayed as animated particles on the Homepage hero. "
            "Separate phrases with  |  and optionally append  ::r,g,b:r,g,b:angle:holdMs  for gradient "
            "colours and per-phrase hold time (ms). "
            "Example: SGC Tech AI. We keep you alive.::0,229,160:0,212,255:270:2500"
        ),
    )

    particle_words_about = fields.Char(
        string="About Page Phrases",
        config_parameter="website_sgctech_ai.particle_words_about",
        help=(
            "Phrases displayed as animated particles on the About Us hero. "
            "Separate phrases with  |  and optionally append  ::r,g,b:r,g,b:angle:holdMs  for gradient "
            "colours and per-phrase hold time (ms)."
        ),
    )
