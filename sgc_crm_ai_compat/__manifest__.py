# -*- coding: utf-8 -*-
{
    "name": "SGC - CRM AI Compatibility",
    'version': '19.0.1.0.0',
    "category": "CRM",
    "summary": "Emergency compatibility fix for ai_enrichment_report field",
    "description": """
 SGC CRM AI Field Compatibility
 ============================
 Emergency module to ensure ai_enrichment_report field exists on crm.lead model.

 This module provides a compatibility layer to prevent OwlError when llm_lead_scoring
 module is not installed or not properly upgraded.

 Features:
 ---------
 * Adds ai_enrichment_report field if missing
 * CloudPepper-safe implementation
 * No dependencies on llm_lead_scoring
 * Emergency fix for production stability

 Deploy Priority: CRITICAL
     """,
    "author": "SmartClinic",
    "website": "https://smartclinic.ae",
    "license": "LGPL-3",
    "depends": [
        "crm",
    ],
    "data": [
        "views/crm_lead_views_compatibility.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
    "sequence": 1,  # Load early
}
