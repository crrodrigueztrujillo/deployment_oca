from odoo import fields, models


class StockBarcodePhoto(models.Model):
    _name = "stock.barcode.photo"
    _description = "Barcode Move Line Photo"
    _order = "create_date desc"

    move_line_id = fields.Many2one("stock.move.line", required=True, ondelete="cascade")
    picking_id = fields.Many2one(related="move_line_id.picking_id", store=True, readonly=True)
    product_id = fields.Many2one(related="move_line_id.product_id", store=True, readonly=True)
    image_1920 = fields.Image(required=True)
    note = fields.Char()


class StockPickingPhoto(models.Model):
    _name = "stock.picking.photo"
    _description = "Delivery/Picking Photo"
    _order = "create_date desc"

    picking_id = fields.Many2one("stock.picking", required=True, ondelete="cascade")
    image_1920 = fields.Image(required=True)
    note = fields.Char()
