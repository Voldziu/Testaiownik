import pytest
from unittest.mock import patch, Mock


class TestCollectionsAPI:
    """Test Collections API endpoints"""

    def test_list_collections_success(self, client, mock_user_id, mock_qdrant_manager):
        """Test successful collections listing"""
        with patch(
            "src.Testaiownik.Backend.api.collections.get_user_id",
            return_value=mock_user_id,
        ):
            mock_qdrant_manager.list_collections.return_value = [
                {"name": "quiz_456", "vector_count": 100},
                {"name": "quiz_789", "vector_count": 50},
            ]

            response = client.get("/api/collections")

            assert response.status_code == 200
            data = response.json()
            assert "collections" in data
            assert len(data["collections"]) == 2

    def test_get_collection_info_success(
        self, client, mock_user_id, mock_qdrant_manager
    ):
        """Test successful collection info retrieval"""
        with patch(
            "src.Testaiownik.Backend.api.collections.get_user_id",
            return_value=mock_user_id,
        ):
            mock_qdrant_manager.get_collection_info.return_value = {
                "name": "quiz_456",
                "vector_count": 100,
                "config": {"size": 1536},
            }

            response = client.get("/api/collections/quiz_456")

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "quiz_456"
            assert data["vector_count"] == 100

    def test_delete_collection_success(self, client, mock_user_id, mock_qdrant_manager):
        """Test successful collection deletion"""
        with patch(
            "src.Testaiownik.Backend.api.collections.get_user_id",
            return_value=mock_user_id,
        ):
            mock_qdrant_manager.delete_collection.return_value = True

            response = client.delete("/api/collections/quiz_456")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_collection_not_found(self, client, mock_user_id, mock_qdrant_manager):
        """Test collection not found error"""
        with patch(
            "src.Testaiownik.Backend.api.collections.get_user_id",
            return_value=mock_user_id,
        ):
            mock_qdrant_manager.get_collection_info.side_effect = Exception(
                "Collection not found"
            )

            response = client.get("/api/collections/nonexistent")
            assert response.status_code == 404
