# -*- coding: utf-8 -*-
{
    'name': 'Bill.com Solid Flow',
    'summary': 'Solid-specific Bill.com approval flow from vendor payments',
    'description': """
        Extends billcom integration with a Solid-specific payment flow:
        - Add Sync Bill + Pay button on vendor payments.
        - Create Bill.com bill from account.payment.
        - Optionally assign specific Bill.com approvers.
    """,
    'author': 'Simple Solutions',
    'website': 'https://simplesolutionsfs.com',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'version': '16.0.1.0.0',
    'depends': [
        'billcom',
    ],
    'data': [
        'views/account_payment_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
