#!/usr/bin/env python3
"""
Services and Products Configuration
Routes services based on active bot type
"""

from typing import List, Dict, Any

class ServicesConfig:
    """Configuration for services/products per bot type"""
    
    # Sales Bot Services [from original repo]
    SALES_SERVICES = [
        {
            "name": "AI Voice Assistant Pro",
            "price": "$99/month",
            "description": "Advanced AI-powered voice assistant for customer support"
        },
        {
            "name": "Custom Bot Development",
            "price": "$299/month", 
            "description": "Tailored voice bot solutions for your specific business needs"
        },
        {
            "name": "Enterprise Voice Platform",
            "price": "$599/month",
            "description": "Full-scale voice AI platform with analytics and integrations"
        }
    ]
    
    # Health Appointment Bot Services
    HEALTH_SERVICES = [
        {
            "name": "General Consultation",
            "duration": "30 minutes",
            "description": "Routine checkup and consultation with healthcare provider"
        },
        {
            "name": "Specialized Consultation",
            "duration": "30 minutes",
            "description": "In-depth consultation with specialist"
        },
        {
            "name": "Follow-up Appointment",
            "duration": "20 minutes",
            "description": "Follow-up visit for ongoing treatment"
        }
    ]
    
    @classmethod
    def get_services(cls, bot_type: str) -> List[Dict[str, Any]]:
        """Get services based on bot type"""
        if bot_type == "sales":
            return cls.SALES_SERVICES
        elif bot_type == "health":
            return cls.HEALTH_SERVICES
        else:
            return []

    @classmethod
    def get_service_by_name(cls, bot_type: str, service_name: str) -> Dict[str, Any]:
        """Get specific service by name"""
        services = cls.get_services(bot_type)
        for service in services:
            if service.get("name").lower() == service_name.lower():
                return service
        return None
