package com.productinventorymanagement.repository;

import com.productinventorymanagement.model.Product;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ProductRepository extends JpaRepository<Product, Long> {

    /**
     * Finds products whose stock quantity is less than or equal to the specified reorder threshold.
     *
     * @param reorderThreshold The threshold to compare against.
     * @return A list of products with low stock.
     */
    List<Product> findByStockQuantityLessThanEqual(Integer reorderThreshold);
}
