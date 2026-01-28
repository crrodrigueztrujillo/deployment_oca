# Copyright 2025 Binhex - Antonio Ruban
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    delivery_proof_enabled = fields.Boolean(
        string="Enable Delivery Proof Capture",
        default=False,
        help="Allow capturing photos as delivery proof from the barcode "
        "scanner interface. Only applies to outgoing pickings (deliveries).",
    )
    delivery_proof_level = fields.Selection(
        [
            ("move_line", "Per Move Line"),
            ("picking", "Per Picking"),
        ],
        default="move_line",
        help="Choose where delivery proof photos are stored:\n"
        "- Per Move Line: Photos are captured for each individual product line\n"
        "- Per Picking: Photos are captured at the picking/delivery level",
    )
