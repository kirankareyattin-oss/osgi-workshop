package com.northwind.oms.shipping;

import com.northwind.oms.core.model.Money;
import com.northwind.oms.customer.Customer;
import com.northwind.oms.customer.Customer.CustomerTier;

/**
 * Computes a shipping fee from parcel weight, with free shipping granted to
 * the higher customer tiers.
 */
public class ShippingCalculator {

    private static final long BASE_FEE_MINOR = 499;   // 4.99
    private static final long PER_KG_MINOR = 150;     // 1.50 per kg
    private final String currency;

    public ShippingCalculator(String currency) {
        this.currency = currency;
    }

    public Money quote(Customer customer, double weightKg) {
        if (weightKg < 0) {
            throw new IllegalArgumentException("weight cannot be negative");
        }
        if (qualifiesForFreeShipping(customer)) {
            return new Money(0, currency);
        }
        long fee = BASE_FEE_MINOR + Math.round(weightKg * PER_KG_MINOR);
        return new Money(fee, currency);
    }

    private boolean qualifiesForFreeShipping(Customer customer) {
        CustomerTier tier = customer.getTier();
        return tier == CustomerTier.GOLD || tier == CustomerTier.PLATINUM;
    }
}
