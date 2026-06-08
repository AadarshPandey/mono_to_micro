This migration plan outlines the process of extracting the "Reporting" service from a monolith using the Strangler Fig pattern.

## Service: Reporting

## 1. Facade Adapter Class (Java Example)

This `ReportServiceFacade` class will replace the original `com.enterprise.monolith.service.ReportService` implementation. It maintains the same interface, allowing existing callers (e.g., `ReportController`) to continue using it without modification. It uses a feature flag to toggle between the original monolith implementation and the new microservice.

**Assumed Original Interface (or base class):**

```java
package com.enterprise.monolith.service;

import com.enterprise.monolith.model.DashboardReport;
import com.enterprise.monolith.model.RevenueReport;
import com.enterprise.monolith.model.ReportConfiguration; // Hypothetical write model

// Define simple POJOs for reports and configuration
// (These would exist in com.enterprise.monolith.model package)
// public class DashboardReport { /* ... */ }
// public class RevenueReport { /* ... */ }
// public class ReportConfiguration { /* ... */ }

public interface ReportService {
    DashboardReport getDashboardReport();
    RevenueReport getRevenueByCustomerReport();
    // Hypothetical write operation for Phase 2
    ReportConfiguration saveReportConfiguration(ReportConfiguration config);
    ReportConfiguration getReportConfiguration(String configId);
}
```

**Facade Adapter Implementation:**

```java
package com.enterprise.monolith.service;

import com.enterprise.monolith.model.DashboardReport;
import com.enterprise.monolith.model.RevenueReport;
import com.enterprise.monolith.model.ReportConfiguration;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Primary;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.ResponseEntity;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;

import java.util.Objects;

@Service("reportService") // Ensures this bean replaces the original ReportService
@Primary // Makes this the primary implementation for the ReportService interface
public class ReportServiceFacade implements ReportService {

    @Value("${feature.flag.reporting.new-service.enabled:false}")
    private boolean newServiceEnabled;

    @Value("${reporting.new-service.base-url:http://localhost:8081/api/v1/reporting}")
    private String newServiceBaseUrl;

    private final ReportService originalReportService; // Injects the original monolith implementation
    private final RestTemplate restTemplate; // For HTTP calls to the new microservice

    // Constructor injection:
    // The original ReportServiceImpl should be renamed or qualified, e.g., @Service("originalReportService")
    public ReportServiceFacade(@Qualifier("originalReportService") ReportService originalReportService, RestTemplate restTemplate) {
        this.originalReportService = originalReportService;
        this.restTemplate = restTemplate;
    }

    @Override
    public DashboardReport getDashboardReport() {
        if (newServiceEnabled) {
            System.out.println("Routing GET /dashboard to new microservice...");
            String url = newServiceBaseUrl + "/dashboard";
            try {
                return restTemplate.getForObject(url, DashboardReport.class);
            } catch (Exception e) {
                System.err.println("Error calling new reporting service for dashboard: " + e.getMessage() + ". Falling back to monolith.");
                // Fallback to monolith in case of new service failure during read phase
                return originalReportService.getDashboardReport();
            }
        } else {
            System.out.println("Routing GET /dashboard to original monolith...");
            return originalReportService.getDashboardReport();
        }
    }

    @Override
    public RevenueReport getRevenueByCustomerReport() {
        if (newServiceEnabled) {
            System.out.println("Routing GET /revenue-by-customer to new microservice...");
            String url = newServiceBaseUrl + "/revenue-by-customer";
            try {
                return restTemplate.getForObject(url, RevenueReport.class);
            } catch (Exception e) {
                System.err.println("Error calling new reporting service for revenue by customer: " + e.getMessage() + ". Falling back to monolith.");
                // Fallback to monolith in case of new service failure during read phase
                return originalReportService.getRevenueByCustomerReport();
            }
        } else {
            System.out.println("Routing GET /revenue-by-customer to original monolith...");
            return originalReportService.getRevenueByCustomerReport();
        }
    }

    // Hypothetical write operation for ReportConfiguration
    @Override
    public ReportConfiguration saveReportConfiguration(ReportConfiguration config) {
        if (newServiceEnabled) {
            System.out.println("Routing POST /report-configurations to new microservice (and monolith for dual write)...");
            String url = newServiceBaseUrl + "/report-configurations";
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<ReportConfiguration> request = new HttpEntity<>(config, headers);

            ReportConfiguration newServiceResult = null;
            try {
                // 1. Call new microservice (primary source of truth during dual write)
                ResponseEntity<ReportConfiguration> response = restTemplate.exchange(url, HttpMethod.POST, request, ReportConfiguration.class);
                newServiceResult = response.getBody();
            } catch (Exception e) {
                System.err.println("CRITICAL: Failed to write to new reporting service for report configuration: " + e.getMessage());
                // Depending on strategy, might throw or attempt to recover. For dual-write, we log and proceed.
            }

            // 2. Call original monolith (for dual write)
            try {
                originalReportService.saveReportConfiguration(config);
            } catch (Exception e) {
                System.err.println("WARNING: Failed to dual-write to monolith for report configuration: " + e.getMessage());
                // Log error, but don't fail the primary operation if newServiceResult is valid
            }
            return Objects.requireNonNullElseGet(newServiceResult, () -> originalReportService.saveReportConfiguration(config)); // Fallback if new service failed
        } else {
            System.out.println("Routing POST /report-configurations to original monolith...");
            return originalReportService.saveReportConfiguration(config);
        }
    }

    // Hypothetical read operation for ReportConfiguration
    @Override
    public ReportConfiguration getReportConfiguration(String configId) {
        if (newServiceEnabled) {
            System.out.println("Routing GET /report-configurations/{id} to new microservice...");
            String url = newServiceBaseUrl + "/report-configurations/" + configId;
            try {
                return restTemplate.getForObject(url, ReportConfiguration.class);
            } catch (Exception e) {
                System.err.println("Error calling new reporting service for report configuration: " + e.getMessage() + ". Falling back to monolith.");
                return originalReportService.getReportConfiguration(configId);
            }
        } else {
            System.out.println("Routing GET /report-configurations/{id} to original monolith...");
            return originalReportService.getReportConfiguration(configId);
        }
    }
}
```

**Example POJOs (com.enterprise.monolith.model):**

```java
package com.enterprise.monolith.model;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

// Simplified for brevity, include getters/setters/constructors in real code
public class DashboardReport {
    private String period;
    private BigDecimal totalRevenue;
    private long totalCustomers;
    private Map<String, BigDecimal> revenueByProductCategory;
    // ...
}

public class RevenueReport {
    private String customerId;
    private String customerName;
    private BigDecimal totalRevenue;
    private int orderCount;
    // ...
}

public class ReportConfiguration {
    private String id;
    private String name;
    private String type; // e.g., "dashboard", "customer_revenue"
    private Map<String, String> parameters;
    // ...
}
```

## 2. Three-Phase Migration Plan

### Phase 1 — Read Traffic (Canary Release / Shadow Mode)

**Goal:** Safely route read-only operations to the new `Reporting` microservice, verify correctness, and monitor performance without impacting production users.

**Steps:**

1.  **Deploy New Service:** Deploy the new `Reporting` microservice to production, exposing its API endpoints (`/dashboard`, `/revenue-by-customer`, `/report-configurations/{id}`). Ensure it can connect to its new data sources (which might be replicated or new).
2.  **Deploy Facade:** Deploy the `ReportServiceFacade` to the monolith.
3.  **Initial Configuration:** In production, set `feature.flag.reporting.new-service.enabled=false` and configure `reporting.new-service.base-url` to point to the new microservice. This ensures all traffic still goes to the monolith initially.
4.  **Staging Verification:** Thoroughly test the `ReportServiceFacade` with `feature.flag.reporting.new-service.enabled=true` in staging environments.
5.  **Enable for Subset (Canary Release):**
    *   In production, enable `feature.flag.reporting.new-service.enabled=true` for a small, controlled percentage of traffic (e.g., 1-5%) or specific internal users/IP ranges (if your feature flag system supports it).
    *   The facade's fallback logic (if new service fails, use monolith) provides an additional safety net.
6.  **Monitor & Compare:**
    *   **Automated Monitoring:** Set up dashboards and alerts for the new service's performance (latency, error rates, resource utilization) and the monolith's.
    *   **Response Comparison (Shadow Mode for Reads):** Implement a mechanism (e.g., in a separate logging aspect or within the facade, though it adds complexity) to make *both* calls for a subset of requests, return the monolith's response, and log any discrepancies between the monolith's and the new service's responses for analysis. This is crucial for data correctness.
    *   **Business Metrics:** Monitor key business metrics derived from reports to ensure consistency.
7.  **Gradual Rollout:** If no discrepancies, performance degradation, or errors are detected, gradually increase the percentage of traffic routed to the new service (e.g., 10%, 25%, 50%, 75%, 100%).
8.  **Full Read Traffic:** Once confident, enable `feature.flag.reporting.new-service.enabled=true` for 100% of read traffic.

**Rollback Procedures for Phase 1:**

1.  **Immediate Action:** Immediately set `feature.flag.reporting.new-service.enabled=false` in the monolith's configuration. This will instantly revert all read traffic to the original monolith implementation.
2.  **Investigation:** Analyze logs and monitoring data to identify the root cause of the issue (e.g., data inconsistency, performance bottleneck in the new service, network issues).
3.  **New Service Remediation:** If the new service is the source of the problem, scale it down, temporarily shut it off, or deploy a fix.
4.  **Monolith Health Check:** Verify the monolith's health and performance after rollback.

### Phase 2 — Write Traffic (Dual Write)

**Goal:** Route write operations (e.g., `saveReportConfiguration`) to both the monolith and the new service, establishing the new service as the primary source of truth for these operations.

**Assumptions:** For the "Reporting" service, direct "write" operations are less common (it's primarily read-only, aggregating data). This phase assumes the existence of operations like `saveReportConfiguration` or `updateDashboardLayout`. If the service is purely read-only, this phase would be skipped, or it would apply to the migration of the *data sources* that the reporting service consumes.

**Steps:**

1.  **Data Synchronization (Pre-requisite):**
    *   Before enabling dual-write, ensure any existing `ReportConfiguration` data from the monolith is migrated to the new service's data store. This could involve a one-time data dump and import, or a continuous data replication setup.
2.  **Implement Dual Write in Facade:** The `ReportServiceFacade` is already set up for dual-write for `saveReportConfiguration`. When `newServiceEnabled` is true, it calls the new service first, then the monolith.
3.  **Enable Dual Write:** In production, ensure `feature.flag.reporting.new-service.enabled=true`. This will activate the dual-write logic for `saveReportConfiguration` and route read operations for `ReportConfiguration` to the new service.
4.  **Monitor & Verify:**
    *   **Consistency Checks:** Implement automated jobs to regularly compare `ReportConfiguration` data between the new service's data store and the monolith's data store. Alert on any discrepancies.
    *   **Error Monitoring:** Closely monitor logs for any errors during dual-write operations (e.g., new service write fails, monolith write fails).
    *   **Performance:** Monitor the performance impact of dual-writing on both services.
5.  **Establish New Service as Source of Truth:** Once data