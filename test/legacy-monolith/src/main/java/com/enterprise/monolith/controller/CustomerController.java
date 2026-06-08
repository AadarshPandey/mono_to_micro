package com.enterprise.monolith.controller;

import com.enterprise.monolith.model.Customer;
import com.enterprise.monolith.model.Product;
import com.enterprise.monolith.service.CustomerService;
import com.enterprise.monolith.service.InventoryService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * Customer & Inventory Controller — manages customers and products.
 * ANTI-PATTERN: Two unrelated domains in one controller.
 */
@RestController
@RequestMapping("/api")
public class CustomerController {

    private final CustomerService customerService;
    private final InventoryService inventoryService;

    public CustomerController(CustomerService customerService, InventoryService inventoryService) {
        this.customerService = customerService;
        this.inventoryService = inventoryService;
    }

    // ── Customer endpoints ────────────────────────────────────────────

    @PostMapping("/customers")
    public ResponseEntity<Customer> createCustomer(@RequestBody Map<String, String> request) {
        Customer customer = customerService.createCustomer(
                request.get("name"), request.get("email"), request.get("phone"));
        return ResponseEntity.status(HttpStatus.CREATED).body(customer);
    }

    @GetMapping("/customers")
    public ResponseEntity<List<Customer>> getAllCustomers() {
        return ResponseEntity.ok(customerService.getAllCustomers());
    }

    @GetMapping("/customers/{id}")
    public ResponseEntity<?> getCustomer(@PathVariable Long id) {
        try {
            return ResponseEntity.ok(customerService.getCustomer(id));
        } catch (Exception e) {
            return ResponseEntity.notFound().build();
        }
    }

    @GetMapping("/customers/high-value")
    public ResponseEntity<List<Customer>> getHighValueCustomers() {
        return ResponseEntity.ok(customerService.getHighValueCustomers());
    }

    // ── Product / Inventory endpoints (WRONG — mixed into Customer controller)

    @PostMapping("/products")
    public ResponseEntity<Product> createProduct(@RequestBody Map<String, Object> request) {
        Product product = inventoryService.createProduct(
                (String) request.get("name"),
                (String) request.get("category"),
                ((Number) request.get("price")).doubleValue(),
                ((Number) request.get("stock")).intValue()
        );
        return ResponseEntity.status(HttpStatus.CREATED).body(product);
    }

    @GetMapping("/products")
    public ResponseEntity<List<Product>> getAllProducts() {
        return ResponseEntity.ok(inventoryService.getAllProducts());
    }

    @GetMapping("/products/{id}")
    public ResponseEntity<?> getProduct(@PathVariable Long id) {
        try {
            return ResponseEntity.ok(inventoryService.getProduct(id));
        } catch (Exception e) {
            return ResponseEntity.notFound().build();
        }
    }

    @GetMapping("/products/low-stock")
    public ResponseEntity<List<Product>> getLowStockProducts() {
        return ResponseEntity.ok(inventoryService.getLowStockProducts());
    }
}
