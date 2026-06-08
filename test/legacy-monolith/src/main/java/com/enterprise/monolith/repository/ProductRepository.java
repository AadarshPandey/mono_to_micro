package com.enterprise.monolith.repository;

import com.enterprise.monolith.model.Product;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import java.util.List;

public interface ProductRepository extends JpaRepository<Product, Long> {
    List<Product> findByCategory(String category);

    @Query("SELECT p FROM Product p WHERE p.stockQuantity <= p.reorderThreshold")
    List<Product> findLowStockProducts();

    @Query("SELECT p FROM Product p WHERE p.stockQuantity > 0 ORDER BY p.price ASC")
    List<Product> findAvailableProducts();
}
