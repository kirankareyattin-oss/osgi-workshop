package com.northwind.oms.core.model;

/**
 * A single requested product with a quantity inside an {@link Order}.
 */
public final class OrderLine {

    private final Product product;
    private final int quantity;

    public OrderLine(Product product, int quantity) {
        if (product == null) {
            throw new IllegalArgumentException("product is required");
        }
        if (quantity <= 0) {
            throw new IllegalArgumentException("quantity must be positive");
        }
        this.product = product;
        this.quantity = quantity;
    }

    public Product getProduct() {
        return product;
    }

    public int getQuantity() {
        return quantity;
    }

    public Money getLineTotal() {
        return product.getUnitPrice().times(quantity);
    }
}
