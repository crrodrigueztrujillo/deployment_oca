# -*- coding: utf-8 -*-
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    billcom_solid_bill_id = fields.Char(
        string='Bill.com Bill ID',
        copy=False,
        readonly=True,
    )
    billcom_solid_sync_date = fields.Datetime(
        string='Solid Sync Date',
        copy=False,
        readonly=True,
    )
    billcom_solid_approval_status = fields.Selection(
        [
            ('unassigned', 'Unassigned'),
            ('assigned', 'Assigned'),
            ('approved', 'Approved'),
            ('approving', 'Approving'),
            ('denied', 'Denied'),
            ('undefined', 'Undefined'),
        ],
        string='Bill.com Approval Status',
        copy=False,
        readonly=True,
        default='undefined',
    )
    billcom_solid_approver_ids = fields.Char(
        string='Bill.com Approver User IDs',
        help='Auto-filled from active Bill.com users selected as approvers.',
    )

    def _is_solid_vendor_payment(self):
        self.ensure_one()
        return self.payment_type == 'outbound' and self.partner_type == 'supplier'

    def _map_solid_approval_status(self, status):
        mapping = {
            'UNASSIGNED': 'unassigned',
            'ASSIGNED': 'assigned',
            'APPROVED': 'approved',
            'APPROVING': 'approving',
            'DENIED': 'denied',
        }
        return mapping.get(status, 'undefined')

    def _parse_billcom_solid_approvers(self):
        self.ensure_one()
        values = [value.strip() for value in (self.billcom_solid_approver_ids or '').split(',') if value.strip()]

        unique_values = []
        seen = set()
        for value in values:
            if value not in seen:
                seen.add(value)
                unique_values.append(value)

        invalid_values = [value for value in unique_values if not value.startswith('006')]
        if invalid_values:
            raise UserError(
                _('Invalid approver IDs: %s. Bill.com user IDs must start with 006.')
                % ', '.join(invalid_values)
            )

        return unique_values

    def _prepare_solid_bill_data(self):
        self.ensure_one()

        vendor_billcom_id = self.partner_id.billcom_id or self.partner_id.billcom
        if not vendor_billcom_id:
            raise UserError(
                _('Vendor %s is not linked to Bill.com. Sync the vendor first.') % self.partner_id.display_name
            )

        invoice_date = self.date or fields.Date.context_today(self)
        description = self.ref or self.name or _('Vendor payment')

        return {
            'vendorId': vendor_billcom_id,
            'invoice': {
                'invoiceNumber': self.name or self.ref or str(self.id),
                'invoiceDate': invoice_date.isoformat(),
            },
            'dueDate': invoice_date.isoformat(),
            'description': description,
            'amount': self.amount,
            'billLineItems': [
                {
                    'description': description,
                    'amount': self.amount,
                }
            ],
            'billApprovals': True,
        }

    def button_sync_to_billcom(self):
        """Disable default payment sync for vendor payments in Solid flow.

        Vendor payments must use the Sync Bill + Pay button so Bill.com creates a bill
        and follows manual approval in Bill.com.
        """
        solid_vendor_payments = self.filtered(lambda payment: payment._is_solid_vendor_payment())
        remaining_payments = self - solid_vendor_payments

        result = False
        if remaining_payments:
            result = super(AccountPayment, remaining_payments).button_sync_to_billcom()

        if solid_vendor_payments and self.env.context.get('billcom_solid_allow_payment_sync'):
            solid_result = super(AccountPayment, solid_vendor_payments).button_sync_to_billcom()
            return solid_result or result

        if solid_vendor_payments:
            _logger.info(
                'Default Bill.com payment sync skipped for %s vendor payment(s); use Sync Bill + Pay flow.',
                len(solid_vendor_payments),
            )

        return result

    def action_sync_bill_pay_to_billcom(self):
        self.ensure_one()

        if not self._is_solid_vendor_payment():
            raise UserError(_('Sync Bill + Pay is only available for vendor payments.'))
        if self.state != 'posted':
            raise UserError(_('Payment must be posted before syncing to Bill.com.'))
        if not self.partner_id.is_sync_to_billcom:
            raise UserError(_('Vendor is not configured to sync with Bill.com.'))
        if self.billcom_solid_bill_id:
            raise UserError(
                _('This payment is already synced as Bill.com bill %s.') % self.billcom_solid_bill_id
            )

        service = self.env['billcom.service']
        approver_ids = service.get_active_bill_approver_ids()
        if not approver_ids:
            raise UserError(
                _(
                    'No active Bill.com approvers were found. '
                    'Please configure active approver users in Bill.com before syncing.'
                )
            )

        bill_data = self._prepare_solid_bill_data()
        result = service._make_request('bills', method='POST', data=bill_data)

        if not result or not result.get('id'):
            raise UserError(_('Bill.com did not return a bill ID for this payment sync.'))

        bill_id = result['id']
        service.set_bill_approvers(bill_id, approver_ids)

        self.with_context(skip_billcom_sync=True).write(
            {
                'billcom_solid_bill_id': bill_id,
                'billcom_solid_sync_date': fields.Datetime.now(),
                'billcom_solid_approval_status': self._map_solid_approval_status(
                    result.get('approvalStatus')
                ),
                'billcom_solid_approver_ids': ','.join(approver_ids),
            }
        )

        message = _(
            'Bill created in Bill.com (%s) and %s approver(s) were assigned automatically.'
        ) % (bill_id, len(approver_ids))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': message,
                'type': 'success',
                'sticky': False,
            },
        }
