"""
Entry point for the bundled backend executable.
This file is used by PyInstaller to create the standalone .exe
"""
import os
import sys
import io

# Fix Unicode encoding for Windows console (allows emojis in print statements)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import uvicorn

# Add the current directory to path for module resolution
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    application_path = sys._MEIPASS
    os.chdir(os.path.dirname(sys.executable))
else:
    # Running as script
    application_path = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, application_path)

# ==========================================
# Set up User Data Directory (Writable)
# ==========================================
from pathlib import Path

# Use ~/.surveyscriber as the working directory for data
USER_DATA_DIR = Path.home() / ".surveyscriber"
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Change working directory to user data dir so relative paths (like "data/") work
os.chdir(USER_DATA_DIR)

# Create data subdirectories
os.makedirs('data/uploads', exist_ok=True)
os.makedirs('data/output', exist_ok=True)

print(f"User Data Directory: {USER_DATA_DIR}")
print(f"Working Directory set to: {os.getcwd()}")

# Import and run the FastAPI app
# uvicorn is imported at the top now

if __name__ == "__main__":
    print("Starting SurveyScriber Backend Server...")
    print(f"   Application path: {application_path}")
    
    # Import the app after setting up paths
    from backend.main import app
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info"
    )
