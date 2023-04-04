from app import app, Ampi
import threading

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run().start())
    ampi.run()
