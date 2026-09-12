package com.northwind.oms.core.spi;

import com.northwind.oms.core.model.Money;
import com.northwind.oms.core.model.Order;

/**
 * Strategy that turns an {@link Order} into a final payable amount.
 * Implementations are contributed by other bundles (e.g. the pricing bundle).
 */
public interface PriceCalculator {

    Money calculateTotal(Order order);
}
