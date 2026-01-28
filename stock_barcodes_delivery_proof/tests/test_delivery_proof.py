# Copyright 2025 Binhex - Antonio Ruban
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).


from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDeliveryProof(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Enable delivery proof with temperature tracking
        cls.env.company.write(
            {
                "delivery_proof_enabled": True,
                "delivery_proof_temperature_required": False,
                "delivery_proof_temperature_min": -20.0,
                "delivery_proof_temperature_max": 20.0,
            }
        )

        # Create test data
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Angelina Bakery",
            }
        )

        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Cake",
                "type": "product",
            }
        )

        cls.warehouse = cls.env["stock.warehouse"].search([], limit=1)
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.customer_location = cls.env.ref("stock.stock_location_customers")

        # Create picking type for outgoing
        cls.picking_type_out = cls.env["stock.picking.type"].search(
            [
                ("code", "=", "outgoing"),
                ("warehouse_id", "=", cls.warehouse.id),
            ],
            limit=1,
        )

        # Sample image data (1x1 transparent PNG)
        cls.sample_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="  # noqa E501

    def test_01_delivery_proof_creation(self):
        """Test creating a delivery proof image."""
        picking = self._create_outgoing_picking()

        # Create delivery proof
        proof = self.env["stock.delivery.proof"].create(
            {
                "name": "Test Photo",
                "image": self.sample_image,
                "picking_id": picking.id,
            }
        )

        self.assertTrue(proof.attachment_id)
        self.assertEqual(proof.picking_id, picking)
        self.assertTrue(proof.image)

    def test_02_delivery_proof_temperature(self):
        """Test delivery proof with temperature tracking."""
        picking = self._create_outgoing_picking()

        # Create proof with temperature
        proof = self.env["stock.delivery.proof"].create(
            {
                "name": "Photo with Temperature",
                "image": self.sample_image,
                "picking_id": picking.id,
                "temperature": 4.5,
                "temperature_unit": "celsius",
            }
        )

        self.assertEqual(proof.temperature, 4.5)
        self.assertEqual(proof.temperature_unit, "celsius")
        self.assertTrue(proof.temperature_valid)  # Within range

    def test_03_picking_proof_count(self):
        """Test delivery proof count on picking."""
        picking = self._create_outgoing_picking()

        self.assertEqual(picking.delivery_proof_count, 0)

        # Create multiple proofs
        for i in range(3):
            self.env["stock.delivery.proof"].create(
                {
                    "name": f"Photo {i}",
                    "image": self.sample_image,
                    "picking_id": picking.id,
                }
            )

        self.assertEqual(picking.delivery_proof_count, 3)

    def test_04_wizard_save_delivery_proof(self):
        """Test saving delivery proof from wizard."""
        picking = self._create_outgoing_picking()
        picking.action_confirm()
        picking.action_assign()

        # Create wizard
        wizard = self.env["wiz.stock.barcodes.read.picking"].create(
            {
                "picking_id": picking.id,
                "picking_type_code": "outgoing",
                "option_group_id": self.env.ref(
                    "stock_barcodes.stock_barcodes_option_group_out"
                ).id,
            }
        )

        # Save delivery proof
        proof = wizard.action_save_delivery_proof(image_data=self.sample_image)

        self.assertEqual(proof.picking_id, picking)
        self.assertTrue(proof.image)
        self.assertEqual(picking.delivery_proof_count, 1)

    def test_05_wizard_save_temperature(self):
        """Test saving temperature from wizard."""
        picking = self._create_outgoing_picking()
        picking.action_confirm()
        picking.action_assign()

        # Create wizard
        wizard = self.env["wiz.stock.barcodes.read.picking"].create(
            {
                "picking_id": picking.id,
                "picking_type_code": "outgoing",
                "option_group_id": self.env.ref(
                    "stock_barcodes.stock_barcodes_option_group_out"
                ).id,
            }
        )

        # Save temperature
        proof = wizard.action_save_delivery_proof(
            temperature=4.5, temperature_unit="celsius"
        )

        self.assertEqual(proof.temperature, 4.5)
        self.assertEqual(proof.temperature_unit, "celsius")
        self.assertEqual(picking.delivery_proof_count, 1)

    def test_06_wizard_delete_delivery_proof(self):
        """Test deleting delivery proof from wizard."""
        picking = self._create_outgoing_picking()

        # Create proof
        proof = self.env["stock.delivery.proof"].create(
            {
                "name": "Test Photo",
                "image": self.sample_image,
                "picking_id": picking.id,
            }
        )

        # Create wizard
        wizard = self.env["wiz.stock.barcodes.read.picking"].create(
            {
                "picking_id": picking.id,
                "picking_type_code": "outgoing",
                "option_group_id": self.env.ref(
                    "stock_barcodes.stock_barcodes_option_group_out"
                ).id,
            }
        )

        # Delete proof
        result = wizard.action_delete_delivery_proof(proof_id=proof.id)

        self.assertTrue(result)
        self.assertFalse(proof.exists())
        self.assertEqual(picking.delivery_proof_count, 0)

    def test_07_attachment_deletion_on_proof_unlink(self):
        """Test that attachment is deleted when proof is deleted."""
        picking = self._create_outgoing_picking()

        proof = self.env["stock.delivery.proof"].create(
            {
                "name": "Test Photo",
                "image": self.sample_image,
                "picking_id": picking.id,
            }
        )

        attachment_id = proof.attachment_id.id

        proof.unlink()

        # Check that attachment is also deleted
        attachment = self.env["ir.attachment"].browse(attachment_id)
        self.assertFalse(attachment.exists())

    def test_08_show_delivery_proof_outgoing_only(self):
        """Test that delivery proof is only shown for outgoing pickings."""
        # Outgoing picking
        picking_out = self._create_outgoing_picking()
        self.assertTrue(picking_out.show_delivery_proof)

        # Incoming picking
        picking_in = self.env["stock.picking"].create(
            {
                "partner_id": self.partner.id,
                "picking_type_id": self.env["stock.picking.type"]
                .search(
                    [
                        ("code", "=", "incoming"),
                    ],
                    limit=1,
                )
                .id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": self.stock_location.id,
            }
        )
        self.assertFalse(picking_in.show_delivery_proof)

    def test_09_get_delivery_proof_data(self):
        """Test getting delivery proof data from wizard."""
        picking = self._create_outgoing_picking()

        # Create proofs
        proof1 = self.env["stock.delivery.proof"].create(
            {
                "name": "Photo 1",
                "image": self.sample_image,
                "picking_id": picking.id,
            }
        )

        proof2 = self.env["stock.delivery.proof"].create(
            {
                "name": "Photo 2",
                "image": self.sample_image,
                "picking_id": picking.id,
                "temperature": 3.0,
                "temperature_unit": "celsius",
            }
        )

        # Create wizard
        wizard = self.env["wiz.stock.barcodes.read.picking"].create(
            {
                "picking_id": picking.id,
                "picking_type_code": "outgoing",
                "option_group_id": self.env.ref(
                    "stock_barcodes.stock_barcodes_option_group_out"
                ).id,
            }
        )

        # Get proof data
        data = wizard.get_delivery_proof_data()

        self.assertEqual(len(data), 2)
        self.assertTrue(any(d["id"] == proof1.id for d in data))
        self.assertTrue(any(d["id"] == proof2.id for d in data))
        # Check temperature data is included
        proof2_data = next(d for d in data if d["id"] == proof2.id)
        self.assertEqual(proof2_data["temperature"], 3.0)

    def _create_outgoing_picking(self):
        """Helper to create an outgoing picking."""
        return self.env["stock.picking"].create(
            {
                "partner_id": self.partner.id,
                "picking_type_id": self.picking_type_out.id,
                "location_id": self.stock_location.id,
                "location_dest_id": self.customer_location.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "name": self.product.name,
                            "product_id": self.product.id,
                            "product_uom_qty": 10.0,
                            "product_uom": self.product.uom_id.id,
                            "location_id": self.stock_location.id,
                            "location_dest_id": self.customer_location.id,
                        },
                    )
                ],
            }
        )
