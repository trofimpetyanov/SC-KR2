import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, func, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class FileAnalysisResult(Base):
    __tablename__ = "file_analysis_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_file_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    analysis_status = Column(String, nullable=False, default="PENDING")
    
    word_cloud_image_location = Column(String, nullable=True)
    
    other_analysis_data = Column(JSON, nullable=True)
    
    error_message = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<FileAnalysisResult(id={self.id}, file_id={self.original_file_id}, status='{self.analysis_status}')>"