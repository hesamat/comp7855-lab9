## **Overview**

In this lab, you will refactor the existing Flask application for better maintainability using Flask Blueprints and add data visualization to the dashboard using Chart.js.

The application already has Firebase Authentication (JWTs), Device Identity (API Keys), and input validation implemented. Your tasks are to:

1. **Modularize the codebase** using Flask Blueprints
2. **Add a time-series chart** to visualize sensor data on the dashboard

---

## **Quick Setup (One-Time)**

1. Install dependencies:
  - `pip install -r requirements.txt`

2. Set the required environment variables (either in a `.env` file or directly in your shell):
  - `FIREBASE_WEB_API_KEY` (required for login/signup)
  - `SENSOR_API_KEY` (required for `/api/sensor_data` POST)

Optional (only if you need them):
  - `FLASK_SECRET_KEY` (recommended for non-demo deployments; defaults to a dev value)
  - `FIREBASE_SERVICE_ACCOUNT` (only if your service account file is not `serviceAccountKey.json`)

## **Current Project Structure**

```
├── app.py                      # Main Flask application (all routes + decorators)
├── config.py                   # Starter: environment variable config
├── firebase.py                 # Starter: Firebase init + exports db
├── mock_sensor_data.json       # Starter: time-series sensor data for Task 2
├── requirements.txt            # Python dependencies
├── serviceAccountKey.json      # Firebase service account credentials
├── .env                        # Environment variables
└── templates/
    ├── login.html              # Login page (form-based)
    ├── signup.html             # Signup page
    ├── dashboard.html          # User dashboard (basic, no chart)
    └── profile.html            # Profile creation/edit form
```

---

## **Task 1: Modularizing the Code with Flask Blueprints**

Currently, all routes, decorators, and helper functions are in a single `app.py` file. You will reorganize the code into separate modules using Flask Blueprints.

### **Target Project Structure**

Create the following directory structure:

```
├── app.py                      # Main Flask application (creates app, registers blueprints, initializes Firebase)
├── config.py                   # Configuration settings
├── firebase.py                 # Firebase initialization and db export
├── requirements.txt            # Python dependencies
├── serviceAccountKey.json      # Firebase service account credentials
├── .env                        # Environment variables
├── blueprints/
│   ├── __init__.py
│   ├── auth/
│   │   ├── __init__.py         # Exports auth_bp
│   │   └── routes.py           # login, signup, logout routes
│   ├── profile/
│   │   ├── __init__.py         # Exports profile_bp
│   │   └── routes.py           # profile web routes
│   ├── dashboard/
│   │   ├── __init__.py         # Exports dashboard_bp
│   │   └── routes.py           # home/dashboard routes
│   └── api/
│       ├── __init__.py         # Exports api_bp
│       └── routes.py           # API routes (profile CRUD, sensor_data)
├── decorators/
│   ├── __init__.py             # Exports require_jwt, require_api_key
│   └── auth.py                 # JWT and API key decorators
├── utils/
│   ├── __init__.py             # Exports helper functions
│   ├── auth.py                 # Auth helper functions
│   ├── profile.py              # Profile helper functions
│   └── validation.py           # Input validation helpers
└── templates/
    ├── login.html
    ├── signup.html
    ├── dashboard.html
    └── profile.html
```

### **Step 1.1: Review the Provided Starter Files**

Review the starter code already provided for you:
- **`config.py`**: Manages environment variables like `WEB_API_KEY`. 
- **`firebase.py`**: Initializes Firestore and exports `db` to prevent circular imports.

Your task is to import from these existing modules inside your blueprints.

### **Step 1.2: Create the Decorators Module**

Create `decorators/__init__.py` and `decorators/auth.py`. Move `require_api_key(f)` and `require_jwt(f)` from `app.py` into `decorators/auth.py`.

Remember to import the necessary elements in your new file: `request`, `jsonify` from `flask`, `os`, `functools.wraps`, and `firebase_admin.auth`.

### **Step 1.3: Create the Utils Module**

Create `utils/__init__.py`, `utils/auth.py`, `utils/profile.py`, and `utils/validation.py`. Move the corresponding functions from `app.py`.
- **`utils/auth.py`**: Move `get_current_user`.
- **`utils/profile.py`**: Move `get_profile_doc_ref`, `get_profile_data`, and `set_profile`. You will need to `from firebase import db` for Firestore access.
- **`utils/validation.py`**: Move `validate_profile_data`, `normalize_profile_data`, and `require_json_content_type`.

### **Step 1.4: Create the Auth Blueprint**

**File:** `blueprints/auth/__init__.py`

Create and export the blueprint instance:
```python
from flask import Blueprint

auth_bp = Blueprint('auth', __name__)

# Import routes at the bottom to avoid circular dependencies
from . import routes
```

**File:** `blueprints/auth/routes.py`

Move the following functions from `app.py` into this file:

1. **Blueprint Routes** (decorated with `@auth_bp.route`):
   - `login()` - GET/POST login page
   - `signup()` - GET/POST signup page
   - `logout()` - Clear session

2. **Internal Helpers** (called by the routes above):
   - `api_login()` - helper used inside `login()`
   - `api_signup()` - helper used inside `signup()`

Example of defining routes in your blueprint:
```python
from flask import request, jsonify, render_template, session, redirect, url_for
from . import auth_bp
import requests
from config import Config

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # ... implementation ...
```

Note: The login and signup routes should remain at `/login` and `/signup` (no URL prefix).
You will also need to import `requests`, `session`, `render_template` and retrieve your API key from `config.py` (e.g., `from config import Config` and `Config.WEB_API_KEY`).

**Important (Blueprint `url_for`)**
After you move routes into blueprints, endpoint names are namespaced.
For example:
- `url_for("login")` becomes `url_for("auth.login")`
- `url_for("signup")` becomes `url_for("auth.signup")`
- `url_for("home")` becomes `url_for("dashboard.home")`

### **Step 1.5: Create the Profile Blueprint**

**File:** `blueprints/profile/__init__.py`

Create and export the blueprint instance.

**File:** `blueprints/profile/routes.py`

Move the following route from `app.py`:
- `profile()` - GET/POST profile form

Import helper functions from `utils.profile`, `utils.validation`, and `utils.auth`.

### **Step 1.6: Create the Dashboard Blueprint**

**File:** `blueprints/dashboard/__init__.py`

Create and export the blueprint instance.

**File:** `blueprints/dashboard/routes.py`

Move the following route from `app.py`:
- `home()` - Root route that renders dashboard

Import `get_profile_data` from `utils.profile` and `get_current_user` from `utils.auth`.

### **Step 1.7: Create the API Blueprint**

**File:** `blueprints/api/__init__.py`

Create and export the blueprint instance.

**File:** `blueprints/api/routes.py`

Move the following routes from `app.py`:
- `api_get_profile(uid)` - GET /api/profile
- `api_create_profile(uid)` - POST /api/profile
- `api_update_profile(uid)` - PUT /api/profile
- `api_delete_profile(uid)` - DELETE /api/profile
- `api_sensor_data(uid)` - POST /api/sensor_data

Import decorators from `decorators` and helper functions from `utils`.

Create the blueprint with `url_prefix='/api'`:
```python
from flask import Blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')
```

Note: After adding the prefix, your routes should be defined as:
- `@api_bp.get("/profile")` instead of `@app.get("/api/profile")`

### **Step 1.8: Update app.py**

**File:** `app.py`

Refactor this file to only contain:
- Flask app initialization
- Session configuration
- Blueprint registration

```python
from flask import Flask
from config import Config

# Import blueprints
from blueprints.auth import auth_bp
from blueprints.profile import profile_bp
from blueprints.dashboard import dashboard_bp
from blueprints.api import api_bp

app = Flask(__name__)
app.config.from_object(Config)

# Register blueprints
app.register_blueprint(dashboard_bp)  # Handles root route /
app.register_blueprint(auth_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(api_bp)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

**Important:** Other modules need access to `db`. Import it from `firebase.py` where needed (e.g. `from firebase import db`). This avoids circular imports previously caused by importing it from `app`.

---

## **Task 2: Visualizing Sensor Data with Chart.js**

### **Background: Handling Continuous Telemetry**
Our hybrid frontend can securely talk to our API. But how do we handle continuous streams of telemetry?

**The HTTP Limitation**
HTTP was built for documents. The client asks, the server answers. The server cannot initiate a conversation with the client. If a sensor detects a fire, the Flask server cannot push that alert to the browser.

**Three Solutions for Dashboards:**
1. **HTTP Polling:** JavaScript asks the server for updates every X seconds. This is simple but can be inefficient.
2. **WebSockets:** A persistent, two-way TCP pipe. Excellent for low-latency dashboards.
3. **MQTT:** The IoT industry standard publish/subscribe protocol.

For this lab, you will use **HTTP Polling** alongside Chart.js to visualize time-series sensor data fetched from a local JSON file.

### **Step 2.1: Create a GET Endpoint for Sensor Data**

**File:** `blueprints/api/routes.py`

Add a new route to fetch sensor data:

```
GET /api/sensor_data
```

This route should:
- Require JWT authentication (use `@require_jwt` decorator). Because of this decorator, remember that your route function must accept `uid` as a parameter (e.g., `def api_get_sensor_data(uid):`).
- Read and parse the `mock_sensor_data.json` file provided in the repository (use Python's `json` module).
- Return the parsed data as a JSON response.

*(Note: The existing POST route for `/api/sensor_data` is also decorated with `@require_jwt`, so its route handler must accept `uid` too.)*

### **Step 2.2: Update dashboard.html**

**File:** `templates/dashboard.html`

Make the following additions:

1. **Include Chart.js** via CDN in the `<head>` section:
   ```html
   <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
   ```

2. **Inject the JWT token** via Jinja so your JavaScript can authenticate API requests. Add this before your charting script:
   ```html
   <script>
       const token = "{{ jwt_token }}";
   </script>
   ```
   The `jwt_token` variable is already passed to this template by `home()` in the dashboard blueprint.

3. **Add a canvas element** for the chart:
   ```html
   <div class="chart-container">
       <canvas id="sensorChart"></canvas>
   </div>
   ```

4. **Add JavaScript** to:
   - Fetch sensor data from `/api/sensor_data` using `token` in the `Authorization: Bearer` header
   - Create a line chart using Chart.js
   - Display at least two data series (e.g., temperature and humidity)
   - Use dual Y-axes for different units

### **Step 2.3: Chart Features**

Your chart implementation should include:

1. **Time Series X-Axis:** Display timestamps on the horizontal axis
2. **Multiple Data Series:** Plot temperature, humidity, or other sensor values
3. **Dual Y-Axes:** Different scales for different units (°C for temperature, % for humidity)
4. **Responsive Design:** Chart should resize with the browser window
5. **Interactive Tooltips:** Show values when hovering over data points

*Hint for Dual Y-Axes:* In Chart.js, configure multiple y-axes in the `scales` options and map datasets using `yAxisID`:

```javascript
datasets: [
  { label: 'Temp', data: [...], yAxisID: 'y' },
  { label: 'Humidity', data: [...], yAxisID: 'y1' }
],
options: {
  scales: {
    y: { type: 'linear', position: 'left' },
    y1: { type: 'linear', position: 'right' }
  }
}
```

### **Step 2.4: Implement HTTP Polling**
Instead of just fetching data once when the page loads, use HTTP polling to repeatedly hit the backend and update your chart.

1. Wrap your data fetching and chart updating logic in an `updateChart()` JavaScript function.
2. In your JS script, execute `setInterval(updateChart, 5000);` to poll the server every 5 seconds.
3. *Crucial:* When new data arrives, do not destroy and recreate the `canvas` HTML element. Instead, update `chart.data` properties with the fresh dataset and call `chart.update()`.

---

## **Testing Your Implementation**

### Testing Blueprints

1. All existing routes should work as before:
   - `/` - Dashboard
   - `/login` - Login page
   - `/signup` - Signup page
   - `/profile` - Profile form
   - `/api/profile` - Profile API (requires JWT)
   - `/api/sensor_data` POST - Submit sensor data (requires API key)

2. No functionality should be lost after refactoring.

### Testing Chart.js & Polling

1. Ensure your `mock_sensor_data.json` file is present and properly formatted.
2. Log in to the web application and view the dashboard.
3. The chart should display the 50 sensor data points immediately.
4. Open the Network tab in your browser's Developer Tools and verify that a new `GET` request to `/api/sensor_data` is made exactly every 5 seconds.
