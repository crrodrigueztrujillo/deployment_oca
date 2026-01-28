# Copyright 2025 Binhex - Antonio Ruban
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    delivery_proof_enabled = fields.Boolean(
        related="company_id.delivery_proof_enabled",
        readonly=False,
    )
    delivery_proof_level = fields.Selection(
        related="company_id.delivery_proof_level",
        readonly=False,
    )
