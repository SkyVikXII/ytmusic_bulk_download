import time
import os
import json

from api import Api
from pathlib import Path
from format import format_get_artist_data, format_get_artist_albums_data
from utils import safe_filename, convert_end_dot, safe_artist_name, get_max_thumbnails, extract_playlist_info, download_image
from download_logic import download_playlist

class Core:
    def __init__(self):
        self.api = Api()
        appdir = Path(__file__).parent
        appdata = appdir / "appdata"
        self.config = {
            'appdir': appdir,
            'appdata': appdata,
            'artist_dir': appdata / "channel",
            'album_dir': appdata / "album"
        }
        self.artist_cache: dict = {}

    def get_artist(self, channelId:str):
        return format_get_artist_data(self.api.get_artist_page(channelId))

    def get_albums(self, browseId: str, params: str):
        return format_get_artist_albums_data(self.api.get_albums_page(browseId,params))

    def download_album(self, input_dir, browseId:str):
        try:
            # Get album data first
            album_data = self.api.lib.get_album(browseId)
                        
            if 'audioPlaylistId' in album_data:
                audio_playlist_id = album_data['audioPlaylistId']
                playlist_url = f"https://music.youtube.com/playlist?list={audio_playlist_id}"
                            
                # Step 1: Extract playlist info first
                print(f"Extracting playlist info: {playlist_url}")
                playlist_info = extract_playlist_info(playlist_url)
                            
            if playlist_info and 'entries' in playlist_info:
                # Build the folder structure
                # Get artist names from album_data
                artist_names = build_artist_folder_name(album_data)
                artist_folder_name = ", ".join(artist_names) if artist_names else "Unknown Artist"
                # Get album title from playlist info (or fallback to album_data)
                album_title = album_data.get('title', 'Unknown Album')
                album_type = album_data.get('type','playlist')
                safe_album_title = safe_filename(album_title)
                                
                # Build full path: {input_dir}/{artists}/{album title} - [{browseId}]
                album_dir = os.path.join(input_dir, convert_end_dot(safe_filename(artist_folder_name)).rstrip(), f"{album_type} - {safe_album_title} - [{browseId}]")
                os.makedirs(album_dir, exist_ok=True)
            
                print(f"Download path: {album_dir}")
                    # Download album cover
                if album_data.get('thumbnails') and len(album_data['thumbnails']) > 0:
                    cover_url = get_max_thumbnails(album_data['thumbnails'][0]['url'])
                    download_image(album_dir, "cover", cover_url)
                    # Step 2: Download the playlist content
                    success = download_playlist(playlist_info, album_dir, album_data, 'ffmpeg.exe', None)
                    #for item in playlist_info[entries]:
                                
                                
                    if success:
                        print('success')
                    else:
                        print('fail')
                else:
                    print(f"No tracks found in playlist")
            else:
                print(f"No audioPlaylistId found")
                        
        except Exception as e:
            print(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()
        time.sleep(1)
        return None

    def get_artist_data(self, channelId: str, max_age_days: int = 3):
        """Get artist data with cache age checking"""
        
        if channelId in self.artist_cache:
            print(self.artist_cache[channelId]['name'])
            return self.artist_cache[channelId]
        artist_dir = os.path.join(self.config['artist_dir'], f"{channelId}")
        os.makedirs(artist_dir, exist_ok=True)
        path = os.path.join(artist_dir,"artist.json")
        
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
            result = {
                'name': cache_data['name'],
                'channelId': cache_data['channelId']
            }
            self.artist_cache[channelId] = result
            return result
        
        # Fetch fresh data from API
        try:
            print(f"  [API ] Fetching YTMusic artist: {channelId}")
            data = self.get_artist(channelId=channelId)
            #print(path)
            '''
            if(channelId!=data['channelId']):
                data = self.get_artist(channelId=channelId)
            '''
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=3, ensure_ascii=False)
            
            #print(f'[debug] Fresh data fetched and saved for {channelId}: {data["name"]}')
            result = {
                'name': data['name'],
                'channelId': data['channelId']
            }
            self.artist_cache[channelId] = result
            return data
            
        except Exception as e:
            print(f"[ERR ] YTMusic fetch failed for {channelId}: {e}")
            # If API fails but we have expired cache, use it as fallback
            if cache_data:
                print(f"[WARN] Using expired cache as fallback for {channelId}")
                self.artist_cache[channelId] = cache_data
                return cache_data
            
            return None

def get_artist_name(channelId: str):
    #print(f"  [DEBUG] Getting artist name for channelId: {channelId}")
    data = get_artist_data(channelId)
    if data:
        #print(f"  [DEBUG] Found name: '{data['name']}'")
        return data['name'].rstrip()
    #print(f"  [DEBUG] No data found for {channelId}")
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