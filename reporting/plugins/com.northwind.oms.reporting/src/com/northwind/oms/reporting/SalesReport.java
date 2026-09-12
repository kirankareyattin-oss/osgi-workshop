package com.northwind.oms.reporting;

import com.northwind.oms.core.model.Money;

/**
 * Aggregated sales figures for a reporting period.
 */
public final class SalesReport {

    private final String period;
    private final int orderCount;
    private final Money grossRevenue;

    public SalesReport(String period, int orderCount, Money grossRevenue) {
        this.period = period;
        this.orderCount = orderCount;
        this.grossRevenue = grossRevenue;
    }

    public String getPeriod() {
        return period;
    }

    public int getOrderCount() {
        return orderCount;
    }

    public Money getGrossRevenue() {
        return grossRevenue;
    }

    public Money getAverageOrderValue() {
        if (orderCount == 0) {
            return new Money(0, grossRevenue.getCurrency());
        }
        return new Money(grossRevenue.getMinorUnits() / orderCount, grossRevenue.getCurrency());
    }
}
