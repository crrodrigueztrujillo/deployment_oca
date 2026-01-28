/** @odoo-module **/

import {Component, useState} from "@odoo/owl";

export class ImageCarousel extends Component {
    static template = "stock_barcodes_delivery_proof.ImageCarousel";
    static props = {
        images: {type: Array},
        onDelete: {type: Function, optional: true},
        readonly: {type: Boolean, optional: true},
    };
    static defaultProps = {
        readonly: false,
    };

    setup() {
        this.state = useState({
            currentIndex: 0,
            showFullscreen: false,
        });
    }

    get currentImage() {
        if (this.props.images.length === 0) {
            return null;
        }
        return this.props.images[this.state.currentIndex];
    }

    get hasMultipleImages() {
        return this.props.images.length > 1;
    }

    get hasImages() {
        return this.props.images.length > 0;
    }

    previous() {
        if (this.state.currentIndex > 0) {
            this.state.currentIndex--;
        } else {
            this.state.currentIndex = this.props.images.length - 1;
        }
    }

    next() {
        if (this.state.currentIndex < this.props.images.length - 1) {
            this.state.currentIndex++;
        } else {
            this.state.currentIndex = 0;
        }
    }

    toggleFullscreen() {
        this.state.showFullscreen = !this.state.showFullscreen;
    }

    async deleteImage() {
        if (this.props.onDelete && this.currentImage) {
            await this.props.onDelete(this.currentImage.id);
            // Adjust index if needed
            if (this.state.currentIndex >= this.props.images.length) {
                this.state.currentIndex = Math.max(0, this.props.images.length - 1);
            }
        }
    }

    getImageUrl(image) {
        if (!image) return "";
        return `/web/image/stock.delivery.proof.image/${image.id}/image`;
    }

    formatDate(dateString) {
        if (!dateString) return "";
        const date = new Date(dateString);
        return date.toLocaleString();
    }

    goToIndex(index) {
        this.state.currentIndex = index;
    }
}
