import os
import asyncio
import uvicorn
from multiprocessing import Process
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import the lightspeed-stack FastAPI app
from lightspeed_stack.app.main import app
from metrics_server import start_metrics_server


def run_lightspeed_service():
    """Run the lightspeed-stack service on port 8000."""
    # Set the config path for lightspeed-stack
    os.environ["LIGHTSPEED_STACK_CONFIG_PATH"] = "lightspeed-stack.yaml"

    # Run the imported FastAPI app
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        access_log=True
    )


def run_metrics_server():
    """Run the Prometheus metrics server on port 9000."""
    start_metrics_server()


if __name__ == "__main__":
    # Start metrics server in a separate process
    metrics_process = Process(target=run_metrics_server)
    metrics_process.start()

    print("Starting Lightspeed Stack on port 8000...")
    print("Starting Metrics Server on port 9000...")

    try:
        # Run the main lightspeed service
        run_lightspeed_service()
    finally:
        metrics_process.terminate()
        metrics_process.join()