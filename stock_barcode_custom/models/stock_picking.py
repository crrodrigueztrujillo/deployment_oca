from odoo import _, fields, models
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    delivery_driver_id = fields.Many2one("res.users", string="Driver")
    delivery_signature = fields.Image(string="Customer Signature")
    delivery_signed_by = fields.Char(string="Signed By")
    delivery_signed_on = fields.Datetime(string="Signed On")
    delivery_note = fields.Text(string="Delivery Notes")
    barcode_photo_ids = fields.One2many("stock.barcode.photo", "picking_id", string="Barcode Line Photos")
    picking_photo_ids = fields.One2many("stock.picking.photo", "picking_id", string="Driver Photos")

    delivery_proof_state = fields.Selection(
        [("pending", "Pending"), ("signed", "Signed")],
        default="pending",
        string="Delivery Proof",
    )


    def write(self, vals):
        res = super().write(vals)
        if "delivery_signature" in vals:
            for picking in self:
                if picking.delivery_signature:
                    picking.delivery_proof_state = "signed"
                    if not picking.delivery_signed_on:
                        picking.delivery_signed_on = fields.Datetime.now()
                else:
                    picking.delivery_proof_state = "pending"
                    picking.delivery_signed_on = False
        return res

    def _action_barcode_force_validate(self):
        self.ensure_one()
        result = self.button_validate()
        if isinstance(result, dict) and result.get("res_model") == "stock.immediate.transfer":
            wizard = self.env["stock.immediate.transfer"].browse(result.get("res_id")).exists()
            if wizard:
                wizard.process()
                result = self.button_validate()
        if isinstance(result, dict) and result.get("res_model") == "stock.backorder.confirmation":
            wizard = self.env["stock.backorder.confirmation"].browse(result.get("res_id")).exists()
            if wizard:
                wizard.process()
        return True

    def action_open_custom_barcode(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "stock_barcode_custom_main",
            "name": "Barcode",
            "context": {
                "default_operation_model": "stock.picking",
                "default_operation_id": self.id,
            },
        }

    def action_open_assign_driver_wizard(self):
        self.ensure_one()
        return {
            "name": _("Assign Driver"),
            "type": "ir.actions.act_window",
            "res_model": "stock.picking.assign.driver",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_picking_id": self.id,
                "default_driver_id": self.delivery_driver_id.id,
            },
        }

    def action_mark_delivery_signed(self):
        for picking in self:
            if picking.delivery_signature:
                picking.delivery_proof_state = "signed"
                if not picking.delivery_signed_on:
                    picking.delivery_signed_on = fields.Datetime.now()

    def action_driver_complete_delivery(self):
        for picking in self:
            if picking.picking_type_code != "outgoing":
                continue
            if not picking.delivery_signature:
                raise ValidationError(_("Customer signature is required to complete delivery."))
            if not picking.delivery_signed_by:
                raise ValidationError(_("Signed by is required to complete delivery."))
            if picking.state in {"assigned", "partially_available", "confirmed"}:
                picking._action_barcode_force_validate()
            picking.delivery_proof_state = "signed"
            if not picking.delivery_signed_on:
                picking.delivery_signed_on = fields.Datetime.now()
        return True

