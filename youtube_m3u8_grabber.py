import requests
import json
import re
from urllib.parse import parse_qs, urlparse
from flask import Flask, request, jsonify
import os
import random
import time

app = Flask(__name__)

class YouTubeM3U8Grabber:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'com.google.android.youtube/17.31.35 (Linux; U; Android 11) gzip',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/json',
            'X-Goog-Api-Key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'
        }
        self.session.headers.update(self.headers)
        self.client_version = "17.31.35"
        self.client_name = "ANDROID"
        self.api_key = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
        self.context = {
            "client": {
                "clientName": self.client_name,
                "clientVersion": self.client_version,
                "androidSdkVersion": 30,
                "osName": "Android",
                "osVersion": "11",
                "platform": "MOBILE"
            },
            "user": {
                "lockedSafetyMode": False
            }
        }

    def _get_video_info(self, video_id):
        """Get video info using innertube API."""
        url = f"https://youtubei.googleapis.com/youtubei/v1/player?key={self.api_key}"
        
        data = {
            "videoId": video_id,
            "context": self.context,
            "playbackContext": {
                "contentPlaybackContext": {
                    "html5Preference": "HTML5_PREF_WANTS"
                }
            },
            "racyCheckOk": True,
            "contentCheckOk": True
        }
        
        try:
            response = self.session.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error getting video info: {str(e)}")
            return None

    def extract_video_id_from_channel(self, channel_url):
        """Extract live video ID from a YouTube channel."""
        try:
            response = self.session.get(channel_url)
            if response.status_code != 200:
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
            
            # Get video info using innertube API
            video_info = self._get_video_info(video_id)
            if not video_info:
                raise ValueError("Could not get video info")
            
            # Extract streaming data
            streaming_data = video_info.get('streamingData', {})
            
            # First try to get HLS manifest
            hls_manifest_url = streaming_data.get('hlsManifestUrl')
            if hls_manifest_url:
                print(f"Found HLS manifest URL: {hls_manifest_url}")
                m3u8_response = self.session.get(hls_manifest_url)
                
                return {
                    'master_m3u8_url': hls_manifest_url,
                    'raw_m3u8_content': m3u8_response.text,
                    'video_id': video_id,
                    'title': video_info.get('videoDetails', {}).get('title', 'Unknown Title')
                }
            
            # If no HLS manifest, try to get adaptive formats
            formats = streaming_data.get('adaptiveFormats', [])
            if formats:
                # Get the highest quality video stream
                video_streams = [f for f in formats if f.get('mimeType', '').startswith('video/')]
                if video_streams:
                    best_stream = max(video_streams, key=lambda x: x.get('bitrate', 0))
                    return {
                        'stream_url': best_stream['url'],
                        'video_id': video_id,
                        'title': video_info.get('videoDetails', {}).get('title', 'Unknown Title'),
                        'format': best_stream.get('mimeType', 'unknown')
                    }
            
            print("No stream URL found")
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
                'error': 'Could not find stream URL. Make sure this is a live stream.',
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