# -*- coding: utf-8 -*-

from odoo import api, models


class TierDefinition(models.Model):
    _inherit = 'tier.definition'

    @api.model
    def _get_tier_validation_model_names(self):
        res = super()._get_tier_validation_model_names()
        if 'account.payment' not in res:
            res.append('account.payment')
        return res
