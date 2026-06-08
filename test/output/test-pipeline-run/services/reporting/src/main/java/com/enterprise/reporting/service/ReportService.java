package com.enterprise.reporting.service;

import com.enterprise.reporting.dto.DashboardReport;
import com.enterprise.reporting.dto.RevenueByCustomerItem;
import com.enterprise.reporting.service.client.CustomerServiceClient;
import com.enterprise.reporting.service.client.InventoryServiceClient;
import com.enterprise.reporting.service.client.OrderServiceClient;
import com.enterprise.reporting.service.client.PaymentServiceClient;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;
import reactor.util.function.Tuple4;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Service
public class ReportService {

    private final CustomerServiceClient customerServiceClient;
    private final OrderServiceClient orderServiceClient;
    private final PaymentServiceClient paymentServiceClient;
    private final InventoryServiceClient inventoryServiceClient;

    public ReportService(CustomerServiceClient customerServiceClient,
                         OrderServiceClient orderServiceClient,
                         PaymentServiceClient paymentServiceClient,
                         InventoryServiceClient inventoryServiceClient) {
        this.customerServiceClient = customerServiceClient;
        this.orderServiceClient = orderServiceClient;
        this.paymentServiceClient = paymentServiceClient;
        this.inventoryServiceClient = inventoryServiceClient;
    }

    public Mono<DashboardReport> getDashboardReport() {
        Mono<com.enterprise.reporting.dto.external.CustomerMetricsResponse> customerMetricsMono = customerServiceClient.getCustomerMetrics();
        Mono<com.enterprise.reporting.dto.external.OrderMetricsResponse> orderMetricsMono = orderServiceClient.getOrderMetrics();
        Mono<com.enterprise.reporting.dto.external.PaymentMetricsResponse> paymentMetricsMono = paymentServiceClient.getPaymentMetrics();
        Mono<com.enterprise.reporting.dto.external.InventoryMetricsResponse> inventoryMetricsMono = inventoryServiceClient.getInventoryMetrics();

        return Mono.zip(customerMetricsMono, orderMetricsMono, paymentMetricsMono, inventoryMetricsMono)
                .map(this::buildDashboardReport);
    }

    private DashboardReport buildDashboardReport(Tuple4<com.enterprise.reporting.dto.external.CustomerMetricsResponse,
            com.enterprise.reporting.dto.external.OrderMetricsResponse,
            com.enterprise.reporting.dto.external.PaymentMetricsResponse,
            com.enterprise.reporting.dto.external.InventoryMetricsResponse> tuple) {

        com.enterprise.reporting.dto.external.CustomerMetricsResponse customerMetrics = tuple.getT1();
        com.enterprise.reporting.dto.external.OrderMetricsResponse orderMetrics = tuple.getT2();
        com.enterprise.reporting.dto.external.PaymentMetricsResponse paymentMetrics = tuple.getT3();
        com.enterprise.reporting.dto.external.InventoryMetricsResponse inventoryMetrics = tuple.getT4();

        return DashboardReport.builder()
                .totalCustomers(customerMetrics.getTotalCustomers())
                .platinumCustomers(customerMetrics.getPlatinumCustomers())
                .avgCreditScore(customerMetrics.getAvgCreditScore())
                .totalOrders(orderMetrics.getTotalOrders())
                .pendingOrders(orderMetrics.getPendingOrders())
                .paidOrders(orderMetrics.getPaidOrders())
                .cancelledOrders(orderMetrics.getCancelledOrders())
                .totalRevenue(paymentMetrics.getTotalRevenue())
                .totalPayments(paymentMetrics.getTotalPayments())
                .totalProducts(inventoryMetrics.getTotalProducts())
                .lowStockProducts(inventoryMetrics.getLowStockProducts())
                .totalInventoryValue(inventoryMetrics.getTotalInventoryValue())
                .build();
    }

    public Mono<List<RevenueByCustomerItem>> getRevenueByCustomer() {
        return orderServiceClient.getRevenueByCustomerSummary()
                .flatMap(customerRevenueSummaries -> {
                    Set<Long> customerIds = customerRevenueSummaries.stream()
                            .map(com.enterprise.reporting.dto.external.CustomerRevenueSummaryResponse::getCustomerId)
                            .collect(Collectors.toSet());

                    if (customerIds.isEmpty()) {
                        return Mono.just(List.of());
                    }

                    return customerServiceClient.getCustomerDetailsByIds(customerIds)
                            .map(customerDetailsList -> {
                                Map<Long, String> customerNames = customerDetailsList.stream()
                                        .collect(Collectors.toMap(
                                                com.enterprise.reporting.dto.external.CustomerDetailsResponse::getCustomerId,
                                                com.enterprise.reporting.dto.external.CustomerDetailsResponse::getCustomerName
                                        ));

                                return customerRevenueSummaries.stream()
                                        .map(summary -> RevenueByCustomerItem.builder()
                                                .customerId(summary.getCustomerId())
                                                .customerName(customerNames.getOrDefault(summary.getCustomerId(), "Unknown"))
                                                .totalRevenue(summary.getTotalRevenue())
                                                .orderCount(summary.getOrderCount())
                                                .build())
                                        .collect(Collectors.toList());
                            });
                });
    }
}
