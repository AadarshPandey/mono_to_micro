package com.enterprise.monolith.repository;

import com.enterprise.monolith.model.Payment;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import java.util.List;

public interface PaymentRepository extends JpaRepository<Payment, Long> {
    List<Payment> findByOrderId(Long orderId);
    List<Payment> findByCustomerId(Long customerId);

    @Query("SELECT COUNT(p) FROM Payment p WHERE p.customer.id = :customerId AND p.status = 'COMPLETED'")
    long countSuccessfulPayments(Long customerId);

    @Query("SELECT SUM(p.amount) FROM Payment p WHERE p.status = 'COMPLETED'")
    Double getTotalRevenue();
}
