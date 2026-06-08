This plan outlines the migration of the `CustomerManagement` service from a monolith to a microservice using the Strangler Fig pattern.

## Service: CustomerManagement

### 1. Facade Adapter Class

This Java class will act as a facade, implementing the original `CustomerService` interface. It uses a feature flag (`customer.migration.mode`) to dynamically route calls to either the original monolith implementation or the new microservice via HTTP.

**Assumptions:**
*   A `com.enterprise.monolith.model.Customer` class exists with `id`, `name`, `email` fields.
*   The original `com.enterprise.monolith.service.CustomerService` is an interface or a class that can be implemented/extended. For this example, we assume it's an interface.
*   A simple HTTP client (`CustomerServiceClient`) is used to interact with the new microservice.
*   A logging framework (e.g., SLF4J) is available.
*   A configuration mechanism (e.g., Spring's `@Value` or a custom `ConfigProvider`) provides the `MigrationMode`.

```java
package com.enterprise.monolith.service;

import com.enterprise.monolith.model.Customer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate; // Assuming Spring for HTTP client

import java.util.Arrays;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.stream.Collectors;

// Enum for migration modes
enum MigrationMode {
    OLD_SERVICE_ONLY, // All traffic to the monolith
    SHADOW_READ,      // Read from both, compare, return monolith's result. Write to monolith.
    DUAL_WRITE,       // Read from new service. Write to both, return new service's result.
    NEW_SERVICE_ONLY  // All traffic to the new microservice
}

/**
 * Interface representing the original CustomerService in the monolith.
 * This is what existing callers depend on.
 */
interface OriginalCustomerService {
    Optional<Customer> getCustomerById(String id);
    List<Customer> getAllCustomers();
    Customer createCustomer(Customer customer);
    Customer updateCustomer(String id, Customer customer);
    void deleteCustomer(String id);
}

/**
 * Client for the new Customer Microservice.
 * This would typically be generated from an OpenAPI spec or hand-written.
 */
@Service
class CustomerServiceClient {
    private static final Logger log = LoggerFactory.getLogger(CustomerServiceClient.class);
    private final RestTemplate restTemplate;
    private final String microserviceBaseUrl;

    public CustomerServiceClient(@Value("${customer.microservice.url:http://localhost:8081/api/customers}") String microserviceBaseUrl) {
        this.restTemplate = new RestTemplate(); // In a real app, use a configured RestTemplate/WebClient
        this.microserviceBaseUrl = microserviceBaseUrl;
        log.info("Customer Microservice URL: {}", microserviceBaseUrl);
    }

    public Optional<Customer> getCustomerById(String id) {
        try {
            Customer customer = restTemplate.getForObject(microserviceBaseUrl + "/" + id, Customer.class);
            return Optional.ofNullable(customer);
        } catch (HttpClientErrorException.NotFound e) {
            return Optional.empty();
        } catch (Exception e) {
            log.error("Error calling new service for getCustomerById({}): {}", id, e.getMessage());
            throw new RuntimeException("Failed to get customer from new service", e);
        }
    }

    public List<Customer> getAllCustomers() {
        try {
            Customer[] customers = restTemplate.getForObject(microserviceBaseUrl, Customer[].class);
            return Arrays.asList(customers != null ? customers : new Customer[0]);
        } catch (Exception e) {
            log.error("Error calling new service for getAllCustomers: {}", e.getMessage());
            throw new RuntimeException("Failed to get all customers from new service", e);
        }
    }

    public Customer createCustomer(Customer customer) {
        try {
            return restTemplate.postForObject(microserviceBaseUrl, customer, Customer.class);
        } catch (Exception e) {
            log.error("Error calling new service for createCustomer({}): {}", customer.getId(), e.getMessage());
            throw new RuntimeException("Failed to create customer in new service", e);
        }
    }

    public Customer updateCustomer(String id, Customer customer) {
        try {
            restTemplate.put(microserviceBaseUrl + "/" + id, customer);
            return customer; // Assuming PUT returns no content but updates successfully
        } catch (Exception e) {
            log.error("Error calling new service for updateCustomer({}): {}", id, e.getMessage());
            throw new RuntimeException("Failed to update customer in new service", e);
        }
    }

    public void deleteCustomer(String id) {
        try {
            restTemplate.delete(microserviceBaseUrl + "/" + id);
        } catch (Exception e) {
            log.error("Error calling new service for deleteCustomer({}): {}", id, e.getMessage());
            throw new RuntimeException("Failed to delete customer in new service", e);
        }
    }
}


/**
 * The Facade Adapter for CustomerService.
 * This class replaces the original CustomerService implementation in the monolith's dependency injection.
 */
@Service("customerService") // Ensure this replaces the original bean
public class CustomerServiceFacade implements OriginalCustomerService {

    private static final Logger log = LoggerFactory.getLogger(CustomerServiceFacade.class);
    private final OriginalCustomerService monolithCustomerService;
    private final CustomerServiceClient microserviceClient;
    private final ExecutorService shadowExecutor = Executors.newFixedThreadPool(5); // For async shadow calls

    @Value("${customer.migration.mode:OLD_SERVICE_ONLY}")
    private MigrationMode currentMigrationMode;

    // Constructor for dependency injection
    public CustomerServiceFacade(
            @Value("#{originalCustomerServiceImpl}") OriginalCustomerService monolithCustomerService, // Inject original impl
            CustomerServiceClient microserviceClient) {
        this.monolithCustomerService = monolithCustomerService;
        this.microserviceClient = microserviceClient;
        log.info("CustomerServiceFacade initialized. Current mode: {}", currentMigrationMode);
    }

    // --- Read Operations ---

    @Override
    public Optional<Customer> getCustomerById(String id) {
        switch (currentMigrationMode) {
            case OLD_SERVICE_ONLY:
                log.debug("getCustomerById({}) - Mode: OLD_SERVICE_ONLY. Calling monolith.", id);
                return monolithCustomerService.getCustomerById(id);

            case SHADOW_READ:
                log.debug("getCustomerById({}) - Mode: SHADOW_READ. Calling both, returning monolith.", id);
                Optional<Customer> monolithResult = monolithCustomerService.getCustomerById(id);
                CompletableFuture.runAsync(() -> {
                    try {
                        Optional<Customer> microserviceResult = microserviceClient.getCustomerById(id);
                        compareCustomers("getCustomerById", id, monolithResult, microserviceResult);
                    } catch (Exception e) {
                        log.error("Shadow call to new service for getCustomerById({}) failed: {}", id, e.getMessage());
                    }
                }, shadowExecutor);
                return monolithResult;

            case DUAL_WRITE: // After dual-write, new service is source of truth for reads
            case NEW_SERVICE_ONLY:
                log.debug("getCustomerById({}) - Mode: {}. Calling microservice.", id, currentMigrationMode);
                return microserviceClient.getCustomerById(id);

            default:
                log.warn("Unknown migration mode: {}. Defaulting to monolith for getCustomerById({}).", currentMigrationMode, id);
                return monolithCustomerService.getCustomerById(id);
        }
    }

    @Override
    public List<Customer> getAllCustomers() {
        switch (currentMigrationMode) {
            case OLD_SERVICE_ONLY:
                log.debug("getAllCustomers() - Mode: OLD_SERVICE_ONLY. Calling monolith.");
                return monolithCustomerService.getAllCustomers();

            case SHADOW_READ:
                log.debug("getAllCustomers() - Mode: SHADOW_READ. Calling both, returning monolith.");
                List<Customer> monolithResult = monolithCustomerService.getAllCustomers();
                CompletableFuture.runAsync(() -> {
                    try {
                        List<Customer> microserviceResult = microserviceClient.getAllCustomers();
                        compareCustomerLists("getAllCustomers", monolithResult, microserviceResult);
                    } catch (Exception e) {
                        log.error("Shadow call to new service for getAllCustomers() failed: {}", e.getMessage());
                    }
                }, shadowExecutor);
                return monolithResult;

            case DUAL_WRITE:
            case NEW_SERVICE_ONLY:
                log.debug("getAllCustomers() - Mode: {}. Calling microservice.", currentMigrationMode);
                return microserviceClient.getAllCustomers();

            default:
                log.warn("Unknown migration mode: {}. Defaulting to monolith for getAllCustomers().", currentMigrationMode);
                return monolithCustomerService.getAllCustomers();
        }
    }

    // --- Write Operations ---

    @Override
    public Customer createCustomer(Customer customer) {
        switch (currentMigrationMode) {
            case OLD_SERVICE_ONLY:
            case SHADOW_READ: // Writes still go to monolith during shadow read
                log.debug("createCustomer({}) - Mode: {}. Calling monolith.", customer.getId(), currentMigrationMode);
                return monolithCustomerService.createCustomer(customer);

            case DUAL_WRITE:
                log.debug("createCustomer({}) - Mode: DUAL_WRITE. Calling both, returning microservice.", customer.getId());
                Customer newServiceResult = microserviceClient.createCustomer(customer);
                CompletableFuture.runAsync(() -> {
                    try {
                        Customer oldServiceResult = monolithCustomerService.createCustomer(customer);
                        if (!Objects.equals(newServiceResult, oldServiceResult)) {
                            log.warn("DUAL_WRITE discrepancy for createCustomer({}): New service result {} differs from old service {}.",
                                    customer.getId(), newServiceResult, oldServiceResult);
                        }
                    } catch (Exception e) {
                        log.error("DUAL_WRITE to monolith for createCustomer({}) failed: {}", customer.getId(), e.getMessage());
                    }
                }, shadowExecutor);
                return newServiceResult; // New service is source of truth

            case NEW_SERVICE_ONLY:
                log.debug("createCustomer({}) - Mode: NEW_SERVICE_ONLY. Calling microservice.", customer.getId());
                return microserviceClient.createCustomer(customer);

            default:
                log.warn("Unknown migration mode: {}. Defaulting to monolith for createCustomer({}).", currentMigrationMode, customer.getId());
                return monolithCustomerService.createCustomer(customer);
        }
    }

    @Override
    public Customer updateCustomer(String id, Customer customer) {
        switch (currentMigrationMode) {
            case OLD_SERVICE_ONLY:
            case SHADOW_READ:
                log.debug("updateCustomer({}) - Mode: {}. Calling monolith.", id, currentMigrationMode);
                return monolithCustomerService.updateCustomer(id, customer);

            case DUAL_WRITE:
                log.debug("updateCustomer({}) - Mode: DUAL_WRITE. Calling both, returning microservice.", id);
                Customer newServiceResult = microserviceClient.updateCustomer(id, customer);
                CompletableFuture.runAsync(() -> {
                    try {
                        Customer oldServiceResult = monolithCustomerService.updateCustomer(id, customer);
                        if (!Objects.equals(newServiceResult, oldServiceResult)) {
                            log.warn("DUAL_WRITE discrepancy for updateCustomer({}): New service result {} differs from old service {}.",
                                    id, newServiceResult, oldServiceResult);
                        }
                    } catch (Exception e) {
                        log.error("DUAL_WRITE to monolith for updateCustomer({}) failed: {}", id, e.getMessage());
                    }
                }, shadowExecutor);
                return newServiceResult;

            case NEW_SERVICE_ONLY:
                log.debug("updateCustomer({}) - Mode: NEW_SERVICE_ONLY. Calling microservice.", id);
                return microserviceClient.updateCustomer(id, customer);

            default:
                log.warn("Unknown migration mode: {}. Defaulting to monolith for updateCustomer({}).", currentMigrationMode, id);
                return monolithCustomerService.updateCustomer(id, customer);
        }
    }

    @Override
    public void deleteCustomer(String id) {
        switch (currentMigrationMode) {
            case OLD_SERVICE_ONLY:
            case SHADOW_READ:
                log.debug("deleteCustomer({}) - Mode: {}. Calling monolith.", id, currentMigrationMode);
                monolithCustomerService.deleteCustomer(id);
                break;

            case DUAL_WRITE:
                log.debug("deleteCustomer({}) - Mode: DUAL_WRITE. Calling both.", id);
                microserviceClient.deleteCustomer(id); // New service is source of truth
                CompletableFuture.runAsync(() -> {
                    try {
                        monolithCustomerService.deleteCustomer(id);
                    } catch (Exception e) {
                        log.error("DUAL_WRITE to monolith for deleteCustomer({}) failed: {}", id, e.getMessage());
                    }
                }, shadowExecutor);
                break;

            case NEW_SERVICE_ONLY:
                log.debug("deleteCustomer({}) - Mode: NEW_SERVICE_ONLY. Calling microservice.", id);
                microserviceClient.deleteCustomer(id);
                break;

            default:
                log.warn("Unknown migration mode: {}. Defaulting to monolith for deleteCustomer({}).", currentMigrationMode, id);
                monolithCustomerService.deleteCustomer(id);
        }
    }

    // --- Helper for comparison ---
    private void compareCustomers(String operation, String id, Optional<Customer> monolithResult, Optional<Customer> microserviceResult) {
        if (!Objects.equals(monolithResult, microserviceResult)) {
            log.warn("DISCREPANCY DETECTED for {}({}): Monolith: {}, Microservice: {}",
                    operation, id, monolithResult.orElse(null), microserviceResult.orElse(null));
            // Further actions: alert, store discrepancy for analysis, etc.
        } else {
            log.debug("Consistency check passed for {}({}).", operation, id);
        }
    }

    private void compareCustomerLists(String operation, List<Customer> monolithResult, List<Customer> microserviceResult) {
        // Simple comparison, more robust comparison might involve sorting and comparing elements
        if (monolithResult.size() != microserviceResult.size() ||
            !monolithResult.containsAll(microserviceResult) ||
            !microserviceResult.containsAll(monolithResult)) {
            log.warn("DISCREPANCY DETECTED for {}: Monolith size {}, Microservice size {}. Monolith: {}, Microservice: {}",
                    operation, monolithResult.size(), microserviceResult.size(),
                    monolithResult.stream().map(Customer::getId).collect(Collectors.joining(",")),
                    microserviceResult.stream().map(Customer::getId).collect(Collectors.joining(",")));
        } else {
            log.debug("Consistency check passed for {}.", operation);
        }
    }
}
```

**Configuration Example (e.g., `application.properties` for Spring Boot):**

```properties
# Default mode for the CustomerServiceFacade
customer.migration.mode=OLD_SERVICE_ONLY

# URL for the new Customer Microservice
customer.microservice.url=http://localhost:8081/api/customers
```

**Monolith Integration:**
To integrate the facade, ensure that your dependency injection framework (e.g., Spring) is configured to provide `CustomerServiceFacade` whenever `OriginalCustomerService` (or `CustomerService`) is requested. The original implementation of `CustomerService` should be renamed (e.g., `OriginalCustomerServiceImpl`) and explicitly injected into the facade.

### 2. Three-Phase Migration Plan

#### Phase 1 — Read Traffic (Shadow Mode)

**Objective:** Safely route read-only operations to the new service in the background, compare results, and ensure the new service is stable and accurate without impacting production.

**Steps:**

1.  **Deploy New Microservice:**
    *   Deploy the `CustomerManagement` microservice to a production-like environment.
    *   Ensure it has access to a *copy* of the current production customer data (e.g., via a one-time data migration or a read-replica).
    *   Perform thorough integration testing of the microservice in isolation.
2.  **Update Monolith Configuration:**
    *   Set the feature flag in the monolith's configuration to `customer.migration.mode=SHADOW_READ`.
    *   Deploy the `CustomerServiceFacade` within the monolith, replacing the original `CustomerService` implementation.
3.  **Monitor & Compare:**
    *   Monitor monolith logs for `DISCREPANCY DETECTED` warnings from the facade.
    *   Set up alerts for high discrepancy rates or errors from the new service.
    *   Analyze discrepancies:
        *   Are they data inconsistencies? (e.g., data not fully migrated, eventual consistency issues).
        *   Are they logic differences? (e.g., new service calculates a field differently).
        *   Are they performance issues? (e.g., new service is too slow).
    *   Collect metrics on new service performance (latency, error rates).
4.  **Iterate & Stabilize:**
    *   Address any identified issues in the new microservice or data synchronization.
    *   Repeat monitoring and comparison until discrepancies are minimal and acceptable.
    *   Ensure the new service can handle the expected read load.

**Rollback Steps (Phase 1):**

1.  **Revert Monolith Configuration:** Change `customer.migration.mode` back to `OLD_SERVICE_ONLY`.
2.  **Redeploy Monolith:** Deploy the monolith with the reverted configuration. This will immediately route all traffic back to the original `CustomerService` implementation.
3.  **Decommission Microservice (Optional):** If issues are severe, temporarily shut down or remove the new microservice deployment until issues are resolved.

#### Phase 2 — Write Traffic (Dual Write)

**Objective:** Route write operations to *both* the monolith and the new service, making the new service the source of truth for reads and returning its results for writes. This ensures data consistency during the transition.

**Steps:**

1.  **Initial Data Synchronization:**
    *   Perform a final, comprehensive one-time data migration from the monolith's customer database to the new microservice's database. This ensures the new service starts with the most up-to-date data.
    *   Consider a mechanism for continuous, one-way data synchronization from monolith to microservice if the initial sync takes too long or if there's a risk of missing writes during the transition.
2.  **Update Monolith Configuration:**
    *   Set the feature flag in the monolith's configuration to `customer.migration.mode=DUAL_WRITE`.
    *   Deploy the monolith with this updated configuration.
3.  **Monitor & Verify:**
    *   Monitor monolith logs for `DUAL_WRITE discrepancy` warnings. These indicate differences in how the old and new services process write operations.
    *   Monitor the new microservice's database to ensure data is being written correctly and consistently.
    *   Perform end-to-end tests involving both read and write operations to verify data integrity.
    *   Monitor performance of both services, especially the new service, under full write load.
4.  **Address Discrepancies:**
    *   Investigate any dual-write discrepancies. These are critical as the new service is now the source of truth.
    *   Fix any bugs in the new service's write logic or data schema.
    *   If discrepancies are due to data drift, refine the data synchronization strategy.
5.  **Switch Read Traffic to New Service:**
    *   Once dual-writes are stable and data consistency is confirmed, the facade will automatically start routing all *read* operations to the new microservice (as per `DUAL_WRITE` mode logic). Monitor closely for any read-related issues.

**Rollback Steps (Phase 2):**

1.  **Revert Monolith Configuration:** Change `customer.migration.mode` back to `OLD_SERVICE_ONLY`.
2.  **Redeploy Monolith:** Deploy the monolith with the reverted configuration. All traffic (reads and writes) will now go back to the original `CustomerService`.
3.  **Data Reconciliation:** This is the most complex part of a dual-write rollback.
    *   If the new service has diverged significantly, a reverse data synchronization might be needed (new service -> monolith) or a full re-sync from monolith to new service after fixing the underlying issues.
    *   Analyze logs to identify any writes that only went to the new service and manually apply them to the monolith if necessary, or accept potential data loss/inconsistency if the rollback is urgent.
    *   Consider a "point-in-time restore" of the monolith's database if data corruption is severe, but this is a last resort.

#### Phase 3 — Decommission

**Objective:** Remove the original `CustomerManagement` module from the monolith and update all callers to directly use the new microservice, completing the migration.

**Steps:**

1.  **Update Monolith Configuration:**
    *   Set the feature flag in the monolith's configuration to `customer.migration.mode=NEW_SERVICE_ONLY`.
    *   Deploy the monolith. At this point, all traffic is routed exclusively to the new microservice via the facade.
2.  **Remove Original Monolith Code:**
    *   Identify and remove the original `com.enterprise.monolith.service.CustomerService` implementation, its data access layer (e.g., `CustomerRepository`), and any related model classes or database tables.
    *   Remove the `CustomerServiceFacade` itself, as it's no longer needed.
    *   Update all callers within the monolith that previously injected `CustomerService` to now inject and use `CustomerServiceClient` directly. This might involve refactoring `com.enterprise.monolith.controller.CustomerController` and other dependent services.
3.  **Deploy Refactored Monolith:**
    *   Deploy the monolith with the `CustomerManagement` module completely removed and direct calls to the new microservice.
4.  **Monitor:**
    *   Monitor the new microservice for continued stability and performance.
    *   Monitor the refactored monolith to ensure all integrations with the new microservice are working correctly.

**Rollback Steps (Phase 3):**

1.  **Revert Monolith Code:**
    *   Revert the code changes in the monolith to restore the `CustomerServiceFacade` and the original `CustomerManagement` module code.
    *   Change `customer.migration.mode` back to `DUAL_WRITE` or `OLD_SERVICE_ONLY` depending on the state of the new microservice and the severity of the issue.
2.  **Redeploy Monolith:** Deploy the monolith with the restored code and configuration.
3.  **Data Reconciliation (if needed):** If data issues were discovered after decommissioning, a data reconciliation step might be necessary, similar to Phase 2 rollback, to ensure the monolith's data is consistent with the new service before attempting re-migration.