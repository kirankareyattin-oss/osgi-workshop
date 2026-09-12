package com.northwind.oms.customer;

/**
 * A registered buyer identified by a stable customer id.
 */
public final class Customer {

    private final String customerId;
    private final String fullName;
    private final String email;
    private final CustomerTier tier;

    public Customer(String customerId, String fullName, String email, CustomerTier tier) {
        if (customerId == null || customerId.isBlank()) {
            throw new IllegalArgumentException("customerId is required");
        }
        this.customerId = customerId;
        this.fullName = fullName;
        this.email = email;
        this.tier = tier == null ? CustomerTier.STANDARD : tier;
    }

    public String getCustomerId() {
        return customerId;
    }

    public String getFullName() {
        return fullName;
    }

    public String getEmail() {
        return email;
    }

    public CustomerTier getTier() {
        return tier;
    }

    public enum CustomerTier {
        STANDARD, SILVER, GOLD, PLATINUM
    }
}
