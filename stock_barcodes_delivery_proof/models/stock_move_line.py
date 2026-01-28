# Copyright 2025 Binhex - Antonio Ruban
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    delivery_proof_image_ids = fields.One2many(
        comodel_name="stock.delivery.proof.image",
        inverse_name="move_line_id",
        string="Delivery Proof Photos",
    )
    delivery_proof_count = fields.Integer(
        compute="_compute_delivery_proof_count",
        string="Photo Count",
        store=True,
    )
    has_delivery_proof = fields.Boolean(
        compute="_compute_delivery_proof_count",
        string="Has Photos",
        store=True,
    )

    @api.depends("delivery_proof_image_ids")
    def _compute_delivery_proof_count(self):
        for line in self:
            count = len(line.delivery_proof_image_ids)
            line.delivery_proof_count = count
            line.has_delivery_proof = count > 0

    def action_open_line_photos(self):
        """Open photo gallery for this move line."""
        self.ensure_one()
        return {
            "name": "Delivery Proof Photos",
            "type": "ir.actions.act_window",
            "res_model": "stock.delivery.proof.image",
            "view_mode": "kanban",
            "domain": [("move_line_id", "=", self.id)],
            "context": {"default_move_line_id": self.id},
        }
