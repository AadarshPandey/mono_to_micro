package com.enterprise.reporting.config;

import io.netty.channel.ChannelOption;
import io.netty.handler.timeout.ReadTimeoutHandler;
import io.netty.handler.timeout.WriteTimeoutHandler;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.netty.http.client.HttpClient;

import java.time.Duration;
import java.util.concurrent.TimeUnit;

@Configuration
public class WebClientConfig {

    @Value("${service.customer.url:http://localhost:8081}")
    private String customerServiceBaseUrl;

    @Value("${service.order.url:http://localhost:8082}")
    private String orderServiceBaseUrl;

    @Value("${service.payment.url:http://localhost:8083}")
    private String paymentServiceBaseUrl;

    @Value("${service.inventory.url:http://localhost:8084}")
    private String inventoryServiceBaseUrl;

    @Bean
    public WebClient customerWebClient(WebClient.Builder webClientBuilder) {
        return buildWebClient(webClientBuilder, customerServiceBaseUrl);
    }

    @Bean
    public WebClient orderWebClient(WebClient.Builder webClientBuilder) {
        return buildWebClient(webClientBuilder, orderServiceBaseUrl);
    }

    @Bean
    public WebClient paymentWebClient(WebClient.Builder webClientBuilder) {
        return buildWebClient(webClientBuilder, paymentServiceBaseUrl);
    }

    @Bean
    public WebClient inventoryWebClient(WebClient.Builder webClientBuilder) {
        return buildWebClient(webClientBuilder, inventoryServiceBaseUrl);
    }

    private WebClient buildWebClient(WebClient.Builder webClientBuilder, String baseUrl) {
        HttpClient httpClient = HttpClient.create()
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 5000) // Connection Timeout
                .responseTimeout(Duration.ofMillis(5000)) // Response Timeout
                .doOnConnected(conn ->
                        conn.addHandlerLast(new ReadTimeoutHandler(5000, TimeUnit.MILLISECONDS))
                                .addHandlerLast(new WriteTimeoutHandler(5000, TimeUnit.MILLISECONDS)));

        return webClientBuilder
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                .baseUrl(baseUrl)
                .build();
    }
}
