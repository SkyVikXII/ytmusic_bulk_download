from api import Api
from pathlib import Path
from format import format_get_artist_data, format_get_artist_albums_data

class Core:
    def __init__(self):
        self.api = Api()
        appdir = Path(__file__).parent
        appdata = appdir / "appdata"
        self.config = {
            'appdir': appdir,
            'appdata': appdata,
            'artist_dir': appdata / "artist",
            'album_dir': appdata / "album"
        }
        self._artist_cache: dict = {}
    def get_artist(self, channelId:str):
        return format_get_artist_data(self.api.get_artist_page(channelId))
        
    def get_albums(self, browseId: str, params: str):
        return format_get_artist_albums_data(self.api.get_albums_page(browseId,params))

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