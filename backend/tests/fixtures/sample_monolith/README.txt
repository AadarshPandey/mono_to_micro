// Sample Monolith Fixture — Synthetic Java monolith for testing
//
// FUTURE DEVELOPMENT:
// - Create a small synthetic Java monolith with:
//     - 4 logical domains: Order, Customer, Inventory, Payment
//     - ~12 classes, ~500 lines total
//     - Deliberate cross-domain coupling to test boundary detection
//     - Example classes:
//         - OrderService.java (depends on CustomerService, InventoryService)
//         - OrderRepository.java
//         - CustomerService.java (depends on PaymentService)
//         - CustomerRepository.java
//         - InventoryService.java
//         - InventoryRepository.java
//         - PaymentService.java (depends on OrderService — circular!)
//         - PaymentRepository.java
//         - OrderDTO.java, CustomerDTO.java, InventoryDTO.java, PaymentDTO.java
// - This fixture is safe to commit — contains no real business logic.
