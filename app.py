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

import tempfile

BASE_TEMP_DIR = os.path.join(tempfile.gettempdir(), "NeonStreamTemps")
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
        base_opts = {
            'quiet': True,
            'extract_flat': False,
            'nocheckcertificate': True,
        }
        
        info = None
        last_exc = None
        
        is_instagram = "instagram.com" in url
        browser_list = [None]

        
        for browser in browser_list:
            ydl_opts = dict(base_opts)
            
            # Prefer cookies.txt if it exists
            if os.path.exists('cookies.txt'):
                ydl_opts['cookiefile'] = 'cookies.txt'
            elif browser:
                ydl_opts['cookiesfrombrowser'] = (browser,)
                
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    break
            except Exception as e:
                last_exc = e
                
        if not info:
            if is_instagram and not os.path.exists('cookies.txt'):
                raise Exception("Instagram requires authentication. Please export your Instagram cookies using a browser extension and save them as 'cookies.txt' in the application folder.")
            raise last_exc
            
        # Extract thumbnail
        thumbnail = info.get('thumbnail')
        if not thumbnail and 'thumbnails' in info and info['thumbnails']:
            thumbnail = info['thumbnails'][-1].get('url', '')
            
        duration = info.get('duration', 0)
        # Instagram often returns a default placeholder duration of 90 seconds for reels.
        # If it is exactly 90, we set it to 0 to disable the trimmer timeline since it is inaccurate.
        if is_instagram and duration == 90:
            duration = 0
            
        return jsonify({
            "title": info.get('title', 'Unknown Title'),
            "thumbnail": thumbnail,
            "url": url,
            "length": duration
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
        
        base_opts = {
            'outtmpl': os.path.join(session_dir, '%(title)s.%(ext)s'),
            'ffmpeg_location': ffmpeg_exe,
            'quiet': True,
            'no_warnings': True,
            'restrictfilenames': True, # Ensures file is safe on all OS
            'nocheckcertificate': True,
            'format_sort': ['res', 'vcodec:h264', 'acodec:m4a']
        }
        
        if resolution == "mp3":
            base_opts['format'] = 'bestaudio/best'
            base_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:
            # Request H.264 video and the best available audio (ffmpeg will normalize the audio to AAC during copy)
            base_opts['format'] = f'bestvideo[height<={res_int}][vcodec^=avc1]+bestaudio/best[height<={res_int}][vcodec^=avc1]/best'
            base_opts['merge_output_format'] = 'mp4'

        success = False
        last_exc = None
        
        is_instagram = "instagram.com" in url
        browser_list = [None]

        
        for browser in browser_list:
            ydl_opts = dict(base_opts)
            
            if os.path.exists('cookies.txt'):
                ydl_opts['cookiefile'] = 'cookies.txt'
            elif browser:
                ydl_opts['cookiesfrombrowser'] = (browser,)
                
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                    success = True
                    break
            except Exception as e:
                last_exc = e
                
        if not success:
            if is_instagram and not os.path.exists('cookies.txt'):
                raise Exception("Instagram requires authentication. Please export your Instagram cookies to 'cookies.txt'.")
            raise last_exc


        # Get the downloaded file
        files = glob.glob(os.path.join(session_dir, "*"))
        if not files:
            return "Download failed", 500
        
        filename = files[0]
        base, ext = os.path.splitext(filename)

        if resolution != "mp3":
            # Always run a fast compatibility pass to ensure AAC audio and H.264 video.
            # Video stream is copied directly (-c:v copy) to prevent CPU usage/timeouts,
            # and audio stream is re-encoded to AAC (-c:a aac) to guarantee playback on all iOS and Android devices.
            out_file = f"{base}_compat.mp4"
            cmd = [ffmpeg_exe, "-y"]
            if start_time: cmd.extend(["-ss", start_time])
            if end_time: cmd.extend(["-to", end_time])
            
            cmd.extend([
                "-i", filename, 
                "-c:v", "copy", 
                "-c:a", "aac", 
                "-movflags", "+faststart", 
                out_file
            ])
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # If the fast copy/encode fails (e.g. video codec is not H.264 and copy fails),
            # fallback to full re-encoding
            if res.returncode != 0:
                cmd_reencode = [ffmpeg_exe, "-y"]
                if start_time: cmd_reencode.extend(["-ss", start_time])
                if end_time: cmd_reencode.extend(["-to", end_time])
                cmd_reencode.extend([
                    "-i", filename, 
                    "-c:v", "libx264", 
                    "-preset", "veryfast", 
                    "-pix_fmt", "yuv420p", 
                    "-c:a", "aac", 
                    "-movflags", "+faststart", 
                    out_file
                ])
                subprocess.run(cmd_reencode, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
            try: os.remove(filename)
            except: pass
            filename = out_file
        else:
            # For MP3, just handle trimming if needed
            if start_time or end_time:
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
        
        # Clean up older session directories (a simple cleanup routine)
        import time
        now = time.time()
        for folder in os.listdir(BASE_TEMP_DIR):
            folder_path = os.path.join(BASE_TEMP_DIR, folder)
            if os.path.isdir(folder_path):
                # If older than 1 hour, remove
                if os.stat(folder_path).st_mtime < now - 3600:
                    shutil.rmtree(folder_path, ignore_errors=True)

        mode = request.args.get("mode")
        if mode == "desktop":
            downloads_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
            os.makedirs(downloads_dir, exist_ok=True)
            
            # Ensure unique filename if it already exists
            final_path = os.path.join(downloads_dir, download_name)
            counter = 1
            base, ext = os.path.splitext(download_name)
            while os.path.exists(final_path):
                final_path = os.path.join(downloads_dir, f"{base}_{counter}{ext}")
                counter += 1
                
            shutil.move(filename, final_path)
            shutil.rmtree(session_dir, ignore_errors=True)
            return jsonify({"success": True, "message": f"Saved to Downloads folder as {os.path.basename(final_path)}"})

        return send_file(filename, as_attachment=True, download_name=download_name)
    except Exception as e:
         if os.path.isdir(session_dir):
            shutil.rmtree(session_dir, ignore_errors=True)
         return jsonify({"error": str(e)}), 500

@app.route('/sw.js')
def sw():
    response = app.send_static_file('sw.js')
    response.headers['Content-Type'] = 'application/javascript'
    return response

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
