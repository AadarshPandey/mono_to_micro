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
public class CustomerManagementClient {

    private static final Logger log = LoggerFactory.getLogger(CustomerManagementClient.class);
    private final WebClient customerManagementWebClient;

    public CustomerManagementClient(@Qualifier("customerManagementWebClient") WebClient customerManagementWebClient) {
        this.customerManagementWebClient = customerManagementWebClient;
    }

    /**
     * Checks if a customer exists in the Customer Management service.
     * Implements basic retry and timeout logic.
     * Circuit breaker (e.g., Resilience4j) would be integrated here for production.
     *
     * @param customerId The ID of the customer to check.
     * @return Mono<Boolean> indicating if the customer exists.
     */
    public Mono<Boolean> checkCustomerExists(Long customerId) {
        log.info("Calling CustomerManagement to check existence for customerId: {}", customerId);
        return customerManagementWebClient.get()
                .uri("/api/v1/customers/{customerId}/exists", customerId)
                .retrieve()
                .bodyToMono(Boolean.class)
                .timeout(Duration.ofSeconds(5)) // Timeout for the entire operation
                .retryWhen(Retry.backoff(3, Duration.ofSeconds(2))
                        .filter(this::isRetryableException)
                        .doBackoff((retrySignal) -> log.warn("Retrying CustomerManagement checkCustomerExists for customerId: {} (attempt {}/{})", customerId, retrySignal.totalRetriesInARow() + 1, 3)))
                .onErrorResume(WebClientResponseException.NotFound.class, e -> {
                    log.warn("Customer not found in CustomerManagement for customerId: {}", customerId);
                    return Mono.just(false);
                })
                .onErrorResume(TimeoutException.class, e -> {
                    log.error("Timeout calling CustomerManagement for customerId: {}", customerId, e);
                    // Consider returning false or throwing a specific service unavailable exception
                    return Mono.error(new RuntimeException("Customer Management service timed out.", e));
                })
                .onErrorResume(WebClientResponseException.class, e -> {
                    log.error("Error calling CustomerManagement for customerId: {}: {}", customerId, e.getMessage(), e);
                    // For other client errors, assume customer doesn't exist or service is unavailable
                    return Mono.error(new RuntimeException("Error from Customer Management service: " + e.getStatusCode(), e));
                })
                .onErrorResume(Exception.class, e -> {
                    log.error("Unexpected error calling CustomerManagement for customerId: {}: {}", customerId, e.getMessage(), e);
                    return Mono.error(new RuntimeException("Unexpected error calling Customer Management service.", e));
                });
    }

    /**
     * Performs a credit check for a customer in the Customer Management service.
     * Implements basic retry and timeout logic.
     * Circuit breaker (e.g., Resilience4j) would be integrated here for production.
     *
     * @param customerId The ID of the customer.
     * @param amount The amount for the credit check.
     * @return Mono<Boolean> indicating if the credit check passed.
     */
    public Mono<Boolean> performCreditCheck(Long customerId, Double amount) {
        log.info("Calling CustomerManagement for credit check for customerId: {} with amount: {}", customerId, amount);
        // Assuming CustomerManagement has an endpoint like /api/v1/customers/{customerId}/credit-check
        // and it returns true/false or throws 402 if credit check fails.
        return customerManagementWebClient.post()
                .uri("/api/v1/customers/{customerId}/credit-check", customerId)
                .bodyValue(new CreditCheckRequest(amount)) // Assuming a DTO for credit check request
                .retrieve()
                .bodyToMono(Boolean.class)
                .timeout(Duration.ofSeconds(5))
                .retryWhen(Retry.backoff(3, Duration.ofSeconds(2))
                        .filter(this::isRetryableException)
                        .doBackoff((retrySignal) -> log.warn("Retrying CustomerManagement credit check for customerId: {} (attempt {}/{})", customerId, retrySignal.totalRetriesInARow() + 1, 3)))
                .onErrorResume(WebClientResponseException.PaymentRequired.class, e -> {
                    log.warn("Credit check failed for customerId: {} (402 Payment Required)", customerId);
                    return Mono.just(false); // Credit check failed
                })
                .onErrorResume(WebClientResponseException.NotFound.class, e -> {
                    log.warn("Customer not found during credit check for customerId: {}", customerId);
                    return Mono.error(new RuntimeException("Customer not found for credit check.", e));
                })
                .onErrorResume(TimeoutException.class, e -> {
                    log.error("Timeout calling CustomerManagement for credit check for customerId: {}", customerId, e);
                    return Mono.error(new RuntimeException("Customer Management service timed out during credit check.", e));
                })
                .onErrorResume(WebClientResponseException.class, e -> {
                    log.error("Error calling CustomerManagement for credit check for customerId: {}: {}", customerId, e.getMessage(), e);
                    return Mono.error(new RuntimeException("Error from Customer Management service during credit check: " + e.getStatusCode(), e));
                })
                .onErrorResume(Exception.class, e -> {
                    log.error("Unexpected error calling CustomerManagement for credit check for customerId: {}: {}", customerId, e.getMessage(), e);
                    return Mono.error(new RuntimeException("Unexpected error calling Customer Management service for credit check.", e));
                });
    }

    private boolean isRetryableException(Throwable throwable) {
        return throwable instanceof TimeoutException ||
               (throwable instanceof WebClientResponseException &&
                ((WebClientResponseException) throwable).getStatusCode().is5xxServerError());
    }

    // DTO for credit check request, assuming CustomerManagement expects this
    private static class CreditCheckRequest {
        public Double amount;

        public CreditCheckRequest(Double amount) {
            this.amount = amount;
        }
    }
}
