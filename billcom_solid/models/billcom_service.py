# -*- coding: utf-8 -*-
import inspect
import json
import logging

import requests

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BillcomService(models.AbstractModel):
    _inherit = 'billcom.service'

    @api.model
    def _get_v2_api_url(self):
        """Build Bill.com v2 base URL from configured v3 URL."""
        config = self._get_config()
        api_url = (config.api_url or '').rstrip('/')
        if 'gateway.stage.bill.com' in api_url:
            return 'https://api-stage.bill.com/api/v2'
        if 'gateway.prod.bill.com' in api_url:
            return 'https://api.bill.com/api/v2'
        if 'gateway.bill.com' in api_url:
            return 'https://api.bill.com/api/v2'
        if 'api.bill.com' in api_url:
            return 'https://api.bill.com/api/v2'
        raise UserError(
            _('Unable to derive Bill.com v2 URL from configured API URL: %s') % api_url
        )

    @api.model
    def _get_v2_token(self):
        """Authenticate against Bill.com v2 and return sessionId."""
        config = self._get_config()
        username = getattr(config, 'api_key', False) or getattr(config, 'username', False)
        password = getattr(config, 'api_secret', False) or getattr(config, 'password', False)
        login_url = '%s/Login.json' % self._get_v2_api_url()
        form_payload = {
            'userName': username,
            'password': password,
            'devKey': config.dev_key,
            'orgId': config.organization_id,
        }
        headers = {'accept': 'application/json', 'content-type': 'application/x-www-form-urlencoded'}

        try:
            response = requests.post(login_url, data=form_payload, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json() if response.content else {}
        except requests.exceptions.RequestException as exc:
            raise UserError(_('Error authenticating to Bill.com v2: %s') % str(exc))
        except ValueError as exc:
            raise UserError(_('Unable to parse Bill.com v2 login response: %s') % str(exc))

        if result.get('response_status') not in (0, '0'):
            response_data = result.get('response_data') or {}
            error_message = response_data.get('error_message') or result.get('response_message')
            raise UserError(_('Bill.com v2 login error: %s') % (error_message or _('Unknown error')))

        session_id = (result.get('response_data') or {}).get('sessionId')
        if not session_id:
            raise UserError(_('Bill.com v2 login did not return sessionId.'))

        return session_id

    @api.model
    def _is_truthy_flag(self, value):
        return str(value).strip().lower() in {'1', 'true', 'yes', 'y'}

    @api.model
    def _is_active_bill_user(self, user_data):
        is_active = user_data.get('isActive')
        if is_active is not None:
            return self._is_truthy_flag(is_active)
        status = str(user_data.get('status') or '').strip().upper()
        if status:
            return status in {'ACTIVE', 'ENABLED'}
        return True

    @api.model
    def _get_bill_user_approver_flag(self, user_data):
        approver_keys = (
            'isApprover',
            'canApprove',
            'approveBills',
            'isBillApprover',
            'isPayerApprover',
            'isApproverForBills',
        )
        matched = False
        for key in approver_keys:
            if key in user_data:
                matched = True
                if self._is_truthy_flag(user_data.get(key)):
                    return True
        if matched:
            return False
        return None

    @api.model
    def _v2_post(self, endpoint, payload=None):
        config = self._get_config()
        token = self._get_v2_token()
        url = '%s/%s' % (self._get_v2_api_url(), endpoint.lstrip('/'))
        form_payload = {
            'devKey': config.dev_key,
            'sessionId': token,
            'data': json.dumps(payload or {}),
        }
        headers = {
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
        }
        try:
            response = requests.post(url, data=form_payload, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json() if response.content else {}
        except requests.exceptions.RequestException as exc:
            raise UserError(_('Error calling Bill.com v2 endpoint %s: %s') % (endpoint, str(exc)))
        except ValueError as exc:
            raise UserError(
                _('Unable to parse Bill.com v2 response for %s: %s') % (endpoint, str(exc))
            )

        if result.get('response_status') not in (0, '0'):
            response_data = result.get('response_data') or {}
            error_message = response_data.get('error_message') or result.get('response_message')
            raise UserError(
                _('Bill.com v2 endpoint %s returned an error: %s')
                % (endpoint, (error_message or _('Unknown error')))
            )
        return result

    @api.model
    def get_active_bill_approver_ids(self):
        """Return active Bill.com approver user IDs, defaulting to active users if no approver flag exists."""
        all_users = []
        start = 0
        page_size = 200

        while True:
            result = self._v2_post('List/User.json', {'start': start, 'max': page_size})
            response_data = result.get('response_data') or []
            if isinstance(response_data, dict):
                response_data = (
                    response_data.get('results')
                    or response_data.get('users')
                    or response_data.get('data')
                    or []
                )
            if not isinstance(response_data, list):
                response_data = []

            if not response_data:
                break

            all_users.extend(response_data)
            if len(response_data) < page_size:
                break
            start += page_size

        active_users = [user for user in all_users if self._is_active_bill_user(user)]
        explicit_approvers = []
        for user in active_users:
            if self._get_bill_user_approver_flag(user) is True:
                explicit_approvers.append(user)

        selected_users = explicit_approvers or active_users
        approver_ids = []
        seen = set()
        for user in selected_users:
            user_id = str(user.get('id') or '').strip()
            if user_id and user_id.startswith('006') and user_id not in seen:
                seen.add(user_id)
                approver_ids.append(user_id)

        _logger.info(
            'Bill.com approver autodiscovery: total_users=%s active_users=%s explicit_approvers=%s selected=%s',
            len(all_users),
            len(active_users),
            len(explicit_approvers),
            len(approver_ids),
        )
        return approver_ids

    @api.model
    def set_bill_approvers(self, bill_id, approver_ids):
        """Assign specific approvers to a bill using Bill.com v2 SetApprovers endpoint."""
        if not bill_id:
            raise UserError(_('Bill ID is required to assign approvers.'))

        clean_approvers = [str(value).strip() for value in (approver_ids or []) if str(value).strip()]
        if not clean_approvers:
            return {}

        payload = {'objectId': bill_id, 'entity': 'Bill', 'approvers': clean_approvers}

        try:
            _logger.info('Setting Bill.com approvers for bill %s', bill_id)
            result = self._v2_post('SetApprovers.json', payload)
        except UserError:
            raise

        return result

    @api.model
    def upload_bill_document(self, bill_id, file_binary, file_name):
        """Upload a supporting document to a Bill.com bill."""
        if not bill_id:
            raise UserError(_('Bill ID is required to upload documents.'))
        if not file_binary:
            raise UserError(_('Document content is empty.'))
        if not file_name:
            file_name = 'payment_supporting_document'

        endpoint = 'documents/bills/%s' % bill_id
        params = {'name': file_name}

        # OCA billcom supports file uploads via _make_request(..., is_file_upload=True).
        # Fallback to raw HTTP for legacy billcom implementations.
        try:
            signature = inspect.signature(self._make_request)
            if 'is_file_upload' in signature.parameters:
                return self._make_request(
                    endpoint,
                    method='POST',
                    data=file_binary,
                    params=params,
                    is_file_upload=True,
                )
        except (TypeError, ValueError):
            pass

        config = self._get_config()
        token = self._get_token()
        url = '%s/%s' % ((config.api_url or '').rstrip('/'), endpoint.lstrip('/'))
        headers = {
            'accept': 'application/json',
            'content-type': 'application/octet-stream',
            'sessionId': token,
            'devKey': config.dev_key,
        }

        try:
            response = requests.post(url, data=file_binary, headers=headers, params=params, timeout=60)
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as exc:
            raise UserError(_('Error uploading document to Bill.com: %s') % str(exc))
        except ValueError as exc:
            raise UserError(_('Unable to parse Bill.com document upload response: %s') % str(exc))
