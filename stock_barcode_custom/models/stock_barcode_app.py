from odoo import _, api, models
from odoo.exceptions import UserError


class StockBarcodeApp(models.AbstractModel):
    _name = "stock.barcode.app"
    _description = "Custom Barcode Application Service"

    @api.model
    def get_dashboard_data(self, warehouse_id=False):
        picking_obj = self.env["stock.picking"]
        base_domain = [("state", "in", ["assigned", "confirmed", "partially_available"])]
        picking_domain = self._append_warehouse_domain([], warehouse_id, "stock.picking")
        inventory_domain = self._append_warehouse_domain([("location_id.usage", "=", "internal")], warehouse_id, "stock.quant")

        data = {
            "receipt": picking_obj.search_count(base_domain + [("picking_type_code", "=", "incoming")] + picking_domain),
            "internal": picking_obj.search_count(base_domain + [("picking_type_code", "=", "internal")] + picking_domain),
            "delivery": picking_obj.search_count(base_domain + [("picking_type_code", "=", "outgoing")] + picking_domain),
            "inventory": self.env["stock.quant"].search_count(inventory_domain),
            "batch": 0,
            "warehouses": self._get_warehouses_payload(),
        }
        if "stock.picking.batch" in self.env:
            batch_domain = self._append_warehouse_domain([("state", "in", ["in_progress", "draft"])], warehouse_id, "stock.picking.batch")
            data["batch"] = self.env["stock.picking.batch"].search_count(batch_domain)
        return data

    def _get_warehouses_payload(self):
        warehouses = self.env["stock.warehouse"].search([])
        values = [{"id": 0, "name": _("All warehouses")}]
        values.extend([{"id": wh.id, "name": wh.display_name} for wh in warehouses])
        return values

    def _append_warehouse_domain(self, domain, warehouse_id, model_name):
        if not warehouse_id:
            return domain
        try:
            warehouse_id = int(warehouse_id)
        except (TypeError, ValueError):
            return domain
        if warehouse_id <= 0:
            return domain
        if model_name == "stock.picking":
            return domain + [("picking_type_id.warehouse_id", "=", warehouse_id)]
        if model_name == "stock.picking.batch":
            return domain + [("picking_ids.picking_type_id.warehouse_id", "=", warehouse_id)]
        if model_name == "stock.location":
            warehouse = self.env["stock.warehouse"].browse(warehouse_id).exists()
            if warehouse and warehouse.lot_stock_id:
                return domain + [("id", "child_of", warehouse.lot_stock_id.id)]
        if model_name == "stock.quant":
            warehouse = self.env["stock.warehouse"].browse(warehouse_id).exists()
            if warehouse and warehouse.lot_stock_id:
                return domain + [("location_id", "child_of", warehouse.lot_stock_id.id)]
        return domain

    @api.model
    def search_operations(self, operation_type, query=None, limit=30, warehouse_id=False):
        query = (query or "").strip()
        if operation_type == "batch":
            if "stock.picking.batch" not in self.env:
                return []
            model = self.env["stock.picking.batch"]
            domain = [("state", "in", ["draft", "in_progress"])]
        elif operation_type in {"receipt", "internal", "delivery"}:
            model = self.env["stock.picking"]
            code_map = {"receipt": "incoming", "internal": "internal", "delivery": "outgoing"}
            domain = [
                ("state", "in", ["assigned", "confirmed", "partially_available"]),
                ("picking_type_code", "=", code_map[operation_type]),
            ]
        elif operation_type == "inventory":
            model = self.env["stock.location"]
            domain = [("usage", "=", "internal")]
        else:
            return []

        domain = self._append_warehouse_domain(domain, warehouse_id, model._name)
        if query:
            if model._name == "stock.picking":
                domain = ["|", "|", "|", ("name", "ilike", query), ("origin", "ilike", query), ("partner_id.name", "ilike", query), ("note", "ilike", query)] + domain
            else:
                domain = ["|", ("name", "ilike", query), ("display_name", "ilike", query)] + domain
        records = model.search(domain, limit=limit)
        return [self._serialize_record(record) for record in records]

    @api.model
    def load_operation(self, operation_model, operation_id):
        rec = self.env[operation_model].browse(operation_id).exists()
        if not rec:
            raise UserError(_("Operation not found."))
        if operation_model == "stock.picking":
            return {
                "header": self._serialize_record(rec),
                "lines": self._serialize_picking_lines(rec),
                "packagings": self._serialize_packagings(rec),
                "can_validate": rec.state in {"assigned", "partially_available"},
                "state": rec.state,
            }
        if operation_model == "stock.picking.batch":
            batch_lines = []
            packagings = []
            for picking in rec.picking_ids:
                batch_lines.extend(self._serialize_picking_lines(picking))
                packagings.extend(self._serialize_packagings(picking))
            unique_packagings = {p["id"]: p for p in packagings if p.get("id")}
            return {
                "header": self._serialize_record(rec),
                "lines": batch_lines,
                "packagings": list(unique_packagings.values()),
                "can_validate": rec.state in {"draft", "in_progress"},
                "state": rec.state,
            }
        if operation_model == "stock.location":
            quants = self.env["stock.quant"].search([
                ("location_id", "=", rec.id),
                ("quantity", "!=", 0),
            ])
            return {
                "header": self._serialize_record(rec),
                "lines": [self._serialize_quant(quant) for quant in quants],
                "packagings": [],
                "can_validate": False,
                "state": "draft",
            }
        raise UserError(_("Unsupported operation."))

    @api.model
    def process_scan(self, operation_model, operation_id, barcode, quantity=1.0, qty_mode="unit", packaging_id=False):
        barcode = (barcode or "").strip()
        if not barcode:
            raise UserError(_("Scan a barcode first."))
        quantity_units = self._convert_qty_to_units(quantity, qty_mode, packaging_id)
        if operation_model in {"stock.picking", "stock.picking.batch"}:
            return self._process_picking_scan(operation_model, operation_id, barcode, quantity_units, qty_mode, packaging_id)
        if operation_model == "stock.location":
            return self._process_inventory_scan(operation_id, barcode, quantity_units)
        raise UserError(_("Unsupported operation model."))

    def _convert_qty_to_units(self, quantity, qty_mode, packaging_id):
        qty = float(quantity or 0.0)
        if qty <= 0:
            raise UserError(_("Quantity must be greater than zero."))
        if qty_mode != "package" or not packaging_id:
            return qty
        packaging = self.env["product.packaging"].browse(packaging_id).exists()
        if not packaging:
            raise UserError(_("Selected packaging is invalid."))
        return qty * packaging.qty

    def _ensure_outgoing_not_overdone(self, move, add_qty):
        if not move or move.picking_id.picking_type_code != "outgoing":
            return
        planned = move.product_uom_qty
        done = sum(move.move_line_ids.mapped("qty_done"))
        if done + add_qty > planned + 1e-6:
            raise UserError(
                _(
                    "Cannot deliver more than planned for %(product)s. Planned: %(planned)s %(uom)s, already done: %(done)s %(uom)s, trying to add: %(add)s %(uom)s."
                )
                % {
                    "product": move.product_id.display_name,
                    "planned": planned,
                    "done": done,
                    "add": add_qty,
                    "uom": move.product_uom.display_name,
                }
            )

    def _get_move_line_expected_qty(self, move_line):
        if "product_uom_qty" in move_line._fields:
            return move_line.product_uom_qty or 0.0
        if "reserved_uom_qty" in move_line._fields:
            return move_line.reserved_uom_qty or 0.0
        return 0.0

    def _process_picking_scan(self, operation_model, operation_id, barcode, quantity_units, qty_mode, packaging_id):
        if operation_model == "stock.picking":
            pickings = self.env["stock.picking"].browse(operation_id).exists()
        else:
            batch = self.env["stock.picking.batch"].browse(operation_id).exists()
            pickings = batch.picking_ids.filtered(lambda p: p.state in {"assigned", "confirmed", "partially_available"})

        if not pickings:
            raise UserError(_("No active transfer found for this operation."))

        product = self.env["product.product"].search(["|", ("barcode", "=", barcode), ("default_code", "=", barcode)], limit=1)
        if product:
            moves = pickings.mapped("move_ids_without_package").filtered(lambda m: m.product_id == product)
            if not moves:
                raise UserError(_("Product %s is not expected in this operation.") % product.display_name)

            move = False
            for m in moves:
                remaining = m.product_uom_qty - sum(m.move_line_ids.mapped("qty_done"))
                if m.picking_id.picking_type_code != "outgoing" or remaining > 1e-6:
                    move = m
                    break
            move = move or moves[0]
            self._ensure_outgoing_not_overdone(move, quantity_units)

            move_lines = move.move_line_ids
            instructed_lot_lines = move_lines.filtered(lambda ml: ml.lot_id and self._get_move_line_expected_qty(ml) > 0)
            if move.product_id.tracking != "none" and instructed_lot_lines:
                raise UserError(_("This move has instructed lots. Scan lot barcode to register real picked quantities."))
            candidates = move_lines.filtered(lambda line: line.qty_done < (line.move_id.product_uom_qty if line.move_id else 0.0))
            if not candidates:
                candidates = move_lines
            if not candidates:
                line_vals = {
                    "picking_id": move.picking_id.id,
                    "move_id": move.id,
                    "company_id": move.company_id.id,
                    "product_id": move.product_id.id,
                    "product_uom_id": move.product_uom.id,
                    "location_id": move.location_id.id,
                    "location_dest_id": move.location_dest_id.id,
                    "qty_done": 0,
                }
                candidates = self.env["stock.move.line"].create(line_vals)
            line = candidates[0]
            line.qty_done += quantity_units
            if qty_mode == "package" and packaging_id:
                packaging = self.env["product.packaging"].browse(packaging_id).exists()
                return {
                    "message": _("%s: +%s %s (%s units).") % (line.product_id.display_name, quantity_units / packaging.qty, packaging.display_name, quantity_units),
                    "line_id": line.id,
                    "product_name": line.product_id.display_name,
                }
            return {
                "message": _("%s updated: %s done.") % (line.product_id.display_name, line.qty_done),
                "line_id": line.id,
                "product_name": line.product_id.display_name,
            }

        lot = self.env["stock.lot"].search([("name", "=", barcode)], limit=1)
        if lot:
            moves = pickings.mapped("move_ids_without_package").filtered(lambda m: m.product_id == lot.product_id)
            if not moves:
                raise UserError(_("Lot %s does not match pending lines.") % lot.name)
            move = moves[0]
            self._ensure_outgoing_not_overdone(move, quantity_units)

            move_lines = move.move_line_ids.filtered(lambda l: l.product_id == lot.product_id)
            existing_lot_line = move_lines.filtered(lambda l: l.lot_id == lot)[:1]
            if existing_lot_line:
                expected_lot_qty = self._get_move_line_expected_qty(existing_lot_line)
                if move.picking_id.picking_type_code == "outgoing" and expected_lot_qty > 0 and existing_lot_line.qty_done + quantity_units > expected_lot_qty + 1e-6:
                    raise UserError(
                        _("Lot %(lot)s exceeds instructed quantity. Instructed: %(exp)s %(uom)s, scanned: %(done)s %(uom)s, adding: %(add)s %(uom)s.")
                        % {
                            "lot": lot.name,
                            "exp": expected_lot_qty,
                            "done": existing_lot_line.qty_done,
                            "add": quantity_units,
                            "uom": move.product_uom.display_name,
                        }
                    )
                existing_lot_line.qty_done += quantity_units
                return {
                    "message": _("Lot %s updated for %s.") % (lot.name, existing_lot_line.product_id.display_name),
                    "line_id": existing_lot_line.id,
                    "product_name": existing_lot_line.product_id.display_name,
                }

            empty_lot_line = move_lines.filtered(lambda l: not l.lot_id)[:1]
            if empty_lot_line:
                expected_lot_qty = self._get_move_line_expected_qty(empty_lot_line)
                if move.picking_id.picking_type_code == "outgoing" and expected_lot_qty > 0 and quantity_units > expected_lot_qty + 1e-6:
                    raise UserError(
                        _("Lot %(lot)s exceeds instructed quantity. Instructed: %(exp)s %(uom)s, adding: %(add)s %(uom)s.")
                        % {
                            "lot": lot.name,
                            "exp": expected_lot_qty,
                            "add": quantity_units,
                            "uom": move.product_uom.display_name,
                        }
                    )
                empty_lot_line.lot_id = lot
                empty_lot_line.qty_done += quantity_units
                return {
                    "message": _("Lot %s assigned to %s.") % (lot.name, empty_lot_line.product_id.display_name),
                    "line_id": empty_lot_line.id,
                    "product_name": empty_lot_line.product_id.display_name,
                }

            instructed_lot_lines = move_lines.filtered(lambda ml: ml.lot_id and self._get_move_line_expected_qty(ml) > 0)
            if move.picking_id.picking_type_code == "outgoing" and instructed_lot_lines:
                raise UserError(_("Lot %s is not part of instructed lots for this move.") % lot.name)

            line_vals = {
                "picking_id": move.picking_id.id,
                "move_id": move.id,
                "company_id": move.company_id.id,
                "product_id": move.product_id.id,
                "product_uom_id": move.product_uom.id,
                "location_id": move.location_id.id,
                "location_dest_id": move.location_dest_id.id,
                "lot_id": lot.id,
                "qty_done": quantity_units,
            }
            new_line = self.env["stock.move.line"].create(line_vals)
            return {
                "message": _("Lot %s assigned to %s.") % (lot.name, new_line.product_id.display_name),
                "line_id": new_line.id,
                "product_name": new_line.product_id.display_name,
            }

        location = self.env["stock.location"].search([("barcode", "=", barcode)], limit=1)
        if location:
            for location_field, label in (("location_id", _("source")), ("location_dest_id", _("destination"))):
                line = pickings.mapped("move_line_ids").filtered(lambda l: getattr(l, location_field) == location)[:1]
                if line:
                    return {
                        "message": _("%s location scanned: %s.") % (label.title(), location.display_name),
                        "line_id": line.id,
                        "product_name": line.product_id.display_name,
                    }
            raise UserError(_("Location %s does not match transfer lines.") % location.display_name)

        raise UserError(_("Barcode not recognized in this operation."))

    def _process_inventory_scan(self, location_id, barcode, quantity):
        location = self.env["stock.location"].browse(location_id).exists()
        product = self.env["product.product"].search([
            "|", ("barcode", "=", barcode), ("default_code", "=", barcode)
        ], limit=1)
        if not location or not product:
            raise UserError(_("Scan a valid product for inventory adjustments."))
        quant = self.env["stock.quant"].search([
            ("product_id", "=", product.id),
            ("location_id", "=", location.id),
        ], limit=1)
        if not quant:
            quant = self.env["stock.quant"].create({
                "product_id": product.id,
                "location_id": location.id,
                "company_id": self.env.company.id,
            })
        quant.inventory_quantity = (quant.inventory_quantity or 0.0) + quantity
        quant.action_apply_inventory()
        return {
            "message": _("Counted %s in %s.") % (product.display_name, location.display_name),
            "line_id": quant.id,
            "product_name": product.display_name,
        }

    @api.model
    def validate_operation(self, operation_model, operation_id):
        rec = self.env[operation_model].browse(operation_id).exists()
        if not rec:
            raise UserError(_("Operation not found."))

        if operation_model == "stock.picking":
            rec._action_barcode_force_validate()
            return {"ok": True, "state": rec.state}
        if operation_model == "stock.picking.batch":
            for picking in rec.picking_ids.filtered(lambda p: p.state in {"assigned", "partially_available", "confirmed"}):
                picking._action_barcode_force_validate()
            return {"ok": True, "state": rec.state}
        return {"ok": True}


    @api.model
    def set_move_done_qty(self, operation_model, operation_id, move_id, qty_done):
        rec = self.env[operation_model].browse(operation_id).exists()
        if not rec:
            raise UserError(_("Operation not found."))

        if operation_model == "stock.picking":
            pickings = rec
        elif operation_model == "stock.picking.batch":
            pickings = rec.picking_ids
        else:
            raise UserError(_("Manual quantity edit is only available for pickings."))

        move = self.env["stock.move"].browse(move_id).exists()
        if not move or move.picking_id not in pickings:
            raise UserError(_("Line not found in selected operation."))

        qty_done = float(qty_done or 0.0)
        if qty_done < 0:
            raise UserError(_("Quantity cannot be negative."))

        self._ensure_outgoing_not_overdone(move, qty_done - sum(move.move_line_ids.mapped("qty_done")))

        move_lines = move.move_line_ids
        if not move_lines:
            move_lines = self.env["stock.move.line"].create({
                "picking_id": move.picking_id.id,
                "move_id": move.id,
                "company_id": move.company_id.id,
                "product_id": move.product_id.id,
                "product_uom_id": move.product_uom.id,
                "location_id": move.location_id.id,
                "location_dest_id": move.location_dest_id.id,
                "qty_done": 0.0,
            })

        first_line = move_lines[0]
        first_line.qty_done = qty_done
        if len(move_lines) > 1:
            (move_lines - first_line).write({"qty_done": 0.0})

        return {"ok": True, "message": _("Quantity updated for %s.") % move.product_id.display_name}

    @api.model
    def set_move_line_lot_instruction(self, operation_model, operation_id, move_line_id, lot_name, qty_expected):
        rec = self.env[operation_model].browse(operation_id).exists()
        if not rec:
            raise UserError(_("Operation not found."))
        if operation_model == "stock.picking":
            pickings = rec
        elif operation_model == "stock.picking.batch":
            pickings = rec.picking_ids
        else:
            raise UserError(_("Lot instruction edit is only available for pickings."))

        move_line = self.env["stock.move.line"].browse(move_line_id).exists()
        if not move_line or move_line.picking_id not in pickings:
            raise UserError(_("Move line not found in selected operation."))

        qty_expected = float(qty_expected or 0.0)
        if qty_expected < 0:
            raise UserError(_("Instruction quantity cannot be negative."))

        lot_name = (lot_name or "").strip()
        lot = False
        if lot_name:
            lot = self.env["stock.lot"].search([
                ("name", "=", lot_name),
                ("product_id", "=", move_line.product_id.id),
            ], limit=1)
            if not lot:
                raise UserError(_("Lot %s does not exist for product %s.") % (lot_name, move_line.product_id.display_name))

        move = move_line.move_id
        if move and move.picking_id.picking_type_code == "outgoing":
            other_expected = sum(self._get_move_line_expected_qty(ml) for ml in (move.move_line_ids - move_line))
            if other_expected + qty_expected > move.product_uom_qty + 1e-6:
                raise UserError(
                    _("Instructed quantity by lots exceeds demand for %s.") % move.product_id.display_name
                )

        vals = {"lot_id": lot.id if lot else False}
        if "reserved_uom_qty" in move_line._fields:
            vals["reserved_uom_qty"] = qty_expected
        elif "product_uom_qty" in move_line._fields:
            vals["product_uom_qty"] = qty_expected
        move_line.write(vals)

        return {"ok": True, "message": _("Lot instruction updated for %s.") % move_line.product_id.display_name}

    @api.model
    def set_move_line_lot_qty(self, operation_model, operation_id, move_line_id, lot_name, qty_done):
        rec = self.env[operation_model].browse(operation_id).exists()
        if not rec:
            raise UserError(_("Operation not found."))
        if operation_model == "stock.picking":
            pickings = rec
        elif operation_model == "stock.picking.batch":
            pickings = rec.picking_ids
        else:
            raise UserError(_("Lot quantity edit is only available for pickings."))

        move_line = self.env["stock.move.line"].browse(move_line_id).exists()
        if not move_line or move_line.picking_id not in pickings:
            raise UserError(_("Move line not found in selected operation."))

        qty_done = float(qty_done or 0.0)
        if qty_done < 0:
            raise UserError(_("Quantity cannot be negative."))

        lot_name = (lot_name or "").strip()
        lot = False
        if lot_name:
            lot = self.env["stock.lot"].search([
                ("name", "=", lot_name),
                ("product_id", "=", move_line.product_id.id),
            ], limit=1)
            if not lot:
                raise UserError(_("Lot %s does not exist for product %s.") % (lot_name, move_line.product_id.display_name))

        move = move_line.move_id
        if move and move.picking_id.picking_type_code == "outgoing":
            other_done = sum((move.move_line_ids - move_line).mapped("qty_done"))
            if other_done + qty_done > move.product_uom_qty + 1e-6:
                raise UserError(_("Cannot deliver more than planned for %s.") % move.product_id.display_name)

        move_line.write({
            "lot_id": lot.id if lot else False,
            "qty_done": qty_done,
        })
        return {"ok": True, "message": _("Lot/quantity updated for %s.") % move_line.product_id.display_name}

    @api.model
    def create_move_line_photo(self, move_line_id, image_base64, note=None):
        line = self.env["stock.move.line"].browse(move_line_id).exists()
        if not line:
            raise UserError(_("Move line not found."))
        photo = self.env["stock.barcode.photo"].create({
            "move_line_id": line.id,
            "image_1920": image_base64,
            "note": note or _("Captured from barcode app"),
        })
        return {"id": photo.id}

    @api.model
    def create_picking_photo(self, picking_id, image_base64, note=None):
        picking = self.env["stock.picking"].browse(picking_id).exists()
        if not picking:
            raise UserError(_("Delivery not found."))
        photo = self.env["stock.picking.photo"].create({
            "picking_id": picking.id,
            "image_1920": image_base64,
            "note": note or _("Captured by driver"),
        })
        return {"id": photo.id}

    @api.model
    def resolve_barcode_product(self, barcode, operation_model=False, operation_id=False):
        barcode = (barcode or "").strip()
        if not barcode:
            return {"found": False}
        product = self.env["product.product"].search([
            "|", ("barcode", "=", barcode), ("default_code", "=", barcode)
        ], limit=1)
        if not product:
            return {"found": False}
        in_operation = True
        if operation_model and operation_id and operation_model in {"stock.picking", "stock.picking.batch"}:
            rec = self.env[operation_model].browse(operation_id).exists()
            products = rec.mapped("move_ids_without_package.product_id") if operation_model == "stock.picking" else rec.picking_ids.mapped("move_ids_without_package.product_id")
            in_operation = product in products
        return {
            "found": True,
            "id": product.id,
            "name": product.display_name,
            "in_operation": in_operation,
        }

    @api.model
    def search_driver_deliveries(self, query=None, limit=30, warehouse_id=False):
        query = (query or "").strip()
        domain = [
            ("picking_type_code", "=", "outgoing"),
            ("delivery_driver_id", "=", self.env.user.id),
            ("state", "in", ["assigned", "confirmed", "partially_available", "done"]),
        ]
        domain = self._append_warehouse_domain(domain, warehouse_id, "stock.picking")
        if query:
            domain = ["|", "|", ("name", "ilike", query), ("origin", "ilike", query), ("partner_id.name", "ilike", query)] + domain
        pickings = self.env["stock.picking"].search(domain, limit=limit)
        return [self._serialize_driver_header(picking) for picking in pickings]

    @api.model
    def load_driver_delivery(self, picking_id):
        picking = self.env["stock.picking"].browse(picking_id).exists()
        if not picking:
            raise UserError(_("Delivery not found."))
        if picking.picking_type_code != "outgoing":
            raise UserError(_("This operation is not a delivery."))
        if picking.delivery_driver_id and picking.delivery_driver_id != self.env.user:
            raise UserError(_("This delivery is not assigned to you."))
        return {
            "header": self._serialize_driver_header(picking),
            "lines": self._serialize_picking_lines(picking),
            "proof": {
                "signed_by": picking.delivery_signed_by or "",
                "note": picking.delivery_note or "",
                "has_signature": bool(picking.delivery_signature),
                "proof_state": picking.delivery_proof_state,
            },
            "photos": [
                {
                    "id": photo.id,
                    "note": photo.note or "",
                    "create_date": photo.create_date,
                    "url": f"/web/image/stock.picking.photo/{photo.id}/image_1920",
                }
                for photo in picking.picking_photo_ids[:20]
            ],
        }

    @api.model
    def save_driver_delivery_proof(self, picking_id, signed_by, note=None, signature_base64=None, complete=False):
        picking = self.env["stock.picking"].browse(picking_id).exists()
        if not picking:
            raise UserError(_("Delivery not found."))
        vals = {
            "delivery_signed_by": (signed_by or "").strip(),
            "delivery_note": note or False,
        }
        if signature_base64:
            vals["delivery_signature"] = signature_base64
        picking.write(vals)
        if complete:
            picking.action_driver_complete_delivery()
        return {
            "ok": True,
            "proof_state": picking.delivery_proof_state,
            "state": picking.state,
        }

    def _serialize_record(self, record):
        warehouse = False
        source_location = False
        dest_location = False
        if record._name == "stock.picking":
            warehouse = record.picking_type_id.warehouse_id.display_name or ""
            source_location = record.location_id.display_name
            dest_location = record.location_dest_id.display_name
        elif record._name == "stock.picking.batch":
            warehouse = ", ".join(record.picking_ids.mapped("picking_type_id.warehouse_id.display_name"))
        return {
            "id": record.id,
            "name": record.display_name,
            "model": record._name,
            "raw_name": getattr(record, "name", record.display_name),
            "warehouse": warehouse,
            "location_src": source_location,
            "location_dest": dest_location,
        }

    def _serialize_driver_header(self, picking):
        partner = picking.partner_id
        address_parts = [partner.street, partner.street2, partner.city]
        address = ", ".join([part for part in address_parts if part])
        return {
            "id": picking.id,
            "name": picking.name,
            "model": picking._name,
            "raw_name": picking.name,
            "customer": partner.display_name,
            "address": address,
            "driver": picking.delivery_driver_id.display_name,
            "state": picking.state,
            "proof_state": picking.delivery_proof_state,
            "warehouse": picking.picking_type_id.warehouse_id.display_name or "",
            "location_src": picking.location_id.display_name,
            "location_dest": picking.location_dest_id.display_name,
        }

    def _serialize_packagings(self, picking):
        values = []
        packages = picking.move_ids_without_package.mapped("product_packaging_id")
        if not packages:
            packages = picking.move_ids_without_package.mapped("product_id.packaging_ids")
        for packaging in packages.filtered(lambda p: p.qty > 0):
            values.append({
                "id": packaging.id,
                "name": packaging.display_name,
                "qty": packaging.qty,
                "product_id": packaging.product_id.id,
            })
        return values

    def _serialize_picking_lines(self, picking):
        lines = []
        move_lines_by_move = {}
        for move_line in picking.move_line_ids:
            if move_line.move_id:
                move_lines_by_move.setdefault(move_line.move_id.id, self.env["stock.move.line"])
                move_lines_by_move[move_line.move_id.id] |= move_line

        for move in picking.move_ids_without_package.sorted(lambda m: (m.product_id.display_name, m.id)):
            move_lines = move_lines_by_move.get(move.id)
            packaging = move.product_packaging_id or move.product_id.packaging_ids[:1]
            package_qty = packaging.qty if packaging and packaging.qty else 0.0
            if move_lines:
                qty_done = sum(move_lines.mapped("qty_done"))
                photo_count = sum(move_lines.mapped("barcode_photo_count"))
                move_line_id = move_lines[:1].id
                lot_name = ", ".join([name for name in move_lines.mapped("lot_id.name") if name])
                lot_details = [
                    {
                        "move_line_id": ml.id,
                        "lot": ml.lot_id.name or "",
                        "qty_done": ml.qty_done,
                        "qty_expected": self._get_move_line_expected_qty(ml),
                    }
                    for ml in move_lines
                ]
            else:
                qty_done = 0.0
                photo_count = 0
                move_line_id = False
                lot_name = ""
                lot_details = []
            lines.append({
                "id": move.id,
                "move_id": move.id,
                "move_line_id": move_line_id,
                "product_id": move.product_id.id,
                "product": move.product_id.display_name,
                "barcode": move.product_id.barcode,
                "lot": lot_name,
                "qty_done": qty_done,
                "qty_expected": move.product_uom_qty,
                "uom": move.product_uom.display_name,
                "photos": photo_count,
                "picking": move.picking_id.name,
                "location_src": move.location_id.display_name,
                "location_dest": move.location_dest_id.display_name,
                "packaging_id": packaging.id if packaging else False,
                "packaging_name": packaging.display_name if packaging else "",
                "packaging_qty": package_qty,
                "qty_done_packages": (qty_done / package_qty) if package_qty else 0.0,
                "qty_expected_packages": (move.product_uom_qty / package_qty) if package_qty else 0.0,
                "lot_details": lot_details,
            })
        return lines

    def _serialize_quant(self, quant):
        return {
            "id": quant.id,
            "move_id": False,
            "move_line_id": False,
            "product_id": quant.product_id.id,
            "product": quant.product_id.display_name,
            "barcode": quant.product_id.barcode,
            "lot": quant.lot_id.name,
            "qty_done": quant.inventory_quantity or 0.0,
            "qty_expected": quant.quantity,
            "uom": quant.product_id.uom_id.display_name,
            "photos": 0,
            "picking": "",
            "location_src": quant.location_id.display_name,
            "location_dest": "",
            "packaging_id": False,
            "packaging_name": "",
            "packaging_qty": 0.0,
            "qty_done_packages": 0.0,
            "qty_expected_packages": 0.0,
            "lot_details": [],
        }
