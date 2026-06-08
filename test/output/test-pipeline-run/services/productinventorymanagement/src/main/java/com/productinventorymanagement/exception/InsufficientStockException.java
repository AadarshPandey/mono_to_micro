package com.productinventorymanagement.exception;

public class InsufficientStockException extends RuntimeException {
    public InsufficientStockException(Long productId, int requested, int available) {
        super(String.format("Insufficient stock for product ID %d. Requested %d, available %d.", productId, requested, available));
    }
}
