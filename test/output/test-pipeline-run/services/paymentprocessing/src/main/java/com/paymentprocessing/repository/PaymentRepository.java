package com.paymentprocessing.repository;

import com.paymentprocessing.model.Payment;
import com.paymentprocessing.model.PaymentStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface PaymentRepository extends JpaRepository<Payment, Long> {
    List<Payment> findByCustomerId(Long customerId);
    List<Payment> findByOrderId(Long orderId);
    List<Payment> findByCustomerIdAndOrderId(Long customerId, Long orderId);
    List<Payment> findByOrderIdAndStatus(Long orderId, PaymentStatus status);
    Long countByCustomerIdAndStatus(Long customerId, PaymentStatus status);

    @Query("SELECT COALESCE(SUM(p.amount), 0.0) FROM Payment p WHERE p.status = :status")
    Double sumAmountByStatus(PaymentStatus status);
}
