from __future__ import annotations

from functools import wraps
from typing import Optional, Tuple, Union
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
from flask.typing import ResponseReturnValue
import firebase_admin
from firebase_admin import credentials, firestore, auth
from firebase_admin.firestore import DocumentReference
import os
import re
import requests
import time

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

# Firebase Web API Key for Identity Toolkit
WEB_API_KEY = os.environ.get("FIREBASE_WEB_API_KEY")

# Initialize Firestore
if not firebase_admin._apps:
    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT", "serviceAccountKey.json")
    cred = credentials.Certificate(service_account_path)
    firebase_admin.initialize_app(cred)
db = firestore.client()

def get_current_user():
    """Return the currently logged-in username (or None).

    Uses session data set during `/login`. This keeps all login checks
    consistent in one place.
    """
    if not session.get("logged_in"):
        return None
    return session.get("username")


def get_profile_doc_ref(username: str):
    """Get the Firestore document reference for a user's profile."""
    return db.collection("profiles").document(username)


def get_profile_data(username: str):
    """Fetch a user's profile from Firestore, returning an empty dict if missing."""
    doc = get_profile_doc_ref(username).get()
    return doc.to_dict() if doc.exists else {}


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
        "student_id": str(student_id).strip() if student_id else ""
    }


def require_json_content_type():
    """Ensure the request is JSON; returns an error response tuple if not."""
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415
    return None


def set_profile(username: str, profile_data: dict[str, str], *, merge: bool):
    """Persist profile data to Firestore.

    Args:
        username: Profile owner.
        profile_data: Data to write.
        merge: When True, merges into existing document (partial update).
    """
    get_profile_doc_ref(username).set(profile_data, merge=merge)


def require_api_key(f):
    """Decorator to require API key authentication for device/iot endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get the expected key from environment
        expected_key = os.environ.get("SENSOR_API_KEY")

        if not expected_key:
            return jsonify({"error": "API key not configured on server"}), 500

        # Get the provided key from request headers
        provided_key = request.headers.get("X-API-Key")

        if not provided_key:
            return jsonify({"error": "Missing X-API-Key header"}), 401

        # Compare keys
        if provided_key != expected_key:
            return jsonify({"error": "Unauthorized"}), 401

        # Allow the route to execute normally
        return f(*args, **kwargs)
    return decorated_function


def require_jwt(f):
    """Decorator to require JWT authentication for API endpoints.

    Verifies the JWT token from the Authorization header and injects
    the user ID into the route function as a keyword argument 'uid'.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return jsonify({"error": "Missing Authorization header"}), 401

        # Check for "Bearer " prefix
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Invalid Authorization header format"}), 401

        token = auth_header.split(" ")[1]

        try:
            # Verify the JWT token using Firebase Admin SDK
            decoded_token = auth.verify_id_token(token)
            uid = decoded_token["uid"]
            # Inject uid into the route function
            return f(*args, uid=uid, **kwargs)
        except Exception:
            return jsonify({"error": "Invalid or expired token"}), 401
    return decorated_function

# --- Web Routes ---

@app.route("/")
def home():
    """Home page. Redirects to login if no active session."""
    current_user = get_current_user()
    if current_user:
        profile_data = get_profile_data(current_user)
        return render_template("dashboard.html", first_name=profile_data.get('first_name', ''), jwt_token=session.get('jwt_token'))
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Signup page for creating new user accounts."""
    if request.method == "GET":
        return render_template("signup.html")

    # Handle form submission (web)
    if request.content_type and "application/json" in request.content_type:
        return api_signup()

    email = request.form.get("email")
    password = request.form.get("password")
    confirm_password = request.form.get("confirm_password")

    # Validate passwords match
    if password != confirm_password:
        return render_template("signup.html", error="Passwords do not match")

    # Validate required fields
    if not email or not password:
        return render_template("signup.html", error="Email and password are required")

    try:
        # Create user with Firebase Admin SDK
        user = auth.create_user(email=email, password=password)

        # Initialize profile in Firestore
        db.collection("profiles").document(user.uid).set({
            "email": email,
            "role": "user"
        })

        return redirect(url_for("login"))
    except Exception as e:
        error_message = str(e)
        if "email-already-exists" in error_message:
            error_message = "An account with this email already exists"
        elif "invalid-email" in error_message:
            error_message = "Invalid email address"
        elif "weak-password" in error_message:
            error_message = "Password is too weak. Please use a stronger password"
        return render_template("signup.html", error=error_message)


def api_signup():
    """JSON API endpoint for user registration."""
    data = request.get_json(silent=True) or {}

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    try:
        # Create user with Firebase Admin SDK
        user = auth.create_user(email=email, password=password)

        # Initialize profile in Firestore
        db.collection("profiles").document(user.uid).set({
            "email": email,
            "role": "user"
        })

        return jsonify({"message": "User created successfully", "uid": user.uid}), 201
    except Exception as e:
        error_message = str(e)
        if "email-already-exists" in error_message:
            return jsonify({"error": "An account with this email already exists"}), 400
        elif "invalid-email" in error_message:
            return jsonify({"error": "Invalid email address"}), 400
        elif "weak-password" in error_message:
            return jsonify({"error": "Password is too weak"}), 400
        return jsonify({"error": "Failed to create user"}), 400


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page. Supports both web form and JSON API login."""
    if request.method == "GET":
        return render_template("login.html")

    # Handle JSON API login
    if request.is_json:
        return api_login()

    # Handle web form login
    email = request.form.get("email")
    password = request.form.get("password")

    if not email or not password:
        return render_template("login.html", error="Email and password are required")

    # Use Firebase Identity REST API to authenticate
    try:
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={WEB_API_KEY}"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }

        res = requests.post(url, json=payload, timeout=10)

        if res.status_code == 200:
            token_data = res.json()
            # For web sessions, we'll use the uid from the response
            uid = token_data.get("localId")
            session["logged_in"] = True
            session["username"] = uid
            session["email"] = email
            session["jwt_token"] = token_data.get("idToken")
            return redirect(url_for("home"))

        error_data = res.json().get("error", {})
        error_message = error_data.get("message", "Invalid credentials")
        if "INVALID_LOGIN_CREDENTIALS" in error_message:
            error_message = "Invalid email or password"
        return render_template("login.html", error=error_message)
    except requests.RequestException:
        return render_template("login.html", error="Authentication service unavailable")


def api_login():
    """JSON API endpoint for login. Returns a JWT token."""
    data = request.get_json(silent=True) or {}

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={WEB_API_KEY}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }

    try:
        res = requests.post(url, json=payload, timeout=10)

        if res.status_code == 200:
            return jsonify({"token": res.json()["idToken"]}), 200

        return jsonify({"error": "Invalid credentials"}), 401
    except requests.RequestException:
        return jsonify({"error": "Authentication service unavailable"}), 503


@app.route("/logout")
def logout():
    """Clear the session and return to login."""
    session.clear()
    return redirect(url_for("login"))


@app.route("/profile", methods=["GET", "POST"])
def profile():
    """HTML form to create/update the current user's profile."""
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for("login"))

    if request.method == "GET":
        profile_data = get_profile_data(current_user)
        return render_template("profile.html", profile=profile_data, error=None)

    first_name = request.form.get("first_name", "")
    last_name = request.form.get("last_name", "")
    student_id = request.form.get("student_id", "")

    error = validate_profile_data(first_name, last_name, student_id)
    if error:
        profile_data = {"first_name": first_name, "last_name": last_name, "student_id": student_id}
        return render_template("profile.html", profile=profile_data, error=error)

    normalized = normalize_profile_data(first_name, last_name, student_id)
    set_profile(current_user, normalized, merge=True)
    return redirect(url_for("home"))


# --- API Routes ---

@app.get("/api/profile")
@require_jwt
def api_get_profile(uid: str):
    """Return the current user's profile."""
    profile_data = get_profile_data(uid)
    return jsonify({"uid": uid, "profile": profile_data}), 200


@app.post("/api/profile")
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


@app.put("/api/profile")
@require_jwt
def api_update_profile(uid: str):
    """Update the current user's profile from a JSON body.

    Implements strict input validation:
    - Whitelist: Only allows first_name, last_name, student_id fields
    - Bounds checking: Names max 50 chars, student_id must be 8-9 alphanumeric
    - Collects all errors before returning
    """
    content_error = require_json_content_type()
    if content_error:
        return content_error

    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "Request body cannot be empty"}), 400

    # Whitelist of allowed fields
    allowed_fields = {"first_name", "last_name", "student_id"}

    # Check for invalid fields
    invalid_fields = set(data.keys()) - allowed_fields
    errors = []

    if invalid_fields:
        errors.append(f"Invalid field(s): {', '.join(sorted(invalid_fields))}. Only first_name, last_name, and student_id are allowed.")

    first_name = data.get("first_name")
    last_name = data.get("last_name")
    student_id = data.get("student_id")

    # Validate first_name if provided
    if first_name is not None:
        first_name = first_name.strip() if first_name else ""
        if len(first_name) > 50:
            errors.append("first_name must not exceed 50 characters")

    # Validate last_name if provided
    if last_name is not None:
        last_name = last_name.strip() if last_name else ""
        if len(last_name) > 50:
            errors.append("last_name must not exceed 50 characters")

    # Validate student_id if provided
    if student_id is not None:
        student_id = str(student_id).strip() if student_id else ""
        if student_id:  # Only validate format if not empty
            if not (len(student_id) == 8 or len(student_id) == 9):
                errors.append("student_id must be exactly 8 or 9 characters")
            elif not re.match(r'^[a-zA-Z0-9]+$', student_id):
                errors.append("student_id must contain only alphanumeric characters")

    # Return all errors at once if any
    if errors:
        return jsonify({"errors": errors}), 400

    # Prepare the update data (only include provided fields)
    update_data = {}
    if first_name is not None:
        update_data["first_name"] = first_name
    if last_name is not None:
        update_data["last_name"] = last_name
    if student_id is not None:
        update_data["student_id"] = student_id

    if not update_data:
        return jsonify({"error": "No updatable fields provided"}), 400

    # Merge update into existing document (or create if missing).
    set_profile(uid, update_data, merge=True)

    updated_profile = get_profile_data(uid)
    return jsonify({"message": "Profile updated successfully", "profile": updated_profile}), 200


@app.delete("/api/profile")
@require_jwt
def api_delete_profile(uid: str):
    """Delete the current user's profile."""
    get_profile_doc_ref(uid).delete()
    return jsonify({"message": "Profile deleted successfully"}), 200


@app.route("/api/sensor_data", methods=["POST"])
@require_api_key
def api_sensor_data(uid: str):
    """Receive sensor data from IoT devices (requires API key authentication)."""
    content_error = require_json_content_type()
    if content_error:
        return content_error

    data = request.get_json(silent=True) or {}

    # Validate that we received some data
    if not data:
        return jsonify({"error": "Request body cannot be empty"}), 400

    # Store sensor data in Firestore (you can customize the collection name)
    # Using a timestamp-based document ID for uniqueness
    doc_id = str(int(time.time() * 1000))
    db.collection("sensor_data").document(doc_id).set({
        "data": data,
        "timestamp": firestore.SERVER_TIMESTAMP
    })

    return jsonify({"message": "Sensor data received successfully", "id": doc_id}), 201


if __name__ == "__main__":
    app.run(debug=True, port=5000)
