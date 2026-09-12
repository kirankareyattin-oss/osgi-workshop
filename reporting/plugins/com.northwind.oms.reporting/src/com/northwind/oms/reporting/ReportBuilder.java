package com.northwind.oms.reporting;

import java.util.ArrayList;
import java.util.List;

import com.northwind.oms.core.model.Money;
import com.northwind.oms.core.model.Order;
import com.northwind.oms.core.model.OrderLine;

/**
 * Accumulates orders and renders a {@link SalesReport}. Revenue is derived from
 * line totals; a real implementation would read settled payments instead.
 */
public class ReportBuilder {

    private final String period;
    private final String currency;
    private final List<Order> orders = new ArrayList<>();

    public ReportBuilder(String period, String currency) {
        this.period = period;
        this.currency = currency;
    }

    public ReportBuilder include(Order order) {
        orders.add(order);
        return this;
    }

    public SalesReport build() {
        Money gross = new Money(0, currency);
        for (Order order : orders) {
            for (OrderLine line : order.getLines()) {
                gross = gross.plus(line.getLineTotal());
            }
        }
        return new SalesReport(period, orders.size(), gross);
    }
}
