/** @odoo-module **/

import {Component, onWillStart, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {useService} from "@web/core/utils/hooks";

export class DeliveryProofGallery extends Component {
    static template = "stock_barcodes_delivery_proof.DeliveryProofGallery";
    static components = {Dialog};
    static props = {
        imageId: Number,
        moveLineId: {type: Number, optional: true},
        pickingId: {type: Number, optional: true},
        close: Function,
    };

    setup() {
        this.orm = useService("orm");

        this.state = useState({
            images: [],
            currentIndex: 0,
            loading: true,
        });

        onWillStart(async () => {
            await this.loadImages();
        });
    }

    async loadImages() {
        let domain = [];

        // Determine domain based on props - both modes use same model now
        if (this.props.pickingId) {
            // Picking-level photos
            domain = [["picking_id", "=", this.props.pickingId]];
        } else if (this.props.moveLineId) {
            // Move line-level photos
            domain = [["move_line_id", "=", this.props.moveLineId]];
        } else {
            // Fallback: no filter
            this.state.loading = false;
            return;
        }

        // All photos use the unified model with same fields
        const model = "stock.delivery.proof.image";
        const fields = [
            "id",
            "image",
            "capture_date",
            "captured_by_id",
            "move_line_id",
            "picking_id",
        ];

        const images = await this.orm.searchRead(model, domain, fields, {
            order: "capture_date desc",
        });

        this.state.images = images;

        // Find the index of the clicked image
        const clickedIndex = images.findIndex((img) => img.id === this.props.imageId);
        this.state.currentIndex = clickedIndex >= 0 ? clickedIndex : 0;
        this.state.loading = false;
    }

    get currentImage() {
        return this.state.images[this.state.currentIndex];
    }

    get hasMultipleImages() {
        return this.state.images.length > 1;
    }

    getImageUrl(image) {
        if (!image || !image.image) {
            return "";
        }
        return `data:image/jpeg;base64,${image.image}`;
    }

    next() {
        if (this.state.currentIndex < this.state.images.length - 1) {
            this.state.currentIndex++;
        } else {
            this.state.currentIndex = 0;
        }
    }

    previous() {
        if (this.state.currentIndex > 0) {
            this.state.currentIndex--;
        } else {
            this.state.currentIndex = this.state.images.length - 1;
        }
    }

    handleKeydown(ev) {
        if (ev.key === "ArrowRight") {
            this.next();
        } else if (ev.key === "ArrowLeft") {
            this.previous();
        } else if (ev.key === "Escape") {
            this.props.close();
        }
    }

    async downloadImage() {
        const image = this.currentImage;
        if (!image) {
            return;
        }
        // Trigger browser download using Odoo's web/content endpoint
        const url = `/web/content/stock.delivery.proof.image/${image.id}/image?download=true`;
        window.location.href = url;
    }
}
