"""
Database Models for Extraction History

SQLite-compatible models for storing extraction history.
Works with PostgreSQL/MySQL when external database URL is configured.
"""

from sqlalchemy import Column, String, Integer, Text, DateTime, Boolean
from sqlalchemy.sql import func
import json

from backend.app.db.database import Base


class Batch(Base):
    """Represents a batch of images processed together."""
    __tablename__ = "batches"

    id = Column(String(36), primary_key=True)  # UUID
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    status = Column(String(20), default="processing")  # processing, completed, error
    custom_filename = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)


class Document(Base):
    """Represents a single extracted document/image."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String(36), index=True)  # Reference to batch
    filename = Column(String(255))
    extracted_data_json = Column(Text)  # JSON stored as text for SQLite compatibility
    status = Column(String(20), default="success")  # success, error
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    @property
    def extracted_data(self) -> dict:
        """Get extracted data as dict."""
        if self.extracted_data_json:
            try:
                return json.loads(self.extracted_data_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    @extracted_data.setter
    def extracted_data(self, value: dict):
        """Set extracted data from dict."""
        self.extracted_data_json = json.dumps(value) if value else None


class ExtractionHistory(Base):
    """Summary record for quick history lookup."""
    __tablename__ = "extraction_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String(36), unique=True, index=True)
    total_images = Column(Integer, default=0)
    successful_extractions = Column(Integer, default=0)
    failed_extractions = Column(Integer, default=0)
    output_filename = Column(String(255), nullable=True)
    excel_path = Column(Text, nullable=True)
    csv_path = Column(Text, nullable=True)
    schema_fields = Column(Text, nullable=True)  # JSON list of field names
    created_at = Column(DateTime, server_default=func.now())
    
    @property
    def schema(self) -> list:
        """Get schema fields as list."""
        if self.schema_fields:
            try:
                return json.loads(self.schema_fields)
            except json.JSONDecodeError:
                return []
        return []
    
    @schema.setter
    def schema(self, value: list):
        """Set schema fields from list."""
        self.schema_fields = json.dumps(value) if value else None


class UsageHistory(Base):
    """Tracks API token usage for each extraction job."""
    __tablename__ = "usage_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String(36), index=True)
    job_id = Column(String(36), index=True, nullable=True)
    
    # Token counts
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # Additional info
    model = Column(String(100), nullable=True)  # e.g., "gpt-4o", "claude-3-haiku"
    provider = Column(String(50), nullable=True)  # openai, anthropic, google
    images_processed = Column(Integer, default=1)
    
    # Cost estimation (in USD cents to avoid float precision issues)
    estimated_cost_cents = Column(Integer, default=0)
    
    # Timestamp
    created_at = Column(DateTime, server_default=func.now())
    
    @classmethod
    def estimate_cost(cls, total_tokens: int, model: str) -> int:
        """Estimate cost in cents based on model and tokens."""
        # Approximate pricing per 1M tokens (input + output averaged)
        pricing = {
            "gpt-4o": 5.0,  # ~$5 per 1M tokens (blended)
            "gpt-4o-mini": 0.3,  # ~$0.30 per 1M tokens
            "gpt-3.5-turbo": 0.5,  # ~$0.50 per 1M tokens
            "claude-3-haiku-20240307": 0.25,  # ~$0.25 per 1M tokens
            "claude-3-sonnet-20240229": 3.0,
            "claude-3-opus-20240229": 15.0,
            "gemini-1.5-flash": 0.075,  # Very cheap
            "gemini-1.5-pro": 1.25,
        }
        
        rate = pricing.get(model, 2.5)  # Default ~$2.50 per 1M tokens
        cost_dollars = (total_tokens / 1_000_000) * rate
        return int(cost_dollars * 100)  # Return cents
