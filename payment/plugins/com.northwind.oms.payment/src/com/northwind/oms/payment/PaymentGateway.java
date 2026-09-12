package com.northwind.oms.payment;

import java.util.UUID;

import com.northwind.oms.core.model.Money;
import com.northwind.oms.security.spi.Principal;

/**
 * Authorizes charges against a customer's account. This demo implementation
 * approves any positive amount for a caller that holds the {@code BILLING} role.
 */
public class PaymentGateway {

    private static final long MAX_AUTOMATIC_AUTH = 500_000L;

    public PaymentResult authorize(Principal caller, Money amount) {
        if (caller == null || !caller.hasRole("BILLING")) {
            return PaymentResult.declined("caller is not authorized to charge payments");
        }
        if (amount == null || amount.getMinorUnits() <= 0) {
            return PaymentResult.declined("amount must be positive");
        }
        if (amount.getMinorUnits() > MAX_AUTOMATIC_AUTH) {
            return PaymentResult.declined("amount exceeds automatic authorization limit");
        }
        return PaymentResult.approved("PAY-" + UUID.randomUUID());
    }
}
