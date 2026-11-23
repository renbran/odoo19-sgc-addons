# -*- coding: utf-8 -*-
"""Pre-migrate for 19.0.1.8: Lead Intelligence Engine schema bump.
New fields (entity_hint, ai_entity_type, ai_entity_type_confidence, 11 score floats,
ai_scoring_rationale, ai_budget_tier, ai_industry, ai_readiness, ai_enrichment_evidence,
ai_classification_mismatch) are created by ORM registry sync on module load with safe defaults:
False for booleans/selections, 0.0 for floats, '' for char/text, None for relations.
No data migration/backfill is needed. Existing records retain their ai_enrichment_data
text field unchanged; new fields get their defaults automatically."""


def migrate(cr, version):
    return
