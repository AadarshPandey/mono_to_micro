package com.enterprise.reporting.service.client;

import com.enterprise.reporting.dto.external.CustomerRevenueSummaryResponse;
import com.enterprise.reporting.dto.external.OrderMetricsResponse;
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

@Component
public class OrderServiceClient {

    private final WebClient orderWebClient;

    public OrderServiceClient(@Qualifier("orderWebClient") WebClient orderWebClient) {
        this.orderWebClient = orderWebClient;
    }

    @Retry(name = "orderService", fallbackMethod = "getOrderMetricsFallback")