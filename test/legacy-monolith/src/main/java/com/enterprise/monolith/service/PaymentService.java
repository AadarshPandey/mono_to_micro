package com.enterprise.monolith.service;

import com.enterprise.monolith.model.Customer;
import com.enterprise.monolith.model.Order;
import com.enterprise.monolith.model.Payment;
import com.enterprise.monolith.model.Payment.PaymentMethod;
import com.enterprise.monolith.model.Payment.PaymentStatus;
import com.enterprise.monolith.repository.PaymentRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

/**
 * Payment Service — payment processing.
 *
 * COUPLING:
 *  - Calls CustomerService.isCreditWorthy() → circular dependency with CustomerService
 *  - Directly reads Order entity → cross-domain DB access
 *  - Called by OrderService.processPayment() → tightly bound lifecycle
 */
@Service
public class PaymentService {

    private static final Logger log = LoggerFactory.getLogger(PaymentService.class);

    private final PaymentRepository paymentRepository;

    // NOTE: CustomerService is injected lazily to avoid Spring circular dependency error.
    // This is a code smell — in microservices, this would be an HTTP call.
    private CustomerService customerService;

    public PaymentService(PaymentRepository paymentRepository) {
        this.paymentRepository = paymentRepository;
    }

    /** Setter injection to break circular dependency — a classic monolith workaround */
    @org.springframework.beans.factory.annotation.Autowired
    public void setCustomerService(CustomerService customerService) {
        this.customerService = customerService;
    }

    /**
     * Process payment for an order.
     * ANTI-PATTERN: Directly accesses Customer entity from Order (cross-domain read),
     * and calls CustomerService for credit check (circular dependency).
     */
    @Transactional
    public Payment processPayment(Order order, PaymentMethod method) {
        Customer customer = order.getCustomer();  // Cross-domain entity access

        // Credit check — calls back into Customer domain (circular dep)
        if (method == PaymentMethod.CREDIT_CARD && !customerService.isCreditWorthy(customer.getId())) {
            log.warn("Credit check failed for customer {} on order {}", customer.getId(), order.getId());
            Payment failed = createPaymentRecord(order, customer, method, PaymentStatus.FAILED);
            return paymentRepository.save(failed);
        }

        // Simulate payment gateway call
        boolean gatewaySuccess = simulatePaymentGateway(order.getTotalAmount(), method);

        Payment payment = createPaymentRecord(order, customer, method,
                gatewaySuccess ? PaymentStatus.COMPLETED : PaymentStatus.FAILED);
        payment.setProcessedAt(LocalDateTime.now());
        payment.setTransactionRef("TXN-" + UUID.randomUUID().toString().substring(0, 8).toUpperCase());

        log.info("Payment {} for order {}: {} ({})",
                payment.getTransactionRef(), order.getId(), payment.getStatus(), method);

        return paymentRepository.save(payment);
    }

    /** Refund all payments for a cancelled order */
    @Transactional
    public void refundOrder(Long orderId) {
        List<Payment> payments = paymentRepository.findByOrderId(orderId);
        for (Payment p : payments) {
            if (p.getStatus() == PaymentStatus.COMPLETED) {
                p.setStatus(PaymentStatus.REFUNDED);
                p.setProcessedAt(LocalDateTime.now());
                paymentRepository.save(p);
                log.info("Refunded payment {} for order {}", p.getTransactionRef(), orderId);
            }
        }
    }

    public long countSuccessfulPayments(Long customerId) {
        return paymentRepository.countSuccessfulPayments(customerId);
    }

    public Double getTotalRevenue() {
        Double revenue = paymentRepository.getTotalRevenue();
        return revenue != null ? revenue : 0.0;
    }

    private Payment createPaymentRecord(Order order, Customer customer, PaymentMethod method, PaymentStatus status) {
        Payment payment = new Payment();
        payment.setOrder(order);
        payment.setCustomer(customer);
        payment.setAmount(order.getTotalAmount());
        payment.setMethod(method);
        payment.setStatus(status);
        return payment;
    }

    /** Simulate external payment gateway — always succeeds for demo */
    private boolean simulatePaymentGateway(double amount, PaymentMethod method) {
        // In real system, this calls Stripe/PayPal API
        return amount < 50000;  // Fail for very large amounts
    }
}
