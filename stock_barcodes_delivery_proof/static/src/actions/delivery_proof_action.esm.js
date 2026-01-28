/** @odoo-module **/

import {PhotoGalleryModal} from "@stock_barcodes_delivery_proof/components/photo_gallery_modal/photo_gallery_modal.esm";
import {registry} from "@web/core/registry";

/**
 * Client action to open photo gallery modal
 * @param {Object} env - Odoo environment
 * @param {Object} action - Action parameters
 * @param {Object} action.params - Action parameters
 * @param {Number} action.params.todo_id - Todo ID (for move_line mode)
 * @param {Number} action.params.picking_id - Picking ID (for picking mode)
 * @param {Number} action.params.wizard_id - Wizard ID
 * @param {String} action.params.mode - Mode ('move_line' or 'picking')
 */
function displayDeliveryProofModal(env, action) {
    const {todo_id, picking_id, wizard_id, mode} = action.params;

    env.services.dialog.add(PhotoGalleryModal, {
        todoId: todo_id,
        pickingId: picking_id,
        wizardId: wizard_id,
        mode: mode,
    });
}

registry
    .category("actions")
    .add("display_delivery_proof_modal", displayDeliveryProofModal);
