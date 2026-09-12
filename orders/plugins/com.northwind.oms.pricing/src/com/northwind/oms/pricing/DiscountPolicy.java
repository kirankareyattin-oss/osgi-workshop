package com.northwind.oms.pricing;

import com.northwind.oms.core.model.Money;

/**
 * Percentage-based discount that applies once an order subtotal crosses a
 * threshold. Amounts are expressed in minor units to match {@link Money}.
 */
public final class DiscountPolicy {

    private final long thresholdMinorUnits;
    private final int percentOff;

    public DiscountPolicy(long thresholdMinorUnits, int percentOff) {
        if (percentOff < 0 || percentOff > 100) {
            throw new IllegalArgumentException("percentOff must be between 0 and 100");
        }
        this.thresholdMinorUnits = thresholdMinorUnits;
        this.percentOff = percentOff;
    }

    public static DiscountPolicy none() {
        return new DiscountPolicy(Long.MAX_VALUE, 0);
    }

    public Money apply(Money subtotal) {
        if (subtotal.getMinorUnits() < thresholdMinorUnits || percentOff == 0) {
            return subtotal;
        }
        long discounted = subtotal.getMinorUnits() * (100L - percentOff) / 100L;
        return new Money(discounted, subtotal.getCurrency());
    }
}
