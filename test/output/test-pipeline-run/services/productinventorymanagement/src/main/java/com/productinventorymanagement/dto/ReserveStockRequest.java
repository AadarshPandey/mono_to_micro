package com.productinventorymanagement.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class ReserveStockRequest {

    @NotNull(message = "Quantity to reserve cannot be null")
    @Min(value = 1, message = "Quantity to reserve must be at least 1")
    private Integer quantity;
}
