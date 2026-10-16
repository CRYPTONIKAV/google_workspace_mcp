"""Unit tests for copy_drive_file copy_comments passthrough (#1206)."""

import os
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from gdrive.drive_tools import copy_drive_file


def _unwrap(tool):
    fn = tool.fn if hasattr(tool, "fn") else tool
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _mock_service():
    mock_service = Mock()
    mock_service.files().copy().execute.return_value = {
        "id": "copy123",
        "name": "Copy of contract.docx",
        "webViewLink": "https://drive.google.com/file/d/copy123",
        "mimeType": "application/vnd.google-apps.document",
    }
    return mock_service


@pytest.mark.asyncio
@patch("gdrive.drive_tools.resolve_drive_item", new_callable=AsyncMock)
@patch("gdrive.drive_tools.resolve_folder_id", new_callable=AsyncMock)
async def test_copy_defaults_copy_comments_false(
    mock_resolve_folder, mock_resolve_item
):
    """Without copy_comments the files.copy call passes copyComments=False."""
    mock_resolve_item.return_value = (
        "file123",
        {"name": "contract.docx", "mimeType": "application/vnd.google-apps.document"},
    )
    mock_resolve_folder.return_value = "root"
    mock_service = _mock_service()

    result = await _unwrap(copy_drive_file)(
        service=mock_service,
        user_google_email="user@example.com",
        file_id="file123",
    )

    copy_kwargs = mock_service.files.return_value.copy.call_args.kwargs
    assert copy_kwargs["copyComments"] is False
    assert "Successfully copied 'contract.docx'" in result


@pytest.mark.asyncio
@patch("gdrive.drive_tools.resolve_drive_item", new_callable=AsyncMock)
@patch("gdrive.drive_tools.resolve_folder_id", new_callable=AsyncMock)
async def test_copy_with_copy_comments_true(
    mock_resolve_folder, mock_resolve_item
):
    """copy_comments=True is forwarded as copyComments=True to files.copy."""
    mock_resolve_item.return_value = (
        "file123",
        {"name": "contract.docx", "mimeType": "application/vnd.google-apps.document"},
    )
    mock_resolve_folder.return_value = "folder456"
    mock_service = _mock_service()

    result = await _unwrap(copy_drive_file)(
        service=mock_service,
        user_google_email="user@example.com",
        file_id="file123",
        new_name="contract v2.docx",
        parent_folder_id="folder456",
        copy_comments=True,
    )

    copy_kwargs = mock_service.files.return_value.copy.call_args.kwargs
    assert copy_kwargs["copyComments"] is True
    assert copy_kwargs["body"]["name"] == "contract v2.docx"
    assert copy_kwargs["body"]["parents"] == ["folder456"]
    assert "Open comments and suggestions" in result
