# Copyright 2025 Binhex - Antonio Ruban
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class WizStockBarcodesReadTodo(models.TransientModel):
    _inherit = "wiz.stock.barcodes.read.todo"

    delivery_proof_count = fields.Integer(
        compute="_compute_delivery_proof_count",
        string="Total Photos",
        help="Total number of delivery proof photos across all move lines",
    )
    has_delivery_proof = fields.Boolean(
        compute="_compute_delivery_proof_count",
        string="Has Photos",
    )

    @api.depends("line_ids.delivery_proof_count")
    def _compute_delivery_proof_count(self):
        """Calculate total photos from all associated move lines."""
        for todo in self:
            total = sum(line.delivery_proof_count for line in todo.line_ids)
            todo.delivery_proof_count = total
            todo.has_delivery_proof = total > 0

    def action_open_line_photos_modal(self):
        """Open photo gallery modal for this todo item.

        This method is called from the kanban button and delegates to the wizard.
        """
        self.ensure_one()

        # Call the wizard method with this todo's ID in context
        if self.wiz_barcode_id:
            return self.wiz_barcode_id.with_context(
                todo_id=self.id
            ).action_open_line_photos_modal()

        # Fallback if no wizard (shouldn't happen)
        return {"type": "ir.actions.act_window_close"}
