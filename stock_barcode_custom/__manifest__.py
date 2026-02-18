{
    "name": "Stock Barcode Custom",
    "summary": "Barcode operations for Odoo Community inventory workflows",
    "version": "16.0.1.0.0",
    "category": "Inventory/Inventory",
    "author": "Custom",
    "license": "LGPL-3",
    "depends": ["stock", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/stock_picking_assign_driver_views.xml",
        "views/stock_barcode_photo_views.xml",
        "views/stock_barcode_menu_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_barcode_custom/static/src/scss/stock_barcode_app.scss",
            "stock_barcode_custom/static/src/js/stock_barcode_app.js",
            "stock_barcode_custom/static/src/xml/stock_barcode_app.xml",
        ]
    },
    "application": True,
    "installable": True,
}
