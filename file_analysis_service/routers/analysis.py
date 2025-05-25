import uuid
from typing import Optional, List
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import FileResponse
import aiofiles

import crud, models, schemas
from database import get_db
from config import Settings
from logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    tags=["analysis"],
)

WORDCLOUDS_STORAGE_DIR = Path("wordclouds_fas")

async def perform_file_analysis(
    db: AsyncSession,
    analysis_id: uuid.UUID,
    file_id: uuid.UUID,
    file_location: str,
    original_filename: str,
    mime_type: str,
    settings: Settings
):
    logger.info(f"Starting analysis for analysis_id: {analysis_id}, original_file_id: {file_id}, file_location: {file_location}")
    await crud.update_analysis_status_and_data(db, await crud.get_analysis_result(db, analysis_id), 
                                               schemas.FileAnalysisResultUpdate(analysis_status="PROCESSING"))

    try:
        file_content_text = ""
        if "text" in mime_type.lower():
            logger.info(f"[{analysis_id}] Downloading file content from FSS at: {file_location}")
            async with httpx.AsyncClient() as client:
                response = await client.get(str(file_location))
                response.raise_for_status()
                file_content_text = response.text
            logger.info(f"[{analysis_id}] Successfully downloaded file content. Length: {len(file_content_text)}")
        else:
            error_msg = f"File type '{mime_type}' not supported for word cloud analysis."
            logger.warning(f"[{analysis_id}] {error_msg}")
            await crud.update_analysis_status_and_data(db, await crud.get_analysis_result(db, analysis_id), 
                                                       schemas.FileAnalysisResultUpdate(analysis_status="FAILED", error_message=error_msg))
            return

        paragraphs = len([p for p in file_content_text.split('\n\n') if p.strip()])
        words = len(file_content_text.split())
        characters = len(file_content_text)
        other_data = {"paragraphs": paragraphs, "words": words, "characters": characters}
        logger.info(f"[{analysis_id}] Text statistics: {other_data}")

        logger.info(f"[{analysis_id}] Requesting word cloud from: {settings.WORDCLOUD_API_URL}")
        word_cloud_params = {"text": file_content_text, "format": "png", "width": 500, "height": 500}
        word_cloud_image_bytes = None
        async with httpx.AsyncClient() as client:
            try:
                wc_response = await client.post(str(settings.WORDCLOUD_API_URL), json=word_cloud_params)
                wc_response.raise_for_status()
                word_cloud_image_bytes = wc_response.content
                logger.info(f"[{analysis_id}] Successfully received word cloud image. Size: {len(word_cloud_image_bytes)} bytes")
            except httpx.HTTPStatusError as e:
                error_msg = f"Word Cloud API request failed: {e.response.status_code} - {e.response.text}"
                logger.error(f"[{analysis_id}] {error_msg}")
                await crud.update_analysis_status_and_data(db, await crud.get_analysis_result(db, analysis_id), 
                                                           schemas.FileAnalysisResultUpdate(analysis_status="FAILED", error_message=error_msg, other_analysis_data=other_data))
                return
            except httpx.RequestError as e:
                error_msg = f"Word Cloud API request failed: {str(e)}"
                logger.error(f"[{analysis_id}] {error_msg}")
                await crud.update_analysis_status_and_data(db, await crud.get_analysis_result(db, analysis_id), 
                                                           schemas.FileAnalysisResultUpdate(analysis_status="FAILED", error_message=error_msg, other_analysis_data=other_data))
                return

        wordclouds_storage_dir = Path(settings.STORAGE_BASE_PATH_FAS)
        if not wordclouds_storage_dir.exists():
            logger.info(f"Creating word cloud storage directory at {wordclouds_storage_dir}")
            wordclouds_storage_dir.mkdir(parents=True, exist_ok=True)
        
        image_filename = f"{analysis_id}_{original_filename.split('.')[0]}_wordcloud.png"
        image_path = wordclouds_storage_dir / image_filename
        
        logger.info(f"[{analysis_id}] Saving word cloud image to: {image_path}")
        async with aiofiles.open(image_path, 'wb') as f:
            await f.write(word_cloud_image_bytes)
        saved_image_location = image_filename

        logger.info(f"[{analysis_id}] Successfully processed. Word cloud stored as: {saved_image_location}")
        await crud.update_analysis_status_and_data(
            db, await crud.get_analysis_result(db, analysis_id), 
            schemas.FileAnalysisResultUpdate(
                analysis_status="COMPLETED",
                word_cloud_image_location=saved_image_location,
                other_analysis_data=other_data
            )
        )
        logger.info(f"Analysis COMPLETED for analysis_id: {analysis_id}, original_file_id: {file_id}")

    except Exception as e:
        logger.exception(f"Critical error during file analysis for analysis_id: {analysis_id}, original_file_id: {file_id}")
        current_other_data = locals().get("other_data")
        await crud.update_analysis_status_and_data(db, await crud.get_analysis_result(db, analysis_id), 
                                                       schemas.FileAnalysisResultUpdate(analysis_status="FAILED", error_message=str(e), other_analysis_data=current_other_data))

from config import settings as global_settings

def get_settings_dependency():
    return global_settings

@router.post("/", response_model=schemas.FileAnalysisResultPublic, status_code=202)
async def initiate_analysis(
    analysis_request_schema: schemas.FileAnalysisRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency)
):
    logger.info(f"Analysis trigger request received for original_file_id: {analysis_request_schema.file_id}")
    existing_analyses = await crud.get_analysis_results_by_original_id(db, analysis_request_schema.file_id)
    
    if existing_analyses:
        for existing_analysis in existing_analyses:
            logger.debug(f"Existing analysis found for {analysis_request_schema.file_id}: id {existing_analysis.id}, status {existing_analysis.analysis_status}")
            if existing_analysis.analysis_status == "COMPLETED":
                logger.info(f"Returning existing COMPLETED analysis {existing_analysis.id} for {analysis_request_schema.file_id}")
                return schemas.FileAnalysisResultPublic.model_validate(existing_analysis, context={"request": request})
            elif existing_analysis.analysis_status in ["PENDING", "PROCESSING"]:
                logger.warning(f"Analysis for file {analysis_request_schema.file_id} (id {existing_analysis.id}) already in progress ({existing_analysis.analysis_status}). Returning 409.")
                raise HTTPException(status_code=409, detail=f"Analysis for file {analysis_request_schema.file_id} is already in progress with status: {existing_analysis.analysis_status}")
        logger.info(f"All existing analyses for {analysis_request_schema.file_id} were FAILED or other. Allowing re-trigger.")

    new_analysis_db = await crud.create_analysis_request(db, analysis_request=analysis_request_schema)
    logger.info(f"Created new PENDING analysis record {new_analysis_db.id} for original_file_id: {analysis_request_schema.file_id}")

    background_tasks.add_task(
        perform_file_analysis, db, new_analysis_db.id,
        analysis_request_schema.file_id, analysis_request_schema.file_location,
        analysis_request_schema.original_filename, analysis_request_schema.mime_type, settings
    )
    logger.info(f"Background task added for analysis_id: {new_analysis_db.id}")
    
    return schemas.FileAnalysisResultPublic.model_validate(new_analysis_db, context={"request": request})

@router.get("/{analysis_id}", response_model=schemas.FileAnalysisResultPublic)
async def get_single_analysis_status(
    analysis_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"Status request for analysis_id: {analysis_id}")
    db_analysis = await crud.get_analysis_result(db, analysis_id)
    if db_analysis is None:
        logger.warning(f"Analysis result not found for analysis_id: {analysis_id}")
        raise HTTPException(status_code=404, detail="Analysis result not found")
    logger.debug(f"Returning status for analysis_id: {analysis_id}")
    return schemas.FileAnalysisResultPublic.model_validate(db_analysis, context={"request": request})

@router.get("/file/{original_file_id}", response_model=List[schemas.FileAnalysisResultPublic])
async def get_all_analysis_statuses_for_file(
    original_file_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"Status request for original_file_id: {original_file_id}")
    db_analyses = await crud.get_analysis_results_by_original_id(db, original_file_id)
    logger.debug(f"Returning {len(db_analyses)} status(es) for original_file_id: {original_file_id}")
    return [schemas.FileAnalysisResultPublic.model_validate(db_analysis, context={"request": request}) for db_analysis in db_analyses]

@router.get("/wordclouds/{analysis_id}/{filename}", tags=["analysis_results"])
async def download_word_cloud_image(
    analysis_id: uuid.UUID,
    filename: str,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency)
):
    logger.info(f"Word cloud image request: analysis_id={analysis_id}, filename={filename}")
    
    if not filename.startswith(str(analysis_id)):
        logger.warning(f"Requested filename {filename} does not match analysis_id {analysis_id}")
        raise HTTPException(status_code=400, detail="Requested filename does not match analysis ID.")

    if ".." in filename or filename.count("/") > 0:
        logger.warning(f"Invalid path characters in filename: {filename}")
        raise HTTPException(status_code=400, detail="Invalid filename or path.")

    analysis_record = await crud.get_analysis_result(db, analysis_id)
    if not analysis_record:
        logger.warning(f"Analysis record {analysis_id} not found for word cloud download.")
        raise HTTPException(status_code=404, detail="Analysis result not found or image not available.")
    
    if analysis_record.analysis_status != "COMPLETED" or not analysis_record.word_cloud_image_location:
        logger.warning(f"Analysis {analysis_id} not completed or no image location. Status: {analysis_record.analysis_status}")
        raise HTTPException(status_code=404, detail="Analysis result not found or image not available.")

    if Path(analysis_record.word_cloud_image_location).name != filename:
        logger.warning(f"Requested filename '{filename}' does not match stored filename '{analysis_record.word_cloud_image_location}' for analysis {analysis_id}.")
        raise HTTPException(status_code=400, detail="Requested filename does not match stored filename.")

    wordclouds_storage_dir = Path(settings.STORAGE_BASE_PATH_FAS)
    image_full_path = wordclouds_storage_dir / filename

    if not image_full_path.is_file():
        logger.error(f"Word cloud image file not found at path: {image_full_path} (analysis_id: {analysis_id})")
        raise HTTPException(status_code=404, detail="Word cloud image file not found on server.")
        
    logger.debug(f"Serving word cloud image from: {image_full_path}")
    return FileResponse(str(image_full_path)) 