#!/usr/bin/env python3
"""Test script to verify all imports and configurations"""

import sys
from pathlib import Path

# Test imports
try:
    from services_config import ServicesConfig
    print("ServicesConfig imports")
except Exception as e:
    print(f"ServicesConfig import failed: {e}")
    sys.exit(1)

try:
    from core.health_appointment_bot import main, HealthAppointmentBot
    print("HealthAppointmentBot imports")
except Exception as e:
    print(f"HealthAppointmentBot import failed: {e}")
    sys.exit(1)

try:
    from core.sales_bot import main
    print("Sales Bot imports")
except Exception as e:
    print(f"Sales Bot import failed: {e}")
    sys.exit(1)

# Test services configuration
try:
    sales = ServicesConfig.get_services("sales")
    health = ServicesConfig.get_services("health")
    print(f"Sales services: {len(sales)} items") # From services_config.py
    print(f"Health services: {len(health)} items") # From services_config.py
    print(f"\nHealth Services:")
    for service in health:
        print(f"  - {service['name']} ({service['duration']})")
except Exception as e:
    print(f"Services configuration failed: {e}")
    sys.exit(1)

print("\nAll imports and configurations verified!")
