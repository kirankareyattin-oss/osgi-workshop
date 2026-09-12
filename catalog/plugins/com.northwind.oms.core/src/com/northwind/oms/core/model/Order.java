package com.northwind.oms.core.model;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * A customer order composed of one or more {@link OrderLine}s.
 */
public final class Order {

    private final String orderId;
    private final List<OrderLine> lines = new ArrayList<>();

    public Order(String orderId) {
        if (orderId == null || orderId.isBlank()) {
            throw new IllegalArgumentException("orderId is required");
        }
        this.orderId = orderId;
    }

    public Order addLine(OrderLine line) {
        lines.add(line);
        return this;
    }

    public String getOrderId() {
        return orderId;
    }

    public List<OrderLine> getLines() {
        return Collections.unmodifiableList(lines);
    }

    public boolean isEmpty() {
        return lines.isEmpty();
    }
}
