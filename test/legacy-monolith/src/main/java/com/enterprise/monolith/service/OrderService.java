package com.enterprise.monolith.service;

import com.enterprise.monolith.model.*;
import com.enterprise.monolith.model.Order.OrderStatus;
import com.enterprise.monolith.model.Payment.PaymentMethod;
import com.enterprise.monolith.repository.OrderRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * ══════════════════════════════════════════════════════════════════════
 *  GOD CLASS — OrderService
 *  This is the central anti-pattern in the monolith.
 *  It directly calls into EVERY other domain:
 *    - CustomerService (customer lookup, lifetime spend update)
 *    - InventoryService (stock reservation/release)
 *    - PaymentService  (payment processing)
 *
 *  In a proper microservice architecture, this class would be split
 *  into an Order Service that communicates via HTTP/events with
 *  separate Customer, Inventory, and Payment services.
 * ══════════════════════════════════════════════════════════════════════
 */
@Service
public class OrderService {

    private static final Logger log = LoggerFactory.getLogger(OrderService.class);

    private final OrderRepository orderRepository;
    private final CustomerService customerService;     // CROSS-DOMAIN
    private final InventoryService inventoryService;   // CROSS-DOMAIN
    private final PaymentService paymentService;       // CROSS-DOMAIN

    public OrderService(
            OrderRepository orderRepository,
            CustomerService customerService,
            InventoryService inventoryService,
            PaymentService paymentService
    ) {
        this.orderRepository = orderRepository;
        this.customerService = customerService;
        this.inventoryService = inventoryService;
        this.paymentService = paymentService;
    }

    /**
     * Create a complete order — orchestrates across ALL domains.
     * This single method touches Customer, Inventory, and Order tables.
     *
     * @param customerId  Customer placing the order
     * @param itemRequests List of {productId, quantity} maps
     * @param shippingAddress Shipping details
     */
    @Transactional
    public Order createOrder(Long customerId, List<Map<String, Object>> itemRequests,
                             String shippingAddress, String shippingCity, String shippingZip) {

        // ── Step 1: Validate customer (Customer domain) ──────────────
        Customer customer = customerService.getCustomer(customerId);
        log.info("Creating order for customer: {} ({})", customer.getName(), customer.getEmail());

        // ── Step 2: Build order and validate/reserve stock (Inventory domain)
        Order order = new Order();
        order.setCustomer(customer);
        order.setShippingAddress(shippingAddress);
        order.setShippingCity(shippingCity);
        order.setShippingZip(shippingZip);
        order.setStatus(OrderStatus.PENDING);

        double totalAmount = 0;

        for (Map<String, Object> itemReq : itemRequests) {
            Long productId = ((Number) itemReq.get("productId")).longValue();
            int quantity = ((Number) itemReq.get("quantity")).intValue();

            // Direct call to Inventory domain — synchronous coupling
            Product product = inventoryService.getProduct(productId);
            boolean reserved = inventoryService.reserveStock(productId, quantity);
            if (!reserved) {
                throw new RuntimeException("Insufficient stock for product: " + product.getName());
            }

            OrderItem item = new OrderItem(product, quantity);
            order.addItem(item);
            totalAmount += item.getSubtotal();
        }

        order.setTotalAmount(totalAmount);
        order.setStatus(OrderStatus.CONFIRMED);
        order = orderRepository.save(order);

        // ── Step 3: Update customer lifetime spend (Customer domain write) ──
        customer.setLifetimeSpend(customer.getLifetimeSpend() + totalAmount);
        customerService.updateTier(customer);

        log.info("Order {} created: {} items, total=${}", order.getId(), order.getItems().size(), totalAmount);
        return order;
    }

    /**
     * Process payment for an order — orchestrates Order + Payment + Customer domains.
     */
    @Transactional
    public Order processPayment(Long orderId, PaymentMethod paymentMethod) {
        Order order = getOrder(orderId);

        if (order.getStatus() != OrderStatus.CONFIRMED) {
            throw new RuntimeException("Order " + orderId + " is not in CONFIRMED state");
        }

        // Direct call to Payment domain
        Payment payment = paymentService.processPayment(order, paymentMethod);

        if (payment.getStatus() == Payment.PaymentStatus.COMPLETED) {
            order.setStatus(OrderStatus.PAID);
            order.setUpdatedAt(LocalDateTime.now());

            // Cross-domain side effect: recalculate customer credit score
            customerService.recalculateCreditScore(order.getCustomer().getId());
        } else {
            order.setStatus(OrderStatus.PENDING);
            log.warn("Payment failed for order {}", orderId);
        }

        return orderRepository.save(order);
    }

    /**
     * Cancel an order — must reverse stock reservations.
     * ANTI-PATTERN: Compensating logic spread across OrderService
     * instead of using a saga pattern.
     */
    @Transactional
    public Order cancelOrder(Long orderId) {
        Order order = getOrder(orderId);

        if (order.getStatus() == OrderStatus.SHIPPED || order.getStatus() == OrderStatus.DELIVERED) {
            throw new RuntimeException("Cannot cancel order " + orderId + " — already " + order.getStatus());
        }

        // Release stock back to inventory (Inventory domain)
        for (OrderItem item : order.getItems()) {
            inventoryService.releaseStock(item.getProduct().getId(), item.getQuantity());
        }

        // Reverse customer lifetime spend (Customer domain)
        Customer customer = order.getCustomer();
        customer.setLifetimeSpend(Math.max(0, customer.getLifetimeSpend() - order.getTotalAmount()));
        customerService.updateTier(customer);

        // Refund payment if paid (Payment domain)
        if (order.getStatus() == OrderStatus.PAID) {
            paymentService.refundOrder(orderId);
        }

        order.setStatus(OrderStatus.CANCELLED);
        order.setUpdatedAt(LocalDateTime.now());
        return orderRepository.save(order);
    }

    public Order getOrder(Long id) {
        return orderRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Order not found: " + id));
    }

    public List<Order> getOrdersByCustomer(Long customerId) {
        return orderRepository.findByCustomerId(customerId);
    }

    public List<Order> getOrdersByStatus(OrderStatus status) {
        return orderRepository.findByStatusWithCustomer(status);
    }
}
