# YouTube M3U8 Grabber

This Python script allows you to extract M3U8 URLs from YouTube live streams using various methods including direct parsing and custom request headers.

## Features

- Extracts M3U8 URLs from YouTube live streams
- Supports both channel URLs and direct video URLs
- Uses multiple fallback methods to ensure reliable extraction
- Handles custom headers and parameters for requests
- Provides both master M3U8 URL and playlist content

## Installation

1. Clone this repository
2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the script:
```bash
python youtube_m3u8_grabber.py
```

Enter a YouTube live channel or video URL when prompted. The script will attempt to extract and display the M3U8 URL and content.

## Requirements

- Python 3.6+
- requests
- pytube
- yt-dlp

## Note

This tool is for educational purposes only. Please respect YouTube's terms of service and content creators' rights when using this tool.
