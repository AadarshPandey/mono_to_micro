package com.enterprise.monolith.controller;

import com.enterprise.monolith.model.Order;
import com.enterprise.monolith.model.Payment.PaymentMethod;
import com.enterprise.monolith.service.OrderService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * Order Controller — full order lifecycle.
 * Delegates to the OrderService god class which orchestrates everything.
 */
@RestController
@RequestMapping("/api/orders")
public class OrderController {

    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    /**
     * Create a new order.
     * Body: { "customerId": 1, "items": [{"productId": 1, "quantity": 2}],
     *         "shippingAddress": "...", "shippingCity": "...", "shippingZip": "..." }
     */
    @PostMapping
    public ResponseEntity<?> createOrder(@RequestBody Map<String, Object> request) {
        try {
            Long customerId = ((Number) request.get("customerId")).longValue();
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> items = (List<Map<String, Object>>) request.get("items");
            String address = (String) request.getOrDefault("shippingAddress", "");
            String city = (String) request.getOrDefault("shippingCity", "");
            String zip = (String) request.getOrDefault("shippingZip", "");

            Order order = orderService.createOrder(customerId, items, address, city, zip);
            return ResponseEntity.status(HttpStatus.CREATED).body(orderToMap(order));
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }

    @GetMapping("/{id}")
    public ResponseEntity<?> getOrder(@PathVariable Long id) {
        try {
            Order order = orderService.getOrder(id);
            return ResponseEntity.ok(orderToMap(order));
        } catch (Exception e) {
            return ResponseEntity.notFound().build();
        }
    }

    @GetMapping("/customer/{customerId}")
    public ResponseEntity<List<Map<String, Object>>> getByCustomer(@PathVariable Long customerId) {
        return ResponseEntity.ok(
                orderService.getOrdersByCustomer(customerId).stream().map(this::orderToMap).toList());
    }

    /** Pay for an order — triggers cross-domain payment + credit score update */
    @PostMapping("/{id}/pay")
    public ResponseEntity<?> payOrder(@PathVariable Long id,
                                      @RequestParam(defaultValue = "CREDIT_CARD") String method) {
        try {
            Order order = orderService.processPayment(id, PaymentMethod.valueOf(method));
            return ResponseEntity.ok(orderToMap(order));
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }

    /** Cancel order — triggers stock release + refund + customer spend reversal */
    @PostMapping("/{id}/cancel")
    public ResponseEntity<?> cancelOrder(@PathVariable Long id) {
        try {
            Order order = orderService.cancelOrder(id);
            return ResponseEntity.ok(orderToMap(order));
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }

    private Map<String, Object> orderToMap(Order o) {
        return Map.of(
                "id", o.getId(),
                "customerId", o.getCustomer().getId(),
                "customerName", o.getCustomer().getName(),
                "status", o.getStatus(),
                "totalAmount", o.getTotalAmount(),
                "itemCount", o.getItems().size(),
                "createdAt", o.getCreatedAt().toString()
        );
    }
}
