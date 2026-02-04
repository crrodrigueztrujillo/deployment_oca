from odoo import api, fields, models, Command


class PurchaseContainer(models.Model):
    _name = "purchase.container"
    _description = "Purchase order related container"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(compute="_compute_name", store=True,
                       readonly=True, index=True)
    code = fields.Char(
        string="Container Reference",
        compute="_compute_code",
        inverse="_inverse_code",
        store=True,
        required=True,
        copy=False,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('at_sea', 'At sea'),
        ('pod_arrived', 'Arribo POD'),
        ('delivered', 'Delivered'),
    ], string='State', default='draft')

    bill_of_lading_ref = fields.Char("Bill Of Lading No.", copy=False)
    shipping_agent_id = fields.Many2one(
        comodel_name="res.partner", string="Shipping Agent", domain=[('category_id', 'in', [121])])
    type_id = fields.Many2one(comodel_name="container.type")
    package_qty = fields.Integer(copy=False)
    cost = fields.Float(digits="Product Price", copy=False)
    cost_currency_id = fields.Many2one(
        "res.currency", "Cost Currency", copy=False)
    volume = fields.Float(digits="Volume", copy=False, string="Area")
    volume_uom_id = fields.Many2one(
        "uom.uom",
        string="Volume Units of Measure",
        domain=lambda self: [
            ("category_id", "=", self.env.ref("uom.product_uom_categ_vol").id)
        ],
        default=lambda self: self.env[
            "product.template"
        ]._get_volume_uom_id_from_ir_config_parameter(),
    )
    weight = fields.Float(string="Bruto Weight",
                          digits="Stock Weight", copy=False)
    weight_uom_id = fields.Many2one(
        "uom.uom",
        string="Weight Units of Measure",
        domain=lambda self: [
            ("category_id", "=", self.env.ref("uom.product_uom_categ_kgm").id)
        ],
        help="Weight Unit of Measure",
        default=lambda self: self.env[
            "product.template"
        ]._get_weight_uom_id_from_ir_config_parameter(),
    )
    purchase_order_ids = fields.Many2many(
        "purchase.order", string="Related Purchases", copy=False
    )
    purchase_order_count = fields.Integer(
        string="Purchases", compute="_compute_purchase_order_count"
    )
    purchase_order_rfq_count = fields.Integer(
        string="RFQ", compute="_compute_purchase_order_rfq_count"
    )
    picking_ids = fields.One2many(
        comodel_name="stock.picking",
        inverse_name="container_id",
        string="Related Pickings",
    )
    picking_count = fields.Integer(
        string="Receipts", compute="_compute_picking_count")

    date_etd = fields.Date('Date ETD')
    date_eta = fields.Date('Date ETA')
    date_received = fields.Date('Date Received')
    date_pickup = fields.Date('Date Pickup')

    product_summary_line_ids = fields.One2many(
        comodel_name="purchase.container.product.line",
        inverse_name="container_id",
        string="Products Summary",
        readonly=True,
        copy=False,
    )

    def sync_product_summary_lines(self):
        """Asegura 1 línea por producto presente en las PO del contenedor.
        Crea faltantes y elimina sobrantes.
        """
        Line = self.env["purchase.container.product.line"]
        for container in self:
            po_lines = container.purchase_order_ids.mapped("order_line").filtered(
                lambda l: not l.display_type and l.product_id
            )
            product_ids = set(po_lines.mapped("product_id").ids)

            existing_lines = container.product_summary_line_ids
            existing_product_ids = set(existing_lines.mapped("product_id").ids)

            # Crear líneas faltantes
            to_create = list(product_ids - existing_product_ids)
            if to_create:
                Line.create([
                    {
                        "container_id": container.id,
                        "product_id": pid,
                    }
                    for pid in to_create
                ])

            # Eliminar líneas que ya no aplican
            to_remove = existing_lines.filtered(
                lambda ln: ln.product_id.id not in product_ids)
            if to_remove:
                to_remove.unlink()

    @api.depends("code", "purchase_order_ids")
    def _compute_name(self):
        for record in self:
            record.name = record.code
            po = record.purchase_order_ids
            if po:
                record.name += " ({})".format(",".join(po.mapped("name")))

    @api.model
    def _code_transform(self, code):
        return code.upper() if code else code

    @api.model
    def _code_from_name(self, name):
        words = name.split() if name else None
        code = words[0] if words else False
        return self._code_transform(code)

    @api.depends("name")
    def _compute_code(self):
        for record in self:
            if not record.code:
                record.code = record._code_from_name(record.name)

    def _inverse_code(self):
        for record in self:
            code = self._code_transform(record.code)
            if record.code != code:
                record.code = code

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("code", self._code_from_name(vals.get("name")))
        records = super().create(vals_list)
        records.sync_product_summary_lines()
        return records

    def write(self, vals):
        res = super().write(vals)
        # Si cambian las POs relacionadas, re-sincroniza líneas
        if "purchase_order_ids" in vals:
            self.sync_product_summary_lines()
        return res

    def _compute_purchase_order_count(self):
        for record in self:
            record.purchase_order_count = self.env["purchase.order"].search_count(
                [
                    ("state", "in", ("purchase", "done")),
                    ("container_ids", "=", self.id),
                ],
            )

    def _compute_purchase_order_rfq_count(self):
        for record in self:
            record.purchase_order_rfq_count = self.env["purchase.order"].search_count(
                [
                    ("state", "in", ("draft", "sent", "to approve")),
                    ("container_ids", "=", self.id),
                ],
            )

    def _compute_picking_count(self):
        for record in self:
            record.picking_count = len(record.picking_ids)

    def action_view_rfq(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "purchase.purchase_rfq")
        action["domain"] = [
            (
                "id",
                "in",
                [
                    po.id
                    for po in self.purchase_order_ids
                    if po.state in ("draft", "sent", "to approve")
                ],
            )
        ]
        action["context"] = {"create": False}
        return action

    def action_view_order(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "purchase.purchase_form_action"
        )
        action["domain"] = [
            (
                "id",
                "in",
                [
                    po.id
                    for po in self.purchase_order_ids
                    if po.state in ("purchase", "done")
                ],
            )
        ]
        action["context"] = {"create": False}
        return action

    def action_view_picking(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock.action_picking_tree_all"
        )
        action["domain"] = [("id", "in", self.picking_ids.ids)]
        action["context"] = {"create": False}
        return action


class PurchaseContainerProductLine(models.Model):
    _name = "purchase.container.product.line"
    _description = "Purchase Container Product Summary Line"
    _order = "product_id"

    container_id = fields.Many2one(
        "purchase.container",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one(
        "product.product",
        required=True,
        index=True,
    )

    uom_id = fields.Many2one(
        "uom.uom",
        compute="_compute_qty",
        store=True,
        readonly=True,
    )
    qty_ordered = fields.Float(
        string="Ordered",
        compute="_compute_qty",
        store=True,
        readonly=True,
        digits="Product Unit of Measure",
    )
    qty_received = fields.Float(
        string="Received",
        compute="_compute_qty",
        store=True,
        readonly=True,
        digits="Product Unit of Measure",
    )
    qty_pending = fields.Float(
        string="Pending",
        compute="_compute_qty",
        store=True,
        readonly=True,
        digits="Product Unit of Measure",
    )

    @api.depends(
        "product_id",
        "container_id.purchase_order_ids",
        "container_id.purchase_order_ids.order_line",
        "container_id.purchase_order_ids.order_line.product_id",
        "container_id.purchase_order_ids.order_line.product_qty",
        "container_id.purchase_order_ids.order_line.qty_received",
        "container_id.purchase_order_ids.order_line.product_uom",
    )
    def _compute_qty(self):
        for line in self:
            ordered = received = 0.0

            if not line.container_id or not line.product_id:
                line.uom_id = False
                line.qty_ordered = 0.0
                line.qty_received = 0.0
                line.qty_pending = 0.0
                continue

            product = line.product_id
            target_uom = product.uom_po_id or product.uom_id
            line.uom_id = target_uom

            po_lines = line.container_id.purchase_order_ids.mapped("order_line").filtered(
                lambda l: not l.display_type and l.product_id.id == product.id
            )

            for pol in po_lines:
                ordered += pol.product_uom._compute_quantity(
                    pol.product_qty, target_uom)
                received += pol.product_uom._compute_quantity(
                    pol.qty_received, target_uom)

            pending = ordered - received
            if pending < 0:
                pending = 0.0

            line.qty_ordered = ordered
            line.qty_received = received
            line.qty_pending = pending
