package com.enterprise.monolith.controller;

import com.enterprise.monolith.service.ReportService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * Report Controller — cross-domain analytics.
 * Delegates to ReportService which queries ALL domain tables.
 */
@RestController
@RequestMapping("/api/reports")
public class ReportController {

    private final ReportService reportService;

    public ReportController(ReportService reportService) {
        this.reportService = reportService;
    }

    /** Dashboard: aggregates Customer + Order + Payment + Inventory data */
    @GetMapping("/dashboard")
    public ResponseEntity<Map<String, Object>> getDashboard() {
        return ResponseEntity.ok(reportService.getDashboardReport());
    }

    /** Revenue breakdown by customer — cross-domain join */
    @GetMapping("/revenue-by-customer")
    public ResponseEntity<List<Map<String, Object>>> getRevenueByCustomer() {
        return ResponseEntity.ok(reportService.getRevenueByCustomer());
    }
}
