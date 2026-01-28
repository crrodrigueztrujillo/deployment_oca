# Copyright 2025 Binhex - Antonio Ruban
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StockDeliveryProofImage(models.Model):
    _name = "stock.delivery.proof.image"
    _description = "Delivery Proof Image"
    _order = "create_date desc"

    move_line_id = fields.Many2one(
        comodel_name="stock.move.line",
        required=False,
        ondelete="cascade",
        index=True,
        help="Link to move line (for per-line mode)",
    )
    picking_id = fields.Many2one(
        comodel_name="stock.picking",
        required=False,
        ondelete="cascade",
        index=True,
        help="Link to picking (for per-picking mode)",
    )
    image = fields.Binary(
        string="Photo",
        required=True,
        attachment=False,  # Store directly in DB, not as ir.attachment
    )
    capture_date = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
    )
    captured_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Captured By",
        default=lambda self: self.env.user,
        required=True,
    )
    notes = fields.Text()

    @api.constrains("move_line_id", "picking_id")
    def _check_move_line_or_picking(self):
        """Ensure at least one reference is provided."""
        for record in self:
            if not record.move_line_id and not record.picking_id:
                raise ValidationError(
                    _("Photo must be linked to either a move line or a picking.")
                )

    def name_get(self):
        """Custom name display for photos."""
        result = []
        for record in self:
            if record.move_line_id:
                ref = record.move_line_id.picking_id.name or "Move Line"
            elif record.picking_id:
                ref = record.picking_id.name or "Picking"
            else:
                ref = "Photo"
            name = _("%(ref)s - %(date)s") % {
                "ref": ref,
                "date": record.capture_date.strftime("%Y-%m-%d %H:%M:%S"),
            }
            result.append((record.id, name))
        return result

    def action_download_image(self):
        """Download the delivery proof image as attachment."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self._name}/{self.id}/image?download=true",
            "target": "self",
        }

    def action_open_gallery(self):
        """Open image gallery carousel starting from this image."""
        self.ensure_one()
        params = {"image_id": self.id}

        if self.move_line_id:
            params["move_line_id"] = self.move_line_id.id
        elif self.picking_id:
            params["picking_id"] = self.picking_id.id

        return {
            "type": "ir.actions.client",
            "tag": "open_delivery_proof_gallery",
            "params": params,
        }
