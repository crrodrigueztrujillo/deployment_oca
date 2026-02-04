
# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, date
from odoo.exceptions import ValidationError, UserError


class AccountMoveInherit(models.Model):
    _inherit = "account.move"

    container_ids = fields.Many2many('purchase.container', string='Containers')
