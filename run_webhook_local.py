"""
Run FastAPI app locally for webhook testing
"""
import uvicorn
import os

# Set webhook mode
os.environ['LOCAL_MODE'] = 'false'
os.environ['WEBHOOK_MODE'] = 'true'

if __name__ == "__main__":
    print("🚀 Starting FastAPI app for webhook testing...")
    print("📡 Running on http://0.0.0.0:8000")
    print("🔗 Will receive callbacks from Robokassa")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
