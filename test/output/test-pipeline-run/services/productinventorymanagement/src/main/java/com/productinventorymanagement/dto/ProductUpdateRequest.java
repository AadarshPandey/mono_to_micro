package com.productinventorymanagement.dto;

import jakarta.validation.constraints.Min;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class ProductUpdateRequest {

    private String name;

    private String category;

    @Min(value = 0, message = "Product price must be non-negative")
    private Double price;

    @Min(value = 0, message = "Reorder threshold must be non-negative")
    private Integer reorderThreshold;
}
