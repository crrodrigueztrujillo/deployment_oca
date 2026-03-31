# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    website_project_name = fields.Char(
        string="Website Project Name",
        help="Project name entered by the customer on /shop/payment (free cart confirmation).",
        copy=False,
    )
