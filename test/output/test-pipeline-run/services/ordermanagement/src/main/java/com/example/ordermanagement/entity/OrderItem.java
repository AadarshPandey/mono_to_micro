package com.example.ordermanagement.entity;

import jakarta.persistence.*;

/**
 * Represents an item within an order in the Order Management microservice.
 * This entity stores a snapshot of product information (ID and price) at the time of order creation,
 * rather than maintaining a direct JPA relationship to an external Product entity.
 * Product details for API responses will be fetched from the Product Inventory Service by the service layer.
 */
@Entity
@Table(name = "order_items")
public class OrderItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // Relationship to the Order entity within the same microservice.
    // An OrderItem must belong to an Order.
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "order_id", nullable = false)
    private Order order;

    // Replaced direct Product entity reference with productId.
    // The actual Product details (like name, description) will be fetched from the Product Inventory Service
    // when constructing DTOs for API responses.
    @Column(name = "product_id", nullable = false)
    private Long productId;

    @Column(nullable = false)
    private int quantity;

    /**
     * Snapshot price of the product at the time the order was placed.
     * Renamed from 'unitPrice' to 'priceAtOrder' to align with the OpenAPI contract schema.
     */
    @Column(name = "price_at_order", nullable = false)
    private double priceAtOrder;

    public OrderItem() {
        // Default constructor for JPA
    }

    /**
     * Constructor for creating an OrderItem entity.
     * The 'priceAtOrder' should be determined by the OrderService by calling the Product Inventory Service
     * before creating this entity, ensuring a price snapshot.
     *
     * @param productId The ID of the product from the Product Inventory Service.
     * @param quantity The quantity of the product ordered.
     * @param priceAtOrder The price of the product at the time the order was placed.
     */
    public OrderItem(Long productId, int quantity, double priceAtOrder) {
        this.productId = productId;
        this.quantity = quantity;
        this.priceAtOrder = priceAtOrder;
    }

    /**
     * Calculates the subtotal for this order item based on the snapshot price and quantity.
     * @return The subtotal amount for this order item.
     */
    public double getSubtotal() {
        return priceAtOrder * quantity;
    }

    // Getters and Setters
    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Order getOrder() {
        return order;
    }

    public void setOrder(Order order) {
        this.order = order;
    }

    public Long getProductId() {
        return productId;
    }

    public void setProductId(Long productId) {
        this.productId = productId;
    }

    public int getQuantity() {
        return quantity;
    }

    public void setQuantity(int quantity) {
        this.quantity = quantity;
    }

    public double getPriceAtOrder() {
        return priceAtOrder;
    }

    public void setPriceAtOrder(double priceAtOrder) {
        this.priceAtOrder = priceAtOrder;
    }
}
