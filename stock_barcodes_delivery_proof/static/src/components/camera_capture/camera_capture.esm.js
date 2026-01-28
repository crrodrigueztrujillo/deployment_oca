/** @odoo-module **/

import {Component, onMounted, onWillUnmount, useRef, useState} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";

export class CameraCapture extends Component {
    static template = "stock_barcodes_delivery_proof.CameraCapture";
    static props = {
        onCapture: {type: Function},
        onClose: {type: Function},
        moveLines: {type: Array, optional: true},
        proofLevel: {type: String, optional: true},
    };
    static defaultProps = {
        moveLines: [],
        proofLevel: "picking",
    };

    // Image compression settings for handheld devices
    static MAX_WIDTH = 1280;
    static MAX_HEIGHT = 960;
    static JPEG_QUALITY = 0.75;

    setup() {
        // Back camera by default
        this.state = useState({
            isStreaming: false,
            error: null,
            facingMode: "environment",
            selectedMoveLineId: null,
            showPreview: false,
            capturedImage: null,
        });
        this.videoRef = useRef("video");
        this.canvasRef = useRef("canvas");
        this.stream = null;
        this.notification = useService("notification");

        onMounted(() => this.startCamera());
        onWillUnmount(() => this.stopCamera());
    }

    async startCamera() {
        try {
            const constraints = {
                video: {
                    facingMode: this.state.facingMode,
                    width: {ideal: 1280},
                    height: {ideal: 720},
                },
            };
            this.stream = await navigator.mediaDevices.getUserMedia(constraints);
            if (this.videoRef.el) {
                this.videoRef.el.srcObject = this.stream;
            }
            this.state.isStreaming = true;
            this.state.error = null;
        } catch (error) {
            console.error("Camera access error:", error);
            this.state.error = this._getErrorMessage(error);
            this.notification.add(this.state.error, {type: "danger"});
        }
    }

    _getErrorMessage(error) {
        if (error.name === "NotAllowedError") {
            return "Camera access denied. Please allow camera access in your browser settings.";
        } else if (error.name === "NotFoundError") {
            return "No camera found on this device.";
        } else if (error.name === "NotReadableError") {
            return "Camera is in use by another application.";
        }
        return "Could not access the camera. Please try again.";
    }

    stopCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach((track) => track.stop());
            this.stream = null;
        }
        this.state.isStreaming = false;
    }

    async switchCamera() {
        this.stopCamera();
        this.state.facingMode =
            this.state.facingMode === "user" ? "environment" : "user";
        await this.startCamera();
    }

    _calculateCompressedDimensions(originalWidth, originalHeight) {
        let width = originalWidth;
        let height = originalHeight;

        // Scale down if exceeds max width
        if (width > CameraCapture.MAX_WIDTH) {
            const ratio = CameraCapture.MAX_WIDTH / width;
            width = CameraCapture.MAX_WIDTH;
            height = Math.round(height * ratio);
        }

        // Scale down if still exceeds max height
        if (height > CameraCapture.MAX_HEIGHT) {
            const ratio = CameraCapture.MAX_HEIGHT / height;
            height = CameraCapture.MAX_HEIGHT;
            width = Math.round(width * ratio);
        }

        return {width, height};
    }

    capturePhoto() {
        const video = this.videoRef.el;
        const canvas = this.canvasRef.el;

        if (!video || !canvas) {
            return;
        }

        const context = canvas.getContext("2d");

        // Calculate compressed dimensions maintaining aspect ratio
        const {width, height} = this._calculateCompressedDimensions(
            video.videoWidth,
            video.videoHeight
        );

        canvas.width = width;
        canvas.height = height;
        context.drawImage(video, 0, 0, width, height);

        // Compress to JPEG with reduced quality for handheld devices
        const imageData = canvas
            .toDataURL("image/jpeg", CameraCapture.JPEG_QUALITY)
            .split(",")[1];

        // Show preview
        this.state.capturedImage = imageData;
        this.state.showPreview = true;

        // Pause video
        this.stopCamera();
    }

    retakePhoto() {
        this.state.showPreview = false;
        this.state.capturedImage = null;
        this.startCamera();
    }

    confirmPhoto() {
        if (this.state.capturedImage) {
            this.props.onCapture(this.state.capturedImage);
        }
        this.close();
    }

    close() {
        this.stopCamera();
        this.props.onClose();
    }

    getPreviewUrl() {
        if (this.state.capturedImage) {
            return `data:image/jpeg;base64,${this.state.capturedImage}`;
        }
        return "";
    }
}
