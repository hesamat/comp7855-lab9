from __future__ import annotations

import json
import re
import time
from pathlib import Path

from flask import jsonify, request
from firebase_admin import firestore

from decorators import require_api_key, require_jwt
from firebase import db
from utils.profile import get_profile_data, get_profile_doc_ref, set_profile
from utils.validation import normalize_profile_data, require_json_content_type, validate_profile_data

from . import api_bp


@api_bp.get("/profile")
@require_jwt
def api_get_profile(uid: str):
    """Return the current user's profile."""
    profile_data = get_profile_data(uid)
    return jsonify({"uid": uid, "profile": profile_data}), 200


@api_bp.post("/profile")
@require_jwt
def api_create_profile(uid: str):
    """Create/replace the current user's profile from a JSON body."""
    content_error = require_json_content_type()
    if content_error:
        return content_error

    data = request.get_json(silent=True) or {}
    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")
    student_id = data.get("student_id", "")

    error = validate_profile_data(first_name, last_name, student_id)
    if error:
        return jsonify({"error": error}), 400

    normalized = normalize_profile_data(first_name, last_name, student_id)
    set_profile(uid, normalized, merge=False)
    return jsonify({"message": "Profile saved successfully", "profile": normalized}), 200


@api_bp.put("/profile")
@require_jwt
def api_update_profile(uid: str):
    """Update the current user's profile from a JSON body with strict validation."""
    content_error = require_json_content_type()
    if content_error:
        return content_error

    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "Request body cannot be empty"}), 400

    allowed_fields = {"first_name", "last_name", "student_id"}
    invalid_fields = set(data.keys()) - allowed_fields
    errors = []

    if invalid_fields:
        errors.append(
            f"Invalid field(s): {', '.join(sorted(invalid_fields))}. Only first_name, last_name, and student_id are allowed."
        )

    first_name = data.get("first_name")
    last_name = data.get("last_name")
    student_id = data.get("student_id")

    if first_name is not None:
        first_name = first_name.strip() if first_name else ""
        if len(first_name) > 50:
            errors.append("first_name must not exceed 50 characters")

    if last_name is not None:
        last_name = last_name.strip() if last_name else ""
        if len(last_name) > 50:
            errors.append("last_name must not exceed 50 characters")

    if student_id is not None:
        student_id = str(student_id).strip() if student_id else ""
        if student_id:
            if len(student_id) not in (8, 9):
                errors.append("student_id must be exactly 8 or 9 characters")
            elif not re.match(r"^[a-zA-Z0-9]+$", student_id):
                errors.append("student_id must contain only alphanumeric characters")

    if errors:
        return jsonify({"errors": errors}), 400

    update_data = {}
    if first_name is not None:
        update_data["first_name"] = first_name
    if last_name is not None:
        update_data["last_name"] = last_name
    if student_id is not None:
        update_data["student_id"] = student_id

    if not update_data:
        return jsonify({"error": "No updatable fields provided"}), 400

    set_profile(uid, update_data, merge=True)

    updated_profile = get_profile_data(uid)
    return jsonify({"message": "Profile updated successfully", "profile": updated_profile}), 200


@api_bp.delete("/profile")
@require_jwt
def api_delete_profile(uid: str):
    """Delete the current user's profile."""
    get_profile_doc_ref(uid).delete()
    return jsonify({"message": "Profile deleted successfully"}), 200


@api_bp.get("/sensor_data")
@require_jwt
def api_get_sensor_data(uid: str):
    """Return mock sensor data for dashboard visualization."""
    _ = uid
    data_file = Path(__file__).resolve().parents[2] / "mock_sensor_data.json"

    try:
        with data_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return jsonify({"error": "mock_sensor_data.json not found"}), 404
    except json.JSONDecodeError:
        return jsonify({"error": "mock_sensor_data.json is not valid JSON"}), 500

    return jsonify(data), 200


@api_bp.post("/sensor_data")
@require_api_key
def api_sensor_data():
    """Receive sensor data from IoT devices (requires API key authentication)."""
    content_error = require_json_content_type()
    if content_error:
        return content_error

    data = request.get_json(silent=True) or {}

    if not data:
        return jsonify({"error": "Request body cannot be empty"}), 400

    doc_id = str(int(time.time() * 1000))
    db.collection("sensor_data").document(doc_id).set(
        {
            "data": data,
            "timestamp": firestore.SERVER_TIMESTAMP,
        }
    )

    return jsonify({"message": "Sensor data received successfully", "id": doc_id}), 201
