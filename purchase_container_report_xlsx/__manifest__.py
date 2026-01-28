# -*- coding: utf-8 -*-
{
    "name": "Purchase Container Excel Report",
    "version": "16.0.1.0.0",
    "category": "Purchases",
    "summary": "Wizard to export container/material report to Excel",
    "license": "LGPL-3",
    "author": "Custom",
    "depends": ["purchase", "sale_management", "account", "stock","purchase_container"],
    "data": [
        "security/ir.model.access.csv",
        "views/purchase_container_report_wizard_views.xml",
        "views/purchase_container_report_menu.xml",
    ],
    "installable": True,
    "application": False,
}
