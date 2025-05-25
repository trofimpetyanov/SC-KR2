import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio
from pathlib import Path
from datetime import datetime

from httpx import AsyncClient
from fastapi import FastAPI, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import HttpUrl

from schemas import FileAnalysisRequest, FileAnalysisResultPublic
from main import app as fas_app
import config as fas_config_module
import main as fas_main_module
import routers.analysis as fas_routers_analysis_module

@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    temp_storage_path = "/tmp/test_wordclouds_fas_pytest"
    Path(temp_storage_path).mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_BASE_PATH_FAS", temp_storage_path)
    monkeypatch.setenv("MAX_FILE_SIZE_MB", "10")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("WORDCLOUD_API_URL", "http://mockwordcloud.api/wordcloud")
    monkeypatch.setenv("FAS_URL", "http://testfasurl:8002")
    monkeypatch.setenv("FSS_URL", "http://testfssurl:8001")
    monkeypatch.setenv("FAS_HOST", "0.0.0.0")
    monkeypatch.setenv("FAS_PORT", "8002")

    new_settings = fas_config_module.Settings()
    monkeypatch.setattr(fas_config_module, "settings", new_settings)
    monkeypatch.setattr(fas_main_module, "settings", new_settings)
    monkeypatch.setattr(fas_routers_analysis_module, "global_settings", new_settings)
    monkeypatch.setattr(fas_routers_analysis_module, "get_settings_dependency", lambda: new_settings)

    return new_settings

@pytest.mark.asyncio
@patch("routers.analysis.crud.create_analysis_request", new_callable=AsyncMock)
@patch("fastapi.BackgroundTasks.add_task")
async def test_initiate_analysis(
    mock_add_task: MagicMock, 
    mock_crud_create_request: AsyncMock, 
    async_client_fas: AsyncClient, 
    db_session: AsyncSession, 
    mock_settings
):
    file_id = uuid.uuid4()
    request_payload = {
        "file_id": str(file_id),
        "file_location": f"{str(mock_settings.FSS_URL)}/files/{file_id}",
        "original_filename": "test.txt",
        "mime_type": "text/plain"
    }

    mock_db_entry = MagicMock(
        id=uuid.uuid4(), 
        original_file_id=file_id, 
        analysis_status="PENDING",
        word_cloud_image_location=None,
        other_analysis_data=None,
        error_message=None,
        created_at=datetime.utcnow(), 
        updated_at=datetime.utcnow(),
        word_cloud_image_url=None, 
        analysis_data=None
    )
    mock_crud_create_request.return_value = mock_db_entry
    
    response = await async_client_fas.post("/analysis/", json=request_payload)

    assert response.status_code == 202, response.text
    json_response = response.json()
    assert json_response["id"] == str(mock_db_entry.id)
    assert json_response["analysis_status"] == "PENDING"
    assert json_response["original_file_id"] == str(file_id)
    assert json_response.get("word_cloud_image_url") is None

    mock_crud_create_request.assert_called_once()
    assert isinstance(mock_crud_create_request.call_args[0][0], AsyncSession)
    call_arg_model = mock_crud_create_request.call_args[1]['analysis_request']
    assert call_arg_model.file_id == file_id
    assert str(call_arg_model.file_location) == request_payload["file_location"]

    mock_add_task.assert_called_once()
    args, kwargs = mock_add_task.call_args
    
    from routers.analysis import perform_file_analysis as actual_perform_file_analysis_func
    assert args[0] == actual_perform_file_analysis_func

    assert isinstance(args[1], AsyncSession)
    assert args[2] == mock_db_entry.id
    assert args[3] == file_id
    assert str(args[4]) == request_payload["file_location"]
    assert args[5] == request_payload["original_filename"]
    assert args[6] == request_payload["mime_type"]
    assert args[7] == mock_settings

@pytest.mark.asyncio
@patch("routers.analysis.crud.get_analysis_result", new_callable=AsyncMock)
async def test_get_analysis_status(mock_crud_get_result, async_client_fas: AsyncClient, db_session: AsyncSession, mock_settings):
    analysis_id = uuid.uuid4()
    original_file_id = uuid.uuid4()
    mock_request_obj = MagicMock(spec=Request)
    mock_request_obj.base_url = HttpUrl("http://testfas/")

    db_model_mock = MagicMock(
        id=analysis_id, 
        original_file_id=original_file_id, 
        analysis_status="COMPLETED", 
        word_cloud_image_location=f"{analysis_id}_image.png", 
        other_analysis_data={"words": 10, "chars": 100},
        error_message=None,
        created_at=datetime.utcnow(), 
        updated_at=datetime.utcnow(),
        word_cloud_image_url=None,
        analysis_data=None
    )
    mock_crud_get_result.return_value = db_model_mock
    
    expected_public_obj = FileAnalysisResultPublic.model_validate(
        {
            "id": analysis_id, 
            "original_file_id": original_file_id, 
            "analysis_status": "COMPLETED", 
            "word_cloud_image_location": f"{analysis_id}_image.png", 
            "other_analysis_data": {"words": 10, "chars": 100},
            "error_message": None,
            "created_at": db_model_mock.created_at, 
            "updated_at": db_model_mock.updated_at
        },
        context={"request": mock_request_obj}
    )
    expected_public_data = expected_public_obj.model_dump(mode='json', by_alias=True)
    
    assert expected_public_data["word_cloud_image_url"] == f"http://testfas/analysis/wordclouds/{analysis_id}/{analysis_id}_image.png"
    assert expected_public_data["analysis_data"] == {"words": 10, "chars": 100}

    response = await async_client_fas.get(f"/analysis/{analysis_id}")
    assert response.status_code == 200, response.text
    assert response.json() == expected_public_data
    mock_crud_get_result.assert_called_with(db_session, analysis_id)

    mock_crud_get_result.return_value = None
    response = await async_client_fas.get(f"/analysis/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Analysis result not found"}

@pytest.mark.asyncio
@patch("routers.analysis.crud.get_analysis_results_by_original_id", new_callable=AsyncMock)
async def test_get_all_analysis_statuses_for_file(mock_crud_get_all_results, async_client_fas: AsyncClient, db_session: AsyncSession, mock_settings):
    original_file_id = uuid.uuid4()
    analysis_id_1 = uuid.uuid4()
    analysis_id_2 = uuid.uuid4()
    mock_request_obj = MagicMock(spec=Request)
    mock_request_obj.base_url = HttpUrl("http://testfas/")

    db_result_1_model_mock = MagicMock(
        id=analysis_id_1, original_file_id=original_file_id, analysis_status="COMPLETED", 
        word_cloud_image_location=f"{analysis_id_1}_loc1.png", 
        other_analysis_data={"data1": "value1"}, 
        error_message=None, created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        word_cloud_image_url=None, analysis_data=None
    )
    db_result_2_model_mock = MagicMock(
        id=analysis_id_2, original_file_id=original_file_id, analysis_status="PENDING", 
        word_cloud_image_location=None, 
        other_analysis_data=None, 
        error_message=None, created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        word_cloud_image_url=None, analysis_data=None
    )
    mock_crud_get_all_results.return_value = [db_result_1_model_mock, db_result_2_model_mock]

    expected_public_data_1 = FileAnalysisResultPublic.model_validate(
        {
            "id": analysis_id_1, "original_file_id": original_file_id, "analysis_status": "COMPLETED",
            "word_cloud_image_location": f"{analysis_id_1}_loc1.png",
            "other_analysis_data": {"data1": "value1"},
            "error_message": None, "created_at": db_result_1_model_mock.created_at, "updated_at": db_result_1_model_mock.updated_at
        },
        context={"request": mock_request_obj}
    ).model_dump(mode='json', by_alias=True)
    expected_public_data_2 = FileAnalysisResultPublic.model_validate(
        {
            "id": analysis_id_2, "original_file_id": original_file_id, "analysis_status": "PENDING",
            "word_cloud_image_location": None,
            "other_analysis_data": None,
            "error_message": None, "created_at": db_result_2_model_mock.created_at, "updated_at": db_result_2_model_mock.updated_at
        },
        context={"request": mock_request_obj}
    ).model_dump(mode='json', by_alias=True)

    assert expected_public_data_1["word_cloud_image_url"] == f"http://testfas/analysis/wordclouds/{analysis_id_1}/{analysis_id_1}_loc1.png"
    assert expected_public_data_1["analysis_data"] == {"data1": "value1"}
    assert expected_public_data_2.get("word_cloud_image_url") is None

    response = await async_client_fas.get(f"/analysis/file/{original_file_id}")
    assert response.status_code == 200, response.text
    assert response.json() == [expected_public_data_1, expected_public_data_2]
    mock_crud_get_all_results.assert_called_with(db_session, original_file_id)

    mock_crud_get_all_results.return_value = []
    response = await async_client_fas.get(f"/analysis/file/{uuid.uuid4()}")
    assert response.status_code == 200
    assert response.json() == []

@pytest.mark.asyncio
@patch("routers.analysis.crud.get_analysis_result", new_callable=AsyncMock)
@patch("pathlib.Path.is_file")
async def test_download_word_cloud(mock_path_is_file, mock_crud_get_result, async_client_fas: AsyncClient, db_session: AsyncSession, mock_settings, tmp_path):
    analysis_id = uuid.uuid4()
    image_filename = f"{analysis_id}_test_cloud.png"
    image_location_in_db = image_filename
    full_path_on_server = Path(mock_settings.STORAGE_BASE_PATH_FAS) / image_filename

    mock_crud_get_result.return_value = None
    response = await async_client_fas.get(f"/analysis/wordclouds/{analysis_id}/{image_filename}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Analysis result not found or image not available."}

    mock_crud_get_result.return_value = MagicMock(id=analysis_id, analysis_status="PENDING", word_cloud_image_location=None)
    response = await async_client_fas.get(f"/analysis/wordclouds/{analysis_id}/{image_filename}")
    assert response.status_code == 404 
    assert response.json() == {"detail": "Analysis result not found or image not available."}

    mock_crud_get_result.return_value = MagicMock(id=analysis_id, analysis_status="COMPLETED", word_cloud_image_location=None)
    response = await async_client_fas.get(f"/analysis/wordclouds/{analysis_id}/{image_filename}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Analysis result not found or image not available."}

    wrong_aid_filename = f"{uuid.uuid4()}_test_cloud.png"
    mock_crud_get_result.return_value = MagicMock(id=analysis_id, analysis_status="COMPLETED", word_cloud_image_location=image_location_in_db)
    response = await async_client_fas.get(f"/analysis/wordclouds/{analysis_id}/{wrong_aid_filename}")
    assert response.status_code == 400, response.text
    assert response.json() == {"detail": "Requested filename does not match analysis ID."}

    mock_crud_get_result.return_value = MagicMock(id=analysis_id, analysis_status="COMPLETED", word_cloud_image_location="different_name.png")
    response = await async_client_fas.get(f"/analysis/wordclouds/{analysis_id}/{image_filename}")
    assert response.status_code == 400
    assert response.json() == {"detail": "Requested filename does not match stored filename."}

    mock_crud_get_result.return_value = MagicMock(id=analysis_id, analysis_status="COMPLETED", word_cloud_image_location=image_location_in_db)
    mock_path_is_file.return_value = False
    response = await async_client_fas.get(f"/analysis/wordclouds/{analysis_id}/{image_filename}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Word cloud image file not found on server."}

    mock_crud_get_result.return_value = MagicMock(id=analysis_id, analysis_status="COMPLETED", word_cloud_image_location=image_location_in_db)
    mock_path_is_file.return_value = True
    
    Path(mock_settings.STORAGE_BASE_PATH_FAS).mkdir(parents=True, exist_ok=True)
    with open(full_path_on_server, "wb") as f:
        f.write(b"dummy image data")
    
    response = await async_client_fas.get(f"/analysis/wordclouds/{analysis_id}/{image_filename}")
    assert response.status_code == 200, response.text
    assert response.content == b"dummy image data"
    assert response.headers["content-type"] == "image/png"

    Path(full_path_on_server).unlink(missing_ok=True) 