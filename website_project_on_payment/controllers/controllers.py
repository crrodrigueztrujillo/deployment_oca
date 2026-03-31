# -*- coding: utf-8 -*-
import logging

from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)


class WebsiteSaleSolidTileProject(WebsiteSale):

    def _solidtile_get_or_create_project(self, order, project_name):
        """Busca o crea project.project para el cliente del sale.order."""
        project_name = (project_name or "").strip()
        if not project_name:
            return False

        partner = order.partner_id.commercial_partner_id
        Project = request.env["project.project"].sudo()

        project = Project.search(
            [("name", "=", project_name), ("partner_id", "=", partner.id)],
            limit=1,
        )
        if not project:
            vals = {
                "name": project_name,
                "partner_id": partner.id,
            }
            # Si tu BD usa multi-company fuerte, esto ayuda:
            if order.company_id:
                vals["company_id"] = order.company_id.id

            project = Project.create(vals)

        return project

    @http.route("/shop/payment/validate", type="http", auth="public", website=True, sitemap=False)
    def shop_payment_validate(self, sale_order_id=None, **post):
        """
        Extiende el flujo nativo:
        - Lee project_name del POST
        - Setea sale.order.website_project_name
        - Crea/busca project.project por cliente
        - Asigna sale.order.project_id
        - Luego continúa el flujo nativo de confirmación
        """
        # --- Inicio: copia fiel del patrón nativo para recuperar order ---
        if sale_order_id is None:
            order = request.website.sale_get_order()
            if not order and "sale_last_order_id" in request.session:
                last_order_id = request.session["sale_last_order_id"]
                order = request.env["sale.order"].sudo().browse(last_order_id).exists()
        else:
            order = request.env["sale.order"].sudo().browse(sale_order_id).exists()
        # --- Fin recuperación order ---

        # 👉 Hook SolidTile: procesar project_name
        if order:
            project_name = (post.get("project_name") or "").strip()
            if project_name:
                # guarda el texto en la SO
                order.sudo().write({"website_project_name": project_name})

                # busca/crea project y setea project_id
                project = self._solidtile_get_or_create_project(order, project_name)
                type_id = request.env['sale.order.type'].sudo().search([('name', '=', 'Samples')], limit=1)
                if project:
                    order.sudo().write({
                        "project_id": project.id,
                        "type_id": type_id.id if type_id else None
                        })

        # Continúa con el flujo nativo llamando al super
        # (IMPORTANTE: ya seteamos project_id antes de confirmar en caso de total 0)
        return super().shop_payment_validate(sale_order_id=sale_order_id, **post)
