package com.enterprise.reporting.service.client;

import com.enterprise.reporting.dto.external.InventoryMetricsResponse;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import io.github.resilience4j.retry.annotation.Retry;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;

@Component
public class InventoryServiceClient {

    private final WebClient inventoryWebClient;

    public InventoryServiceClient(@Qualifier("inventoryWebClient") WebClient inventoryWebClient) {
        this.inventoryWebClient = inventoryWebClient;
    }

    @Retry(name = "inventoryService", fallbackMethod = "getInventoryMetricsFallback")
    @CircuitBreaker(name = "inventoryService", fallbackMethod = "getInventoryMetricsFallback")
    public Mono<InventoryMetricsResponse> getInventoryMetrics() {
        return inventoryWebClient.get()
                .uri("/api/inventory/metrics")
                .retrieve()
                .onStatus(HttpStatus::isError, response -> response.bodyToMono(String.class).flatMap(error -> Mono.error(new WebClientResponseException(response.statusCode().value(), "Inventory Service Error", response.headers().asHttpHeaders(), error.getBytes(), null))))
                .bodyToMono(InventoryMetricsResponse.class)
                .log()
                .onErrorResume(e -> {
                    System.err.println("Error fetching inventory metrics: " + e.getMessage());
                    return Mono.error(new RuntimeException("Failed to fetch inventory metrics", e));
                });
    }

    private Mono<InventoryMetricsResponse> getInventoryMetricsFallback(Throwable t) {
        System.err.println("Fallback for getInventoryMetrics triggered: " + t.getMessage());
        return Mono.just(new InventoryMetricsResponse(0, 0, 0.0));
    }
}
