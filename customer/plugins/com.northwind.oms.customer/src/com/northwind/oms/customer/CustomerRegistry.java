package com.northwind.oms.customer;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * In-memory directory of {@link Customer} records keyed by customer id.
 */
public class CustomerRegistry {

    private final Map<String, Customer> customers = new ConcurrentHashMap<>();

    public void register(Customer customer) {
        customers.put(customer.getCustomerId(), customer);
    }

    public Optional<Customer> find(String customerId) {
        return Optional.ofNullable(customers.get(customerId));
    }

    public boolean exists(String customerId) {
        return customers.containsKey(customerId);
    }

    public int size() {
        return customers.size();
    }
}
