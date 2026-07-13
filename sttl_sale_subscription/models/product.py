from odoo import fields, models, api
from odoo.exceptions import ValidationError



class Product(models.Model):
    _inherit = 'product.product'

    is_recurring = fields.Boolean("Recurring")
    subscription_price_ids = fields.One2many(comodel_name='product.subscription.pricing', inverse_name='product_id')

    @api.model_create_multi
    def create(self,vals):
        result = super(Product,self).create(vals)
        for rec in result:
            if rec.is_recurring and len(rec.subscription_price_ids):
                if rec.product_tmpl_id:
                    for price in rec.product_tmpl_id.subscription_price_ids:
                        price.unlink()
                    
                    for price in rec.subscription_price_ids:
                        rec.product_tmpl_id.subscription_price_ids.create({
                            "period_id": price.period_id.id,
                            "price": price.price,
                            "product_id": price.product_id.product_tmpl_id.id
                        })
                    rec.product_tmpl_id.is_recurring = True
                
        return result

    def write(self,vals):
        result = super(Product,self).write(vals)
        for rec in self:
            if rec.is_recurring :
                if len(rec.subscription_price_ids):
                    if rec.product_tmpl_id:
                        for price in rec.product_tmpl_id.subscription_price_ids:
                            price.unlink()
                        
                        for price in rec.subscription_price_ids:
                            rec.product_tmpl_id.subscription_price_ids.create({
                                "period_id": price.period_id.id,
                                "price": price.price,
                                "product_id": price.product_id.product_tmpl_id.id
                            })
                        rec.product_tmpl_id.is_recurring = True
                else:
                    for price in rec.product_tmpl_id.subscription_price_ids:
                        price.unlink()
            else:
                rec.product_tmpl_id.is_recurring = False
                for price in rec.subscription_price_ids:
                    price.unlink()
                for price in rec.product_tmpl_id.subscription_price_ids:
                    price.unlink()
        return result

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_recurring = fields.Boolean("Recurring")
    subscription_price_ids = fields.One2many(comodel_name='product.subscription.pricing', inverse_name='product_id' )

    # @api.model_create_multi
    # def create(self,vals):
    #     result = super(ProductTemplate,self).create(vals)
    #     print("CREATe is called", result)
    #     for rec in result:
    #         if rec.is_recurring and len(rec.subscription_price_ids):
    #             if len(rec.subscription_price_ids):
    #                 for variant in rec.product_variant_ids:
    #                     for price in variant.subscription_price_ids:
    #                         price.unlink()
    #
    #                 for price in rec.subscription_price_ids:
    #                     for variant in rec.product_variant_ids:
    #                         variant.subscription_price_ids.create({
    #                             "period_id": price.period_id.id,
    #                             "price": price.price,
    #                             "product_id": variant.id
    #                         })
    #                         variant.is_recurring = True
    #
    #     return result
    #
    # def write(self,vals):
    #     result = super(ProductTemplate,self).write(vals)
    #     for rec in self:
    #         if rec.is_recurring :
    #             if len(rec.subscription_price_ids):
    #                 if len(rec.product_variant_ids):
    #                     for variant in rec.product_variant_ids:
    #                         for price in variant.subscription_price_ids:
    #                             price.unlink()
    #                         for price in rec.subscription_price_ids:
    #                             for variant in rec.product_variant_ids:
    #                                 variant.subscription_price_ids.create({
    #                                     "period_id": price.period_id.id,
    #                                     "price": price.price,
    #                                     "product_id": variant.id
    #                                 })
    #                         variant.is_recurring = True
    #             else:
    #                 for variant in rec.product_variant_ids:
    #                     for price in variant.subscription_price_ids:
    #                         price.unlink()
    #         else:
    #             # rec.is_recurring = False
    #             for price in rec.subscription_price_ids:
    #                 price.unlink()
    #             for variant in rec.product_variant_ids:
    #                 for price in variant.subscription_price_ids:
    #                     price.unlink()
    #     return result

class ProductSubscriptionPricing(models.Model):
    _name = 'product.subscription.pricing'
    _description = 'product subscription pricing'

    name = fields.Char(string='Name')
    price = fields.Float(string='Price')
    period_id = fields.Many2one(comodel_name='product.subscription.period', string='Period')
    product_id = fields.Many2one(comodel_name='product.product', string='Product')

    

class ProductSubscriptionPeriod(models.Model):
    _name = "product.subscription.period"
    _description = "Product Subscription Period"

    name = fields.Char(string='Name')
    duration = fields.Integer(string='Duration')
    unit = fields.Selection(
        string='Unit',
        selection=[
            ('days', 'Days'),
            ('weeks', 'Weeks'),
            ('month', 'Months'),
            ('year', 'Years'),
            ('semi_monthly', 'Semi-Monthly (Twice a Month)'),
        ],
    )
    day_1 = fields.Integer(
        string='First Day of Month',
        default=14,
        help='First billing day of the month (1-31). Automatically capped to the last day for shorter months like February.',
    )
    day_2 = fields.Integer(
        string='Second Day of Month',
        default=24,
        help='Second billing day of the month (1-31). Automatically capped to the last day for shorter months like February.',
    )

    price_ids = fields.One2many(comodel_name='product.subscription.pricing', inverse_name='period_id', string='Pricing')

    @api.constrains('day_1', 'day_2', 'unit')
    def _check_semi_monthly_days(self):
        for rec in self:
            if rec.unit == 'semi_monthly':
                if not (1 <= rec.day_1 <= 31) or not (1 <= rec.day_2 <= 31):
                    raise ValidationError("Billing days must be between 1 and 31.")
                if rec.day_1 == rec.day_2:
                    raise ValidationError("The two billing days must be different.")
        