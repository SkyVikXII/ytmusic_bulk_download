from ytmusicapi import YTMusic
import requests
import gzip
import urllib.parse
import json
import time

class api:
    def __init__(self):
        self.lib = YTMusic()
        self.session = requests.Session()
        self.base_url = "https://music.youtube.com/youtubei/v1/"
        self._visitor_data = self._get_visitor_data()  # Initialize visitor data
        self.context = {
            "client": {
                "clientName": "WEB_REMIX",
                "clientVersion": "1.20260302.03.01",
                "hl": "en",
                "platform": "DESKTOP",
                "userInterfaceTheme": "USER_INTERFACE_THEME_DARK",
            }
        }
    
    def _get_visitor_data(self):
        """Fetch visitor data from ytmusicapi"""
        try:
            return self.lib.get_visitor_data()
        except:
            return None
    
    def _build_context(self):
        ctx = {"client": self.context["client"].copy()}
        if self._visitor_data:
            ctx["client"]["visitorData"] = self._visitor_data
        return ctx

    def get_context(self):
        return self.context

    def get_session(self):
        return self.session
    
    def get_artist(self, channelId: str):
        data = self.get_artist_page(channelId)
        return data
    def get_artist_page(self, channelId: str):
        """Fetch artist data from YouTube Music"""
        payload = {
            "context": self._build_context(),
            "browseId": channelId
        }
        
        try:
            compressed_body = gzip.compress(json.dumps(payload).encode('utf-8'))
            endpoint = f"{self.base_url}browse?prettyPrint=false"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Content-Type': 'application/json',
                'Content-Encoding': 'gzip',
                'Origin': 'https://music.youtube.com',
                'X-Origin': 'https://music.youtube.com',
                'X-Youtube-Client-Name': '67',
                'X-Youtube-Client-Version': '1.20260302.03.01',
                'X-Youtube-Bootstrap-Logged-In': 'false',
            }
            
            if self._visitor_data:
                headers['X-Goog-Visitor-Id'] = self._visitor_data
            
            response = self.session.post(endpoint, data=compressed_body, headers=headers)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            return {"error": f"Request failed: {str(e)}"}
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON response: {str(e)}"}

    '''
    Topsongs{
        title
        playlistId
        videoId
        duration
        artists[
            {
                name
                browseId
            }
        ]
        plays
        albums{
            title
            browseId
        }
    }
    '''
    def get_topsongs_page(self, browseId: str, params: str):
        #get from video param = ggMCCAI%3D
        num = 0;
        data=[]
        while(True):
            if num==0:
                data.append(self.querry_topsongs_page(browseId, params))
            else:
                continuation_data = self.extract_continuation_data(data[num-1])
                if continuation_data == None:
                    break
                data.append(self.querry_topsongs_page(browseId, params, continuation_data['continuation']))
            print(data[num])
            with open(f'data_topsongs_page_{num}.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=3, ensure_ascii=False)
            num+=1
            time.sleep(0.5)
        return data
    def querry_topsongs_page(self, browseId: str, params: str, continuation=None):
        payload = {"context": self._build_context()}
        if continuation:
            url_encoded_token = urllib.parse.quote(continuation, safe='')
            payload["continuation"] = continuation
        if not continuation:
            if browseId:
                payload["browseId"] = browseId
            if params:
                payload["params"] = params
        endpoint = f"{self.base_url}browse?prettyPrint=false"
        compressed_body = gzip.compress(json.dumps(payload).encode('utf-8'))
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/json',
            'Content-Encoding': 'gzip',
            'Origin': 'https://music.youtube.com',
            'Referer': f'https://music.youtube.com/browse/{browseId or ""}',
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
        
        visitor_data = (data.get('responseContext', {}).get('visitorData'))
        if visitor_data and not self._visitor_data:
            self._visitor_data = visitor_data
            print(f"Got visitorData: {visitor_data[:30]}...")
        
        return data

    def get_albums_page(self, browseId: str, params: str):
        num = 0;
        data=[]
        while(True):
            if num ==0:
                data.append(self.querry_albums_page(browseId, params))
            else:
                continuation_data = self.extract_continuation_data(data[num-1])
                if continuation_data == None:
                    break
                data.append(self.querry_albums_page(browseId, params, continuation_data['continuation']))
            print(data[num])
            #with open(f'data_albums_page_{num}.json', 'w', encoding='utf-8') as f:
            #    json.dump(data, f, indent=3, ensure_ascii=False)
            num += 1;
            time.sleep(0.5)
        return data;

    def querry_albums_page(self, browseId: str, params: str, continuation=None):
        if continuation:
            url_encoded_token = urllib.parse.quote(continuation, safe='')
            parts = [
                f"ctoken={url_encoded_token}",
                f"continuation={url_encoded_token}",
                "type=next",
                "prettyPrint=false",
            ]
            #if click_tracking_params:
                #parts.append(f"itct={urllib.parse.quote(click_tracking_params, safe='')}")
            endpoint = f"{self.base_url}browse?" + "&".join(parts)
        else:
            endpoint = f"{self.base_url}browse?prettyPrint=false"

        payload = {"context": self._build_context()}
        
        if not continuation:
            if browseId:
                payload["browseId"] = browseId
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
            'Referer': f'https://music.youtube.com/browse/{browseId or ""}',
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
        
        visitor_data = (data.get('responseContext', {}).get('visitorData'))
        if visitor_data and not self._visitor_data:
            self._visitor_data = visitor_data
            print(f"Got visitorData: {visitor_data[:30]}...")
        
        return data

    def extract_continuation_data(self, data):
        """Extract continuation tokens - handles all response structures"""
        try:
            result = {}

            # Method 1: Grid continuation from initial page
            try:
                if 'contents' in data:
                    tabs = data['contents'].get('singleColumnBrowseResultsRenderer', {}).get('tabs', [])
                    for tab in tabs:
                        sections = tab.get('tabRenderer', {}).get('content', {}).get('sectionListRenderer', {}).get('contents', [])
                        for section in sections:
                            grid = section.get('gridRenderer', {})
                            for cont in grid.get('continuations', []):
                                if 'nextContinuationData' in cont:
                                    result['continuation'] = cont['nextContinuationData']['continuation']
                                    result['clickTrackingParams'] = cont['nextContinuationData'].get('clickTrackingParams')
                                    return result
            except Exception as e:
                print(f"Method 1 (grid continuation) failed: {e}")

            # Method 2: Continuation page responses
            try:
                if 'continuationContents' in data:
                    cont_contents = data['continuationContents']
                    
                    for key in ['gridContinuation', 'sectionListContinuation', 
                                'musicShelfContinuation', 'itemSectionContinuation']:
                        if key not in cont_contents:
                            continue
                        
                        container = cont_contents[key]
                        
                        # Check direct continuations
                        for cont in container.get('continuations', []):
                            if 'nextContinuationData' in cont:
                                result['continuation'] = cont['nextContinuationData']['continuation']
                                result['clickTrackingParams'] = cont['nextContinuationData'].get('clickTrackingParams')
                                return result
                        
                        # Special handling for sectionListContinuation
                        if key == 'sectionListContinuation':
                            for section in container.get('contents', []):
                                grid = section.get('gridRenderer', {})
                                for cont in grid.get('continuations', []):
                                    if 'nextContinuationData' in cont:
                                        result['continuation'] = cont['nextContinuationData']['continuation']
                                        result['clickTrackingParams'] = cont['nextContinuationData'].get('clickTrackingParams')
                                        return result
            except Exception as e:
                print(f"Method 2 (continuationContents) failed: {e}")
            
            # Method 3: Playlist shelf continuation items
            try:
                if 'contents' in data:
                    tabs = data['contents'].get('singleColumnBrowseResultsRenderer', {}).get('tabs', [])
                    for tab in tabs:
                        sections = tab.get('tabRenderer', {}).get('content', {}).get('sectionListRenderer', {}).get('contents', [])
                        for section in sections:
                            # Check for musicPlaylistShelfRenderer
                            shelf_contents = section.get('musicPlaylistShelfRenderer', {}).get('contents', [])
                            for item in shelf_contents:
                                if 'continuationItemRenderer' in item:
                                    continuation = item['continuationItemRenderer']
                                    result['continuation'] = continuation['continuationEndpoint']['continuationCommand'].get('token')
                                    result['clickTrackingParams'] = continuation['continuationEndpoint'].get('clickTrackingParams')
                                    return result
                                    
                            # Check for musicShelfRenderer as fallback
                            if 'musicShelfRenderer' in section:
                                shelf_contents = section['musicShelfRenderer'].get('contents', [])
                                for item in shelf_contents:
                                    if 'continuationItemRenderer' in item:
                                        continuation = item['continuationItemRenderer']
                                        result['continuation'] = continuation['continuationEndpoint']['continuationCommand'].get('token')
                                        result['clickTrackingParams'] = continuation['continuationEndpoint'].get('clickTrackingParams')
                                        return result
            except Exception as e:
                print(f"Method 3 (playlist shelf) failed: {e}")

            # Method 4: Check for continuation in the last item (optimization)
            try:
                if 'contents' in data:
                    tabs = data['contents'].get('singleColumnBrowseResultsRenderer', {}).get('tabs', [])
                    for tab in tabs:
                        sections = tab.get('tabRenderer', {}).get('content', {}).get('sectionListRenderer', {}).get('contents', [])
                        for section in sections:
                            for renderer_type in ['musicPlaylistShelfRenderer', 'musicShelfRenderer', 'gridRenderer']:
                                if renderer_type in section:
                                    contents_list = section[renderer_type].get('contents', [])
                                    if contents_list and 'continuationItemRenderer' in contents_list[-1]:
                                        continuation = contents_list[-1]['continuationItemRenderer']
                                        result['continuation'] = continuation['continuationEndpoint']['continuationCommand'].get('token')
                                        result['clickTrackingParams'] = continuation['continuationEndpoint'].get('clickTrackingParams')
                                        return result
            except Exception as e:
                print(f"Method 4 (last item check) failed: {e}")

            return None

        except Exception as e:
            print(f"Error extracting continuation data: {e}")
            return None