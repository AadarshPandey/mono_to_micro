package com.enterprise.reporting.dto.external;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class CustomerRevenueSummaryResponse {
    private Long customerId;
    private Double totalRevenue;
    private Integer orderCount;
}
