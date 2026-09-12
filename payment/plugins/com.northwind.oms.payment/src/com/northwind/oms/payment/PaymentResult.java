package com.northwind.oms.payment;

/**
 * Outcome of a payment authorization attempt.
 */
public final class PaymentResult {

    private final boolean approved;
    private final String reference;
    private final String declineReason;

    private PaymentResult(boolean approved, String reference, String declineReason) {
        this.approved = approved;
        this.reference = reference;
        this.declineReason = declineReason;
    }

    public static PaymentResult approved(String reference) {
        return new PaymentResult(true, reference, null);
    }

    public static PaymentResult declined(String reason) {
        return new PaymentResult(false, null, reason);
    }

    public boolean isApproved() {
        return approved;
    }

    public String getReference() {
        return reference;
    }

    public String getDeclineReason() {
        return declineReason;
    }
}
