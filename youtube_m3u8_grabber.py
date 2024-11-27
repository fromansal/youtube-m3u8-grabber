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
            'Cookie': 'CONSENT=YES+cb; YSC=DwKYllHNwEw; VISITOR_INFO1_LIVE=KbL2t0k3Iyk;'
        }
        self.session.headers.update(self.headers)

    def extract_video_id_from_channel(self, channel_url):
        """Extract live video ID from a YouTube channel."""
        try:
            print(f"Fetching channel URL: {channel_url}")
            response = self.session.get(channel_url, timeout=10)
            print(f"Response status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Failed to fetch channel. Status code: {response.status_code}")
                return None

            # Try different patterns to find live video ID
            patterns = [
                r'"videoId":"([^"]+)".*?"isLive":true',
                r'href="/watch\?v=([^"]+)".*?isLive":true',
                r'data-video-id="([^"]+)".*?isLive":true',
                r'"videoId":"([^"]+)","thumbnail"',
                r'href="/watch\?v=([^"]+)"'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, response.text)
                print(f"Found matches for pattern {pattern}: {matches}")
                if matches:
                    for video_id in matches:
                        print(f"Checking video ID: {video_id}")
                        # Verify if this video exists
                        watch_url = f'https://www.youtube.com/watch?v={video_id}'
                        watch_response = self.session.get(watch_url, timeout=10)
                        if watch_response.status_code == 200:
                            print(f"Found valid video ID: {video_id}")
                            return video_id
            
            print("No valid video ID found")
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
            
            # Try multiple methods to get the manifest URL
            methods = [
                self._try_direct_method,
                self._try_embed_method,
                self._try_android_api
            ]
            
            for method in methods:
                result = method(video_id)
                if result:
                    return result
            
            print("No manifest URL found after trying all methods")
            return None
                
        except Exception as e:
            print(f"Error getting M3U8 URLs: {str(e)}")
            return None

    def _try_direct_method(self, video_id):
        """Try getting manifest URL directly from watch page."""
        try:
            watch_url = f'https://www.youtube.com/watch?v={video_id}'
            response = self.session.get(watch_url, timeout=10)
            
            manifest_pattern = r'hlsManifestUrl":"([^"]+)"'
            manifest_matches = re.findall(manifest_pattern, response.text)
            
            if manifest_matches:
                manifest_url = manifest_matches[0].replace('\\u0026', '&')
                print(f"Found manifest URL (direct): {manifest_url}")
                
                m3u8_response = self.session.get(manifest_url, timeout=10)
                
                title_pattern = r'"title":"([^"]+)"'
                title_match = re.search(title_pattern, response.text)
                title = title_match.group(1) if title_match else "Unknown Title"
                
                return {
                    'master_m3u8_url': manifest_url,
                    'raw_m3u8_content': m3u8_response.text,
                    'video_id': video_id,
                    'title': title
                }
        except Exception as e:
            print(f"Direct method failed: {str(e)}")
        return None

    def _try_embed_method(self, video_id):
        """Try getting manifest URL from embed page."""
        try:
            embed_url = f'https://www.youtube.com/embed/{video_id}'
            response = self.session.get(embed_url, timeout=10)
            
            manifest_pattern = r'hlsManifestUrl":"([^"]+)"'
            manifest_matches = re.findall(manifest_pattern, response.text)
            
            if manifest_matches:
                manifest_url = manifest_matches[0].replace('\\u0026', '&')
                print(f"Found manifest URL (embed): {manifest_url}")
                
                m3u8_response = self.session.get(manifest_url, timeout=10)
                return {
                    'master_m3u8_url': manifest_url,
                    'raw_m3u8_content': m3u8_response.text,
                    'video_id': video_id
                }
        except Exception as e:
            print(f"Embed method failed: {str(e)}")
        return None

    def _try_android_api(self, video_id):
        """Try getting manifest URL using Android API."""
        try:
            api_url = 'https://youtubei.googleapis.com/youtubei/v1/player'
            data = {
                'videoId': video_id,
                'context': {
                    'client': {
                        'clientName': 'ANDROID',
                        'clientVersion': '18.11.34',
                        'androidSdkVersion': 30,
                        'hl': 'en',
                        'gl': 'US',
                        'clientScreen': 'WATCH'
                    }
                }
            }
            
            api_headers = {
                'User-Agent': 'com.google.android.youtube/18.11.34 (Linux; U; Android 11)',
                'Accept': '*/*',
                'Content-Type': 'application/json',
            }
            
            print("Trying Android API...")
            response = self.session.post(api_url, json=data, headers=api_headers, timeout=10)
            json_data = response.json()
            
            if 'streamingData' in json_data:
                hls_url = json_data['streamingData'].get('hlsManifestUrl')
                if hls_url:
                    print(f"Found manifest URL (Android API): {hls_url}")
                    m3u8_response = self.session.get(hls_url, timeout=10)
                    return {
                        'master_m3u8_url': hls_url,
                        'raw_m3u8_content': m3u8_response.text,
                        'video_id': video_id
                    }
        except Exception as e:
            print(f"Android API method failed: {str(e)}")
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