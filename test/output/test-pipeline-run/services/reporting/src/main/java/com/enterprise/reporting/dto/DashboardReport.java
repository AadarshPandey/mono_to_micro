package com.enterprise.reporting.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class DashboardReport {
    private Integer totalCustomers;
    private Integer platinumCustomers;
    private Double avgCreditScore;
    private Integer totalOrders;
    private Integer pendingOrders;
    private Integer paidOrders;
    private Integer cancelledOrders;
    private Double totalRevenue;
    private Integer totalPayments;
    private Integer totalProducts;
    private Integer lowStockProducts;
    private Double totalInventoryValue;
}
