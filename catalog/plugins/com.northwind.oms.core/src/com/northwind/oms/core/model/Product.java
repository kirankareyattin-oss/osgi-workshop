package com.northwind.oms.core.model;

/**
 * A sellable catalog item identified by its SKU.
 */
public final class Product {

    private final String sku;
    private final String displayName;
    private final Money unitPrice;

    public Product(String sku, String displayName, Money unitPrice) {
        if (sku == null || sku.isBlank()) {
            throw new IllegalArgumentException("sku is required");
        }
        this.sku = sku;
        this.displayName = displayName;
        this.unitPrice = unitPrice;
    }

    public String getSku() {
        return sku;
    }

    public String getDisplayName() {
        return displayName;
    }

    public Money getUnitPrice() {
        return unitPrice;
    }

    @Override
    public String toString() {
        return sku + " (" + displayName + ")";
    }
}
