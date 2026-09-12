package com.northwind.oms.core.spi;

/**
 * Raised when a reservation cannot be satisfied from available stock.
 */
public class InsufficientStockException extends Exception {

    private static final long serialVersionUID = 1L;

    public InsufficientStockException(String sku, int requested, int available) {
        super("Cannot reserve " + requested + " of " + sku + "; only " + available + " available");
    }
}
