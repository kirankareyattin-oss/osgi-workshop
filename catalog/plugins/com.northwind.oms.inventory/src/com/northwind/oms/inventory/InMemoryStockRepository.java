package com.northwind.oms.inventory;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import com.northwind.oms.core.spi.InsufficientStockException;
import com.northwind.oms.core.spi.StockRepository;

/**
 * Thread-safe, non-persistent {@link StockRepository} backed by a map.
 * Suitable for demos and unit tests; a real deployment would swap this for a
 * database-backed implementation registered as an OSGi service.
 */
public class InMemoryStockRepository implements StockRepository {

    private final Map<String, Integer> onHand = new ConcurrentHashMap<>();

    public void stock(String sku, int quantity) {
        if (quantity < 0) {
            throw new IllegalArgumentException("quantity cannot be negative");
        }
        onHand.merge(sku, quantity, Integer::sum);
    }

    @Override
    public int availableQuantity(String sku) {
        return onHand.getOrDefault(sku, 0);
    }

    @Override
    public void reserve(String sku, int quantity) throws InsufficientStockException {
        onHand.compute(sku, (key, current) -> {
            int available = current == null ? 0 : current;
            if (available < quantity) {
                throw new ReservationRejected(sku, quantity, available);
            }
            return available - quantity;
        });
    }

    /** Unchecked wrapper so it can escape the {@link Map#compute} lambda. */
    private static final class ReservationRejected extends RuntimeException {
        private static final long serialVersionUID = 1L;
        private final transient InsufficientStockException cause;

        ReservationRejected(String sku, int requested, int available) {
            this.cause = new InsufficientStockException(sku, requested, available);
        }
    }

    /**
     * Variant of {@link #reserve} that surfaces the checked exception cleanly.
     */
    public void reserveChecked(String sku, int quantity) throws InsufficientStockException {
        try {
            reserve(sku, quantity);
        } catch (ReservationRejected rejected) {
            throw rejected.cause;
        }
    }
}
