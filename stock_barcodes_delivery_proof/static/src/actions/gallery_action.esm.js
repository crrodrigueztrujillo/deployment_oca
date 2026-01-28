/** @odoo-module **/

import {DeliveryProofGallery} from "@stock_barcodes_delivery_proof/components/delivery_proof_gallery/delivery_proof_gallery.esm";
import {registry} from "@web/core/registry";

/**
 * Client action to open delivery proof gallery
 * @param {Object} env - Odoo environment
 * @param {Object} action - Action parameters
 * @param {Object} action.params - Action parameters
 * @param {Number} action.params.image_id - Image ID to open
 * @param {Number} action.params.move_line_id - Move line ID to filter images
 */
function openDeliveryProofGallery(env, action) {
    const {image_id, move_line_id, picking_id} = action.params;

    env.services.dialog.add(DeliveryProofGallery, {
        imageId: image_id,
        moveLineId: move_line_id,
        pickingId: picking_id,
    });
}

registry
    .category("actions")
    .add("open_delivery_proof_gallery", openDeliveryProofGallery);
