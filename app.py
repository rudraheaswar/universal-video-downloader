import os
import glob
import uuid
import shutil
import subprocess
from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
import yt_dlp
import imageio_ffmpeg

app = Flask(__name__)
CORS(app)

BASE_TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__name__)), "temps")
os.makedirs(BASE_TEMP_DIR, exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/info", methods=["POST"])
def get_info():
    data = request.json
    url = data.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': False,
            'nocheckcertificate': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
        # Extract thumbnail
        thumbnail = info.get('thumbnail')
        if not thumbnail and 'thumbnails' in info and info['thumbnails']:
            thumbnail = info['thumbnails'][-1].get('url', '')
            
        return jsonify({
            "title": info.get('title', 'Unknown Title'),
            "thumbnail": thumbnail,
            "url": url,
            "length": info.get('duration', 0)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/download", methods=["GET"])
def download_video():
    url = request.args.get("url")
    resolution = request.args.get("res", "720")
    start_time = request.args.get("start")
    end_time = request.args.get("end")
    
    if not url:
        return "URL parameter is required", 400
        
    try:
        if resolution != "mp3":
            res_int = int(resolution)
        else:
            res_int = 0
    except ValueError:
        return "Invalid resolution", 400

    # Create a unique temp directory for this download session
    session_id = str(uuid.uuid4())
    session_dir = os.path.join(BASE_TEMP_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)

    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        
        ydl_opts = {
            'outtmpl': os.path.join(session_dir, '%(title)s.%(ext)s'),
            'ffmpeg_location': ffmpeg_exe,
            'quiet': True,
            'no_warnings': True,
            'restrictfilenames': True, # Ensures file is safe on all OS
            'nocheckcertificate': True,
        }
        
        if resolution == "mp3":
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:
            # We request the best video up to the given resolution and best audio
            ydl_opts['format'] = f'bestvideo[height<={res_int}]+bestaudio/best'
            ydl_opts['merge_output_format'] = 'mp4'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Get the downloaded file
        files = glob.glob(os.path.join(session_dir, "*"))
        if not files:
            return "Download failed", 500
        
        filename = files[0]

        # Trimming if requested
        if start_time or end_time:
            base, ext = os.path.splitext(filename)
            out_file = f"{base}_trimmed{ext}"
            
            cmd = [ffmpeg_exe, "-y"]
            if start_time: cmd.extend(["-ss", start_time])
            if end_time: cmd.extend(["-to", end_time])
            cmd.extend(["-i", filename, "-c", "copy", out_file])
            
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            try: os.remove(filename)
            except: pass
            filename = out_file

        download_name = os.path.basename(filename)
        
        # After send_file we ideally delete the folder, but send_file is async.
        # We can clean up older folders occasionally.
        # Clean up older session directories (a simple cleanup routine)
        import time
        now = time.time()
        for folder in os.listdir(BASE_TEMP_DIR):
            folder_path = os.path.join(BASE_TEMP_DIR, folder)
            if os.path.isdir(folder_path):
                # If older than 1 hour, remove
                if os.stat(folder_path).st_mtime < now - 3600:
                    shutil.rmtree(folder_path, ignore_errors=True)

        return send_file(filename, as_attachment=True, download_name=download_name)
    except Exception as e:
        # On error, clean up session dir immediately
        shutil.rmtree(session_dir, ignore_errors=True)
        return str(e), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
