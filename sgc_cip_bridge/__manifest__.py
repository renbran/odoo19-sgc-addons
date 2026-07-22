{
    "name": "SGC CIP Bridge",
    "version": "19.0.1.0.0",
    "summary": "Receives priced proposals pushed from the Commercial Intelligence Platform (CIP) and creates sale quotations.",
    "description": (
        "Exposes a single authenticated webhook endpoint "
        "(/cip-webhook/proposal-push) that the CIP backend calls when an "
        "approved proposal is pushed to Odoo. Creates or reuses a "
        "res.partner for the customer and a sale.order quotation with a "
        "single line item for the proposal total."
    ),
    "category": "Sales",
    "author": "SGCTECH",
    "depends": ["sale"],
    "data": ["data/product_data.xml"],
    "installable": True,
    "application": False,
}
