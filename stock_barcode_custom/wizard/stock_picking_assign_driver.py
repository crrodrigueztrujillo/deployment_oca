from odoo import fields, models


class StockPickingAssignDriver(models.TransientModel):
    _name = "stock.picking.assign.driver"
    _description = "Assign Driver to Delivery"

    picking_id = fields.Many2one("stock.picking", required=True)
    driver_id = fields.Many2one("res.users", required=True)

    def action_assign(self):
        self.ensure_one()
        self.picking_id.delivery_driver_id = self.driver_id
        return {"type": "ir.actions.act_window_close"}
