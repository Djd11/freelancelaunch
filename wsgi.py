"""WSGI entry point with import diagnostics."""
import sys
import os
import traceback

# Store startup error globally so fallback can display it
_startup_error = None

print(f"Python: {sys.version}", flush=True)
print(f"CWD: {os.getcwd()}", flush=True)
print(f"Files in CWD: {os.listdir('.')}", flush=True)

try:
    from app import create_app
    print("✅ app.create_app imported", flush=True)
    app = create_app()
    print("✅ App created successfully", flush=True)
except Exception as e:
    _startup_error = traceback.format_exc()
    print(f"❌ FATAL: {e}", flush=True)
    print(_startup_error, flush=True)
    
    # Create a minimal fallback app that shows the error
    from flask import Flask
    fallback_app = Flask(__name__)
    
    @fallback_app.route("/")
    @fallback_app.route("/health")
    def error_page():
        global _startup_error
        return f"""<html><body>
<h1>Startup Error</h1>
<pre style="background:#fdd;padding:20px;border-radius:8px;overflow:auto;max-height:80vh">
{_startup_error}
</pre>
</body></html>""", 500, {"Content-Type": "text/html"}
    
    app = fallback_app
    print("⚠️ Using fallback error app", flush=True)
