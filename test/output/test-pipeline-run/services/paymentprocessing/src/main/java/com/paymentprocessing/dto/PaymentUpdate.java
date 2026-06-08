package com.paymentprocessing.dto;

import com.paymentprocessing.model.PaymentStatus;
import jakarta.validation.constraints.AssertTrue;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class PaymentUpdate {
    private PaymentStatus status;
    private String transactionRef;

    @AssertTrue(message = "At least one field (status or transactionRef) must be provided for update")
    private boolean isAtLeastOneFieldPresent() {
        return status != null || transactionRef != null;
    }
}
