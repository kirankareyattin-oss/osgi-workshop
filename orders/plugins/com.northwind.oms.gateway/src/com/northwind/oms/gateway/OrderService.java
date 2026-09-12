package com.northwind.oms.gateway;

import com.northwind.oms.core.model.Money;
import com.northwind.oms.core.model.Order;
import com.northwind.oms.core.model.OrderLine;
import com.northwind.oms.core.spi.InsufficientStockException;
import com.northwind.oms.core.spi.PriceCalculator;
import com.northwind.oms.core.spi.StockRepository;

/**
 * Application-facing entry point that ties together the pricing and inventory
 * capabilities. It depends only on the SPI interfaces from the core bundle, so
 * the concrete implementations can be swapped without touching this class.
 */
public class OrderService {

    private final StockRepository stockRepository;
    private final PriceCalculator priceCalculator;

    public OrderService(StockRepository stockRepository, PriceCalculator priceCalculator) {
        this.stockRepository = stockRepository;
        this.priceCalculator = priceCalculator;
    }

    /**
     * Reserves stock for every line and returns the payable total.
     *
     * @throws InsufficientStockException if any line cannot be fulfilled
     */
    public Money checkout(Order order) throws InsufficientStockException {
        if (order.isEmpty()) {
            throw new IllegalArgumentException("cannot checkout an empty order");
        }
        for (OrderLine line : order.getLines()) {
            stockRepository.reserve(line.getProduct().getSku(), line.getQuantity());
        }
        return priceCalculator.calculateTotal(order);
    }

    public boolean canFulfill(Order order) {
        for (OrderLine line : order.getLines()) {
            int available = stockRepository.availableQuantity(line.getProduct().getSku());
            if (available < line.getQuantity()) {
                return false;
            }
        }
        return true;
    }
}
