import sys
import traceback

try:
    from app import create_app
    app = create_app()
    print("✅ App started successfully", flush=True)
except Exception as e:
    print(f"❌ App failed to start: {e}", flush=True)
    traceback.print_exc(file=sys.stdout)
    sys.exit(1)
