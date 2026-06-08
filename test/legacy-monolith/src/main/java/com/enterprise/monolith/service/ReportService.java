package com.enterprise.monolith.service;

import com.enterprise.monolith.model.*;
import com.enterprise.monolith.repository.*;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * ══════════════════════════════════════════════════════════════════════
 *  SECOND GOD CLASS — ReportService
 *  Aggregates data across ALL domains. Imports every repository and
 *  every service. In a microservice architecture, this would need to
 *  call 4 separate services via HTTP/gRPC and aggregate responses.
 * ══════════════════════════════════════════════════════════════════════
 */
@Service
public class ReportService {

    private final OrderRepository orderRepository;
    private final CustomerRepository customerRepository;
    private final ProductRepository productRepository;
    private final PaymentRepository paymentRepository;
    private final PaymentService paymentService;
    private final InventoryService inventoryService;

    public ReportService(
            OrderRepository orderRepository,
            CustomerRepository customerRepository,
            ProductRepository productRepository,
            PaymentRepository paymentRepository,
            PaymentService paymentService,
            InventoryService inventoryService
    ) {
        this.orderRepository = orderRepository;
        this.customerRepository = customerRepository;
        this.productRepository = productRepository;
        this.paymentRepository = paymentRepository;
        this.paymentService = paymentService;
        this.inventoryService = inventoryService;
    }

    /**
     * Generate a business dashboard report.
     * ANTI-PATTERN: Single method queries across ALL domain tables.
     * Each line would be a separate HTTP call in microservices.
     */
    public Map<String, Object> getDashboardReport() {
        Map<String, Object> report = new HashMap<>();

        // Customer domain
        List<Customer> allCustomers = customerRepository.findAll();
        report.put("totalCustomers", allCustomers.size());
        report.put("platinumCustomers", customerRepository.findByTier(Customer.CustomerTier.PLATINUM).size());
        report.put("avgCreditScore", allCustomers.stream()
                .mapToInt(Customer::getCreditScore).average().orElse(0));

        // Order domain
        List<Order> allOrders = orderRepository.findAll();
        report.put("totalOrders", allOrders.size());
        report.put("pendingOrders", orderRepository.findByStatus(Order.OrderStatus.PENDING).size());
        report.put("paidOrders", orderRepository.findByStatus(Order.OrderStatus.PAID).size());
        report.put("cancelledOrders", orderRepository.findByStatus(Order.OrderStatus.CANCELLED).size());

        // Payment domain
        report.put("totalRevenue", paymentService.getTotalRevenue());
        report.put("totalPayments", paymentRepository.count());

        // Inventory domain
        List<Product> allProducts = productRepository.findAll();
        report.put("totalProducts", allProducts.size());
        report.put("lowStockProducts", inventoryService.getLowStockProducts().size());
        report.put("totalInventoryValue", allProducts.stream()
                .mapToDouble(p -> p.getPrice() * p.getStockQuantity()).sum());

        return report;
    }

    /**
     * Revenue by customer report — joins Order, Payment, and Customer data.
     */
    public List<Map<String, Object>> getRevenueByCustomer() {
        List<Customer> customers = customerRepository.findAll();
        return customers.stream().map(c -> {
            Map<String, Object> row = new HashMap<>();
            row.put("customerId", c.getId());
            row.put("name", c.getName());
            row.put("tier", c.getTier());
            row.put("lifetimeSpend", c.getLifetimeSpend());
            row.put("successfulPayments", paymentService.countSuccessfulPayments(c.getId()));
            return row;
        }).toList();
    }
}
