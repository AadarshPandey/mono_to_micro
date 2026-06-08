package com.paymentprocessing.client;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;
import reactor.util.retry.Retry;

import java.time.Duration;
import java.util.concurrent.TimeoutException;

@Component
public class OrderManagementClient {

    private static final Logger log = LoggerFactory.getLogger(OrderManagementClient.class);
    private final WebClient orderManagementWebClient;

    public OrderManagementClient(@Qualifier("orderManagementWebClient") WebClient orderManagementWebClient) {
        this.orderManagementWebClient = orderManagementWebClient;
    }

    /**
     * Checks if an order exists in the Order Management service.
     * Implements basic retry and timeout logic.
     * Circuit breaker (e.g., Resilience4j) would be integrated here for production.
     *
     * @param orderId The ID of the order to check.
     * @return Mono<Boolean> indicating if the order exists.
     */
    public Mono<Boolean> checkOrderExists(Long orderId) {
        log.info("Calling OrderManagement to check existence for orderId: {}", orderId);
        // Assuming OrderManagement has an endpoint like /api/v1/orders/{orderId}/exists
        return orderManagementWebClient.get()
                .uri("/api/v1/orders/{orderId}/exists", orderId)
                .retrieve()
                .bodyToMono(Boolean.class)
                .timeout(Duration.ofSeconds(5)) // Timeout for the entire operation
                .retryWhen(Retry.backoff(3, Duration.ofSeconds(2))
                        .filter(this::isRetryableException)
                        .doBackoff((retrySignal) -> log.warn("Retrying OrderManagement checkOrderExists for orderId: {} (attempt {}/{})", orderId, retrySignal.totalRetriesInARow() + 1, 3)))
                .onErrorResume(WebClientResponseException.NotFound.class, e -> {
                    log.warn("Order not found in OrderManagement for orderId: {}", orderId);
                    return Mono.just(false);
                })
                .onErrorResume(TimeoutException.class, e -> {
                    log.error("Timeout calling OrderManagement for orderId: {}", orderId, e);
                    return Mono.error(new RuntimeException("