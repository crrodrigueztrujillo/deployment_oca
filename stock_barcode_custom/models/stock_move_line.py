from odoo import fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    barcode_photo_ids = fields.One2many("stock.barcode.photo", "move_line_id")
    barcode_photo_count = fields.Integer(compute="_compute_barcode_photo_count")

    def _compute_barcode_photo_count(self):
        for line in self:
            line.barcode_photo_count = len(line.barcode_photo_ids)
