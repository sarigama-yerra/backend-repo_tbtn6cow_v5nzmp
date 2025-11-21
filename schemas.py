"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

# Example schemas (keep for reference)

class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: Optional[str] = Field(None, description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# Application-specific schemas for the property verification workflow
# ------------------------------------------------------------------

class AppUser(BaseModel):
    """Minimal user profile for authentication"""
    name: str
    email: str
    wallet_balance_cents: int = 0

class VerificationTask(BaseModel):
    """Task assigned to users to verify property listings"""
    title: str
    price: float
    location: str
    image_url: str
    property_type: str
    reward_cents: int = Field(30, description="Reward in cents, e.g., 30 = $0.30")
    instructions: str = "Please review this property information and confirm whether the listing is still active."
    status: Literal["pending", "completed", "disabled"] = "pending"
    assigned_to: Optional[str] = None
    last_assigned_at: Optional[datetime] = None

class TaskResult(BaseModel):
    """Stores user submissions for tasks"""
    task_id: str
    user_id: str
    choice: Literal["active", "inactive", "unknown"]
    reward_cents: int
    submitted_at: Optional[datetime] = None

# Note: The Flames database viewer will automatically:
# 1. Read these schemas from GET /schema endpoint
# 2. Use them for document validation when creating/editing
# 3. Handle all database operations (CRUD) directly
# 4. You don't need to create any database endpoints!
