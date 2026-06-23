# Saltoria Tools :: yt-dlp Audio API
# Deploy di Railway. Terima URL, return audio stream langsung.

import os
import subprocess
import tempfile
import mimetypes
from flask import Flask, request, Response, jsonify

app = Flask(__name__)

SUPPORTED_EXTS = {'mp3', 'ogg', 'wav', 'opus', 'm4a'}
MAX_DURATION_SEC = 600  # 10 menit max

def err(msg, code=400):
    return jsonify({'error': msg}), code

@app.route('/', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'saltoria-ytdlp', 'version': '1.0'})

@app.route('/audio', methods=['POST'])
def download_audio():
    data = request.get_json(silent=True) or {}
    url      = data.get('url', '').strip()
    fmt      = data.get('format', 'mp3').lower()
    bitrate  = str(data.get('bitrate', '128'))

    if not url:
        return err('Missing url')
    if fmt not in SUPPORTED_EXTS:
        return err(f'Unsupported format: {fmt}')
    if bitrate not in ['320','256','128','96','64']:
        bitrate = '128'

    with tempfile.TemporaryDirectory() as tmpdir:
        out_tmpl = os.path.join(tmpdir, 'audio.%(ext)s')

        # yt-dlp command
        cmd = [
            'yt-dlp',
            '--no-playlist',
            '--max-filesize', '80m',
            '--match-filter', f'duration <= {MAX_DURATION_SEC}',
            '-x',                          # extract audio only
            '--audio-format', fmt,
            '--audio-quality', bitrate + 'K' if fmt != 'opus' else '0',
            '--no-warnings',
            '-o', out_tmpl,
            url
        ]

        # Add cookies file if present (optional, for YouTube bot bypass)
        cookies_path = os.environ.get('COOKIE_PATH')
        if cookies_path and os.path.isfile(cookies_path):
            cmd += ['--cookies', cookies_path]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=90
            )
        except subprocess.TimeoutExpired:
            return err('Download timeout (>90s) — coba video yang lebih pendek', 504)

        if result.returncode != 0:
            stderr = result.stderr or ''
            # Friendly error messages
            if 'Video unavailable' in stderr or 'Private video' in stderr:
                msg = 'Video tidak tersedia atau private'
            elif 'age' in stderr.lower() and 'restricted' in stderr.lower():
                msg = 'Video age-restricted — tambahkan cookies YouTube'
            elif 'duration' in stderr.lower() or 'match-filter' in stderr.lower():
                msg = f'Video terlalu panjang (max {MAX_DURATION_SEC//60} menit)'
            elif 'not supported' in stderr.lower() or 'Unsupported URL' in stderr:
                msg = 'Platform tidak didukung'
            else:
                msg = 'Download gagal: ' + stderr[-300:].strip()
            return err(msg, 502)

        # Find the output file
        out_file = None
        for f in os.listdir(tmpdir):
            if f.startswith('audio.'):
                out_file = os.path.join(tmpdir, f)
                break

        if not out_file or not os.path.isfile(out_file):
            return err('Output file tidak ditemukan setelah download', 502)

        file_size = os.path.getsize(out_file)
        if file_size == 0:
            return err('File audio kosong (0 bytes)', 502)

        # Read and return
        with open(out_file, 'rb') as f:
            audio_data = f.read()

        ext = os.path.splitext(out_file)[1].lstrip('.')
        content_type = {
            'mp3':  'audio/mpeg',
            'ogg':  'audio/ogg',
            'wav':  'audio/wav',
            'opus': 'audio/opus',
            'm4a':  'audio/mp4',
        }.get(ext, 'audio/mpeg')

        return Response(
            audio_data,
            status=200,
            mimetype=content_type,
            headers={
                'Content-Length': str(len(audio_data)),
                'Cache-Control': 'no-store',
                'X-Audio-Size': str(file_size),
            }
        )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
