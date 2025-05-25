import pytest
from httpx import AsyncClient
from fastapi import UploadFile
from pathlib import Path
import io
import os

@pytest.mark.asyncio
async def test_upload_new_file_successful(
    async_client: AsyncClient, 
    mock_fss_settings
):
    file_content = b"This is a new test file content for FSS."
    file_name = "new_fss_test_file.txt"
    files = {"file": (file_name, io.BytesIO(file_content), "text/plain")}

    response = await async_client.post("/upload", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["original_filename"] == file_name
    assert data["mime_type"] == "text/plain"
    assert data["size_bytes"] == len(file_content)
    assert "id" in data
    assert "file_hash" in data
    assert "file_location" in data

    expected_file_path = mock_fss_settings.STORAGE_BASE_PATH / data["file_location"]
    assert expected_file_path.exists()
    assert expected_file_path.read_bytes() == file_content

@pytest.mark.asyncio
async def test_upload_existing_file_returns_existing_metadata(
    async_client: AsyncClient, 
    mock_fss_settings
):
    file_content = b"This is an existing test file content for FSS."
    file_name_1 = "existing_fss_file_1.txt"
    file_name_2 = "existing_fss_file_2.txt"

    files_1 = {"file": (file_name_1, io.BytesIO(file_content), "text/plain")}
    files_2 = {"file": (file_name_2, io.BytesIO(file_content), "text/plain")}

    response_1 = await async_client.post("/upload", files=files_1)
    assert response_1.status_code == 200
    data_1 = response_1.json()
    file_id_1 = data_1["id"]
    file_hash_1 = data_1["file_hash"]
    file_location_1 = data_1["file_location"]

    expected_file_path_1 = mock_fss_settings.STORAGE_BASE_PATH / file_location_1
    assert expected_file_path_1.exists()

    response_2 = await async_client.post("/upload", files=files_2)
    assert response_2.status_code == 200
    data_2 = response_2.json()

    assert data_2["id"] == file_id_1
    assert data_2["original_filename"] == file_name_1
    assert data_2["file_hash"] == file_hash_1
    assert data_2["file_location"] == file_location_1
    assert data_2["mime_type"] == "text/plain"
    assert data_2["size_bytes"] == len(file_content)

    hash_subdir = mock_fss_settings.STORAGE_BASE_PATH / file_location_1.split('/')[0]
    files_in_hash_dir = list(hash_subdir.iterdir())
    assert len(files_in_hash_dir) == 1

@pytest.mark.asyncio
async def test_download_file_successful(
    async_client: AsyncClient, 
    mock_fss_settings
):
    file_content = b"Content for FSS download test."
    file_name = "fss_download_me.txt"
    files_to_upload = {"file": (file_name, io.BytesIO(file_content), "text/plain")}

    upload_response = await async_client.post("/upload", files=files_to_upload)
    assert upload_response.status_code == 200
    uploaded_file_data = upload_response.json()
    file_id = uploaded_file_data["id"]

    download_response = await async_client.get(f"/{file_id}/download")

    assert download_response.status_code == 200
    assert download_response.content == file_content
    assert download_response.headers["content-type"] == "text/plain; charset=utf-8"
    assert f"filename=\"{file_name}\"" in download_response.headers["content-disposition"]

@pytest.mark.asyncio
async def test_download_nonexistent_file_returns_404(
    async_client: AsyncClient, 
    mock_fss_settings
):
    non_existent_file_id = "123e4567-e89b-12d3-a456-426614174000"
    
    response = await async_client.get(f"/{non_existent_file_id}/download")
    
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "File not found"