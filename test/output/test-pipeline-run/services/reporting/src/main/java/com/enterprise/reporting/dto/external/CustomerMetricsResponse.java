package com.enterprise.reporting.dto.external;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class CustomerMetricsResponse {
    private Integer totalCustomers;
    private Integer platinumCustomers;
    private Double avgCreditScore;
}
