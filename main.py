"""
Main application entry point for SDASystem
"""
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from backend.api.routes import app


# Mount static files
if os.path.exists("frontend/static"):
    app.mount("/static", StaticFiles(directory="frontend/static"), name="static")


@app.get("/ui")
@app.get("/ui/{path:path}")
async def serve_ui(path: str = ""):
    """Serve the UI"""
    ui_file = "frontend/templates/index.html"
    if os.path.exists(ui_file):
        return FileResponse(ui_file)
    return {"message": "UI not found. Please check frontend/templates/index.html"}


if __name__ == "__main__":
    print("=" * 60)
    print("SDASystem v0.1 - Story Driven Analytical System")
    print("=" * 60)
    print("Starting server...")
    print("API Documentation: http://localhost:8000/docs")
    print("UI Interface: http://localhost:8000/ui")
    print("=" * 60)

    uvicorn.run(
        "main:app",
        host="127.0.0.1",  # Use localhost explicitly to avoid IPv6 issues
        port=8000,
        reload=True,
        log_level="info"
    )
