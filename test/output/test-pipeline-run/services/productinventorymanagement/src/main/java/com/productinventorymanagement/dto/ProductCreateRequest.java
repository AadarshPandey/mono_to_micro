package com.productinventorymanagement.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class ProductCreateRequest {

    @NotBlank(message = "Product name cannot be empty")
    private String name;

    private String category;

    @NotNull(message = "Product price cannot be null")
    @Min(value = 0, message = "Product price must be non-negative")
    private Double price;

    @NotNull(message = "Initial stock cannot be null")
    @Min(value = 0, message = "Initial stock must be non-negative")
    private Integer stock;
}
