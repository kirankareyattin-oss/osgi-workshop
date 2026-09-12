package com.northwind.oms.inventory;

/**
 * Snapshot of the stock position for a single SKU.
 */
public final class StockLevel {

    private final String sku;
    private final int available;
    private final int reorderThreshold;

    public StockLevel(String sku, int available, int reorderThreshold) {
        this.sku = sku;
        this.available = available;
        this.reorderThreshold = reorderThreshold;
    }

    public String getSku() {
        return sku;
    }

    public int getAvailable() {
        return available;
    }

    public boolean needsReorder() {
        return available <= reorderThreshold;
    }
}
