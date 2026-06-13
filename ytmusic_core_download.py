from ytmusicapi import YTMusic
import requests
import json
import os
import sys
from datetime import datetime, timedelta
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
import gzip
import urllib.parse
import hashlib
import yt_dlp

raw_dir = "./raw_responses"
download_base = "./downloads"
class YouTubeMusicHybrid:
    def __init__(self):
        self.ytmusic = YTMusic()
        self.session = requests.Session()
        self.base_url = "https://music.youtube.com/youtubei/v1/"
        self._visitor_data = None
        self.context = {
            "client": {
                "clientName": "WEB_REMIX",
                "clientVersion": "1.20260302.03.01",
                "hl": "en",
                "gl": "VN",
                "utcOffsetMinutes": 420,
                "timeZone": "Asia/Bangkok",
                "platform": "DESKTOP",
                "userInterfaceTheme": "USER_INTERFACE_THEME_DARK",
            }
        }

    def _build_context(self):
        """Build context, injecting visitorData if we have it"""
        ctx = {"client": self.context["client"].copy()}
        if self._visitor_data:
            ctx["client"]["visitorData"] = self._visitor_data
        return ctx

    def browse_raw(self, browse_id=None, params=None, continuation=None, click_tracking_params=None):
        if continuation:
            url_encoded_token = urllib.parse.quote(continuation, safe='')
            parts = [
                f"ctoken={url_encoded_token}",
                f"continuation={url_encoded_token}",
                "type=next",
                "prettyPrint=false",
            ]
            if click_tracking_params:
                parts.append(f"itct={urllib.parse.quote(click_tracking_params, safe='')}")
            endpoint = f"{self.base_url}browse?" + "&".join(parts)
        else:
            endpoint = f"{self.base_url}browse?prettyPrint=false"

        payload = {"context": self._build_context()}
        
        if not continuation:
            if browse_id:
                payload["browseId"] = browse_id
            if params:
                payload["params"] = params

        compressed_body = gzip.compress(json.dumps(payload).encode('utf-8'))
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/json',
            'Content-Encoding': 'gzip',
            'Origin': 'https://music.youtube.com',
            'Referer': f'https://music.youtube.com/browse/{browse_id or ""}',
            'X-Origin': 'https://music.youtube.com',
            'X-Youtube-Client-Name': '67',
            'X-Youtube-Client-Version': '1.20260302.03.01',
            'X-Youtube-Bootstrap-Logged-In': 'false',
        }
        
        if self._visitor_data:
            headers['X-Goog-Visitor-Id'] = self._visitor_data

        response = self.session.post(endpoint, data=compressed_body, headers=headers)
        
        if response.status_code != 200:
            print(f"HTTP {response.status_code}: {response.text[:500]}")
            return {}
        
        data = response.json()
        
        visitor_data = (data.get('responseContext', {})
                           .get('visitorData'))
        if visitor_data and not self._visitor_data:
            self._visitor_data = visitor_data
            print(f"✅ Got visitorData: {visitor_data[:30]}...")
        
        return data

    def _generate_sapisidhash(self):
        if not self.sapisid:
            raise ValueError("No SAPISID found in cookies")
        
        timestamp = int(time.time())
        origin = "https://music.youtube.com"
        raw = f"{timestamp} {self.sapisid} {origin}"
        sha1 = hashlib.sha1(raw.encode()).hexdigest()
        
        return f"SAPISIDHASH {timestamp}_{sha1}"

    def _get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/json',
            'Origin': 'https://music.youtube.com',
            'Referer': 'https://music.youtube.com',
            'X-Origin': 'https://music.youtube.com',
            'X-Goog-AuthUser': self.auth.get('x-goog-authuser') or self.auth.get('X-Goog-AuthUser', '0'),
            'X-Youtube-Client-Name': '67',
            'X-Youtube-Client-Version': '1.20260225.03.00',
            'X-Youtube-Bootstrap-Logged-In': 'true',
            'Authorization': self._generate_sapisidhash(),
        }
    
    def get_artist_with_params(self, channel_id):
        """Get artist data including browseId and params for albums and singles"""
        print(f"Fetching artist data for channel ID: {channel_id}")
        artist_data = self.ytmusic.get_artist(channel_id)
        
        albums_info = {}
        if 'albums' in artist_data:
            albums_info = {
                'browseId': artist_data['albums'].get('browseId'),
                'params': artist_data['albums'].get('params'),
                'results': artist_data['albums'].get('results', [])
            }
            print(f"Found albums browseId: {albums_info['browseId']}")
            print(f"Found albums params: {albums_info['params']}")
        
        singles_info = {}
        if 'singles' in artist_data:
            singles_info = {
                'browseId': artist_data['singles'].get('browseId'),
                'params': artist_data['singles'].get('params'),
                'results': artist_data['singles'].get('results', [])
            }
            print(f"Found singles/EPs browseId: {singles_info['browseId']}")
            print(f"Found singles/EPs params: {singles_info['params']}")
        
        return {
            'artist_data': artist_data,
            'albums': albums_info,
            'singles': singles_info
        }
    
    def fetch_all_pages_raw(self, browse_id, params):
        """Fetch all pages of a browse request and return raw responses"""
        if not browse_id or not params:
            print("Missing browseId or params")
            return []
        
        print(f"Fetching first page with browseId: {browse_id} and params: {params}")
        
        first_page = self.browse_raw(browse_id, params)
        all_pages = [first_page]
        
        first_page_count = len(self.extract_browse_ids_from_grid(first_page))
        print(f"First page items: {first_page_count}")
        
        continuation_data = self.extract_continuation_data(first_page)
        
        if not continuation_data:
            print("No continuation data found in first page")
            return all_pages
        
        continuation = continuation_data.get('continuation')
        click_tracking_params = continuation_data.get('clickTrackingParams')
        
        if not continuation:
            print("No continuation token found")
            return all_pages
        
        print(f"First continuation token: {continuation[:100]}...")
        
        page_num = 1
        max_pages = 50
        
        while continuation and page_num < max_pages:
            print(f"\nFetching page {page_num + 1} with continuation token...")
            
            time.sleep(2)
            
            next_page = self.browse_raw(
                continuation=continuation,
                click_tracking_params=click_tracking_params
            )
            
            if not next_page:
                print(f"⚠️ Empty response on page {page_num + 1}")
                break
                
            if 'error' in next_page:
                print(f"⚠️ Error on page {page_num + 1}: {next_page['error']}")
                break
            
            has_error, error_msg = self.check_for_error(next_page)
            if has_error:
                print(f"⚠️ Error message on page {page_num + 1}: {error_msg}")
                all_pages.append(next_page)
                break
            
            all_pages.append(next_page)
            
            page_count = len(self.extract_browse_ids_from_grid(next_page))
            print(f"Page {page_num + 1} items: {page_count}")
            
            continuation_data = self.extract_continuation_data(next_page)
            
            if continuation_data:
                continuation = continuation_data.get('continuation')
                click_tracking_params = continuation_data.get('clickTrackingParams')
                if continuation:
                    print(f"Next continuation token found")
                else:
                    print("No more continuation data - reached last page")
                    continuation = None
            else:
                print("No continuation data in response - reached last page")
                continuation = None
            
            page_num += 1
            
            if page_count == 0:
                print("No more items found, stopping")
                break
        
        print(f"\nTotal pages fetched: {len(all_pages)}")
        total_items = 0
        for i, page in enumerate(all_pages):
            page_items = len(self.extract_browse_ids_from_grid(page))
            total_items += page_items
            print(f"  Page {i+1}: {page_items} items")
        print(f"Total items across all pages: {total_items}")
        
        return all_pages
    
    def extract_continuation_data(self, data):
        """Extract continuation tokens - handles all response structures"""
        try:
            result = {}

            try:
                if 'contents' in data:
                    tabs = (data['contents'].get('singleColumnBrowseResultsRenderer', {}).get('tabs', []))
                    for tab in tabs:
                        sections = (tab.get('tabRenderer', {}).get('content', {}).get('sectionListRenderer', {}).get('contents', []))
                        for section in sections:
                            grid = section.get('gridRenderer', {})
                            for cont in grid.get('continuations', []):
                                if 'nextContinuationData' in cont:
                                    result['continuation'] = cont['nextContinuationData']['continuation']
                                    result['clickTrackingParams'] = cont['nextContinuationData'].get('clickTrackingParams')
                                    print("Found grid continuation token in first page")
                                    return result
            except Exception as e:
                print(f"Method 1 failed: {e}")

            try:
                if 'continuationContents' in data:
                    cont_contents = data['continuationContents']
                    
                    for key in ['gridContinuation', 'sectionListContinuation', 
                                'musicShelfContinuation', 'itemSectionContinuation']:
                        if key not in cont_contents:
                            continue
                        
                        container = cont_contents[key]
                        
                        for cont in container.get('continuations', []):
                            if 'nextContinuationData' in cont:
                                result['continuation'] = cont['nextContinuationData']['continuation']
                                result['clickTrackingParams'] = cont['nextContinuationData'].get('clickTrackingParams')
                                print(f"Found continuation in {key}")
                                return result
                        
                        if key == 'sectionListContinuation':
                            for section in container.get('contents', []):
                                grid = section.get('gridRenderer', {})
                                for cont in grid.get('continuations', []):
                                    if 'nextContinuationData' in cont:
                                        result['continuation'] = cont['nextContinuationData']['continuation']
                                        result['clickTrackingParams'] = cont['nextContinuationData'].get('clickTrackingParams')
                                        print("Found continuation inside sectionListContinuation → gridRenderer")
                                        return result
            except Exception as e:
                print(f"Method 2 failed: {e}")

            return None

        except Exception as e:
            print(f"Error extracting continuation data: {e}")
            return None

    def extract_click_tracking_params(self, data):
        """Extract click tracking params from response"""
        try:
            if 'contents' in data:
                contents = data['contents']
                if 'singleColumnBrowseResultsRenderer' in contents:
                    tabs = contents['singleColumnBrowseResultsRenderer'].get('tabs', [])
                    for tab in tabs:
                        if 'tabRenderer' in tab:
                            if 'trackingParams' in tab['tabRenderer']:
                                return tab['tabRenderer']['trackingParams']
        except:
            pass
        return None

    def check_for_error(self, data):
        """Check if the response contains an error"""
        try:
            if 'error' in data:
                return True, data['error'].get('message', 'Unknown error')
            
            if 'continuationContents' in data:
                cont = data['continuationContents']
                has_items = bool(self.extract_browse_ids_from_grid(data))
                has_message = 'messageRenderer' in str(cont)
                
                if has_message and not has_items:
                    has_continuation = False
                    for key in cont:
                        if cont[key].get('continuations'):
                            has_continuation = True
                    if not has_continuation:
                        return True, "Something went wrong"
        except:
            pass
        return False, None

    def extract_browse_ids_from_grid(self, data):
        """Extract browseIds - handles all response structures"""
        browse_ids = []

        def extract_from_items(items):
            for item in items:
                two_row = item.get('musicTwoRowItemRenderer', {})
                title_runs = two_row.get('title', {}).get('runs', [])
                if title_runs:
                    endpoint = title_runs[0].get('navigationEndpoint', {})
                    browse_id = endpoint.get('browseEndpoint', {}).get('browseId')
                    if browse_id:
                        browse_ids.append({
                            'browseId': browse_id,
                            'title': title_runs[0].get('text', ''),
                            'status': 'none'
                        })

        try:
            if 'contents' in data:
                tabs = (data['contents']
                        .get('singleColumnBrowseResultsRenderer', {})
                        .get('tabs', []))
                for tab in tabs:
                    sections = (tab.get('tabRenderer', {})
                                .get('content', {})
                                .get('sectionListRenderer', {})
                                .get('contents', []))
                    for section in sections:
                        extract_from_items(section.get('gridRenderer', {}).get('items', []))

            elif 'continuationContents' in data:
                cont = data['continuationContents']
                for key in ['gridContinuation', 'sectionListContinuation',
                            'musicShelfContinuation', 'itemSectionContinuation']:
                    if key in cont:
                        extract_from_items(cont[key].get('items', []))
                        for section in cont[key].get('contents', []):
                            extract_from_items(section.get('gridRenderer', {}).get('items', []))

        except Exception as e:
            print(f"Error extracting browseIds: {e}")
            import traceback
            traceback.print_exc()

        return browse_ids
    
    def get_all_browse_ids(self, channel_id):
        """Get all album and EP browseIds for a channel"""
        print(f"\n{'='*60}")
        print(f"EXTRACTING ALL BROWSE IDs FOR CHANNEL: {channel_id}")
        print(f"{'='*60}")
        
        artist_info = self.get_artist_with_params(channel_id)
        
        all_browse_ids = []
        
        if artist_info['singles'].get('results'):
            print(f"\nFound {len(artist_info['singles']['results'])} singles/EPs in preview:")
            for result in artist_info['singles']['results']:
                if result.get('browseId'):
                    browse_id = {
                        'browseId': result['browseId'],
                        'title': result.get('title', ''),
                        'type': 'single',
                        'status': 'none'
                    }
                    all_browse_ids.append(browse_id)
                    print(f"  - {result.get('title', 'Unknown')}: {result['browseId']}")
        
        if artist_info['albums'].get('results'):
            print(f"\nFound {len(artist_info['albums']['results'])} albums in preview:")
            for result in artist_info['albums']['results']:
                if result.get('browseId'):
                    browse_id = {
                        'browseId': result['browseId'],
                        'title': result.get('title', ''),
                        'type': 'album',
                        'status': 'none'
                    }
                    all_browse_ids.append(browse_id)
                    print(f"  - {result.get('title', 'Unknown')}: {result['browseId']}")
        
        if artist_info['albums'].get('browseId') and artist_info['albums'].get('params'):
            print("\n" + "="*50)
            print("FETCHING FULL ALBUMS LIST")
            print("="*50)
            
            album_pages = self.fetch_all_pages_raw(
                artist_info['albums']['browseId'],
                artist_info['albums']['params']
            )
            
            print(f"\nExtracting browseIds from {len(album_pages)} album pages...")
            for page_num, page in enumerate(album_pages):
                page_browse_ids = self.extract_browse_ids_from_grid(page)
                if page_browse_ids:
                    for item in page_browse_ids:
                        item['type'] = 'album'
                        if not any(existing['browseId'] == item['browseId'] for existing in all_browse_ids):
                            all_browse_ids.append(item)
                    print(f"  Page {page_num + 1}: Found {len(page_browse_ids)} albums (Total so far: {len([x for x in all_browse_ids if x.get('type') == 'album'])}")
        
        if artist_info['singles'].get('browseId') and artist_info['singles'].get('params'):
            print("\n" + "="*50)
            print("FETCHING FULL SINGLES/EPs LIST")
            print("="*50)
            
            singles_pages = self.fetch_all_pages_raw(
                artist_info['singles']['browseId'],
                artist_info['singles']['params']
            )
            
            print(f"\nExtracting browseIds from {len(singles_pages)} singles pages...")
            for page_num, page in enumerate(singles_pages):
                page_browse_ids = self.extract_browse_ids_from_grid(page)
                if page_browse_ids:
                    for item in page_browse_ids:
                        item['type'] = 'single'
                        if not any(existing['browseId'] == item['browseId'] for existing in all_browse_ids):
                            all_browse_ids.append(item)
                    print(f"  Page {page_num + 1}: Found {len(page_browse_ids)} singles/EPs (Total so far: {len([x for x in all_browse_ids if x.get('type') == 'single'])}")
        
        return all_browse_ids
    
    def get_total_items_count(self, data):
        """Try to extract total items count from response"""
        try:
            contents = data.get('contents', {})
            if 'singleColumnBrowseResultsRenderer' in contents:
                tabs = contents['singleColumnBrowseResultsRenderer'].get('tabs', [])
                if tabs and len(tabs) > 0:
                    tab = tabs[0]
                    if 'tabRenderer' in tab:
                        content = tab['tabRenderer'].get('content', {})
                        if 'sectionListRenderer' in content:
                            sections = content['sectionListRenderer'].get('contents', [])
                            for section in sections:
                                if 'gridRenderer' in section:
                                    grid = section['gridRenderer']
                                    if 'header' in grid:
                                        header = grid['header']
                                        if 'gridHeaderRenderer' in header:
                                            title = header['gridHeaderRenderer'].get('title', {})
                                            if 'runs' in title:
                                                for run in title['runs']:
                                                    text = run.get('text', '')
                                                    if '(' in text and ')' in text:
                                                        import re
                                                        match = re.search(r'\((\d+)\)', text)
                                                        if match:
                                                            return int(match.group(1))
        except Exception as e:
            print(f"Error extracting total count: {e}")
        return None
    
    def save_raw_responses(self, channel_id, output_dir="raw_responses"):
        """Fetch and save raw responses for both albums and EPs"""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")
        
        artist_info = self.get_artist_with_params(channel_id)
        artist_info_channel_id = artist_info['artist_data']['channelId']
        
        artist_file = os.path.join(output_dir, f"{artist_info_channel_id}_artist_data.json")
        with open(artist_file, 'w') as f:
            json.dump(artist_info['artist_data'], f, indent=3)
        print(artist_info['artist_data']['name'])
        print(f"Artist data saved to: {artist_file}")
        artist_thumbnails = get_max_thumbnails(artist_info['artist_data']['thumbnails'][0]['url'])
        
        results = {
            'channel_id': artist_info_channel_id,
            'name': artist_info['artist_data']['name'],
            'thumbnails': artist_thumbnails,
            'timestamp': datetime.now().isoformat(),
            'albums': {
                'browseId': None,
                'params': None,
                'pages': []
            },
            'singles': {
                'browseId': None,
                'params': None,
                'pages': []
            }
        }
        
        if artist_info['albums'].get('browseId') and artist_info['albums'].get('params'):
            print("\n" + "="*50)
            print("FETCHING ALBUMS")
            print("="*50)
            
            results['albums']['browseId'] = artist_info['albums']['browseId']
            results['albums']['params'] = artist_info['albums']['params']
            
            album_pages = self.fetch_all_pages_raw(
                artist_info['albums']['browseId'],
                artist_info['albums']['params']
            )
            
            results['albums']['pages'] = album_pages
            
            albums_file = os.path.join(output_dir, f"{artist_info_channel_id}_albums_raw.json")
            with open(albums_file, 'w') as f:
                json.dump({
                    'browseId': artist_info['albums']['browseId'],
                    'params': artist_info['albums']['params'],
                    'total_pages': len(album_pages),
                    'pages': album_pages
                }, f, indent=3)
            print(f"Albums raw responses saved to: {albums_file}")
            
            albums_dir = os.path.join(output_dir, f"{artist_info_channel_id}_albums_pages")
            if not os.path.exists(albums_dir):
                os.makedirs(albums_dir)
            
            for i, page in enumerate(album_pages):
                page_file = os.path.join(albums_dir, f"page_{i+1}.json")
                with open(page_file, 'w') as f:
                    json.dump(page, f, indent=3)
            print(f"Individual album pages saved to: {albums_dir}/")
        
        if artist_info['singles'].get('browseId') and artist_info['singles'].get('params'):
            print("\n" + "="*50)
            print("FETCHING SINGLES/EPs")
            print("="*50)
            
            results['singles']['browseId'] = artist_info['singles']['browseId']
            results['singles']['params'] = artist_info['singles']['params']
            
            singles_pages = self.fetch_all_pages_raw(
                artist_info['singles']['browseId'],
                artist_info['singles']['params']
            )
            
            results['singles']['pages'] = singles_pages
            
            singles_file = os.path.join(output_dir, f"{artist_info_channel_id}_singles_raw.json")
            with open(singles_file, 'w') as f:
                json.dump({
                    'browseId': artist_info['singles']['browseId'],
                    'params': artist_info['singles']['params'],
                    'total_pages': len(singles_pages),
                    'pages': singles_pages
                }, f, indent=3)
            print(f"Singles/EPs raw responses saved to: {singles_file}")
            
            singles_dir = os.path.join(output_dir, f"{channel_id}_singles_pages")
            if not os.path.exists(singles_dir):
                os.makedirs(singles_dir)
            
            for i, page in enumerate(singles_pages):
                page_file = os.path.join(singles_dir, f"page_{i+1}.json")
                with open(page_file, 'w') as f:
                    json.dump(page, f, indent=3)
            print(f"Individual singles pages saved to: {singles_dir}/")
        
        summary_file = os.path.join(output_dir, f"{artist_info_channel_id}_summary.json")
        summary = {
            'channel_id': artist_info_channel_id,
            'name': results['name'],
            'timestamp': results['timestamp'],
            'albums': {
                'browseId': results['albums']['browseId'],
                'params': results['albums']['params'],
                'total_pages': len(results['albums']['pages']),
                'total_items': sum(len(self.extract_browse_ids_from_grid(page)) for page in results['albums']['pages'])
            },
            'singles': {
                'browseId': results['singles']['browseId'],
                'params': results['singles']['params'],
                'total_pages': len(results['singles']['pages']),
                'total_items': sum(len(self.extract_browse_ids_from_grid(page)) for page in results['singles']['pages'])
            }
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=3)
        print(f"\nSummary saved to: {summary_file}")
        
        return results


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def safe_filename(text):
    replacements = {
        '/': '⧸', '\\': '⧹', ':': '：', '*': '＊', '?': '？', 
        '"': '＂', '<': '＜', '>': '＞', '|': '｜',
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text

def convert_end_dot(text: str):
    if text and text[-1] == '.':
        return text[:-1] + '。'
    return text

def safe_artist_name(text):
    replacements = {',':'，'}
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text

def get_max_thumbnails(url):
    thumbnails_base_url, thumbnails_params_url = url.rsplit('=', 1)
    res = thumbnails_base_url + "=w3000-h3000-p-l100-rj"
    return res

def download_image(file_path, file_name, url):
    """Download image from URL and save to file"""
    try:
        full_path = os.path.join(file_path, file_name)
        full_path += '.jpg'
        os.makedirs(file_path, exist_ok=True)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, stream=True, timeout=10)
        response.raise_for_status()
        content_type = response.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            return False, f"URL does not point to an image. Content-Type: {content_type}"
        
        with open(full_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        
        print(f"  Image downloaded: {full_path}")
        return True, f"Image downloaded successfully: {full_path}"
    
    except requests.exceptions.RequestException as e:
        print(f"  Image download error: {str(e)}")
        return False, f"Error downloading image: {str(e)}"
    except Exception as e:
        print(f"  Unexpected error: {str(e)}")
        return False, f"Unexpected error: {str(e)}"


def find_ffmpeg():
    """Find ffmpeg executable in current directory only"""
    current_dir = os.getcwd()
    ffmpeg_names = ['ffmpeg', 'ffmpeg.exe']
    
    for name in ffmpeg_names:
        ffmpeg_path = os.path.join(current_dir, name)
        if os.path.exists(ffmpeg_path):
            print(f"✓ Found ffmpeg in current directory: {ffmpeg_path}")
            return ffmpeg_path
    
    for name in ffmpeg_names:
        if os.path.exists(name):
            abs_path = os.path.abspath(name)
            print(f"✓ Found ffmpeg in current directory: {abs_path}")
            return abs_path
    
    print("\nFFmpeg not found in current directory.")
    print("Please place ffmpeg.exe in the same folder as this script.")
    return None


def load_metadata_file(metadata_file):
    """Load existing metadata file or create empty list"""
    if os.path.exists(metadata_file):
        with open(metadata_file, 'r') as f:
            return json.load(f)
    return []


def save_metadata_file(metadata_file, metadata_list):
    """Save metadata list to file"""
    with open(metadata_file, 'w') as f:
        json.dump(metadata_list, f, indent=3)


def update_browse_id_status(browse_ids_file, browse_id, new_status):
    """Update the status of a specific browseId in the JSON file"""
    try:
        if os.path.exists(browse_ids_file):
            with open(browse_ids_file, 'r') as f:
                data = json.load(f)
            
            for item in data:
                if item['browseId'] == browse_id:
                    item['status'] = new_status
                    break
            
            with open(browse_ids_file, 'w') as f:
                json.dump(data, f, indent=3)
    except Exception as e:
        print(f"Error updating status file: {e}")


# ============================================================================
# YT-DLP FUNCTIONS
# ============================================================================
def get_numbering(number):
    res = len(str(number))
    if res < 2:
        return 2;
    return res

def padding_zero(lenght: int, char: str):
    res =''
    res = res + "0"*(lenght-len(char))
    res = res+char
    return res;

def extract_playlist_info(url):
    try:
        with yt_dlp.YoutubeDL({'quiet': True,'no_warnings': True,'ignoreerrors': True,'extract_flat': True,}) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        print(f"  Extract error: {str(e)}")
        return None
        
def download_track_lib(url: str, path: str, track: str, filename: str, ext: str):
    #track = padding_zero
    download_opts = {
        'outtmpl': {
            'default': path + '/' + track + '.' + filename,
        },
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'ffmpeg_location': 'ffmpeg.exe',
        'extractaudio': True,
        'audioformat': ext,
        'audioquality': '0',
        'writethumbnail': True,
        'embedthumbnail': True,
        'embeddinfo': True,
        'addmetadata': True,
        'postprocessors': [
            {'key': 'FFmpegExtractAudio','preferredcodec': 'm4a','preferredquality': '0',},
            {'key': 'FFmpegMetadata',},
            {'key': 'EmbedThumbnail',},
        ],
        'keepvideo': False,
        #'progress_hooks': None,
    }
    try:
        with yt_dlp.YoutubeDL(download_opts) as ydl_download:
            ydl_download.download([url])
        return True
    except Exception as e:
        return False

def download_track_exc(url: str, path: str, track: str, filename: str, ext: str):
    error = False
    cmd = [
        'yt-dlp',
        '--cookies-from-browser', 'firefox',
        #'--remote-components', 'ejs:github',
        '-f', 'bestaudio',
        '--extract-audio',
        '--audio-format', ext,
        '--audio-quality', '0',
        '--embed-thumbnail',
        '--add-metadata',
        '--output', path + '/' + track + '.' + filename,
        '--ffmpeg-location', 'ffmpeg.exe',
        '--ignore-errors',
        url,
    ]
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    for line in process.stdout:
        #print (line.strip())
        if line:
            if 'ERROR' in line:
                print(f"   {line}")
                error = True
    return_code = process.wait()
    if return_code == 0:
        if error == True:
            return False
        else:
            return True
    else:
        return False

def download_playlist(info, download_dir, album_data, ffmpeg_path, logger, progress_hook=None):
    try:
        # Get the original URL from the info
        playlist_url = info.get('original_url', info.get('webpage_url', ''))
        playlist_id = playlist_url.split('list=')[-1] if 'list=' in playlist_url else 'unknown'
        
        current_dir = os.getcwd()
        env = os.environ.copy()
        env['PATH'] = current_dir + os.pathsep + env.get('PATH', '')
        
        if info and 'entries' in info:
            playlist_title = info.get('title', playlist_id)
            track_count = len(info['entries'])
            print(f"  Playlist: {playlist_title}")
            print(f"  Total tracks: {track_count}")
            print(f"  Starting download...")
            print()
            
            # Default progress hook if none provided
            if progress_hook is None:
                def progress_hook(d):
                    if d['status'] == 'downloading':
                        if 'info_dict' in d:
                            track_title = d['info_dict'].get('title', 'Unknown')
                            track_index = d['info_dict'].get('playlist_index', '?')
                            
                            if 'total_bytes' in d and d['total_bytes']:
                                percent = d['downloaded_bytes'] / d['total_bytes'] * 100
                                downloaded_mb = d['downloaded_bytes'] / (1024 * 1024)
                                total_mb = d['total_bytes'] / (1024 * 1024)
                                status = f"⬇️  [{percent:.1f}%] {downloaded_mb:.1f}MB/{total_mb:.1f}MB"
                            elif 'total_bytes_estimate' in d and d['total_bytes_estimate']:
                                percent = d['downloaded_bytes'] / d['total_bytes_estimate'] * 100
                                downloaded_mb = d['downloaded_bytes'] / (1024 * 1024)
                                total_mb = d['total_bytes_estimate'] / (1024 * 1024)
                                status = f"⬇️  [{percent:.1f}%] {downloaded_mb:.1f}MB/~{total_mb:.1f}MB"
                            else:
                                downloaded_mb = d['downloaded_bytes'] / (1024 * 1024)
                                status = f"⬇️  [???%] {downloaded_mb:.1f}MB"
                            
                            print(f"\r  Track {track_index}/{track_count}: {track_title[:50]}{'...' if len(track_title) > 50 else ''} {status}", end='')
                    
                    elif d['status'] == 'finished':
                        track_title = d['info_dict'].get('title', 'Unknown')
                        track_index = d['info_dict'].get('playlist_index', '?')
                        total_size = d.get('total_bytes', d.get('total_bytes_estimate', 0)) / (1024 * 1024)
                        print(f"\r  Track {track_index}/{track_count}: {track_title[:50]}{'...' if len(track_title) > 50 else ''} [Complete] ({total_size:.1f}MB)")
                    
                    elif d['status'] == 'error':
                        track_title = d['info_dict'].get('title', 'Unknown') if 'info_dict' in d else 'Unknown'
                        track_index = d['info_dict'].get('playlist_index', '?') if 'info_dict' in d else '?'
                        print(f"\r  Track {track_index}/{track_count}: {track_title[:50]}{'...' if len(track_title) > 50 else ''} [Failed]")
            
            # Calculate track numbering width
            track_numbering = len(str(track_count))
            if track_numbering < 2:
                track_numbering = 2
            
            # Download options - save directly to download_dir
            download_opts = {
                'outtmpl': {
                    'default': os.path.join(download_dir, '%(playlist_index)' + f'0{track_numbering}d' + '.%(title)s.%(ext)s'),
                },
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,
                'ffmpeg_location': ffmpeg_path,
                'extractaudio': True,
                'audioformat': 'm4a',
                'audioquality': '0',
                'writethumbnail': True,
                'embedthumbnail': True,
                'embeddinfo': True,
                'addmetadata': True,
                'postprocessors': [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'm4a',
                        'preferredquality': '0',
                    },
                    {
                        'key': 'FFmpegMetadata',
                    },
                    {
                        'key': 'EmbedThumbnail',
                    },
                ],
                'keepvideo': False,
                'progress_hooks': [progress_hook],
            }
            
            # Download with progress tracking - use the playlist URL
            with yt_dlp.YoutubeDL(download_opts) as ydl_download:
                ydl_download.download([playlist_url])
            
            print(f"\n  Completed: {playlist_title} ({track_count} tracks)")
            return info
        else:
            print(f"  No tracks found in playlist")
            return False
            
    except Exception as e:
        print(f"  Download error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

_artist_cache: dict = {}

def get_artist_data(channelId: str, max_age_days: int = 3):
    """Get artist data with cache age checking"""
    
    if channelId in _artist_cache:
        print(_artist_cache[channelId]['name'])
        return _artist_cache[channelId]
    
    os.makedirs(raw_dir, exist_ok=True)
    path = os.path.join(raw_dir, f"{channelId}_artist_data.json")
    
    # Check if cache file exists and is not too old
    cache_valid = False
    cache_data = None
    
    if os.path.isfile(path):
        # Get file modification time
        file_mtime = os.path.getmtime(path)
        file_age_days = (time.time() - file_mtime) / (24 * 3600)
        
        if file_age_days <= max_age_days:
            # Cache is fresh enough
            with open(path, encoding="utf-8") as f:
                cache_data = json.load(f)
            cache_valid = True
            print(f'[debug] Using cached artist data for {channelId} (age: {file_age_days:.1f} days)')
            print(f'[debug] def get_artist_data: {cache_data["name"]}')
        else:
            print(f'[debug] Cache expired for {channelId} (age: {file_age_days:.1f} days > {max_age_days} days)')
            print(f'[debug] Will fetch fresh data from API')
    
    if cache_valid and cache_data:
        _artist_cache[channelId] = cache_data
        return cache_data
    
    # Fetch fresh data from API
    try:
        print(f"  [API ] Fetching YTMusic artist: {channelId}")
        ytmusic = YTMusic()
        data = ytmusic.get_artist(channelId=channelId)
        
        # Save with timestamp metadata
        data['_cache_timestamp'] = datetime.now().isoformat()
        data['_cache_age_days'] = 0
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=3, ensure_ascii=False)
        
        print(f'[debug] Fresh data fetched and saved for {channelId}: {data["name"]}')
        _artist_cache[channelId] = data
        return data
        
    except Exception as e:
        print(f"  [ERR ] YTMusic fetch failed for {channelId}: {e}")
        
        # If API fails but we have expired cache, use it as fallback
        if cache_data:
            print(f"  [WARN] Using expired cache as fallback for {channelId}")
            _artist_cache[channelId] = cache_data
            return cache_data
        
        return None

def get_artist_name(channelId: str):
    print(f"  [DEBUG] Getting artist name for channelId: {channelId}")
    data = get_artist_data(channelId)
    if data:
        print(f"  [DEBUG] Found name: '{data['name']}'")
        return data['name'].rstrip()
    print(f"  [DEBUG] No data found for {channelId}")
    return "Unknown Artist"

def build_artist_folder_name(album_data):
    """get from ytmusic.get_album(browseId: str)"""
    artists = album_data['artists']
    res = []
    for artist in artists:
        if artist['id'] != None:
            #print('case 1')
            res.append(safe_artist_name(get_artist_name(artist['id'].rstrip())))
            print(res)
        else:
            if artist['name'].lower() == "various artists":
                #print('case 2')
                res.append("Various Artists")
            elif  artist['name'].lower() == "v.a.":
                #print('case 3')
                res.append("Various Artists")
            elif  artist['name'].lower() == "v.a":
                #print('case 4')
                res.append("Various Artists")
            else:
                #print('case 5')
                res.append(artist['name'].lstrip(',&'))
    return res
# Add this function after update_browse_id_status function

def update_browse_ids_cache(cache_file, all_browse_ids):
    """Update the cache file with current statuses"""
    try:
        # Create cache directory if it doesn't exist
        cache_dir = os.path.dirname(cache_file)
        if cache_dir and not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        
        # Load existing cache data
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
        else:
            cache_data = []
        
        # Create lookup of current all_browse_ids
        current_lookup = {item['browseId']: item for item in all_browse_ids}
        
        # Update cache entries
        for i, cache_item in enumerate(cache_data):
            if cache_item['browseId'] in current_lookup:
                # Update status and any other fields that might have changed
                cache_data[i]['status'] = current_lookup[cache_item['browseId']].get('status', 'none')
        
        # Add any new items not in cache
        existing_ids = {item['browseId'] for item in cache_data}
        for item in all_browse_ids:
            if item['browseId'] not in existing_ids:
                cache_data.append(item.copy())
        
        # Save updated cache
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=3, ensure_ascii=True)
        
        return cache_data
    except Exception as e:
        print(f"  Warning: Failed to update cache file: {e}")
        return None
# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main function to run the script with command line input"""
    print("="*60)
    print("YouTube Music Downloader")
    print("="*60)
    print(f"Current directory: {os.getcwd()}")
    print("="*60)
    
    if len(sys.argv) > 1:
        channel_id = sys.argv[1]
        print(f"Channel ID from command line: {channel_id}")
    else:
        channel_id = input("Enter YouTube Music channel ID: ").strip()
        if not channel_id:
            print("No channel ID provided. Exiting.")
            return
            
    output_dir = "raw_responses"
    print(f"\nProcessing channel ID: {channel_id}")
    print(f"Output directory: {output_dir}")
    print("\n" + "="*60)
    
    try:
        ffmpeg_path = find_ffmpeg()
        if not ffmpeg_path:
            print("\nFFmpeg is required but not found in current directory.")
            print("Please download ffmpeg and place it in this folder:")
            print("  - From: https://ffmpeg.org/download.html")
            print("  - Or use: https://www.gyan.dev/ffmpeg/builds/ (Windows)")
            proceed = input("\nContinue without ffmpeg? (y/n): ").strip().lower()
            if proceed != 'y':
                return
        else:
            try:
                result = subprocess.run([ffmpeg_path, '-version'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    version_line = result.stdout.split('\n')[0] if result.stdout else 'Unknown version'
                    print(f"✓ FFmpeg verified: {version_line}")
                else:
                    print(f"⚠️ FFmpeg found but may not work properly")
            except Exception as e:
                print(f"⚠️ FFmpeg verification failed: {e}")
        
        hybrid = YouTubeMusicHybrid()
        
        results = hybrid.save_raw_responses(channel_id, output_dir)
        
        print("\n" + "="*60)
        print("EXTRACTING ALL BROWSE IDs")
        print("="*60)
        
        all_browse_ids = hybrid.get_all_browse_ids(results['channel_id'])
        
        list_dir = "list"
        cache_dir = "cache"  # Add this
        if not os.path.exists(list_dir):
            os.makedirs(list_dir)
            print(f"Created list directory: {list_dir}")

        # Add this line to create cache directory if it doesn't exist
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
            print(f"Created cache directory: {cache_dir}")
        _artist_cache[results['channel_id']] = results
        artist_name = safe_filename(get_artist_name(results['channel_id']))

        browse_ids_file = os.path.join(list_dir, f"{results['channel_id']}_{artist_name}_browseId.json")
        metadata_file = os.path.join(list_dir, f"{results['channel_id']}_{artist_name}_listmetadata.json")
        browse_ids_cache_file = os.path.join(cache_dir, "browseId.json")  # This line already exists
        
        if os.path.exists(browse_ids_cache_file):
            print(f"\nFound existing browse IDs file. Merging status...")
            with open(browse_ids_cache_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            existing_lookup = {item['browseId']: item for item in existing_data}
            
            for item in all_browse_ids:
                if item['browseId'] in existing_lookup:
                    item['status'] = existing_lookup[item['browseId']].get('status', 'none')

            for item in all_browse_ids:
                if item['browseId'] not in existing_lookup:
                    existing_data.append(item)
            with open(browse_ids_cache_file, 'w') as f:
                json.dump(existing_data, f, indent=3, ensure_ascii=True)
            
            print(f"Merged {len(existing_data)} existing items")
        
        print("\n" + "="*60)
        print("BROWSE ID EXTRACTION SUMMARY")
        print("="*60)
        print(f"Total items found: {len(all_browse_ids)}")
        
        albums_count = sum(1 for item in all_browse_ids if item.get('type') == 'album')
        singles_count = sum(1 for item in all_browse_ids if item.get('type') == 'single')
        done_count = sum(1 for item in all_browse_ids if item.get('status') == 'done')
        error_count = sum(1 for item in all_browse_ids if item.get('status') == 'error')
        none_count = sum(1 for item in all_browse_ids if item.get('status') == 'none')
        
        print(f"Albums: {albums_count}")
        print(f"Singles/EPs: {singles_count}")
        print(f"Status: {done_count} done, {error_count} error, {none_count} pending")
        
        if all_browse_ids:
            print("\nAll items:")
            str_num_width = len(str(len(all_browse_ids)))
            for i, item in enumerate(all_browse_ids):
                str_padding = " "*(str_num_width-len(str(i)))
                print(f"  {i}.{str_padding} [{item.get('status', 'none')}] [{item.get('type', 'unknown')}] {item.get('title', 'Unknown')}: {item['browseId']}")
        
        with open(browse_ids_file, 'w') as f:
            json.dump(all_browse_ids, f, indent=3)
        print(f"\nBrowse IDs saved to: {browse_ids_file}")
        
        metadata_list = load_metadata_file(metadata_file)
        print(f"Loaded {len(metadata_list)} existing metadata entries")
        
        print("\n" + "="*60)
        print("DOWNLOAD SETUP")
        print("="*60)
        
        download_base = input("Enter base download directory (default: ./downloads): ").strip()
        if not download_base:
            download_base = os.path.join(os.getcwd(), "downloads")
        
        os.makedirs(download_base, exist_ok=True)
        print(f"Downloads will be saved to: {download_base}")
        
        print("\n" + "="*60)
        print("ITEM SELECTION")
        print("="*60)
        print("Selection options:")
        print("  all              - Select all items")
        print("  default          - Select items with status 'none' or 'error'")
        print("  none             - Select items with status 'none' only")
        print("  error            - Select items with status 'error' only")
        print("  indices list     - e.g., 0,1,2,3,4 (select specific indices)")
        print("  exclude indices  - e.g., all,-1,-2 (select all except indices 1 and 2)")
        print("  combinations     - e.g., none,5,6,-2 (select 'none' status + indices 5,6, exclude index 2)")
        print("-"*60)

        selection_input = input("Enter your selection (default: default): ").strip().lower()
        if not selection_input:
            selection_input = "default"

        items_to_process = set()
        excluded_indices = set()

        parts = [part.strip() for part in selection_input.split(',')]

        for part in parts:
            if part == "all":
                items_to_process = set(range(len(all_browse_ids)))
            elif part == "default":
                default_indices = {i for i, item in enumerate(all_browse_ids) 
                                  if item['status'] in ['none', 'error']}
                items_to_process.update(default_indices)
            elif part == "none":
                none_indices = {i for i, item in enumerate(all_browse_ids) 
                               if item['status'] == 'none'}
                items_to_process.update(none_indices)
            elif part == "error":
                error_indices = {i for i, item in enumerate(all_browse_ids) 
                                if item['status'] == 'error'}
                items_to_process.update(error_indices)
            elif part.startswith('-'):
                try:
                    excluded_indices.add(int(part[1:]))
                except ValueError:
                    print(f"  Warning: Invalid exclusion '{part}', skipping")
            else:
                try:
                    index = int(part)
                    if 0 <= index < len(all_browse_ids):
                        items_to_process.add(index)
                    else:
                        print(f"  Warning: Index {index} out of range (0-{len(all_browse_ids)-1}), skipping")
                except ValueError:
                    print(f"  Warning: Invalid input '{part}', skipping")

        items_to_process = items_to_process - excluded_indices
        items_to_process = sorted(list(items_to_process))

        if items_to_process:
            items_to_process = [all_browse_ids[i] for i in items_to_process]
        else:
            items_to_process = []
        
        if not items_to_process:
            print("No items to process.")
        else:
            print(f"Found {len(items_to_process)} items to process")
            print(results['thumbnails'])
            artist_dir = os.path.join(download_base, convert_end_dot(safe_artist_name(artist_name)))
            os.makedirs(artist_dir, exist_ok=True)
            download_image(artist_dir, convert_end_dot(safe_artist_name(artist_name)), results['thumbnails'])
            
            for i, item in enumerate(items_to_process, 1):
                print(f"\n[{i}/{len(items_to_process)}] Processing: {item.get('title', 'Unknown')} ({item['browseId']})")
                
                try:
                    # Get album data first
                    album_data = hybrid.ytmusic.get_album(item['browseId'])
                    
                    if 'related_recommendations' in album_data:
                        del album_data['related_recommendations']
                    
                    if 'audioPlaylistId' in album_data:
                        audio_playlist_id = album_data['audioPlaylistId']
                        playlist_url = f"https://music.youtube.com/playlist?list={audio_playlist_id}"
                        
                        # Step 1: Extract playlist info first
                        print(f"  🔗 Extracting playlist info: {playlist_url}")
                        playlist_info = extract_playlist_info(playlist_url)
                        
                        if playlist_info and 'entries' in playlist_info:
                            # Build the folder structure
                            # Get artist names from album_data
                            artist_names = build_artist_folder_name(album_data)
                            artist_folder_name = ", ".join(artist_names) if artist_names else "Unknown Artist"
                            print(_artist_cache[results['channel_id']]['name'])
                            # Get album title from playlist info (or fallback to album_data)
                            album_title = playlist_info.get('title', item.get('title', 'Unknown Album'))
                            safe_album_title = safe_filename(album_title)
                            
                            # Build full path: {download_base}/{artists}/{album title} - [{browseId}]
                            album_dir = os.path.join(download_base, convert_end_dot(safe_filename(artist_folder_name)).rstrip(), f"{safe_album_title} - [{item['browseId']}]")
                            os.makedirs(album_dir, exist_ok=True)
                            
                            # Save playlist info to file
                            file_path = f"raw_responses/Albums"
                            if not os.path.exists(file_path):
                                os.makedirs(file_path)
                            info_file = os.path.join(file_path, f"[{item['browseId']}] - {safe_filename(playlist_info['title'])}.json")
                            with open(info_file, 'w') as f:
                                json.dump(playlist_info, f, indent=3)
                            
                            print(f"  📁 Download path: {album_dir}")
                            # Download album cover
                            if album_data.get('thumbnails') and len(album_data['thumbnails']) > 0:
                                cover_url = get_max_thumbnails(album_data['thumbnails'][0]['url'])
                                download_image(album_dir, "cover", cover_url)
                            # Step 2: Download the playlist content
                            success = download_playlist(playlist_info, album_dir, album_data, ffmpeg_path, None)
                            #for item in playlist_info[entries]:
                            
                            
                            if success:
                                item['status'] = 'done'
                                
                                metadata_entry = {
                                    'browseId': item['browseId'],
                                    'title': item.get('title', ''),
                                    'type': item.get('type', 'unknown'),
                                    'audioPlaylistId': audio_playlist_id,
                                    'playlistUrl': playlist_url,
                                    'downloadPath': album_dir,
                                    'downloadDate': datetime.now().isoformat(),
                                    'albumData': album_data,
                                    'albumInfo': success,
                                }
                                
                                existing_index = next((index for (index, d) in enumerate(metadata_list) if d['browseId'] == item['browseId']), None)
                                if existing_index is not None:
                                    metadata_list[existing_index] = metadata_entry
                                    print(f"  📝 Updated existing metadata entry")
                                else:
                                    metadata_list.append(metadata_entry)
                                    print(f"  📝 Added new metadata entry")
                                
                                print(f"  ✅ Success: {item.get('title')} -> {album_dir}")
                            else:
                                item['status'] = 'error'
                                print(f"  ❌ Failed to download: {item.get('title')}")
                        else:
                            print(f"  ⚠️ No tracks found in playlist")
                            item['status'] = 'error'
                    else:
                        print(f"  ⚠️ No audioPlaylistId found")
                        item['status'] = 'error'
                    
                except Exception as e:
                    print(f"  ❌ Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    item['status'] = 'error'
                # Save progress after each item
                with open(browse_ids_file, 'w') as f:
                    json.dump(all_browse_ids, f, indent=3)
                # Update the cache file as well
                update_browse_ids_cache(browse_ids_cache_file, all_browse_ids)
                save_metadata_file(metadata_file, metadata_list)
                time.sleep(1)
        
        print("\n" + "="*60)
        print("FINAL SUMMARY")
        print("="*60)
        
        final_done = sum(1 for item in all_browse_ids if item.get('status') == 'done')
        final_error = sum(1 for item in all_browse_ids if item.get('status') == 'error')
        final_none = sum(1 for item in all_browse_ids if item.get('status') == 'none')
        
        print(f"Total items: {len(all_browse_ids)}")
        print(f"✅ Completed: {final_done}")
        print(f"❌ Failed: {final_error}")
        print(f"⏳ Pending: {final_none}")
        print(f"\nBrowse IDs file updated: {browse_ids_file}")
        print(f"Metadata file updated: {metadata_file} ({len(metadata_list)} entries)")
        print(f"Downloads saved to: {download_base}")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()