package com.enterprise.reporting.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class RevenueByCustomerItem {
    private Long customerId;
    private String customerName;
    private Double totalRevenue;
    private Integer orderCount;
}
