package com.northwind.oms.pricing;

import com.northwind.oms.core.model.Money;
import com.northwind.oms.core.model.Order;
import com.northwind.oms.core.model.OrderLine;
import com.northwind.oms.core.spi.PriceCalculator;

/**
 * Default {@link PriceCalculator}: sums the line totals and then applies an
 * optional {@link DiscountPolicy}.
 */
public class StandardPriceCalculator implements PriceCalculator {

    private final String currency;
    private final DiscountPolicy discountPolicy;

    public StandardPriceCalculator(String currency, DiscountPolicy discountPolicy) {
        this.currency = currency;
        this.discountPolicy = discountPolicy == null ? DiscountPolicy.none() : discountPolicy;
    }

    @Override
    public Money calculateTotal(Order order) {
        Money subtotal = new Money(0, currency);
        for (OrderLine line : order.getLines()) {
            subtotal = subtotal.plus(line.getLineTotal());
        }
        return discountPolicy.apply(subtotal);
    }
}
