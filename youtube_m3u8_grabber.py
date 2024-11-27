import requests
import json
import re
from urllib.parse import parse_qs, urlparse
from flask import Flask, request, jsonify
import os

app = Flask(__name__)

class YouTubeM3U8Grabber:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        self.session.headers.update(self.headers)

    def extract_video_id_from_channel(self, channel_url):
        """Extract live video ID from a YouTube channel."""
        try:
            print(f"Fetching channel URL: {channel_url}")
            response = self.session.get(channel_url)
            
            if response.status_code != 200:
                print(f"Failed to fetch channel. Status code: {response.status_code}")
                return None

            patterns = [
                r'"videoId":"([^"]+)".*?"isLive":true',
                r'href="/watch\?v=([^"]+)".*?isLive":true',
                r'data-video-id="([^"]+)".*?isLive":true'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, response.text)
                if matches:
                    return matches[0]
            
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
            
            # First try the direct video URL
            watch_url = f'https://www.youtube.com/watch?v={video_id}'
            response = self.session.get(watch_url)
            
            # Look for the hlsManifestUrl in the page source
            manifest_pattern = r'hlsManifestUrl":"([^"]+)"'
            manifest_matches = re.findall(manifest_pattern, response.text)
            
            if manifest_matches:
                manifest_url = manifest_matches[0].replace('\\u0026', '&')
                print(f"Found manifest URL: {manifest_url}")
                
                # Get the M3U8 content
                m3u8_response = self.session.get(manifest_url)
                
                # Extract video title
                title_pattern = r'"title":"([^"]+)"'
                title_match = re.search(title_pattern, response.text)
                title = title_match.group(1) if title_match else "Unknown Title"
                
                return {
                    'master_m3u8_url': manifest_url,
                    'raw_m3u8_content': m3u8_response.text,
                    'video_id': video_id,
                    'title': title
                }
            
            # If not found, try the embed URL
            embed_url = f'https://www.youtube.com/embed/{video_id}'
            embed_response = self.session.get(embed_url)
            manifest_matches = re.findall(manifest_pattern, embed_response.text)
            
            if manifest_matches:
                manifest_url = manifest_matches[0].replace('\\u0026', '&')
                print(f"Found manifest URL from embed: {manifest_url}")
                m3u8_response = self.session.get(manifest_url)
                
                return {
                    'master_m3u8_url': manifest_url,
                    'raw_m3u8_content': m3u8_response.text,
                    'video_id': video_id
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