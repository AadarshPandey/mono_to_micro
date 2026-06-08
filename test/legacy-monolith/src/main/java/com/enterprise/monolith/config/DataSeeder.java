package com.enterprise.monolith.config;

import com.enterprise.monolith.model.Customer;
import com.enterprise.monolith.model.Product;
import com.enterprise.monolith.repository.CustomerRepository;
import com.enterprise.monolith.repository.ProductRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Seed data — loads sample customers and products on startup.
 * Makes the app immediately usable for demo.
 */
@Configuration
public class DataSeeder {

    private static final Logger log = LoggerFactory.getLogger(DataSeeder.class);

    @Bean
    CommandLineRunner seedDatabase(CustomerRepository customerRepo, ProductRepository productRepo) {
        return args -> {
            // Seed customers
            if (customerRepo.count() == 0) {
                customerRepo.save(new Customer("Alice Johnson", "alice@enterprise.com", "555-0101"));
                customerRepo.save(new Customer("Bob Smith", "bob@enterprise.com", "555-0102"));
                customerRepo.save(new Customer("Charlie Brown", "charlie@enterprise.com", "555-0103"));
                log.info("Seeded 3 customers");
            }

            // Seed products
            if (productRepo.count() == 0) {
                productRepo.save(new Product("Enterprise Server License", "Software", 2999.99, 50));
                productRepo.save(new Product("Database Cluster Module", "Software", 1499.99, 30));
                productRepo.save(new Product("API Gateway Pro", "Infrastructure", 899.99, 100));
                productRepo.save(new Product("Monitoring Dashboard", "Tools", 499.99, 200));
                productRepo.save(new Product("Load Balancer Unit", "Infrastructure", 1299.99, 15));
                log.info("Seeded 5 products");
            }
        };
    }
}
