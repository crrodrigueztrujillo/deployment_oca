# Copyright 2025 Binhex - Antonio Ruban
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    # Visibility
    show_delivery_proof = fields.Boolean(
        compute="_compute_show_delivery_proof",
    )

    delivery_proof_level = fields.Selection(related="company_id.delivery_proof_level")

    # Picking-level photos (using unified model)
    picking_proof_image_ids = fields.One2many(
        "stock.delivery.proof.image",
        "picking_id",
        string="Delivery Proof Photos (Picking Level)",
    )
    picking_proof_count = fields.Integer(
        compute="_compute_picking_proof_count",
        string="Photo Count (Picking)",
    )

    # Filtered move lines
    move_lines_with_photos = fields.Many2many(
        comodel_name="stock.move.line",
        compute="_compute_move_lines_with_photos",
        string="Move Lines with Delivery Proof",
        help="Move lines that have at least one delivery proof photo",
    )

    @api.depends("picking_type_code", "company_id.delivery_proof_enabled")
    def _compute_show_delivery_proof(self):
        for picking in self:
            picking.show_delivery_proof = (
                picking.picking_type_code in ("outgoing", "incoming")
                and picking.company_id.delivery_proof_enabled
            )

    @api.depends("picking_proof_image_ids")
    def _compute_picking_proof_count(self):
        for picking in self:
            picking.picking_proof_count = len(picking.picking_proof_image_ids)

    @api.depends("move_line_ids_without_package.delivery_proof_count")
    def _compute_move_lines_with_photos(self):
        for picking in self:
            picking.move_lines_with_photos = (
                picking.move_line_ids_without_package.filtered(
                    lambda line: line.delivery_proof_count > 0
                )
            )
