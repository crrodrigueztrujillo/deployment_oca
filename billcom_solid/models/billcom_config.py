# -*- coding: utf-8 -*-
import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class BillcomSolidApprover(models.Model):
    _name = 'billcom.solid.approver'
    _description = 'Bill.com Solid Approver'
    _order = 'name, billcom_user_id'

    name = fields.Char(
        string='Bill.com User Name',
        required=True,
    )
    billcom_user_id = fields.Char(
        string='Bill.com User ID',
        required=True,
        index=True,
    )
    email = fields.Char(string='Email')
    is_active_bill_user = fields.Boolean(
        string='Active in Bill.com',
        default=True,
        readonly=True,
    )
    is_authorized_approver = fields.Boolean(
        string='Authorized Approver',
        default=False,
        readonly=True,
        help='Detected from Bill.com user permissions/profile.',
    )
    active = fields.Boolean(default=True)
    config_id = fields.Many2one(
        'billcom.config',
        string='Bill.com Configuration',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='config_id.company_id',
        store=True,
        readonly=True,
    )

    _sql_constraints = [
        (
            'billcom_solid_approver_unique_per_config',
            'unique(config_id, billcom_user_id)',
            'Bill.com User ID must be unique per Bill.com configuration.',
        ),
    ]


class BillcomConfig(models.Model):
    _inherit = 'billcom.config'

    billcom_solid_available_approver_ids = fields.One2many(
        'billcom.solid.approver',
        'config_id',
        string='Available Bill.com Users',
        copy=False,
    )
    billcom_solid_default_approver_ids = fields.Many2many(
        'billcom.solid.approver',
        'billcom_config_solid_approver_rel',
        'config_id',
        'approver_id',
        string='Default Bill.com Approvers',
        domain="[('config_id', '=', id), ('active', '=', True), ('is_active_bill_user', '=', True), ('is_authorized_approver', '=', True)]",
        help=(
            'Approvers to assign by default when using Sync Bill + Pay.\n'
            'If empty, payments will be synced without SetApprovers.'
        ),
    )

    def action_refresh_billcom_solid_approvers(self):
        self.ensure_one()

        service = self.env['billcom.service']
        user_rows = service.get_bill_users_for_selection()
        all_existing = self.billcom_solid_available_approver_ids.with_context(active_test=False)
        existing_by_user_id = {record.billcom_user_id: record for record in all_existing}

        seen_user_ids = set()
        for row in user_rows:
            user_id = (row.get('billcom_user_id') or '').strip()
            if not user_id:
                continue
            seen_user_ids.add(user_id)

            vals = {
                'name': row.get('name') or user_id,
                'billcom_user_id': user_id,
                'email': row.get('email') or False,
                'is_active_bill_user': bool(row.get('is_active_bill_user')),
                'is_authorized_approver': bool(row.get('is_authorized_approver')),
                'active': bool(row.get('is_active_bill_user')),
            }
            existing = existing_by_user_id.get(user_id)
            if existing:
                existing.write(vals)
            else:
                vals['config_id'] = self.id
                self.env['billcom.solid.approver'].create(vals)

        missing_users = all_existing.filtered(lambda rec: rec.billcom_user_id not in seen_user_ids)
        if missing_users:
            missing_users.write({'active': False})

        invalid_defaults = self.billcom_solid_default_approver_ids.filtered(
            lambda rec: (not rec.active) or (not rec.is_active_bill_user) or (not rec.is_authorized_approver)
        )
        if invalid_defaults:
            self.billcom_solid_default_approver_ids = [(3, record.id) for record in invalid_defaults]

        if not self.billcom_solid_default_approver_ids:
            irene_candidates = self.billcom_solid_available_approver_ids.filtered(
                lambda rec: rec.active
                and rec.is_active_bill_user
                and rec.is_authorized_approver
                and 'irene' in (rec.name or '').lower()
            ).sorted(lambda rec: (rec.name or '', rec.billcom_user_id or ''))
            if irene_candidates:
                selected = irene_candidates[:1]
                self.billcom_solid_default_approver_ids = [(6, 0, selected.ids)]
                _logger.info(
                    'Auto-selected Bill.com approver for config %s: %s',
                    self.display_name,
                    selected[0].billcom_user_id,
                )

        default_count = len(self.billcom_solid_default_approver_ids)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bill.com Users Refreshed'),
                'message': _(
                    'Users refreshed: %(users)s. Default approvers selected: %(defaults)s.'
                )
                % {
                    'users': len(user_rows),
                    'defaults': default_count,
                },
                'type': 'success',
                'sticky': False,
            },
        }
