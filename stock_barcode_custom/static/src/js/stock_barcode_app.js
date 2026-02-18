/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { SignatureDialog } from "@web/core/signature/signature_dialog";

class StockBarcodeCustomApp extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.state = useState({
            driverMode: false,
            dashboard: { warehouses: [] },
            operationType: "receipt",
            warehouseId: false,
            query: "",
            operations: [],
            selected: null,
            selectedModel: null,
            lines: [],
            filteredLines: [],
            packagings: [],
            qtyMode: "unit",
            packagingId: false,
            scanBarcode: "",
            lineQuery: "",
            message: "",
            lastProductMessage: "",
            quantity: 1,
            driverPhotos: [],
            driverProof: {
                signedBy: "",
                note: "",
                signatureBase64: "",
                hasSignature: false,
                proofState: "pending",
            },
        });

        onWillStart(async () => {
            const ctx = this.props.action.context || {};
            this.state.driverMode = Boolean(ctx.driver_mode);
            await this.loadDashboard();
            if (ctx.default_warehouse_id) {
                this.state.warehouseId = ctx.default_warehouse_id;
            }
            if (this.state.driverMode) {
                await this.searchDriverDeliveries();
                if (ctx.default_operation_id) {
                    await this.loadDriverDelivery(ctx.default_operation_id);
                }
                return;
            }
            await this.searchOperations();
            if (ctx.default_operation_model && ctx.default_operation_id) {
                await this.loadOperation(ctx.default_operation_model, ctx.default_operation_id);
            }
        });
    }

    async loadDashboard() {
        this.state.dashboard = await this.orm.call("stock.barcode.app", "get_dashboard_data", [this.state.warehouseId || false]);
    }

    async searchOperations() {
        this.state.operations = await this.orm.call("stock.barcode.app", "search_operations", [
            this.state.operationType,
            this.state.query,
            30,
            this.state.warehouseId || false,
        ]);
    }

    async searchDriverDeliveries() {
        this.state.operations = await this.orm.call("stock.barcode.app", "search_driver_deliveries", [
            this.state.query,
            30,
            this.state.warehouseId || false,
        ]);
    }

    async onWarehouseChange() {
        this.state.selected = null;
        this.state.lines = [];
        this.state.filteredLines = [];
        await this.loadDashboard();
        if (this.state.driverMode) {
            await this.searchDriverDeliveries();
        } else {
            await this.searchOperations();
        }
    }

    async onOperationSearchInput() {
        if (this.state.driverMode) {
            await this.searchDriverDeliveries();
            return;
        }
        await this.searchOperations();
    }

    async onOperationSearchScan(ev) {
        if (ev.key !== "Enter") {
            return;
        }
        await this.onOperationSearchInput();
    }

    async changeOperationType(type) {
        this.state.operationType = type;
        this.state.selected = null;
        this.state.selectedModel = null;
        this.state.lines = [];
        this.state.filteredLines = [];
        this.state.packagings = [];
        await this.searchOperations();
    }

    async loadOperation(model, id) {
        const data = await this.orm.call("stock.barcode.app", "load_operation", [model, id]);
        this.state.selected = data.header;
        this.state.selectedModel = model;
        this.state.lines = data.lines;
        this.state.filteredLines = data.lines;
        this.state.packagings = data.packagings || [];
        if (!this.state.packagings.find((pack) => pack.id === this.state.packagingId)) {
            this.state.packagingId = this.state.packagings.length ? this.state.packagings[0].id : false;
        }
        this.state.lineQuery = "";
        this.state.lastProductMessage = "";
    }

    async loadDriverDelivery(id) {
        const data = await this.orm.call("stock.barcode.app", "load_driver_delivery", [id]);
        this.state.selected = data.header;
        this.state.selectedModel = "stock.picking";
        this.state.lines = data.lines || [];
        this.state.filteredLines = this.state.lines;
        this.state.driverPhotos = data.photos || [];
        this.state.driverProof.signedBy = data.proof.signed_by || "";
        this.state.driverProof.note = data.proof.note || "";
        this.state.driverProof.hasSignature = Boolean(data.proof.has_signature);
        this.state.driverProof.proofState = data.proof.proof_state || "pending";
        this.state.driverProof.signatureBase64 = "";
    }

    filterLines() {
        const q = (this.state.lineQuery || "").trim().toLowerCase();
        if (!q) {
            this.state.filteredLines = this.state.lines;
            return;
        }
        this.state.filteredLines = this.state.lines.filter((line) => {
            return (
                (line.product || "").toLowerCase().includes(q) ||
                (line.barcode || "").toLowerCase().includes(q) ||
                (line.lot || "").toLowerCase().includes(q) ||
                (line.picking || "").toLowerCase().includes(q)
            );
        });
    }

    async onLineFilterScan(ev) {
        if (ev.key !== "Enter") {
            return;
        }
        const code = (this.state.lineQuery || "").trim();
        if (!code || !this.state.selected) {
            this.filterLines();
            return;
        }
        const productInfo = await this.orm.call("stock.barcode.app", "resolve_barcode_product", [
            code,
            this.state.selectedModel,
            this.state.selected.id,
        ]);
        if (productInfo.found) {
            this.state.lastProductMessage = `${productInfo.name}${productInfo.in_operation ? "" : " (no esperado en operación)"}`;
            this.state.lineQuery = productInfo.name;
        }
        this.filterLines();
    }

    async onScanBarcode() {
        const barcode = (this.state.scanBarcode || "").trim();
        if (!barcode || !this.state.selected) {
            return;
        }
        try {
            const result = await this.orm.call("stock.barcode.app", "process_scan", [
                this.state.selectedModel,
                this.state.selected.id,
                barcode,
                this.state.quantity,
                this.state.qtyMode,
                this.state.packagingId || false,
            ]);
            this.state.message = result.message;
            if (result.product_name) {
                this.state.lastProductMessage = result.product_name;
            }
            await this.loadOperation(this.state.selectedModel, this.state.selected.id);
            this.notification.add(result.message, { type: "success" });
        } catch (error) {
            this.notification.add(error.message, { type: "danger" });
        } finally {
            this.state.scanBarcode = "";
        }
    }

    async validateOperation() {
        if (!this.state.selected) {
            return;
        }
        await this.orm.call("stock.barcode.app", "validate_operation", [
            this.state.selectedModel,
            this.state.selected.id,
        ]);
        this.notification.add(this.env._t("Operation validated"), { type: "success" });
        await this.searchOperations();
        if (this.state.selected) {
            await this.loadOperation(this.state.selectedModel, this.state.selected.id);
        }
    }

    openSignatureModal() {
        const isLikelyBase64 = (value) => {
            if (typeof value !== "string") {
                return false;
            }
            const cleaned = value.replace(/\s+/g, "");
            return cleaned.length > 100 && /^[A-Za-z0-9+/]+={0,2}$/.test(cleaned);
        };

        const toBase64 = (value) => {
            if (!value) {
                return false;
            }
            if (typeof value === "string") {
                const trimmed = value.trim();
                if (!trimmed) {
                    return false;
                }
                if (trimmed.startsWith("data:image") && trimmed.includes(",")) {
                    return trimmed.split(",")[1].replace(/\s+/g, "");
                }
                if (trimmed.startsWith("<svg")) {
                    return btoa(unescape(encodeURIComponent(trimmed)));
                }
                if (isLikelyBase64(trimmed)) {
                    return trimmed.replace(/\s+/g, "");
                }
                return false;
            }
            if (Array.isArray(value)) {
                if (value.length >= 2 && typeof value[0] === "string" && value[0].includes("image")) {
                    return toBase64(value[1]);
                }
                for (const item of value) {
                    const nested = toBase64(item);
                    if (nested) {
                        return nested;
                    }
                }
                return false;
            }
            if (typeof value === "object") {
                if (value.signatureImage) {
                    const fromTuple = toBase64(value.signatureImage);
                    if (fromTuple) {
                        return fromTuple;
                    }
                }
                return toBase64(value.signature) || toBase64(value.image) || toBase64(value.value) || toBase64(value.data) || false;
            }
            return false;
        };

        this.dialog.add(SignatureDialog, {
            defaultName: this.state.driverProof.signedBy || "",
            uploadSignature: async (...args) => {
                let signature = false;
                for (const arg of args) {
                    signature = toBase64(arg);
                    if (signature) {
                        break;
                    }
                }
                if (!signature) {
                    this.notification.add(this.env._t("Signature could not be captured."), { type: "warning" });
                    return false;
                }
                this.state.driverProof.signatureBase64 = signature;
                this.state.driverProof.hasSignature = true;
                return true;
            },
        });
    }

    async saveDriverProof(complete = false) {
        if (!this.state.selected) {
            return;
        }
        if (!this.state.driverProof.signedBy) {
            this.notification.add(this.env._t("Signed by is required."), { type: "warning" });
            return;
        }
        await this.orm.call("stock.barcode.app", "save_driver_delivery_proof", [
            this.state.selected.id,
            this.state.driverProof.signedBy,
            this.state.driverProof.note,
            this.state.driverProof.signatureBase64 || false,
            complete,
        ]);
        this.notification.add(complete ? this.env._t("Delivery completed") : this.env._t("Proof saved"), { type: "success" });
        await this.searchDriverDeliveries();
        await this.loadDriverDelivery(this.state.selected.id);
    }


    async onSetLineQty(line) {
        if (!this.state.selected || !line.move_id) {
            return;
        }
        const current = Number(line.qty_done || 0);
        const value = window.prompt(this.env._t("Set done quantity for ") + line.product, String(current));
        if (value === null) {
            return;
        }
        const qty = Number(value);
        if (Number.isNaN(qty) || qty < 0) {
            this.notification.add(this.env._t("Invalid quantity."), { type: "warning" });
            return;
        }
        try {
            const result = await this.orm.call("stock.barcode.app", "set_move_done_qty", [
                this.state.selectedModel,
                this.state.selected.id,
                line.move_id,
                qty,
            ]);
            this.notification.add(result.message || this.env._t("Quantity updated"), { type: "success" });
            await this.loadOperation(this.state.selectedModel, this.state.selected.id);
        } catch (error) {
            this.notification.add(error.message, { type: "danger" });
        }
    }

    async onSetLotInstruction(line, lotDetail) {
        if (!this.state.selected || !lotDetail || !lotDetail.move_line_id) {
            return;
        }
        const lotValue = window.prompt(this.env._t("Instruction lot"), lotDetail.lot || "");
        if (lotValue === null) {
            return;
        }
        const qtyValue = window.prompt(this.env._t("Instruction quantity"), String(lotDetail.qty_expected || 0));
        if (qtyValue === null) {
            return;
        }
        const qty = Number(qtyValue);
        if (Number.isNaN(qty) || qty < 0) {
            this.notification.add(this.env._t("Invalid quantity."), { type: "warning" });
            return;
        }
        try {
            const result = await this.orm.call("stock.barcode.app", "set_move_line_lot_instruction", [
                this.state.selectedModel,
                this.state.selected.id,
                lotDetail.move_line_id,
                lotValue,
                qty,
            ]);
            this.notification.add(result.message || this.env._t("Lot instruction updated"), { type: "success" });
            await this.loadOperation(this.state.selectedModel, this.state.selected.id);
        } catch (error) {
            this.notification.add(error.message, { type: "danger" });
        }
    }

    async onSetLotQty(line, lotDetail) {
        if (!this.state.selected || !lotDetail || !lotDetail.move_line_id) {
            return;
        }
        const lotValue = window.prompt(this.env._t("Lot"), lotDetail.lot || "");
        if (lotValue === null) {
            return;
        }
        const qtyValue = window.prompt(this.env._t("Done quantity"), String(lotDetail.qty_done || 0));
        if (qtyValue === null) {
            return;
        }
        const qty = Number(qtyValue);
        if (Number.isNaN(qty) || qty < 0) {
            this.notification.add(this.env._t("Invalid quantity."), { type: "warning" });
            return;
        }
        try {
            const result = await this.orm.call("stock.barcode.app", "set_move_line_lot_qty", [
                this.state.selectedModel,
                this.state.selected.id,
                lotDetail.move_line_id,
                lotValue,
                qty,
            ]);
            this.notification.add(result.message || this.env._t("Lot/quantity updated"), { type: "success" });
            await this.loadOperation(this.state.selectedModel, this.state.selected.id);
        } catch (error) {
            this.notification.add(error.message, { type: "danger" });
        }
    }

    async onUploadPhoto(line, ev) {
        const file = ev.target.files[0];
        if (!file) {
            return;
        }
        if (!line.move_line_id) {
            this.notification.add(this.env._t("Scan product first to create a move line for photo evidence."), { type: "warning" });
            return;
        }
        const imageBase64 = await this._toBase64(file);
        const stripped = imageBase64.split(",")[1];
        await this.orm.call("stock.barcode.app", "create_move_line_photo", [line.move_line_id, stripped, "Captured from barcode app"]);
        this.notification.add(this.env._t("Photo uploaded"), { type: "success" });
        await this.loadOperation(this.state.selectedModel, this.state.selected.id);
    }

    async onUploadDriverPhoto(ev) {
        const file = ev.target.files[0];
        if (!file || !this.state.selected) {
            return;
        }
        const imageBase64 = await this._toBase64(file);
        const stripped = imageBase64.split(",")[1];
        await this.orm.call("stock.barcode.app", "create_picking_photo", [this.state.selected.id, stripped, "Captured by driver"]);
        this.notification.add(this.env._t("Driver photo uploaded"), { type: "success" });
        await this.loadDriverDelivery(this.state.selected.id);
    }

    _toBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = () => resolve(reader.result);
            reader.onerror = (error) => reject(error);
        });
    }
}

StockBarcodeCustomApp.template = "stock_barcode_custom.Main";

registry.category("actions").add("stock_barcode_custom_main", StockBarcodeCustomApp);
registry.category("actions").add("stock_barcode_custom_driver", StockBarcodeCustomApp);
