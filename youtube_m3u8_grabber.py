import requests
import json
import re
from urllib.parse import parse_qs, urlparse, urljoin
from flask import Flask, request, jsonify
import os
import random
import time

app = Flask(__name__)

class YouTubeM3U8Grabber:
    def __init__(self):
        self.session = requests.Session()
        self.client_version = "18.48.37"
        self.api_key = "AIzaSyDCU8hByM-4DrUqRUYnGn-3llEO78bcxq8"
        self.client = {
            "clientName": "ANDROID",
            "clientVersion": self.client_version,
            "androidSdkVersion": 31,
            "osName": "Android",
            "osVersion": "12",
            "platform": "MOBILE",
            "clientFormFactor": "UNKNOWN_FORM_FACTOR",
            "userAgent": f"com.google.android.youtube/{self.client_version} (Linux; U; Android 12) gzip",
            "timeZone": "UTC",
            "browserName": "Chrome",
            "browserVersion": "102.0.0.0",
            "acceptHeader": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "deviceMake": "Google",
            "deviceModel": "Pixel 6",
            "utcOffsetMinutes": 0,
        }
        self.context = {
            "client": self.client,
            "thirdParty": {
                "embedUrl": "https://www.youtube.com"
            }
        }
        self.headers = {
            "User-Agent": self.client["userAgent"],
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
            "X-YouTube-Client-Name": "3",
            "X-YouTube-Client-Version": self.client_version,
            "Origin": "https://www.youtube.com",
            "Referer": "https://www.youtube.com"
        }
        self.session.headers.update(self.headers)

    def _get_video_info(self, video_id):
        """Get video info using innertube API."""
        url = f"https://www.youtube.com/youtubei/v1/player?key={self.api_key}"
        
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

    def _get_initial_data(self, video_id):
        """Get initial data from watch page."""
        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            response = self.session.get(watch_url)
            response.raise_for_status()
            
            # Extract ytInitialData
            match = re.search(r'ytInitialData\s*=\s*({.+?});', response.text)
            if match:
                return json.loads(match.group(1))
            return None
        except Exception as e:
            print(f"Error getting initial data: {str(e)}")
            return None

    def _get_channel_id(self, channel_url):
        """Get channel ID from custom URL."""
        try:
            response = self.session.get(channel_url)
            response.raise_for_status()
            
            # Try to find channel ID in meta tags
            channel_id_match = re.search(r'<meta itemprop="channelId" content="([^"]+)">', response.text)
            if channel_id_match:
                return channel_id_match.group(1)
            
            # Try to find channel ID in page source
            channel_id_pattern = r'"channelId":"([^"]+)"'
            channel_id_match = re.search(channel_id_pattern, response.text)
            if channel_id_match:
                return channel_id_match.group(1)
                
            return None
        except Exception as e:
            print(f"Error getting channel ID: {str(e)}")
            return None

    def _get_live_broadcast_content(self, channel_id):
        """Get live broadcast content using YouTube Data API."""
        url = f"https://www.youtube.com/youtubei/v1/browse?key={self.api_key}"
        data = {
            "context": self.context,
            "browseId": channel_id,
            "params": "EgJAAQ%3D%3D"  # Filter for live streams
        }
        
        try:
            response = self.session.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error getting live broadcast content: {str(e)}")
            return None

    def extract_video_id_from_channel(self, channel_url):
        """Extract live video ID from a YouTube channel."""
        try:
            print(f"Processing channel URL: {channel_url}")
            
            # First, try to get channel ID
            channel_id = self._get_channel_id(channel_url)
            if channel_id:
                print(f"Found channel ID: {channel_id}")
                browse_data = self._get_live_broadcast_content(channel_id)
                
                if browse_data:
                    # Try to find live video in browse response
                    tabs = browse_data.get('contents', {}).get('twoColumnBrowseResultsRenderer', {}).get('tabs', [])
                    for tab in tabs:
                        if 'tabRenderer' in tab:
                            items = tab['tabRenderer'].get('content', {}).get('richGridRenderer', {}).get('contents', [])
                            for item in items:
                                if 'richItemRenderer' in item:
                                    video = item['richItemRenderer'].get('content', {}).get('videoRenderer', {})
                                    badges = video.get('badges', [])
                                    for badge in badges:
                                        if badge.get('metadataBadgeRenderer', {}).get('label') == 'LIVE':
                                            video_id = video.get('videoId')
                                            if video_id:
                                                print(f"Found live video ID: {video_id}")
                                                return video_id
            
            # If channel ID method fails, try direct page scraping
            print("Trying direct page scraping...")
            response = self.session.get(channel_url)
            response.raise_for_status()
            page_content = response.text
            
            # Try multiple patterns
            patterns = [
                r'"videoId":"([^"]+)".*?"isLive":true',
                r'href="/watch\?v=([^"]+)".*?isLive":true',
                r'data-video-id="([^"]+)".*?isLive":true',
                r'"videoId":"([^"]+)".*?"badges":\[{"metadataBadgeRenderer":{"label":"LIVE"',
                r'"url":"/watch\?v=([^"]+)".*?"badges":\[{"metadataBadgeRenderer":{"label":"LIVE"'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, page_content)
                if matches:
                    video_id = matches[0]
                    print(f"Found video ID using pattern: {video_id}")
                    
                    # Verify if this is actually a live video
                    watch_url = f'https://www.youtube.com/watch?v={video_id}'
                    watch_response = self.session.get(watch_url)
                    if 'isLive":true' in watch_response.text:
                        print(f"Verified live video ID: {video_id}")
                        return video_id
            
            print("No live video ID found")
            return None
            
        except Exception as e:
            print(f"Error extracting channel video ID: {str(e)}")
            return None

    def extract_video_id(self, url):
        """Extract video ID from YouTube URL."""
        print(f"Extracting video ID from URL: {url}")
        
        if 'youtube.com/watch?v=' in url:
            video_id = parse_qs(urlparse(url).query)['v'][0]
            print(f"Found video ID from watch URL: {video_id}")
            return video_id
        elif 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[-1].split('?')[0]
            print(f"Found video ID from short URL: {video_id}")
            return video_id
        elif '/live' in url or 'youtube.com/channel/' in url or 'youtube.com/c/' in url:
            video_id = self.extract_video_id_from_channel(url)
            if video_id:
                print(f"Found video ID from channel: {video_id}")
            else:
                print("Could not find video ID from channel")
            return video_id
        
        print("URL format not recognized")
        return None

    def get_m3u8_urls(self, url):
        """Get M3U8 URLs from YouTube live stream."""
        try:
            video_id = self.extract_video_id(url)
            if not video_id:
                raise ValueError("Could not extract video ID from URL")

            print(f"Processing video ID: {video_id}")
            
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