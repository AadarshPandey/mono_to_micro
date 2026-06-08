package com.productinventorymanagement.service;

import com.productinventorymanagement.dto.ProductCreateRequest;
import com.productinventorymanagement.dto.ProductUpdateRequest;
import com.productinventorymanagement.exception.InsufficientStockException;
import com.productinventorymanagement.exception.ProductNotFoundException;
import com.productinventorymanagement.model.Product;
import com.productinventorymanagement.repository.ProductRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class ProductService {

    private final ProductRepository productRepository;

    @Autowired
    public ProductService(ProductRepository productRepository) {
        this.productRepository = productRepository;
    }

    @Transactional
    public Product createProduct(ProductCreateRequest request) {
        Product product = new Product();
        product.setName(request.getName());
        product.setCategory(request.getCategory());
        product.setPrice(request.getPrice());
        product.setStockQuantity(request.getStock());
        // reorderThreshold is optional in create, default is 0 in model
        return productRepository.save(product);
    }

    public List<Product> getAllProducts() {
        return productRepository.findAll();
    }

    public List<Product> getLowStockProducts() {
        // Find products where current stock is at or below their reorder threshold
        return productRepository.findAll().stream()
                .filter(product -> product.getStockQuantity() <= product.getReorderThreshold())
                .toList();
    }

    public Product getProductById(Long productId) {
        return productRepository.findById(productId)
                .orElseThrow(() -> new ProductNotFoundException(productId));
    }

    @Transactional
    public Product updateProduct(Long productId, ProductUpdateRequest request) {
        Product existingProduct = productRepository.findById(productId)
                .orElseThrow(() -> new ProductNotFoundException(productId));

        if (request.getName() != null) {
            existingProduct.setName(request.getName());
        }
        if (request.getCategory() != null) {
            existingProduct.setCategory(request.getCategory());
        }
        if (request.getPrice() != null) {
            existingProduct.setPrice(request.getPrice());
        }
        if (request.getReorderThreshold() != null) {
            existingProduct.setReorderThreshold(request.getReorderThreshold());
        }
        // Stock quantity is NOT updated via this method, as per OpenAPI contract
        return productRepository.save(existingProduct);
    }

    @Transactional
    public void deleteProduct(Long productId) {
        if (!productRepository.existsById(productId)) {
            throw new ProductNotFoundException(productId);
        }
        productRepository.deleteById(productId);
    }

    @Transactional
    public Product reserveStock(Long productId, int quantity) {
        Product product = productRepository.findById(productId)
                .orElseThrow(() -> new ProductNotFoundException(productId));

        if (product.getStockQuantity() < quantity) {
            throw new InsufficientStockException(productId, quantity, product.getStockQuantity());
        }

        product.setStockQuantity(product.getStockQuantity() - quantity);
        return productRepository.save(product);
    }

    @Transactional
    public Product releaseStock(Long productId, int quantity) {
        Product product = productRepository.findById(productId)
                .orElseThrow(() -> new ProductNotFoundException(productId));

        // Assuming stock can be released even if it goes above initial, or there's no upper bound.
        // If there was an upper bound, additional logic would be needed.
        product.setStockQuantity(product.getStockQuantity() + quantity);
        return productRepository.save(product);
    }
}
