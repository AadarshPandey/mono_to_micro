package com.enterprise.reporting.dto.external;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class OrderMetricsResponse {
    private Integer totalOrders;
    private Integer pendingOrders;
    private Integer paidOrders;
    private Integer cancelledOrders;
}
