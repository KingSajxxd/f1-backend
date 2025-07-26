import os
import asyncio
import uvicorn
import json

from app.state.state_manager import StateManager
from app.streaming.f1_stream_processor import F1StreamProcessor
from app.utils.helpers import DateTimeEncoder

# Import the API router
from app.api.main import app as api_app, get_state_manager

async def main():
    print("--- F1 Live Timing Backend Starting ---")

    # 1. Initialize the core components (no change here)
    state_manager = StateManager()

    # Override the placeholder `get_state_manager` with our actual instance
    api_app.dependency_overrides[get_state_manager] = lambda: state_manager

    
    f1_processor = F1StreamProcessor(
        state_manager=state_manager
    )

    # 2. Configure the Uvicorn server to run our FastAPI app
    config = uvicorn.Config(api_app, host="0.0.0.0", port=8000, log_level="info")
    api_server = uvicorn.Server(config)
    
    # --- CHOOSE YOUR MODE BASED ON THE ENVIRONMENT VARIABLE---
    mode = os.getenv("MODE", "LIVE")  # Default to "LIVE" if not set

    if mode == "REPLAY":
        print("--- Running in REPLAY mode ---")
        replay_file = os.getenv("REPLAY_FILE_PATH", "data/default_replay.jsonl")
        f1_processor_task = asyncio.create_task(f1_processor.replay_from_file(
        filepath=replay_file,
        # Set to 1.0 for real-time, or higher for faster replay
        speed=50
        ))
    else:
        print("--- Running in LIVE mode ---")
        f1_processor_task = asyncio.create_task(f1_processor.connect_and_process_live())
    
    api_task = asyncio.create_task(api_server.serve())

    try:
        # 3. Run the tasks concurrently
        await asyncio.gather(f1_processor_task, api_task)
    finally:
        # 4. NEW: This 'finally' block will ALWAYS run, whether the
        # program finishes normally or is interrupted by Ctrl+C.
        print("\n--- Application shutting down. Saving state... ---")

        # Get the final state from the StateManager
        final_state = state_manager.get_full_state()
        output_filename = "final_structured_state.json"

        # Write the state to a nicely formatted JSON file
        with open(output_filename, 'w') as f:
            json.dump(final_state, f, indent=2, cls=DateTimeEncoder)

        print(f"✅ Success! Final state saved to '{output_filename}'")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n--- Application shutting down ---")