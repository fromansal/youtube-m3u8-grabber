import requests
import json
import re
from urllib.parse import parse_qs, urlparse
from flask import Flask, request, jsonify
import os
import yt_dlp

app = Flask(__name__)

class YouTubeM3U8Grabber:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'DNT': '1',
        }
        self.session.headers.update(self.headers)
        
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'format': 'best',
        }

    def extract_video_id_from_channel(self, channel_url):
        """Extract live video ID from a YouTube channel."""
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(channel_url, download=False)
                if info and 'entries' in info:
                    for entry in info['entries']:
                        if entry.get('is_live', False):
                            return entry['id']
                elif info and info.get('is_live', False):
                    return info['id']
            return None
        except Exception as e:
            print(f"Error extracting channel video ID: {str(e)}")
            return None

    def extract_video_id(self, url):
        """Extract video ID from YouTube URL."""
        print(f"Extracting video ID from URL: {url}")
        
        if 'youtube.com/watch?v=' in url:
            return parse_qs(urlparse(url).query)['v'][0]
        elif 'youtu.be/' in url:
            return url.split('youtu.be/')[-1].split('?')[0]
        elif '/live' in url or 'youtube.com/channel/' in url or 'youtube.com/c/' in url:
            return self.extract_video_id_from_channel(url)
        return None

    def get_m3u8_urls(self, url):
        """Get M3U8 URLs from YouTube live stream."""
        try:
            video_id = self.extract_video_id(url)
            if not video_id:
                raise ValueError("Could not extract video ID from URL")

            print(f"Found video ID: {video_id}")
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'format': 'best',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f'https://www.youtube.com/watch?v={video_id}', download=False)
                
                if info:
                    formats = info.get('formats', [])
                    manifest_url = None
                    
                    # First try to find an HLS manifest
                    for f in formats:
                        if f.get('protocol') == 'm3u8_native':
                            manifest_url = f.get('url')
                            break
                    
                    if manifest_url:
                        print(f"Found manifest URL: {manifest_url}")
                        m3u8_response = self.session.get(manifest_url)
                        
                        return {
                            'master_m3u8_url': manifest_url,
                            'raw_m3u8_content': m3u8_response.text,
                            'video_id': video_id,
                            'title': info.get('title', 'Unknown Title')
                        }
                    
                    # If no HLS manifest found, try to get the best available stream URL
                    best_format = info.get('url')
                    if best_format:
                        return {
                            'stream_url': best_format,
                            'video_id': video_id,
                            'title': info.get('title', 'Unknown Title')
                        }
            
            print("No manifest URL found")
            return None
                
        except Exception as e:
            print(f"Error getting M3U8 URLs: {str(e)}")
            return None

@app.route('/get_m3u8', methods=['POST'])
def get_m3u8():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'No URL provided'}), 400
    
    youtube_url = data['url']
    grabber = YouTubeM3U8Grabber()
    
    try:
        result = grabber.get_m3u8_urls(youtube_url)
        if result:
            return jsonify(result)
        else:
            return jsonify({
                'error': 'Could not find M3U8 stream. Make sure this is a live stream.',
                'details': 'If this is a channel URL, make sure the channel is currently streaming.'
            }), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)