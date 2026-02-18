from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPickingLotInstruction(models.TransientModel):
    _name = "stock.picking.lot.instruction"
    _description = "Define Lot Instructions"

    picking_id = fields.Many2one("stock.picking", required=True)
    line_ids = fields.One2many("stock.picking.lot.instruction.line", "wizard_id", string="Lot Instructions")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        picking = self.env["stock.picking"].browse(self.env.context.get("default_picking_id")).exists()
        if not picking:
            return res

        line_commands = []
        for move in picking.move_ids_without_package:
            move_lines = move.move_line_ids
            if move_lines:
                for ml in move_lines:
                    line_commands.append((0, 0, {
                        "move_id": move.id,
                        "move_line_id": ml.id,
                        "lot_id": ml.lot_id.id,
                        "qty_expected": ml.reserved_uom_qty if "reserved_uom_qty" in ml._fields else ml.product_uom_qty,
                    }))
            else:
                line_commands.append((0, 0, {
                    "move_id": move.id,
                    "qty_expected": 0.0,
                }))

        res["line_ids"] = line_commands
        return res

    def action_apply(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Add at least one lot instruction line."))

        app = self.env["stock.barcode.app"]
        for line in self.line_ids:
            if not line.move_id:
                continue
            move_line = line.move_line_id
            if not move_line:
                vals = {
                    "picking_id": self.picking_id.id,
                    "move_id": line.move_id.id,
                    "company_id": line.move_id.company_id.id,
                    "product_id": line.move_id.product_id.id,
                    "product_uom_id": line.move_id.product_uom.id,
                    "location_id": line.move_id.location_id.id,
                    "location_dest_id": line.move_id.location_dest_id.id,
                    "qty_done": 0.0,
                }
                if line.lot_id:
                    vals["lot_id"] = line.lot_id.id
                move_line = self.env["stock.move.line"].create(vals)
                line.move_line_id = move_line

            app.set_move_line_lot_instruction(
                "stock.picking",
                self.picking_id.id,
                move_line.id,
                line.lot_id.name if line.lot_id else "",
                line.qty_expected,
            )

        return {"type": "ir.actions.act_window_close"}


class StockPickingLotInstructionLine(models.TransientModel):
    _name = "stock.picking.lot.instruction.line"
    _description = "Define Lot Instruction Line"

    wizard_id = fields.Many2one("stock.picking.lot.instruction", required=True, ondelete="cascade")
    move_id = fields.Many2one("stock.move", required=True)
    move_line_id = fields.Many2one("stock.move.line")
    product_id = fields.Many2one(related="move_id.product_id", readonly=True)
    lot_id = fields.Many2one("stock.lot", domain="[('product_id', '=', product_id)]")
    qty_expected = fields.Float(string="Instruction Qty", digits="Product Unit of Measure")

    @api.onchange("move_id")
    def _onchange_move_id(self):
        for line in self:
            if line.move_id:
                line.move_line_id = line.move_id.move_line_ids[:1]
