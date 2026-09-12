package com.northwind.oms.core.spi;

/**
 * Read/write access to on-hand stock levels keyed by SKU.
 * Implementations are contributed by other bundles (e.g. the inventory bundle).
 */
public interface StockRepository {

    int availableQuantity(String sku);

    void reserve(String sku, int quantity) throws InsufficientStockException;
}
