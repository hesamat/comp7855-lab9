from __future__ import annotations

from flask import jsonify, request


def validate_profile_data(first_name: str, last_name: str, student_id: str):
    """Validate that required profile fields are present and well-formed."""
    if not first_name or not last_name or not student_id:
        return "All fields are required."
    return None


def normalize_profile_data(first_name: str, last_name: str, student_id: str):
    """Normalize profile field values (strip whitespace, stringify student_id)."""
    return {
        "first_name": first_name.strip() if first_name else "",
        "last_name": last_name.strip() if last_name else "",
        "student_id": str(student_id).strip() if student_id else "",
    }


def require_json_content_type():
    """Ensure the request is JSON; returns an error response tuple if not."""
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415
    return None
