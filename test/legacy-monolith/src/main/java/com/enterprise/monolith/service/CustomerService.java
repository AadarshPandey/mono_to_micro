package com.enterprise.monolith.service;

import com.enterprise.monolith.model.Customer;
import com.enterprise.monolith.model.Customer.CustomerTier;
import com.enterprise.monolith.repository.CustomerRepository;
import org.springframework.context.annotation.Lazy;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * Customer Service — manages customer lifecycle.
 *
 * COUPLING: Calls PaymentService to recalculate credit scores.
 * This creates a bidirectional dependency since PaymentService also
 * calls CustomerService for credit checks.
 *
 * WORKAROUND: @Lazy on PaymentService to break circular DI.
 * This is a band-aid — the real fix is to split into separate microservices.
 */
@Service
public class CustomerService {

    private final CustomerRepository customerRepository;
    private final PaymentService paymentService;  // CROSS-DOMAIN DEPENDENCY

    public CustomerService(CustomerRepository customerRepository, @Lazy PaymentService paymentService) {
        this.customerRepository = customerRepository;
        this.paymentService = paymentService;
    }

    public Customer createCustomer(String name, String email, String phone) {
        Customer customer = new Customer(name, email, phone);
        return customerRepository.save(customer);
    }

    public Customer getCustomer(Long id) {
        return customerRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Customer not found: " + id));
    }

    public List<Customer> getAllCustomers() {
        return customerRepository.findAll();
    }

    /**
     * Recalculate credit score based on payment history.
     * ANTI-PATTERN: Customer domain depends on Payment domain logic.
     */
    @Transactional
    public void recalculateCreditScore(Long customerId) {
        Customer customer = getCustomer(customerId);
        long successfulPayments = paymentService.countSuccessfulPayments(customerId);
        int newScore = (int) Math.min(850, 500 + (successfulPayments * 25));
        customer.setCreditScore(newScore);
        updateTier(customer);
        customerRepository.save(customer);
    }

    /**
     * Update customer tier based on lifetime spend.
     * ANTI-PATTERN: Tier logic uses data written by OrderService.
     */
    @Transactional
    public void updateTier(Customer customer) {
        double spend = customer.getLifetimeSpend();
        if (spend >= 10000) customer.setTier(CustomerTier.PLATINUM);
        else if (spend >= 5000) customer.setTier(CustomerTier.GOLD);
        else if (spend >= 1000) customer.setTier(CustomerTier.SILVER);
        else customer.setTier(CustomerTier.BRONZE);
        customerRepository.save(customer);
    }

    /**
     * Check if customer is eligible for credit-based purchases.
     * Called by PaymentService — creates circular dependency path.
     */
    public boolean isCreditWorthy(Long customerId) {
        Customer customer = getCustomer(customerId);
        return customer.getCreditScore() >= 600;
    }

    public List<Customer> getHighValueCustomers() {
        return customerRepository.findHighValueCustomers(700, 5000);
    }
}
