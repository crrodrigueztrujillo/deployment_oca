# Copyright 2025 Binhex - Antonio Ruban
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class WizStockBarcodesReadPicking(models.TransientModel):
    _inherit = "wiz.stock.barcodes.read.picking"

    # Computed fields for UI
    show_delivery_proof = fields.Boolean(compute="_compute_show_delivery_proof")
    delivery_proof_level = fields.Selection(
        related="picking_id.company_id.delivery_proof_level",
        string="Delivery Proof Level",
    )
    picking_proof_count = fields.Integer(
        related="picking_id.picking_proof_count",
        string="Picking Photo Count",
    )

    @api.depends("picking_type_code", "picking_id.company_id.delivery_proof_enabled")
    def _compute_show_delivery_proof(self):
        for wiz in self:
            wiz.show_delivery_proof = (
                wiz.picking_type_code in ("outgoing", "incoming")
                and wiz.picking_id.company_id.delivery_proof_enabled
            )

    def action_save_delivery_photo(self, move_line_id, image_data):
        """Save a new delivery proof photo for a specific move line.

        Args:
            move_line_id: ID of the stock.move.line
            image_data: Base64 encoded image data

        Returns:
            dict: Created photo record data
        """
        self.ensure_one()

        photo = self.env["stock.delivery.proof.image"].create(
            {
                "move_line_id": move_line_id,
                "image": image_data,
            }
        )

        return {
            "id": photo.id,
            "capture_date": (
                photo.capture_date.isoformat() if photo.capture_date else None
            ),
            "captured_by": photo.captured_by_id.name if photo.captured_by_id else None,
        }

    def action_save_delivery_photo_from_todo(self, todo_id, image_data):
        """Save photo based on company delivery_proof_level setting.

        - If 'move_line': Creates duplicate photo records for each move line in todo
        - If 'picking': Creates single photo record at picking level

        Args:
            todo_id (int): ID of wiz.stock.barcodes.read.todo (optional for picking)
            image_data (str): Base64 encoded image data

        Returns:
            dict: {
                'success': bool,
                'photo_ids': list of created photo IDs,
                'move_line_count': number of lines affected (0 for picking mode),
                'message': success/error message
            }
        """
        self.ensure_one()

        # Check delivery proof level from company settings
        proof_level = self.picking_id.company_id.delivery_proof_level

        if proof_level == "picking":
            # Save to picking level - NO todo_id required
            photo = self.env["stock.delivery.proof.image"].create(
                {
                    "picking_id": self.picking_id.id,
                    "image": image_data,
                }
            )
            return {
                "success": True,
                "photo_ids": [photo.id],
                "move_line_count": 0,
                "message": "Photo saved to picking",
                "mode": "picking",
            }

        # For move_line mode, we MUST have a valid todo
        todo = self.env["wiz.stock.barcodes.read.todo"].browse(todo_id)
        if not todo.exists():
            return {
                "success": False,
                "message": "Todo item not found",
                "photo_ids": [],
                "move_line_count": 0,
            }

        # Default: save to move_line level
        if not todo.line_ids:
            return {
                "success": False,
                "message": "No move lines found for this todo",
                "photo_ids": [],
                "move_line_count": 0,
            }

        # Create photo for each move line
        photo_ids = []
        for move_line in todo.line_ids:
            photo = self.env["stock.delivery.proof.image"].create(
                {
                    "move_line_id": move_line.id,
                    "image": image_data,
                }
            )
            photo_ids.append(photo.id)

        return {
            "success": True,
            "photo_ids": photo_ids,
            "move_line_count": len(photo_ids),
            "message": f"Photo saved to {len(photo_ids)} move line(s)",
            "mode": "move_line",
        }

    def get_todo_photo_data(self, todo_id):
        """Get all photos based on delivery_proof_level setting.

        - If 'picking': Returns all picking-level photos
        - If 'move_line': Returns aggregated photos from all move lines in todo

        Args:
            todo_id (int): ID of wiz.stock.barcodes.read.todo

        Returns:
            dict: {
                'photos': list of photo dicts with metadata,
                'total_count': total number of photos,
                'lines_count': number of move lines (0 for picking mode),
                'lines_with_photos': number of lines that have photos (0 for picking)
            }
        """
        self.ensure_one()
        todo = self.env["wiz.stock.barcodes.read.todo"].browse(todo_id)

        if not todo.exists():
            return {
                "photos": [],
                "total_count": 0,
                "lines_count": 0,
                "lines_with_photos": 0,
            }

        # Check delivery proof level
        proof_level = self.picking_id.company_id.delivery_proof_level

        if proof_level == "picking":
            # Get picking-level photos
            all_photos = []
            for photo in self.picking_id.picking_proof_image_ids:
                all_photos.append(
                    {
                        "id": photo.id,
                        "capture_date": (
                            photo.capture_date.isoformat()
                            if photo.capture_date
                            else None
                        ),
                        "captured_by": (
                            photo.captured_by_id.name if photo.captured_by_id else None
                        ),
                        "picking_id": self.picking_id.id,
                        "picking_name": self.picking_id.name,
                        "model": "stock.delivery.proof.image",
                    }
                )

            # Sort by capture_date (newest first)
            all_photos.sort(key=lambda x: x["capture_date"] or "", reverse=True)

            return {
                "photos": all_photos,
                "total_count": len(all_photos),
                "lines_count": 0,
                "lines_with_photos": 0,
                "mode": "picking",
            }

        # Default: move_line level
        # Collect all photos from all move lines
        all_photos = []
        lines_with_photos = 0

        for move_line in todo.line_ids:
            if move_line.delivery_proof_image_ids:
                lines_with_photos += 1

            for photo in move_line.delivery_proof_image_ids:
                all_photos.append(
                    {
                        "id": photo.id,
                        "capture_date": (
                            photo.capture_date.isoformat()
                            if photo.capture_date
                            else None
                        ),
                        "captured_by": (
                            photo.captured_by_id.name if photo.captured_by_id else None
                        ),
                        "move_line_id": move_line.id,
                        "product_name": move_line.product_id.display_name,
                        "lot_name": move_line.lot_id.name if move_line.lot_id else None,
                        "qty": move_line.qty_done,
                        "uom": move_line.product_uom_id.name,
                        "model": "stock.delivery.proof.image",
                    }
                )

        # Sort by capture date (newest first)
        all_photos.sort(key=lambda x: x.get("capture_date") or "", reverse=True)

        return {
            "photos": all_photos,
            "total_count": len(all_photos),
            "lines_count": len(todo.line_ids),
            "lines_with_photos": lines_with_photos,
            "mode": "move_line",
        }

    def get_picking_photo_data(self):
        """Get all photos for current picking (picking-level mode).

        Returns:
            dict: {
                'photos': list of photo dicts with metadata,
                'total_count': total number of photos,
                'lines_count': 0 (not applicable for picking mode),
                'lines_with_photos': 0 (not applicable for picking mode),
                'mode': 'picking'
            }
        """
        self.ensure_one()
        all_photos = []

        for photo in self.picking_id.picking_proof_image_ids:
            all_photos.append(
                {
                    "id": photo.id,
                    "capture_date": (
                        photo.capture_date.isoformat() if photo.capture_date else None
                    ),
                    "captured_by": (
                        photo.captured_by_id.name if photo.captured_by_id else None
                    ),
                    "picking_id": self.picking_id.id,
                    "picking_name": self.picking_id.name,
                    "model": "stock.delivery.proof.image",
                }
            )

        # Sort by capture_date (newest first)
        all_photos.sort(key=lambda x: x["capture_date"] or "", reverse=True)

        return {
            "photos": all_photos,
            "total_count": len(all_photos),
            "lines_count": 0,
            "lines_with_photos": 0,
            "mode": "picking",
        }

    def action_delete_delivery_photo(self, photo_id):
        """Delete a delivery proof photo.

        Args:
            photo_id: ID of the stock.delivery.proof.image to delete

        Returns:
            bool: True if successful
        """
        self.ensure_one()
        photo = self.env["stock.delivery.proof.image"].browse(photo_id)

        if photo.exists():
            photo.unlink()
            return True
        return False

    def get_move_line_proof_data(self, move_line_id):
        """Get delivery proof data for a specific move line.

        Args:
            move_line_id: ID of the stock.move.line

        Returns:
            dict: Dictionary with photos data for the move line
        """
        self.ensure_one()
        move_line = self.env["stock.move.line"].browse(move_line_id)

        if not move_line.exists():
            return {"photos": [], "photo_count": 0}

        return {
            "photos": [
                {
                    "id": photo.id,
                    "capture_date": (
                        photo.capture_date.isoformat() if photo.capture_date else None
                    ),
                    "captured_by": (
                        photo.captured_by_id.name if photo.captured_by_id else None
                    ),
                }
                for photo in move_line.delivery_proof_image_ids
            ],
            "photo_count": move_line.delivery_proof_count,
        }

    def action_open_line_photos(self, move_line_id):
        """Open photo gallery for a specific move line.

        Args:
            move_line_id: ID of the stock.move.line

        Returns:
            dict: Action dictionary for opening photo modal (handled in JS)
        """
        self.ensure_one()
        move_line = self.env["stock.move.line"].browse(move_line_id)

        if move_line.exists():
            return self.get_move_line_proof_data(move_line_id)
        return {"photos": [], "photo_count": 0}

    def action_open_line_photos_modal(self):
        """Open photo gallery modal for a todo item.

        This is called from the kanban button. The todo_id comes from context.
        We return a client action that triggers the JS modal.
        """
        todo_id = self.env.context.get("todo_id")

        if not todo_id:
            return {"type": "ir.actions.act_window_close"}

        # Return a client action to trigger JS
        return {
            "type": "ir.actions.client",
            "tag": "display_delivery_proof_modal",
            "params": {
                "todo_id": todo_id,
                "wizard_id": self.id,
                "mode": "move_line",
            },
        }

    def action_open_picking_photos_modal(self):
        """Open photo gallery modal for the picking.

        This is called from the bottom bar camera button when in picking mode.
        """
        self.ensure_one()

        return {
            "type": "ir.actions.client",
            "tag": "display_delivery_proof_modal",
            "params": {
                "picking_id": self.picking_id.id,
                "wizard_id": self.id,
                "mode": "picking",
            },
        }
