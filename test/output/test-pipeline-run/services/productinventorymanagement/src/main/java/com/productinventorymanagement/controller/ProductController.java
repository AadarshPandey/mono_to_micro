package com.productinventorymanagement.controller;

import com.productinventorymanagement.dto.ProductCreateRequest;
import com.productinventorymanagement.dto.ProductUpdateRequest;
import com.productinventorymanagement.dto.ReleaseStockRequest;
import com.productinventorymanagement.dto.ReserveStockRequest;
import com.productinventorymanagement.model.Product;
import com.productinventorymanagement.service.ProductService;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/products")
public class ProductController {

    private final ProductService productService;

    @Autowired
    public ProductController(ProductService productService) {
        this.productService = productService;
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> getHealth() {
        return ResponseEntity.ok(Map.of("status", "UP"));
    }

    @GetMapping
    public ResponseEntity<List<Product>> getAllProducts() {
        List<Product> products = productService.getAllProducts();
        return ResponseEntity.ok(products);
    }

    @PostMapping
    public ResponseEntity<Product> createProduct(@Valid @RequestBody ProductCreateRequest request) {
        Product newProduct = productService.createProduct(request);
        return new ResponseEntity<>(newProduct, HttpStatus.CREATED);
    }

    @GetMapping("/low-stock")
    public ResponseEntity<List<Product>> getLowStockProducts() {
        List<Product> lowStockProducts = productService.getLowStockProducts();
        return ResponseEntity.ok(lowStockProducts);
    }

    @GetMapping("/{productId}")
    public ResponseEntity<Product> getProductById(@PathVariable Long productId) {
        Product product = productService.getProductById(productId);
        return ResponseEntity.ok(product);
    }

    @PutMapping("/{productId}")
    public ResponseEntity<Product> updateProduct(@PathVariable Long productId, @Valid @RequestBody ProductUpdateRequest request) {
        Product updatedProduct = productService.updateProduct(productId, request);
        return ResponseEntity.ok(updatedProduct);
    }

    @DeleteMapping("/{productId}")
    public ResponseEntity<Void> deleteProduct(@PathVariable Long productId) {
        productService.deleteProduct(productId);
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/{productId}/reserve")
    public ResponseEntity<Map<String, Object>> reserveProductStock(@PathVariable Long productId, @Valid @RequestBody ReserveStockRequest request) {
        Product updatedProduct = productService.reserveStock(productId, request.getQuantity());
        return ResponseEntity.ok(Map.of(
                "message", "Stock reserved successfully.",
                "currentStock", updatedProduct.getStockQuantity()
        ));
    }

    @PostMapping("/{productId}/release")
    public ResponseEntity<Map<String, Object>> releaseProductStock(@PathVariable Long productId, @Valid @RequestBody ReleaseStockRequest request) {
        Product updatedProduct = productService.releaseStock(productId, request.getQuantity());
        return ResponseEntity.ok(Map.of(
                "message", "Stock released successfully.",
                "currentStock", updatedProduct.getStockQuantity()
        ));
    }
}
