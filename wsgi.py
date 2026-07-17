"""WSGI entry point with import diagnostics."""
import sys
import os
import traceback

# Print diagnostics
print(f"Python: {sys.version}", flush=True)
print(f"CWD: {os.getcwd()}", flush=True)
print(f"Files in CWD: {os.listdir('.')}", flush=True)

try:
    from app import create_app
    print("✅ app.create_app imported", flush=True)
    app = create_app()
    print("✅ App created successfully", flush=True)
except Exception as e:
    print(f"❌ FATAL: {e}", flush=True)
    traceback.print_exc(file=sys.stdout)
    # Create a minimal fallback app
    from flask import Flask
    app = Flask(__name__)
    
    @app.route("/")
    @app.route("/health")
    def error_page():
        return f"<h1>Startup Error</h1><pre>{traceback.format_exc()}</pre>", 500
    
    print("⚠️ Using fallback error app", flush=True)
