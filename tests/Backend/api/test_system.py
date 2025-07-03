import pytest
from unittest.mock import patch, Mock


class TestSystemAPI:
    """Test System API endpoints"""

    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/api/")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "TESTAIOWNIK API"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"

    def test_health_check_success(self, client):
        """Test successful health check"""
        with patch("src.Testaiownik.Backend.api.system.QdrantManager") as mock_qdrant:
            mock_qdrant.return_value = Mock()

            with patch("src.Testaiownik.Backend.api.system.get_llm") as mock_llm:
                mock_llm.return_value = Mock()

                response = client.get("/api/health")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "healthy"

    def test_get_stats_success(self, client, mock_user_id):
        """Test successful stats retrieval"""
        with patch(
            "src.Testaiownik.Backend.api.system.get_user_id", return_value=mock_user_id
        ):
            with patch(
                "src.Testaiownik.Backend.api.system.get_system_stats"
            ) as mock_system_stats:
                with patch(
                    "src.Testaiownik.Backend.api.system.get_user_stats"
                ) as mock_user_stats:
                    mock_system_stats.return_value = {
                        "total_users": 10,
                        "total_quizzes": 50,
                        "total_documents": 100,
                    }
                    mock_user_stats.return_value = {
                        "quiz_count": 5,
                        "document_count": 10,
                    }

                    response = client.get("/api/stats")

                    assert response.status_code == 200
                    data = response.json()
                    assert "system_stats" in data
                    assert "user_stats" in data

    def test_backup_user_data_success(self, client, mock_user_id):
        """Test successful user data backup"""
        with patch(
            "src.Testaiownik.Backend.api.system.get_user_id", return_value=mock_user_id
        ):
            with patch("src.Testaiownik.Backend.api.system.get_user") as mock_get_user:
                with patch(
                    "src.Testaiownik.Backend.api.system.get_quizzes_by_user"
                ) as mock_get_quizzes:
                    mock_get_user.return_value = Mock(user_id=mock_user_id)
                    mock_get_quizzes.return_value = [Mock(documents=[Mock(), Mock()])]

                    response = client.post("/api/backup/user")

                    assert response.status_code == 200
                    data = response.json()
                    assert "backup_id" in data
                    assert data["user_id"] == mock_user_id

    def test_unauthorized_access(self, client):
        """Test unauthorized access to protected endpoints"""
        response = client.get("/api/stats")
        assert response.status_code == 401

        response = client.post("/api/backup/user")
        assert response.status_code == 401
