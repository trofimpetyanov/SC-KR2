import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from crud import (
    create_analysis_request,
    get_analysis_result,
    update_analysis_status_and_data,
    get_analysis_results_by_original_id
)
from schemas import FileAnalysisRequest, FileAnalysisResultUpdate
from models import FileAnalysisResult

@pytest.mark.asyncio
async def test_create_analysis_request(db_session: AsyncSession):
    original_file_uuid = uuid.uuid4()
    request_data = FileAnalysisRequest(
        file_id=original_file_uuid,
        file_location="http://mockfss/files/location.txt",
        original_filename="location.txt",
        mime_type="text/plain"
    )
    db_obj = await create_analysis_request(db_session, request_data)
    
    assert db_obj is not None
    assert db_obj.original_file_id == original_file_uuid
    assert db_obj.analysis_status == "PENDING"
    assert db_obj.id is not None

    result = await db_session.execute(select(FileAnalysisResult).filter(FileAnalysisResult.id == db_obj.id))
    retrieved = result.scalar_one_or_none()
    assert retrieved is not None
    assert retrieved.original_file_id == original_file_uuid

@pytest.mark.asyncio
async def test_get_analysis_result(db_session: AsyncSession):
    original_file_uuid = uuid.uuid4()
    request_data = FileAnalysisRequest(
        file_id=original_file_uuid,
        file_location="http://mockfss/files/retrieved.txt",
        original_filename="retrieved.txt",
        mime_type="text/plain"
    )
    created_obj = await create_analysis_request(db_session, request_data)
    
    retrieved_obj = await get_analysis_result(db_session, created_obj.id)
    assert retrieved_obj is not None
    assert retrieved_obj.id == created_obj.id
    assert retrieved_obj.original_file_id == original_file_uuid

    non_existent_id = uuid.uuid4()
    not_found_obj = await get_analysis_result(db_session, non_existent_id)
    assert not_found_obj is None

@pytest.mark.asyncio
async def test_update_analysis_status_and_data(db_session: AsyncSession):
    original_file_uuid = uuid.uuid4()
    request_data = FileAnalysisRequest(
        file_id=original_file_uuid,
        file_location="http://mockfss/files/update.txt",
        original_filename="update.txt",
        mime_type="text/plain"
    )
    created_obj = await create_analysis_request(db_session, request_data)
    
    update_data_completed = FileAnalysisResultUpdate(
        analysis_status="COMPLETED",
        word_cloud_image_location="/path/to/cloud.png",
        other_analysis_data={"words": 100, "chars": 500}
    )
    updated_obj_completed = await update_analysis_status_and_data(db_session, created_obj, update_data_completed)
    assert updated_obj_completed is not None
    assert updated_obj_completed.analysis_status == "COMPLETED"
    assert updated_obj_completed.word_cloud_image_location == "/path/to/cloud.png"
    assert updated_obj_completed.other_analysis_data == {"words": 100, "chars": 500}
    assert updated_obj_completed.error_message is None

    created_obj_for_fail = await get_analysis_result(db_session, created_obj.id)
    update_data_failed = FileAnalysisResultUpdate(
        analysis_status="FAILED",
        error_message="Something went wrong"
    )
    updated_obj_failed = await update_analysis_status_and_data(db_session, created_obj_for_fail, update_data_failed)
    assert updated_obj_failed is not None
    assert updated_obj_failed.analysis_status == "FAILED"
    assert updated_obj_failed.error_message == "Something went wrong"
    assert updated_obj_failed.word_cloud_image_location is None 
    assert updated_obj_failed.other_analysis_data is None

    non_existent_id = uuid.uuid4()
    non_existent_db_obj = await get_analysis_result(db_session, non_existent_id)
    assert non_existent_db_obj is None 
    non_updated_obj = await update_analysis_status_and_data(db_session, non_existent_db_obj, update_data_completed)
    assert non_updated_obj is None

@pytest.mark.asyncio
async def test_get_analysis_results_by_original_id(db_session: AsyncSession):
    original_file_uuid_1 = uuid.uuid4()
    original_file_uuid_2 = uuid.uuid4()

    req_data_1 = FileAnalysisRequest(
        file_id=original_file_uuid_1,
        file_location="http://mockfss/files/list1.txt",
        original_filename="list1.txt",
        mime_type="text/plain"
    )
    req_data_2 = FileAnalysisRequest(
        file_id=original_file_uuid_1,
        file_location="http://mockfss/files/list1_again.txt",
        original_filename="list1_again.txt",
        mime_type="text/plain"
    )
    req_data_3 = FileAnalysisRequest(
        file_id=original_file_uuid_2,
        file_location="http://mockfss/files/otherfile.txt",
        original_filename="otherfile.txt",
        mime_type="text/plain"
    )

    obj1 = await create_analysis_request(db_session, req_data_1)
    obj2 = await create_analysis_request(db_session, req_data_2)
    obj3 = await create_analysis_request(db_session, req_data_3)

    results_1 = await get_analysis_results_by_original_id(db_session, original_file_uuid_1)
    assert len(results_1) == 2
    for res in results_1:
        assert res.original_file_id == original_file_uuid_1

    results_2 = await get_analysis_results_by_original_id(db_session, original_file_uuid_2)
    assert len(results_2) == 1
    assert results_2[0].original_file_id == original_file_uuid_2

    non_existent_original_id = uuid.uuid4()
    results_none = await get_analysis_results_by_original_id(db_session, non_existent_original_id)
    assert len(results_none) == 0 