package com.northwind.oms.core.model;

/**
 * Immutable monetary amount stored in minor units (e.g. cents) to avoid
 * floating point rounding problems in price calculations.
 */
public final class Money {

    private final long minorUnits;
    private final String currency;

    public Money(long minorUnits, String currency) {
        if (currency == null || currency.isBlank()) {
            throw new IllegalArgumentException("currency is required");
        }
        this.minorUnits = minorUnits;
        this.currency = currency;
    }

    public static Money of(long majorUnits, int cents, String currency) {
        return new Money(majorUnits * 100 + cents, currency);
    }

    public long getMinorUnits() {
        return minorUnits;
    }

    public String getCurrency() {
        return currency;
    }

    public Money plus(Money other) {
        requireSameCurrency(other);
        return new Money(this.minorUnits + other.minorUnits, currency);
    }

    public Money times(int factor) {
        return new Money(this.minorUnits * factor, currency);
    }

    private void requireSameCurrency(Money other) {
        if (!this.currency.equals(other.currency)) {
            throw new IllegalArgumentException(
                    "currency mismatch: " + currency + " vs " + other.currency);
        }
    }

    @Override
    public String toString() {
        return String.format("%d.%02d %s", minorUnits / 100, Math.abs(minorUnits % 100), currency);
    }
}
