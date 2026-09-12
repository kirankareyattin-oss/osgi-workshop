package com.northwind.oms.shipping;

import com.northwind.oms.customer.Customer;

/**
 * A dispatched parcel bound for a specific customer.
 */
public final class Shipment {

    public enum Status { CREATED, IN_TRANSIT, DELIVERED, RETURNED }

    private final String trackingId;
    private final String customerId;
    private Status status;

    public Shipment(String trackingId, Customer customer) {
        if (trackingId == null || trackingId.isBlank()) {
            throw new IllegalArgumentException("trackingId is required");
        }
        this.trackingId = trackingId;
        this.customerId = customer.getCustomerId();
        this.status = Status.CREATED;
    }

    public String getTrackingId() {
        return trackingId;
    }

    public String getCustomerId() {
        return customerId;
    }

    public Status getStatus() {
        return status;
    }

    public void advanceTo(Status next) {
        this.status = next;
    }
}
