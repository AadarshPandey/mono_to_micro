package com.enterprise.reporting.controller;

import com.enterprise.reporting.dto.DashboardReport;
import com.enterprise.reporting.dto.RevenueByCustomerItem;
import com.enterprise.reporting.service.ReportService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

import java.util.Collections;
import java.util.Map;

@RestController
@RequestMapping("/api/reports")
public class ReportController {

    private final ReportService reportService;

    public ReportController(ReportService reportService) {
        this.reportService = reportService;
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> healthCheck() {
        return ResponseEntity.ok(Collections.singletonMap("status", "UP"));
    }

    /** Dashboard: aggregates Customer + Order + Payment + Inventory data */
    @GetMapping("/dashboard")
    public Mono<ResponseEntity<DashboardReport>> getDashboard() {
        return reportService.getDashboardReport()
                .map(ResponseEntity::ok);
    }

    /** Revenue breakdown by customer — cross-domain join */
    @GetMapping("/revenue-by-customer")
    public Mono<ResponseEntity<java.util.List<RevenueByCustomerItem>>> getRevenueByCustomer() {
        return reportService.getRevenueByCustomer()
                .map(ResponseEntity::ok);
    }
}
