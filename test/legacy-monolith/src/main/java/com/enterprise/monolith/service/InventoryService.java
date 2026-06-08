package com.enterprise.monolith.service;

import com.enterprise.monolith.model.Product;
import com.enterprise.monolith.repository.ProductRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * Inventory Service — stock management.
 *
 * COUPLING: OrderService directly calls reserveStock() and releaseStock(),
 * bypassing any event-driven decoupling pattern.
 */
@Service
public class InventoryService {

    private static final Logger log = LoggerFactory.getLogger(InventoryService.class);
    private final ProductRepository productRepository;

    public InventoryService(ProductRepository productRepository) {
        this.productRepository = productRepository;
    }

    public Product createProduct(String name, String category, double price, int stock) {
        Product product = new Product(name, category, price, stock);
        return productRepository.save(product);
    }

    public Product getProduct(Long id) {
        return productRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Product not found: " + id));
    }

    public List<Product> getAllProducts() {
        return productRepository.findAvailableProducts();
    }

    /**
     * Reserve stock for an order.
     * ANTI-PATTERN: Called directly by OrderService — tight synchronous coupling.
     * Should be event-driven in a microservice architecture.
     */
    @Transactional
    public boolean reserveStock(Long productId, int quantity) {
        Product product = getProduct(productId);
        if (product.getStockQuantity() < quantity) {
            log.warn("Insufficient stock for product {}: requested={}, available={}",
                    productId, quantity, product.getStockQuantity());
            return false;
        }
        product.setStockQuantity(product.getStockQuantity() - quantity);
        productRepository.save(product);

        checkReorderThreshold(product);
        return true;
    }

    /** Release stock on order cancellation */
    @Transactional
    public void releaseStock(Long productId, int quantity) {
        Product product = getProduct(productId);
        product.setStockQuantity(product.getStockQuantity() + quantity);
        productRepository.save(product);
    }

    /**
     * Check if stock has fallen below reorder threshold.
     * ANTI-PATTERN: This triggers a notification inline — should be async event.
     */
    private void checkReorderThreshold(Product product) {
        if (product.getStockQuantity() <= product.getReorderThreshold()) {
            log.warn("LOW STOCK ALERT: {} (id={}) has only {} units remaining",
                    product.getName(), product.getId(), product.getStockQuantity());
            // In a monolith, this would call NotificationService directly
            // rather than publishing a domain event
        }
    }

    public List<Product> getLowStockProducts() {
        return productRepository.findLowStockProducts();
    }
}
