/** @odoo-module **/

import {Component, onWillStart, useState} from "@odoo/owl";
import {CameraCapture} from "@stock_barcodes_delivery_proof/components/camera_capture/camera_capture.esm";
import {Dialog} from "@web/core/dialog/dialog";
import {ImageCarousel} from "@stock_barcodes_delivery_proof/components/image_carousel/image_carousel.esm";
import {useService} from "@web/core/utils/hooks";

export class PhotoGalleryModal extends Component {
    static template = "stock_barcodes_delivery_proof.PhotoGalleryModal";
    static components = {Dialog, CameraCapture, ImageCarousel};
    static props = {
        todoId: {type: Number, optional: true},
        pickingId: {type: Number, optional: true},
        wizardId: Number,
        // Mode can be 'move_line' or 'picking'
        mode: {type: String, optional: true},
        close: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        // Track if photos were added/deleted
        this.state = useState({
            photos: [],
            showCamera: false,
            loading: true,
            photosChanged: false,
            mode: this.props.mode || "move_line",
            stats: {
                total_count: 0,
                lines_count: 0,
                lines_with_photos: 0,
            },
        });

        onWillStart(async () => {
            await this.loadPhotos();
        });
    }

    async loadPhotos() {
        this.state.loading = true;
        try {
            let result = null;

            if (this.state.mode === "picking") {
                // Picking mode: load picking-level photos
                result = await this.orm.call(
                    "wiz.stock.barcodes.read.picking",
                    "get_picking_photo_data",
                    [this.props.wizardId]
                );
            } else {
                // Move line mode: load todo photos
                result = await this.orm.call(
                    "wiz.stock.barcodes.read.picking",
                    "get_todo_photo_data",
                    [this.props.wizardId, this.props.todoId]
                );
            }

            this.state.photos = result.photos || [];
            this.state.mode = result.mode || this.state.mode;
            this.state.stats = {
                total_count: result.total_count || 0,
                lines_count: result.lines_count || 0,
                lines_with_photos: result.lines_with_photos || 0,
            };
        } catch (error) {
            console.error("Error loading photos:", error);
            this.notification.add("Failed to load photos. Please try again.", {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    onAddPhoto() {
        this.state.showCamera = true;
    }

    /**
     * Close the modal and trigger a reload if photos were changed
     */
    closeModal() {
        if (this.state.photosChanged) {
            // Close with a flag to reload the parent view
            this.props.close();
            // Force a page reload to update the badge
            window.location.reload();
        } else {
            // Just close normally
            this.props.close();
        }
    }

    async onPhotoCapture(imageData) {
        try {
            // In picking mode, we don't have a todo_id, so we need to handle it differently
            // The wizard's action_save_delivery_photo_from_todo already handles both modes
            // by checking the delivery_proof_level setting

            let result = null;
            if (this.state.mode === "picking") {
                // For picking mode, we still call the same method but with a dummy todo_id
                // The wizard will ignore it and save to picking level based on delivery_proof_level
                result = await this.orm.call(
                    "wiz.stock.barcodes.read.picking",
                    "action_save_delivery_photo_from_todo",
                    [this.props.wizardId, 0, imageData]
                );
            } else {
                // Move line mode: pass the actual todo_id
                result = await this.orm.call(
                    "wiz.stock.barcodes.read.picking",
                    "action_save_delivery_photo_from_todo",
                    [this.props.wizardId, this.props.todoId, imageData]
                );
            }

            if (result.success) {
                this.notification.add(result.message, {type: "success"});

                // Mark that photos were changed
                this.state.photosChanged = true;

                // Reload photos in the modal
                await this.loadPhotos();

                // Close camera view and return to gallery
                this.state.showCamera = false;
            } else {
                this.notification.add(result.message || "Failed to save photo", {
                    type: "danger",
                });
            }
        } catch (error) {
            console.error("Error saving photo:", error);
            this.notification.add("Failed to save photo. Please try again.", {
                type: "danger",
            });
        }
    }

    async onDeletePhoto(photoId) {
        try {
            const success = await this.orm.call(
                "wiz.stock.barcodes.read.picking",
                "action_delete_delivery_photo",
                [this.props.wizardId, photoId]
            );

            if (success) {
                this.notification.add("Photo deleted successfully", {type: "success"});

                // Mark that photos were changed
                this.state.photosChanged = true;

                // Reload photos in the modal
                await this.loadPhotos();
            } else {
                this.notification.add("Failed to delete photo", {type: "danger"});
            }
        } catch (error) {
            console.error("Error deleting photo:", error);
            this.notification.add("Failed to delete photo. Please try again.", {
                type: "danger",
            });
        }
    }

    onCloseCamera() {
        this.state.showCamera = false;
    }
}
