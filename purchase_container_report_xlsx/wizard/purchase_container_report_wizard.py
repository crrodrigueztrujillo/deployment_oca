# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError
import io
import base64
import xlsxwriter


class PurchaseContainerReportWizard(models.TransientModel):
    _name = "purchase.container.report.wizard"
    _description = "Purchase Container Excel Report Wizard"

    date_from = fields.Date(string="Date From", required=True)
    date_to = fields.Date(string="Date To", required=True)

    file_data = fields.Binary(string="File", readonly=True)
    file_name = fields.Char(string="Filename", readonly=True)

    def _get_out_invoices_for_so(self, so):
        """Return customer invoices linked to the SO (best-effort)."""
        Move = self.env["account.move"].sudo()
        domain = [
            ("move_type", "=", "out_invoice"),
            ("state", "!=", "cancel"),
        ]
        invoices = Move.search(domain).filtered(
            lambda m: (
                so in m.invoice_line_ids.mapped("sale_line_ids.order_id")
            ) or (
                m.invoice_origin and so.name in m.invoice_origin
            )
        )
        return invoices

    def _find_purchase_orders_for_so(self, so):
        """purchase_sale_link_by_origin behavior: PO.origin contains SO name."""
        PO = self.env["purchase.order"].sudo()
        return PO.search([("origin", "ilike", so.name)])

    def _state_label(self, container):
        return dict(container._fields["state"].selection).get(container.state, container.state or "")

    def action_generate_excel(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_("Date From must be before Date To."))

        # SALES ORDERS filter (by date_order).
        # If you want invoice_date instead, change this domain.
        SO = self.env["sale.order"].sudo()
        so_domain = [
            ("date_order", ">=", fields.Datetime.to_datetime(self.date_from)),
            ("date_order", "<=", fields.Datetime.to_datetime(self.date_to)),
        ]
        sale_orders = SO.search(so_domain, order="date_order, id")

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {"in_memory": True})
        ws = wb.add_worksheet("Report")

        headers = [
            "Date", "Project", "SO", "PO", "Status", "Container", "Invoice", "Vendor",
            "Material", "Quantity", "Unit", "Quantity", "Unit", "Milagros", "SqFt", "Pablo", "Odoo"
        ]

        header_fmt = wb.add_format({
            "bold": True, "align": "center", "valign": "vcenter",
            "border": 1, "bg_color": "#D9D9D9"
        })
        text_fmt = wb.add_format({"border": 1, "valign": "vcenter"})
        num_fmt = wb.add_format(
            {"border": 1, "valign": "vcenter", "num_format": "#,##0.00"})
        date_fmt = wb.add_format(
            {"border": 1, "valign": "vcenter", "num_format": "yyyy-mm-dd"})

        ws.freeze_panes(1, 0)
        ws.set_row(0, 18)
        ws.set_column(0, len(headers) - 1, 13)

        for col, h in enumerate(headers):
            ws.write(0, col, h, header_fmt)

        row = 1
        today = fields.Date.context_today(self)

        for so in sale_orders:
            project = so.project_id.display_name if hasattr(
                so, "project_id") and so.project_id else ""
            po_list = self._find_purchase_orders_for_so(so)
            po_name = ", ".join(po_list.mapped("name")) if po_list else ""
            vendor = ", ".join(sorted(
                set(po_list.mapped("partner_id").mapped("display_name")))) if po_list else ""

            containers = po_list.mapped("container_ids")
            if not containers:
                containers = po_list.mapped(
                    "picking_ids").mapped("container_id")

            invoices = self._get_out_invoices_for_so(so)

            # If there are invoices, group rows by invoice so Milagros/SqFt appear once per invoice.
            # If not, print rows without invoice grouping.
            if invoices:
                for inv in invoices:
                    # Lines: 1 row per product_summary_line in each related container
                    lines_to_print = []
                    for c in containers:
                        for pl in c.product_summary_line_ids:
                            lines_to_print.append((c, pl))

                    if not lines_to_print:
                        continue

                    group_start_row = row
                    sqft_sum = 0.0

                    for (container, pline) in lines_to_print:
                        material = pline.product_id.display_name
                        qty = pline.qty_ordered or 0.0
                        uom = pline.uom_id.name if pline.uom_id else ""
                        sqft_sum += qty

                        ws.write_datetime(
                            row, 0, fields.Date.to_date(today), date_fmt)
                        ws.write(row, 1, project, text_fmt)
                        ws.write(row, 2, so.name or "", text_fmt)
                        ws.write(row, 3, po_name, text_fmt)
                        ws.write(row, 4, self._state_label(
                            container), text_fmt)
                        ws.write(row, 5, container.name or "", text_fmt)
                        # "Invoice" column: numeric reference like sample file (we use invoice id).
                        ws.write(row, 6, inv.id, text_fmt)
                        ws.write(row, 7, vendor, text_fmt)
                        ws.write(row, 8, material, text_fmt)
                        ws.write_number(row, 9, qty, num_fmt)
                        ws.write(row, 10, uom, text_fmt)
                        ws.write(row, 11, "", text_fmt)
                        ws.write(row, 12, "", text_fmt)

                        if row == group_start_row:
                            ws.write(row, 13, inv.name or "", text_fmt)
                            # overwritten after loop
                            ws.write_number(row, 14, sqft_sum, num_fmt)
                        else:
                            ws.write(row, 13, "", text_fmt)
                            ws.write(row, 14, "", text_fmt)

                        ws.write(row, 15, "", text_fmt)  # Pablo
                        ws.write(row, 16, "", text_fmt)  # Odoo
                        row += 1

                    ws.write_number(group_start_row, 14, sqft_sum, num_fmt)
            else:
                for container in containers:
                    for pline in container.product_summary_line_ids:
                        material = pline.product_id.display_name
                        qty = pline.qty_ordered or 0.0
                        uom = pline.uom_id.name if pline.uom_id else ""

                        ws.write_datetime(
                            row, 0, fields.Date.to_date(today), date_fmt)
                        ws.write(row, 1, project, text_fmt)
                        ws.write(row, 2, so.name or "", text_fmt)
                        ws.write(row, 3, po_name, text_fmt)
                        ws.write(row, 4, self._state_label(
                            container), text_fmt)
                        ws.write(row, 5, container.name or "", text_fmt)
                        ws.write(row, 6, "", text_fmt)
                        ws.write(row, 7, vendor, text_fmt)
                        ws.write(row, 8, material, text_fmt)
                        ws.write_number(row, 9, qty, num_fmt)
                        ws.write(row, 10, uom, text_fmt)
                        ws.write(row, 11, "", text_fmt)
                        ws.write(row, 12, "", text_fmt)
                        ws.write(row, 13, "", text_fmt)
                        ws.write(row, 14, "", text_fmt)
                        ws.write(row, 15, "", text_fmt)
                        ws.write(row, 16, "", text_fmt)
                        row += 1

        wb.close()
        output.seek(0)

        filename = "reporte_contenedores_%s_%s.xlsx" % (
            self.date_from, self.date_to)

        # IMPORTANT: fields.Binary must be base64-encoded
        xlsx_bytes = output.read()
        self.write({
            "file_name": filename,
            "file_data": base64.b64encode(xlsx_bytes),
        })

        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/?model=%s&id=%s&field=file_data&filename_field=file_name&download=true" % (self._name, self.id),
            "target": "self",
        }
