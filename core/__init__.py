"""
Core bot components for the Voice AI Bot System
"""

# Import only the main bot classes to avoid circular imports
from .sales_bot import SalesBot
from .health_appointment_bot import HealthAppointmentBot

__all__ = [
    'SalesBot',
    'HealthAppointmentBot'
] 