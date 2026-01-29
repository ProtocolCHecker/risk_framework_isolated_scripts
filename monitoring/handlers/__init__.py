"""
AWS Lambda Handlers for Risk Monitoring System.

Frequency-based handlers:
- critical_handler: 5 min (PoR, oracle freshness, peg deviation)
- high_handler: 30 min (TVL, utilization, slippage)
- medium_handler: 6 hr (HHI, Gini, CLR, RLR)
- daily_handler: 24 hr (Volatility, VaR)
- notification_handler: Process and send pending alerts
"""

from .critical_handler import handler as critical_handler
from .high_handler import handler as high_handler
from .medium_handler import handler as medium_handler
from .daily_handler import handler as daily_handler
from .notification_handler import handler as notification_handler

__all__ = [
    "critical_handler",
    "high_handler",
    "medium_handler",
    "daily_handler",
    "notification_handler",
]
