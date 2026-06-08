package com.enterprise.monolith.model;

import javax.persistence.*;
import javax.validation.constraints.Email;
import javax.validation.constraints.NotBlank;

/**
 * Customer entity — shared across Order, Payment, and Report domains.
 * Anti-pattern: every service directly queries this table.
 */
@Entity
@Table(name = "customers")
public class Customer {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank
    private String name;

    @Email
    @NotBlank
    @Column(unique = true)
    private String email;

    private String phone;

    /** Credit score calculated from payment history — tight coupling to Payment domain */
    private int creditScore = 500;

    /** Lifetime spend — updated by OrderService (cross-domain write) */
    private double lifetimeSpend = 0.0;

    @Enumerated(EnumType.STRING)
    private CustomerTier tier = CustomerTier.BRONZE;

    public enum CustomerTier { BRONZE, SILVER, GOLD, PLATINUM }

    public Customer() {}

    public Customer(String name, String email, String phone) {
        this.name = name;
        this.email = email;
        this.phone = phone;
    }

    // Getters & Setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }
    public String getPhone() { return phone; }
    public void setPhone(String phone) { this.phone = phone; }
    public int getCreditScore() { return creditScore; }
    public void setCreditScore(int creditScore) { this.creditScore = creditScore; }
    public double getLifetimeSpend() { return lifetimeSpend; }
    public void setLifetimeSpend(double lifetimeSpend) { this.lifetimeSpend = lifetimeSpend; }
    public CustomerTier getTier() { return tier; }
    public void setTier(CustomerTier tier) { this.tier = tier; }
}
