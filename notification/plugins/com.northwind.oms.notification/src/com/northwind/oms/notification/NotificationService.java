package com.northwind.oms.notification;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import com.northwind.oms.customer.Customer;
import com.northwind.oms.shipping.Shipment;

/**
 * Builds and records customer-facing messages. Messages are captured in memory
 * so tests can assert on what would have been sent.
 */
public class NotificationService {

    public record Notification(String customerId, Channel channel, String body) { }

    private final List<Notification> outbox = new ArrayList<>();

    public Notification notifyShipmentUpdate(Customer customer, Shipment shipment) {
        Channel channel = preferredChannel(customer);
        String body = "Hi " + customer.getFullName() + ", your parcel " + shipment.getTrackingId()
                + " is now " + shipment.getStatus() + ".";
        Notification notification = new Notification(customer.getCustomerId(), channel, body);
        outbox.add(notification);
        return notification;
    }

    public List<Notification> getOutbox() {
        return Collections.unmodifiableList(outbox);
    }

    private Channel preferredChannel(Customer customer) {
        return customer.getEmail() == null ? Channel.SMS : Channel.EMAIL;
    }
}
