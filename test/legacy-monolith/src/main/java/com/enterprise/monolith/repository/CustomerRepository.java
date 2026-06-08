package com.enterprise.monolith.repository;

import com.enterprise.monolith.model.Customer;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import java.util.List;
import java.util.Optional;

public interface CustomerRepository extends JpaRepository<Customer, Long> {
    Optional<Customer> findByEmail(String email);

    /** Cross-domain query: filters customers by their order/payment history */
    @Query("SELECT c FROM Customer c WHERE c.creditScore >= :minScore AND c.lifetimeSpend >= :minSpend")
    List<Customer> findHighValueCustomers(int minScore, double minSpend);

    List<Customer> findByTier(Customer.CustomerTier tier);
}
