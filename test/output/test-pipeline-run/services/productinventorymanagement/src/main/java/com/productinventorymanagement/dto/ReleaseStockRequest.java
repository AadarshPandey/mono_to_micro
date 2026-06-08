package com.productinventorymanagement.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class ReleaseStockRequest {

    @NotNull(message = "Quantity to release cannot be null")
    @Min(value = 1, message = "Quantity to release must be at least 1")
    private Integer quantity;
}
