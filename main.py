import threading
import webview
import time
from app import app
import os
import sys

def get_base_path():
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def start_server():
    # Flask will serve from its defined templates/static folder
    # In PyInstaller, the templates and static folders are packed into sys._MEIPASS
    app.template_folder = os.path.join(get_base_path(), 'templates')
    app.static_folder = os.path.join(get_base_path(), 'static')
    app.run(host='127.0.0.1', port=5001, use_reloader=False)

if __name__ == '__main__':
    # Start Flask server in a daemon thread
    t = threading.Thread(target=start_server)
    t.daemon = True
    t.start()
    
    # Wait a tiny bit for the server to bind the port
    time.sleep(1)

    # Create the native window
    webview.create_window(
        title='NeonStream - Premium YouTube Downloader', 
        url='http://127.0.0.1:5001',
        width=900, 
        height=800,
        resizable=True,
        text_select=True
    )
    
    webview.start()
