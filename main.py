import os
import threading
import time
import webbrowser

from app import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    if os.getenv("OPEN_BROWSER", "0") == "1":
        threading.Thread(target=lambda: (time.sleep(1.5), webbrowser.open(f"http://{host}:{port}")), daemon=True).start()
    uvicorn.run(app, host=host, port=port)
