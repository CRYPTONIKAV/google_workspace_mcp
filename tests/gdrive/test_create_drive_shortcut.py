"""
Unit tests for create_drive_shortcut tool.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from gdrive.drive_helpers import (
    SHORTCUT_MIME_TYPE,
    _create_drive_shortcut_impl as _raw_create_drive_shortcut,
)


def _make_service(created_response, create_spy=None):
    """Build a mock Drive service whose files().create().execute returns *created_response*."""
    execute = MagicMock(return_value=created_response)
    create = MagicMock()
    create.return_value.execute = execute
    if create_spy is not None:
        create.side_effect = create_spy
    files = MagicMock()
    files.return_value.create = create
    service = MagicMock()
    service.files = files
    return service


@pytest.mark.asyncio
async def test_create_shortcut_sends_shortcut_mime_and_target():
    """The create body must carry the shortcut MIME type and shortcutDetails.targetId."""
    api_response = {
        "id": "shortcut-id",
        "name": "Q3 Report",
        "webViewLink": "https://drive.google.com/file/d/shortcut-id/view",
    }
    seen = {}

    def spy(**kwargs):
        seen.update(kwargs.get("body", {}))
        m = MagicMock()
        m.execute = MagicMock(return_value=api_response)
        return m

    service = _make_service(api_response, create_spy=spy)

    with patch(
        "gdrive.drive_helpers.resolve_folder_id",
        new_callable=AsyncMock,
        return_value="parent-id",
    ):
        result = await _raw_create_drive_shortcut(
            service,
            user_google_email="user@example.com",
            target_file_id="target-id",
            parent_folder_id="parent-id",
            shortcut_name="Q3 Report",
        )

    assert seen["mimeType"] == SHORTCUT_MIME_TYPE
    assert seen["shortcutDetails"] == {"targetId": "target-id"}
    assert seen["parents"] == ["parent-id"]
    assert "shortcut-id" in result
    assert "Q3 Report" in result


@pytest.mark.asyncio
async def test_create_shortcut_custom_parent_resolves():
    """A non-root parent_folder_id should go through resolve_folder_id."""
    api_response = {"id": "shortcut-id", "name": "target-id"}
    service = _make_service(api_response)

    with patch(
        "gdrive.drive_helpers.resolve_folder_id",
        new_callable=AsyncMock,
        return_value="resolved-parent",
    ) as mock_resolve:
        result = await _raw_create_drive_shortcut(
            service,
            user_google_email="user@example.com",
            target_file_id="target-id",
            parent_folder_id="some-folder",
        )

    mock_resolve.assert_called_once()
    assert "shortcut-id" in result


@pytest.mark.asyncio
async def test_create_shortcut_rejects_empty_target():
    """An empty target ID must fail fast without calling the API."""
    service = _make_service({})
    with pytest.raises(ValueError, match="target_file_id"):
        await _raw_create_drive_shortcut(
            service,
            user_google_email="user@example.com",
            target_file_id="  ",
            parent_folder_id="root",
        )
    service.files.return_value.create.assert_not_called()


def _make_service_with_target(created_response, target_name=None, target_raises=False):
    """Mock service with files().get() for the target-name lookup."""
    service = _make_service(created_response)
    get_execute = MagicMock()
    if target_raises:
        get_execute.side_effect = Exception("not found")
    else:
        get_execute.return_value = {"name": target_name} if target_name else {}
    get = MagicMock()
    get.return_value.execute = get_execute
    files = MagicMock()
    real_files = service.files
    files.return_value.create = real_files.return_value.create
    files.return_value.get = get
    service.files = files
    return service, get


@pytest.mark.asyncio
async def test_create_shortcut_defaults_name_to_target_name():
    """Without shortcut_name, the shortcut takes the target file's name."""
    service, get = _make_service_with_target(
        {"id": "shortcut-id", "name": "Q3 Report"}, target_name="Q3 Report"
    )
    with patch(
        "gdrive.drive_helpers.resolve_folder_id",
        new_callable=AsyncMock,
        return_value="parent-id",
    ):
        result = await _raw_create_drive_shortcut(
            service,
            user_google_email="user@example.com",
            target_file_id="target-id",
            parent_folder_id="parent-id",
        )
    get.assert_called_once()
    assert "Q3 Report" in result


@pytest.mark.asyncio
async def test_create_shortcut_name_falls_back_to_id_when_target_unreadable():
    """When the target lookup fails, the raw target ID is used as the name."""
    service, _ = _make_service_with_target({"id": "shortcut-id"}, target_raises=True)
    with patch(
        "gdrive.drive_helpers.resolve_folder_id",
        new_callable=AsyncMock,
        return_value="parent-id",
    ):
        result = await _raw_create_drive_shortcut(
            service,
            user_google_email="user@example.com",
            target_file_id="target-id",
            parent_folder_id="parent-id",
        )
    assert "target-id" in result
