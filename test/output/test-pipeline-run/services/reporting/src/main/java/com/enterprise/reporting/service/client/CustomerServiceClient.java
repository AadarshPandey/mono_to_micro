package com.enterprise.reporting.service.client;

import com.enterprise.reporting.dto.external.CustomerDetailsResponse;
import com.enterprise.reporting.dto.external.CustomerMetricsResponse;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import io.github.resilience4j.retry.annotation.Retry;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;

import java.util.Collections;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

@Component
public class CustomerServiceClient {

    private final WebClient customerWebClient;

    public CustomerServiceClient(@Qualifier("customerWebClient") WebClient customerWebClient) {
        this.customerWebClient = customerWebClient;
    }

    @Retry(name = "customerService", fallbackMethod = "getCustomerMetricsFallback")
    @CircuitBreaker(name = "customerService", fallbackMethod = "getCustomerMetricsFallback")
    public Mono<CustomerMetricsResponse> getCustomerMetrics() {
        return customerWebClient.get()
                .uri("/api/customers/metrics")
                .retrieve()
                .onStatus(HttpStatus::isError, response -> response.bodyToMono(String.class).flatMap(error -> Mono.error(new WebClientResponseException(response.statusCode().value(), "Customer Service Error", response.headers().asHttpHeaders(), error.getBytes(), null))))
                .bodyToMono(CustomerMetricsResponse.class)
                .log()
                .onErrorResume(e -> {
                    // Log the error and return a fallback or rethrow a custom exception
                    System.err.println("Error fetching customer metrics: " + e.getMessage());
                    return Mono.error(new RuntimeException("Failed to fetch customer metrics", e));
                });
    }

    private Mono<CustomerMetricsResponse> getCustomerMetricsFallback(Throwable t) {
        System.err.println("Fallback for getCustomerMetrics triggered: " + t.getMessage());
        // Return a default/empty metrics object or throw a specific fallback exception
        return Mono.just(new CustomerMetricsResponse(0, 0, 0.0));
    }

    @Retry(name = "customerService", fallbackMethod = "getCustomerDetailsByIdsFallback")
    @CircuitBreaker(name = "customerService", fallbackMethod = "getCustomerDetailsByIdsFallback")
    public Mono<List<CustomerDetailsResponse>> getCustomerDetailsByIds(Set<Long> customerIds) {
        String idsParam = customerIds.stream().map(String::valueOf).collect(Collectors.joining(","));
        return customerWebClient.get()
                .uri(uriBuilder -> uriBuilder.path("/api/customers/details-by-ids")
                        .queryParam("ids", idsParam)
                        .build())
                .retrieve()
                .onStatus(HttpStatus::isError, response -> response.bodyToMono(String.class).flatMap(error -> Mono.error(new WebClientResponseException(response.statusCode().value(), "Customer Service Error", response.headers().asHttpHeaders(), error.getBytes(), null))))
                .bodyToMono(new ParameterizedTypeReference<List<CustomerDetailsResponse>>() {})
                .log()
                .onErrorResume(e -> {
                    System.err.println("Error fetching customer details by IDs: " + e.getMessage());
                    return Mono.error(new RuntimeException("Failed to fetch customer details", e));
                });
    }

    private Mono<List<CustomerDetailsResponse>> getCustomerDetailsByIdsFallback(Set<Long> customerIds, Throwable t) {
        System.err.println("Fallback for getCustomerDetailsByIds triggered for IDs " + customerIds + ": " + t.getMessage());
        return Mono.just(Collections.emptyList());
    }
}
