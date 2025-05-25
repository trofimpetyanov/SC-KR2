import uuid
from typing import Optional, Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

import models, schemas

async def create_analysis_request(db: AsyncSession, analysis_request: schemas.FileAnalysisRequest) -> models.FileAnalysisResult:
    db_analysis = models.FileAnalysisResult(
        original_file_id=analysis_request.file_id,
        analysis_status="PENDING"
    )
    db.add(db_analysis)
    await db.commit()
    await db.refresh(db_analysis)
    return db_analysis

async def get_analysis_result(db: AsyncSession, analysis_id: uuid.UUID) -> Optional[models.FileAnalysisResult]:
    result = await db.execute(select(models.FileAnalysisResult).filter(models.FileAnalysisResult.id == analysis_id))
    return result.scalars().first()

async def get_analysis_results_by_original_id(db: AsyncSession, original_file_id: uuid.UUID) -> List[models.FileAnalysisResult]:
    result = await db.execute(select(models.FileAnalysisResult).filter(models.FileAnalysisResult.original_file_id == original_file_id))
    return result.scalars().all()

async def update_analysis_status_and_data(
    db: AsyncSession, 
    db_obj: Optional[models.FileAnalysisResult],
    obj_in: schemas.FileAnalysisResultUpdate
) -> Optional[models.FileAnalysisResult]:
    if db_obj is None:
        return None

    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    
    if db_obj.analysis_status != "FAILED" and "error_message" not in update_data:
        db_obj.error_message = None
    if db_obj.analysis_status == "FAILED":
        if "word_cloud_image_location" not in update_data:
            db_obj.word_cloud_image_location = None
        if "other_analysis_data" not in update_data:
            db_obj.other_analysis_data = None

    await db.commit()
    await db.refresh(db_obj)
    return db_obj 