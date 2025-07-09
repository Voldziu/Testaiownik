# services/api_client.py

import requests
from typing import List, Dict, Any, Optional
from config.settings import BASE_URL, get_api_headers, BASIC_TIMEOUT, SHORT_TIMEOUT


class APIError(Exception):
    """Custom exception for API errors"""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API Error {status_code}: {message}")


class QuizAPIClient:
    """Client for Quiz API communication"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.headers = get_api_headers(user_id)
        self._base_url = BASE_URL

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response and raise errors if needed"""
        if response.status_code == 200:
            return response.json()
        else:
            raise APIError(response.status_code, response.text)

    # Quiz operations
    def create_quiz(self, name) -> Dict[str, Any]:
        """Create a new quiz"""

        response = requests.post(
            f"{BASE_URL}/api/quiz/create", headers=self.headers, params={"name": name}
        )

        return self._handle_response(response)

    # Document operations
    def upload_files(self, quiz_id: str, files: List) -> Dict[str, Any]:
        """Upload files to quiz"""
        response = requests.post(
            f"{BASE_URL}/api/documents/{quiz_id}/upload",
            files=files,
            headers=self.headers,
            timeout=SHORT_TIMEOUT,
        )
        return self._handle_response(response)

    def index_documents(self, quiz_id: str) -> Dict[str, Any]:
        """Start document indexing"""
        response = requests.post(
            f"{BASE_URL}/api/documents/{quiz_id}/index",
            headers=self.headers,
            timeout=BASIC_TIMEOUT,
        )
        return self._handle_response(response)

    def get_indexing_stats(self, quiz_id: str) -> Dict[str, Any]:
        """Get indexing statistics"""
        response = requests.get(
            f"{BASE_URL}/api/documents/{quiz_id}/stats", headers=self.headers
        )
        return self._handle_response(response)

    # Topic operations
    def start_topic_generation(self, quiz_id: str, topic_count: int) -> Dict[str, Any]:
        """Start topic generation"""
        response = requests.post(
            f"{BASE_URL}/api/topics/{quiz_id}/start",
            json={"desired_topic_count": topic_count},
            headers=self.headers,
            timeout=BASIC_TIMEOUT,
        )
        return self._handle_response(response)

    def get_topics(self, quiz_id: str) -> Dict[str, Any]:
        """Get quiz topics"""
        response = requests.get(
            f"{BASE_URL}/api/topics/{quiz_id}/status", headers=self.headers
        )
        return self._handle_response(response)

    def add_topic(self, quiz_id: str, topic_name: str, weight: float) -> Dict[str, Any]:
        """Add new topic"""
        response = requests.post(
            f"{BASE_URL}/api/topics/{quiz_id}/add",
            json={"topic_name": topic_name, "weight": weight},
            headers=self.headers,
        )
        return self._handle_response(response)

    def update_topic(
        self, quiz_id: str, old_name: str, new_name: str, new_weight: float
    ) -> Dict[str, Any]:
        """Update existing topic"""
        response = requests.patch(
            f"{BASE_URL}/api/topics/{quiz_id}/topic/{old_name}",
            json={"new_name": new_name, "new_weight": new_weight},
            headers=self.headers,
        )
        return self._handle_response(response)

    def delete_topic(self, quiz_id: str, topic_name: str) -> Dict[str, Any]:
        """Delete topic"""
        response = requests.delete(
            f"{BASE_URL}/api/topics/{quiz_id}/topic/{topic_name}", headers=self.headers
        )
        return self._handle_response(response)

    def submit_topic_feedback(self, quiz_id: str, feedback: str) -> Dict[str, Any]:
        """Submit feedback for all topics"""
        response = requests.post(
            f"{BASE_URL}/api/topics/{quiz_id}/feedback",  # Endpoint to send feedback
            json={"user_input": feedback},  # Sending feedback data
            headers=self.headers,
            timeout=BASIC_TIMEOUT,
        )
        return self._handle_response(response)

    def confirm_topics(self, quiz_id: str) -> Dict[str, Any]:
        """Confirm selected topics"""
        response = requests.post(
            f"{BASE_URL}/api/topics/{quiz_id}/confirm", headers=self.headers
        )
        return self._handle_response(response)

    def start_quiz(
        self,
        quiz_id: str,
        total_questions: int,
        user_questions: List[str],
        difficulty: str,
    ) -> Dict[str, Any]:
        """Start quiz execution with the user-defined settings"""
        data = {
            "total_questions": total_questions,
            "user_questions": user_questions,
            "difficulty": difficulty,
        }
        response = requests.post(
            f"{BASE_URL}/api/quiz/{quiz_id}/start",
            json=data,
            headers=self.headers,
            timeout=BASIC_TIMEOUT,
        )
        return self._handle_response(response)

    def get_current_question(self, quiz_id: str) -> Dict[str, Any]:
        """Get the current question for a quiz"""
        response = requests.get(
            f"{BASE_URL}/api/quiz/{quiz_id}/current", headers=self.headers
        )
        return self._handle_response(response)

    # Submit the user's answer to a question
    def submit_answer(
        self, quiz_id: str, question_id: str, selected_choices: List[str]
    ) -> Dict[str, Any]:
        """Submit an answer for a specific question"""
        data = {"question_id": question_id, "selected_choices": selected_choices}
        response = requests.post(
            f"{BASE_URL}/api/quiz/{quiz_id}/answer", json=data, headers=self.headers
        )
        return self._handle_response(response)

    # Fetch explanation for a specific question
    def get_explanation(self, quiz_id: str, question_id: str) -> Dict[str, Any]:
        """Get the explanation for a question"""
        response = requests.get(
            f"{BASE_URL}/api/quiz/{quiz_id}/explanation/{question_id}",
            headers=self.headers,
        )
        return self._handle_response(response)

    def get_quiz_status(self, quiz_id: str) -> Dict[str, Any]:
        """Get the status of the quiz"""
        response = requests.get(
            f"{BASE_URL}/api/quiz/{quiz_id}/status", headers=self.headers
        )
        return self._handle_response(response)

    def get_quiz_progress(self, quiz_id: str) -> Dict[str, Any]:
        """Get the progress of the quiz"""
        response = requests.get(
            f"{BASE_URL}/api/quiz/{quiz_id}/progress", headers=self.headers
        )
        return self._handle_response(response)

    def restart_quiz(self, quiz_id: str, hard: bool = False) -> Dict[str, Any]:
        """Restart the quiz, either soft or hard reset"""
        url = f"{BASE_URL}/api/quiz/{quiz_id}/restart"
        params = {"hard": hard}  # Soft reset - hard=False
        response = requests.post(url, params=params, headers=self.headers)
        return self._handle_response(response)

    def get_quizzes(self, limit: int = 10, offset: int = 0) -> Dict[str, Any]:
        """Fetch list of quizzes created by the user"""
        response = requests.get(
            f"{BASE_URL}/api/quiz/list",
            headers=self.headers,
            params={"limit": limit, "offset": offset},
        )
        return self._handle_response(response)

    def get_question_estimate(self, quiz_id: str, ratio: int = 2) -> Dict[str, Any]:
        """Get estimate of maximum number of questions based on document chunks"""
        response = requests.get(
            f"{BASE_URL}/api/documents/{quiz_id}/question-estimate",
            headers=self.headers,
            params={"ratio": ratio},
        )
        return self._handle_response(response)


# Convenience function to get API client
def get_api_client(user_id: str) -> QuizAPIClient:
    """Get configured API client"""
    return QuizAPIClient(user_id)
