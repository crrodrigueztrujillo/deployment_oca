{
    "name": "Stock Barcodes Delivery Proof",
    "summary": "Capture delivery proof photos via barcode scanner per move line",
    "version": "16.0.6.4.0",
    "author": "Binhex, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/stock-logistics-barcode",
    "license": "AGPL-3",
    "category": "Warehouse",
    "depends": ["stock_barcodes"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/stock_barcodes_read_picking_views.xml",
        "views/stock_delivery_proof_image_views.xml",
        "views/stock_picking_views.xml",
    ],
    "qweb": [
        "static/src/components/photo_gallery_modal/photo_gallery_modal.xml",
        "static/src/components/camera_capture/camera_capture.xml",
        "static/src/components/image_carousel/image_carousel.xml",
        "static/src/components/delivery_proof_gallery/delivery_proof_gallery.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_barcodes_delivery_proof/static/src/components/**/*",
            "stock_barcodes_delivery_proof/static/src/actions/**/*.esm.js",
            "stock_barcodes_delivery_proof/static/src/scss/**/*.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
