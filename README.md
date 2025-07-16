# Mouse Flow Tracking System

A Flask-based web application that captures mouse movements, clicks, and scroll events from web pages and generates videos showing the actual web page with mouse interactions using Selenium and OpenCV.

## Features

- **Real-time mouse tracking**: Captures mouse movements, clicks, and scroll events
- **Video generation**: Creates videos showing the actual web page with mouse interactions
- **Session management**: View and manage recorded sessions
- **Dashboard**: Web interface to view all recorded sessions

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Chrome WebDriver

The application uses Selenium with Chrome. You need to have Chrome browser installed and the ChromeDriver.

**Option A: Automatic (Recommended)**
```bash
pip install webdriver-manager
```

Then update the app.py to use webdriver-manager:
```python
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Replace the driver initialization with:
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
```

**Option B: Manual**
1. Download ChromeDriver from: https://chromedriver.chromium.org/
2. Add it to your system PATH or place it in the project directory

### 3. Test the Setup

Run the test script to verify everything is working:

```bash
python test_selenium_setup.py
```

### 4. Run the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Usage

### 1. Embed the Tracking Script

Add this script to the `<head>` of any webpage you want to track:

```html
<script src="http://localhost:5000/static/tracker.js"></script>
```

### 2. View Sessions

Visit `http://localhost:5000/sessions` to see all recorded sessions.

### 3. Generate Videos

Click the "Generate Video" button for any session to create a video showing the actual web page with mouse interactions.

## Configuration

### Change Target URL

In `app.py`, modify the `target_url` variable in the `generate_video` function:

```python
target_url = 'https://your-website.com'  # Change this to your target website
```

### Video Settings

You can adjust video quality and timing in the `generate_video` function:

- `fps = 10` - Frames per second
- `time_per_event` - Time between events
- Window size: `--window-size=1280,720`

## File Structure

```
Mouse_Flow/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── test_selenium_setup.py # Test script
├── static/
│   ├── tracker.js        # JavaScript tracking script
│   └── videos/          # Generated videos
└── templates/
    └── dashboard.html    # Web dashboard
```

## Troubleshooting

### Common Issues

1. **ChromeDriver not found**: Install webdriver-manager or download ChromeDriver manually
2. **Video not generating**: Check that Chrome is installed and accessible
3. **Selenium errors**: Ensure Chrome browser is installed and up to date

### Debug Mode

Run the application in debug mode for more detailed error messages:

```python
app.run(debug=True, host='0.0.0.0', port=5000)
```

## API Endpoints

- `POST /collect` - Collect mouse events
- `GET /sessions` - View all sessions
- `GET /session/<id>` - Get session details
- `POST /generate_video/<id>` - Generate video for session
- `DELETE /delete_session/<id>` - Delete session
- `DELETE /clear_sessions` - Clear all sessions

## How It Works

1. **Data Collection**: The JavaScript tracker captures mouse events and sends them to the Flask backend
2. **Session Storage**: Events are stored in SQLite database with timestamps
3. **Video Generation**: Selenium opens a browser, replays the recorded events, and captures screenshots
4. **Video Creation**: OpenCV combines screenshots into a video with mouse cursor overlays

## Security Notes

- This is a development setup. For production, add proper authentication and security measures
- The tracking script should be served over HTTPS in production
- Consider rate limiting and input validation for the `/collect` endpoint
