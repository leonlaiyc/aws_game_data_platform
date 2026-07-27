"""Static FX rates to USD, used only by Gold-layer aggregation.

A production platform would convert at transaction time using a live rate
feed; a fixed table is a deliberate simplification for this project (see
ARCHITECTURE.md) since FX accuracy isn't the point being demonstrated.
"""

FX_TO_USD = {
    "USD": 1.0,
    "BRL": 0.18,
    "EUR": 1.08,
}
