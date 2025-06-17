# models/mobile_mobile_service_provider.py
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Union

class ServiceProvider(BaseModel):
    """Pydantic model for service provider data structure"""
    name: str = Field(..., description="Name of the service provider")
    service_type: str = Field(..., description="Type of service (electricity/mobile/banking)")
    monthly_price: Optional[float] = Field(None, description="Price in NOK per month")
    data_limit: Optional[Union[float, str]] = Field(None, description="Data allowance in GB or 'unlimited'")
    contract_duration: Optional[int] = Field(None, description="Contract length in months")
    network: Optional[str] = Field(None, description="Telenor, Telia or Ice")
    features: Optional[List[str]] = Field(None, description="e.g., data_rollover, EU_roaming")
    trustpilot_score: Optional[float] = Field(None, description="Trustpilot rating score")
    trustpilot_reviews: Optional[int] = Field(None, description="Number of Trustpilot reviews")
    trustpilot_url: Optional[str] = Field(None, description="URL to Trustpilot reviews page")
    website: Optional[str] = Field(None, description="Official website URL")
    phone: Optional[str] = Field(None, description="Contact phone number")
    description: Optional[str] = Field(None, description="Brief description of the service")
    last_updated: Optional[str] = Field(None, description="Timestamp of last data update")