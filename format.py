import json

#TODO: alot data have same field make it more clean.

def format_get_song(data):
    renderer = data['musicResponsiveListItemRenderer']
    
    # Extract title and navigation info from first flex column
    title = None
    video_id = renderer['playlistItemData']['videoId']
    video_type = None
    
    # Get title from first flex column
    if renderer['flexColumns'][0]['musicResponsiveListItemFlexColumnRenderer']['text']['runs']:
        title_run = renderer['flexColumns'][0]['musicResponsiveListItemFlexColumnRenderer']['text']['runs'][0]
        title = title_run['text']
        # Check for video type in navigation endpoint
        if 'navigationEndpoint' in title_run and 'watchEndpointMusicSupportedConfigs' in title_run['navigationEndpoint']['watchEndpoint']:
            if 'watchEndpointMusicConfig' in title_run['navigationEndpoint']['watchEndpoint']['watchEndpointMusicSupportedConfigs']:
                video_type = title_run['navigationEndpoint']['watchEndpoint']['watchEndpointMusicSupportedConfigs']['watchEndpointMusicConfig'].get('musicVideoType')
    
    # Extract artists from second flex column
    artists = []
    if len(renderer['flexColumns']) > 1:
        artist_runs = renderer['flexColumns'][1]['musicResponsiveListItemFlexColumnRenderer']['text']['runs']
        for artist_run in artist_runs:
            if artist_run.get('text') and artist_run.get('navigationEndpoint'):
                artist_id = None
                if 'browseEndpoint' in artist_run['navigationEndpoint']:
                    artist_id = artist_run['navigationEndpoint']['browseEndpoint'].get('browseId')
                artists.append({
                    'name': artist_run['text'],
                    'id': artist_id
                })
    
    # Extract album from fourth flex column (index 3)
    album = None
    if len(renderer['flexColumns']) > 3:
        album_runs = renderer['flexColumns'][3]['musicResponsiveListItemFlexColumnRenderer']['text']['runs']
        if album_runs:
            album_name = album_runs[0].get('text')
            album_id = None
            if 'navigationEndpoint' in album_runs[0] and 'browseEndpoint' in album_runs[0]['navigationEndpoint']:
                album_id = album_runs[0]['navigationEndpoint']['browseEndpoint'].get('browseId')
            album = {
                'name': album_name,
                'id': album_id
            }
    
    # Extract like status from top level buttons
    like_status = "INDIFFERENT"
    if 'menu' in renderer and 'menuRenderer' in renderer['menu']:
        top_level_buttons = renderer['menu']['menuRenderer'].get('topLevelButtons', [])
        for button in top_level_buttons:
            if 'likeButtonRenderer' in button:
                like_status = button['likeButtonRenderer'].get('likeStatus', 'INDIFFERENT')
                break
    
    # Extract thumbnails
    thumbnails = renderer['thumbnail']['musicThumbnailRenderer']['thumbnail']['thumbnails']
    
    # Views (extract from third flex column if available)
    views = None
    if len(renderer['flexColumns']) > 2:
        views_text = renderer['flexColumns'][2]['musicResponsiveListItemFlexColumnRenderer']['text']['runs'][0].get('text')
        if views_text:
            views = views_text
    
    result = {
        'videoId': video_id,
        'title': title,
        'artists': artists,
        'album': album,
        'likeStatus': like_status,
        'thumbnails': thumbnails,
        'videoType': video_type,
        'views': views
    }
    
    return result

def format_get_album(data):
    renderer = data['musicTwoRowItemRenderer']
    
    # Extract title
    title = None
    if 'title' in renderer and 'runs' in renderer['title']:
        title = renderer['title']['runs'][0]['text']
    
    # Extract type and year from subtitle
    album_type = None
    year = None
    
    if 'subtitle' in renderer and 'runs' in renderer['subtitle']:
        subtitle_runs = renderer['subtitle']['runs']
        
        if len(subtitle_runs) == 1:
            # Single field like "2024" (just year)
            year = subtitle_runs[0]['text']
        else:
            # Multiple fields like "Single • 2026" or "EP • 2023"
            for run in subtitle_runs:
                text = run.get('text', '').strip()
                # Skip separator
                if text == '•' or text == ' • ' or text == '• ':
                    continue
                # Check if it looks like a year (4 digits)
                if text.isdigit() and len(text) == 4:
                    year = text
                elif text and not year:
                    # First non-separator, non-year text is the type
                    album_type = text
    
    # Extract browseId from navigation endpoint
    browse_id = None
    audio_playlist_id = None
    
    if 'navigationEndpoint' in renderer and 'browseEndpoint' in renderer['navigationEndpoint']:
        browse_id = renderer['navigationEndpoint']['browseEndpoint'].get('browseId')
    
    # Extract audioPlaylistId from the play button or shuffle play menu
    # Priority 1: From thumbnail overlay play button
    if 'thumbnailOverlay' in renderer and 'musicItemThumbnailOverlayRenderer' in renderer['thumbnailOverlay']:
        overlay = renderer['thumbnailOverlay']['musicItemThumbnailOverlayRenderer']
        if 'content' in overlay and 'musicPlayButtonRenderer' in overlay['content']:
            play_button = overlay['content']['musicPlayButtonRenderer']
            if 'playNavigationEndpoint' in play_button:
                if 'watchPlaylistEndpoint' in play_button['playNavigationEndpoint']:
                    audio_playlist_id = play_button['playNavigationEndpoint']['watchPlaylistEndpoint'].get('playlistId')
    
    # Priority 2: If not found, try from shuffle play menu item
    if not audio_playlist_id and 'menu' in renderer and 'menuRenderer' in renderer['menu']:
        items = renderer['menu']['menuRenderer'].get('items', [])
        for item in items:
            if 'menuNavigationItemRenderer' in item:
                nav_item = item['menuNavigationItemRenderer']
                if 'navigationEndpoint' in nav_item:
                    # Check for watchPlaylistEndpoint to get audioPlaylistId
                    if 'watchPlaylistEndpoint' in nav_item['navigationEndpoint']:
                        playlist_id = nav_item['navigationEndpoint']['watchPlaylistEndpoint'].get('playlistId')
                        # Remove RDAMPL prefix if present (for radio mixes)
                        if playlist_id and playlist_id.startswith('RDAMPL'):
                            audio_playlist_id = playlist_id[6:]  # Remove 'RDAMPL' prefix
                        elif playlist_id:
                            audio_playlist_id = playlist_id
                        break
    
    # Extract artist info from menu items
    artists = []
    
    if 'menu' in renderer and 'menuRenderer' in renderer['menu']:
        items = renderer['menu']['menuRenderer'].get('items', [])
        for item in items:
            if 'menuNavigationItemRenderer' in item:
                nav_item = item['menuNavigationItemRenderer']
                if 'navigationEndpoint' in nav_item:
                    # Check for "Go to artist" menu item
                    if 'browseEndpoint' in nav_item['navigationEndpoint']:
                        # Check if this is the artist menu item by text or icon
                        text = nav_item.get('text', {}).get('runs', [{}])[0].get('text', '')
                        icon = nav_item.get('icon', {}).get('iconType', '')
                        
                        if text == "Go to artist" or icon == "ARTIST":
                            browse_endpoint = nav_item['navigationEndpoint']['browseEndpoint']
                            artist_id = browse_endpoint.get('browseId')
                            if artist_id:
                                artists.append({
                                    'name': None,
                                    'id': artist_id
                                })
    
    # Extract thumbnails
    thumbnails = []
    if 'thumbnailRenderer' in renderer and 'musicThumbnailRenderer' in renderer['thumbnailRenderer']:
        if 'thumbnail' in renderer['thumbnailRenderer']['musicThumbnailRenderer']:
            if 'thumbnails' in renderer['thumbnailRenderer']['musicThumbnailRenderer']['thumbnail']:
                thumbnails = renderer['thumbnailRenderer']['musicThumbnailRenderer']['thumbnail']['thumbnails']
    
    result = {
        'title': title,
        'type': album_type,
        'year': year,
        'artists': artists,
        'browseId': browse_id,
        'audioPlaylistId': audio_playlist_id,
        'thumbnails': thumbnails
    }
    
    return result

def format_get_video(data):
    renderer = data['musicTwoRowItemRenderer']
    
    # Extract title
    title = None
    if 'title' in renderer and 'runs' in renderer['title']:
        title = renderer['title']['runs'][0]['text']
    
    # Extract videoId and playlistId from navigation endpoint
    video_id = None
    playlist_id = None
    
    if 'navigationEndpoint' in renderer and 'watchEndpoint' in renderer['navigationEndpoint']:
        watch_endpoint = renderer['navigationEndpoint']['watchEndpoint']
        video_id = watch_endpoint.get('videoId')
        playlist_id = watch_endpoint.get('playlistId')
    
    # Extract artists from subtitle
    artists = []
    if 'subtitle' in renderer and 'runs' in renderer['subtitle']:
        for run in renderer['subtitle']['runs']:
            # Look for artist text with navigation endpoint
            if 'text' in run and 'navigationEndpoint' in run:
                if 'browseEndpoint' in run['navigationEndpoint']:
                    artist_name = run.get('text')
                    artist_id = run['navigationEndpoint']['browseEndpoint'].get('browseId')
                    if artist_name and artist_id:
                        artists.append({
                            'name': artist_name,
                            'id': artist_id
                        })
    
    # Extract views from subtitle
    views = None
    if 'subtitle' in renderer and 'runs' in renderer['subtitle']:
        for run in renderer['subtitle']['runs']:
            if 'text' in run and 'views' in run['text'].lower():
                # Extract text like "23K views"
                views_text = run.get('text')
                if views_text:
                    # Remove " views" or " • " if present
                    views = views_text.replace(' views', '').replace(' • ', '').strip()
                    break
    
    # Extract thumbnails
    thumbnails = []
    if 'thumbnailRenderer' in renderer and 'musicThumbnailRenderer' in renderer['thumbnailRenderer']:
        if 'thumbnail' in renderer['thumbnailRenderer']['musicThumbnailRenderer']:
            if 'thumbnails' in renderer['thumbnailRenderer']['musicThumbnailRenderer']['thumbnail']:
                thumbnails = renderer['thumbnailRenderer']['musicThumbnailRenderer']['thumbnail']['thumbnails']
    
    result = {
        'title': title,
        'videoId': video_id,
        'artists': artists,
        'playlistId': playlist_id,
        'thumbnails': thumbnails,
        'views': views
    }
    
    return result

def format_get_playlist(data):
    renderer = data['musicTwoRowItemRenderer']
    
    # Extract title and browseId
    title = None
    browse_id = None
    
    if 'title' in renderer and 'runs' in renderer['title']:
        title_run = renderer['title']['runs'][0]
        title = title_run.get('text')
        # Check for navigation endpoint in title
        if 'navigationEndpoint' in title_run and 'browseEndpoint' in title_run['navigationEndpoint']:
            browse_id = title_run['navigationEndpoint']['browseEndpoint'].get('browseId')
    
    # If browse_id not found in title, try navigationEndpoint at root level
    if not browse_id and 'navigationEndpoint' in renderer and 'browseEndpoint' in renderer['navigationEndpoint']:
        browse_id = renderer['navigationEndpoint']['browseEndpoint'].get('browseId')
    
    # Extract playlistId from menu items (shuffle play or play next endpoint)
    playlist_id = None
    audio_playlist_id = None
    
    if 'menu' in renderer and 'menuRenderer' in renderer['menu']:
        items = renderer['menu']['menuRenderer'].get('items', [])
        for item in items:
            if 'menuNavigationItemRenderer' in item:
                nav_item = item['menuNavigationItemRenderer']
                if 'navigationEndpoint' in nav_item:
                    # Check for watchPlaylistEndpoint
                    if 'watchPlaylistEndpoint' in nav_item['navigationEndpoint']:
                        playlist_id = nav_item['navigationEndpoint']['watchPlaylistEndpoint'].get('playlistId')
                        if playlist_id:
                            break
                    # Also check in queueAddEndpoint
                    elif 'queueAddEndpoint' in nav_item['navigationEndpoint']:
                        queue_target = nav_item['navigationEndpoint']['queueAddEndpoint'].get('queueTarget', {})
                        if 'playlistId' in queue_target:
                            playlist_id = queue_target['playlistId']
                            break
    
    # Extract artists/creator from subtitle
    artists = []
    views = None
    
    if 'subtitle' in renderer and 'runs' in renderer['subtitle']:
        for run in renderer['subtitle']['runs']:
            if 'text' in run:
                # Check for artist/creator (has navigation endpoint)
                if 'navigationEndpoint' in run and 'browseEndpoint' in run['navigationEndpoint']:
                    artist_name = run.get('text')
                    artist_id = run['navigationEndpoint']['browseEndpoint'].get('browseId')
                    if artist_name and artist_id:
                        artists.append({
                            'name': artist_name,
                            'id': artist_id
                        })
                # Extract views (contains "views" in text)
                elif 'views' in run['text']:
                    views = run['text'].replace(' views', '').strip()
    
    # Extract thumbnails
    thumbnails = []
    if 'thumbnailRenderer' in renderer and 'musicThumbnailRenderer' in renderer['thumbnailRenderer']:
        if 'thumbnail' in renderer['thumbnailRenderer']['musicThumbnailRenderer']:
            if 'thumbnails' in renderer['thumbnailRenderer']['musicThumbnailRenderer']['thumbnail']:
                thumbnails = renderer['thumbnailRenderer']['musicThumbnailRenderer']['thumbnail']['thumbnails']
    
    # Determine playlist type from subtitle (first part usually says "Playlist" or "Album")
    playlist_type = None
    if 'subtitle' in renderer and 'runs' in renderer['subtitle']:
        first_run = renderer['subtitle']['runs'][0]
        if first_run.get('text'):
            playlist_type = first_run.get('text')
    
    result = {
        'title': title,
        'type': playlist_type,
        'artists': artists,
        'browseId': browse_id,
        'playlistId': playlist_id,
        'thumbnails': thumbnails,
        'views': views
    }
    
    return result

def format_get_related(data):
    renderer = data['musicTwoRowItemRenderer']
    
    # Extract title (artist name)
    title = None
    browse_id = None
    
    if 'title' in renderer and 'runs' in renderer['title']:
        title_run = renderer['title']['runs'][0]
        title = title_run.get('text')
        # Extract browseId from title navigation endpoint
        if 'navigationEndpoint' in title_run and 'browseEndpoint' in title_run['navigationEndpoint']:
            browse_id = title_run['navigationEndpoint']['browseEndpoint'].get('browseId')
    
    # If browse_id not found in title, try root navigation endpoint
    if not browse_id and 'navigationEndpoint' in renderer and 'browseEndpoint' in renderer['navigationEndpoint']:
        browse_id = renderer['navigationEndpoint']['browseEndpoint'].get('browseId')
    
    # Extract subscribers/monthly audience from subtitle
    subscribers = None
    if 'subtitle' in renderer and 'runs' in renderer['subtitle']:
        subtitle_text = renderer['subtitle']['runs'][0].get('text', '')
        if subtitle_text:
            # Extract number from text like "104K monthly audience" or "795 subscribers"
            # Remove common suffixes
            subscribers = subtitle_text.replace(' monthly audience', '').replace(' subscribers', '').strip()
    
    # Extract thumbnails
    thumbnails = []
    if 'thumbnailRenderer' in renderer and 'musicThumbnailRenderer' in renderer['thumbnailRenderer']:
        if 'thumbnail' in renderer['thumbnailRenderer']['musicThumbnailRenderer']:
            if 'thumbnails' in renderer['thumbnailRenderer']['musicThumbnailRenderer']['thumbnail']:
                thumbnails = renderer['thumbnailRenderer']['musicThumbnailRenderer']['thumbnail']['thumbnails']
    
    result = {
        'title': title,
        'browseId': browse_id,
        'subscribers': subscribers,
        'thumbnails': thumbnails
    }
    
    return result

def format_get_artist_topsongs(data):
    songs = []
    for item in data['musicShelfRenderer']['contents']:
        songs.append(format_get_song(item))
    result = {
        'browseId': data['musicShelfRenderer']['title']['runs'][0]['navigationEndpoint']['browseEndpoint']['browseId'],
        'results': songs,
        'params': data['musicShelfRenderer']['title']['runs'][0]['navigationEndpoint']['browseEndpoint']['params'],
    }
    return result

def format_get_artist_albums(data):
    albums = []
    for item in data['musicCarouselShelfRenderer']['contents']:
        albums.append(format_get_album(item))
    browse_id = None
    params = None
    header = data['musicCarouselShelfRenderer']['header']
    if 'musicCarouselShelfBasicHeaderRenderer' in header:
        header_renderer = header['musicCarouselShelfBasicHeaderRenderer']
        if 'title' in header_renderer and 'runs' in header_renderer['title']:
            title_run = header_renderer['title']['runs'][0]
            if 'navigationEndpoint' in title_run:
                if 'browseEndpoint' in title_run['navigationEndpoint']:
                    browse_id = title_run['navigationEndpoint']['browseEndpoint'].get('browseId')
                    params = title_run['navigationEndpoint']['browseEndpoint'].get('params')
    
    result = {
        'browseId': browse_id,
        'results': albums,
        'params': params,
    }
    return result

def format_get_artist_videos(data):
    videos = []
    for item in data['musicCarouselShelfRenderer']['contents']:
        videos.append(format_get_video(item))
    browse_id = None
    params = None
    header = data['musicCarouselShelfRenderer']['header']
    if 'musicCarouselShelfBasicHeaderRenderer' in header:
        header_renderer = header['musicCarouselShelfBasicHeaderRenderer']
        if 'title' in header_renderer and 'runs' in header_renderer['title']:
            title_run = header_renderer['title']['runs'][0]
            if 'navigationEndpoint' in title_run:
                if 'browseEndpoint' in title_run['navigationEndpoint']:
                    browse_id = title_run['navigationEndpoint']['browseEndpoint'].get('browseId')
                    params = title_run['navigationEndpoint']['browseEndpoint'].get('params')
    
    result = {
        'browseId': browse_id,
        'results': videos,
        'params': params,
    }
    return result

def format_get_artist_playlists(data):
    playlists = []
    for item in data['musicCarouselShelfRenderer']['contents']:
        playlists.append(format_get_playlist(item))
    browse_id = None
    params = None
    header = data['musicCarouselShelfRenderer']['header']
    if 'musicCarouselShelfBasicHeaderRenderer' in header:
        header_renderer = header['musicCarouselShelfBasicHeaderRenderer']
        if 'title' in header_renderer and 'runs' in header_renderer['title']:
            title_run = header_renderer['title']['runs'][0]
            if 'navigationEndpoint' in title_run:
                if 'browseEndpoint' in title_run['navigationEndpoint']:
                    browse_id = title_run['navigationEndpoint']['browseEndpoint'].get('browseId')
                    params = title_run['navigationEndpoint']['browseEndpoint'].get('params')
    
    result = {
        'browseId': browse_id,
        'results': playlists,
        'params': params,
    }
    return result

def format_get_artist_related(data):
    related = []
    for item in data['musicCarouselShelfRenderer']['contents']:
        #print(item)
        related.append(format_get_related(item))
    browse_id = None
    params = None
    header = data['musicCarouselShelfRenderer']['header']
    if 'musicCarouselShelfBasicHeaderRenderer' in header:
        header_renderer = header['musicCarouselShelfBasicHeaderRenderer']
        if 'title' in header_renderer and 'runs' in header_renderer['title']:
            title_run = header_renderer['title']['runs'][0]
            if 'navigationEndpoint' in title_run:
                if 'browseEndpoint' in title_run['navigationEndpoint']:
                    browse_id = title_run['navigationEndpoint']['browseEndpoint'].get('browseId')
                    params = title_run['navigationEndpoint']['browseEndpoint'].get('params')
    
    result = {
        'browseId': browse_id,
        'results': related,
        'params': params,
    }
    return result

def format_get_artist_data(data):
    # Navigate to the contents of the first tab
    try:
        tabs = data['contents']['singleColumnBrowseResultsRenderer']['tabs']
        if not tabs:
            return None
        
        # Find the selected tab (Music tab)
        music_tab = None
        for tab in tabs:
            if 'tabRenderer' in tab and tab['tabRenderer'].get('selected', False):
                music_tab = tab['tabRenderer']
                break
        
        if not music_tab:
            music_tab = tabs[0]['tabRenderer']
        
        # Check if there's content key
        if 'content' not in music_tab:
            # No content sections - artist has no music content
            tab_result = {
                'songs': {'browseId': None, 'results': [], 'params': None},
                'albums': {'browseId': None, 'results': [], 'params': None},
                'singles': {'browseId': None, 'results': [], 'params': None},
                'videos': {'browseId': None, 'results': [], 'params': None},
                'playlists': {'browseId': None, 'results': [], 'params': None},
                'related': {'browseId': None, 'results': [], 'params': None}
            }
        else:
            # Get section list contents
            section_list = music_tab['content']['sectionListRenderer']['contents']
            
            # Initialize result dictionary
            tab_result = {}
            
            # Process each section (same as before)
            for section in section_list:
                # Handle Top Songs (musicShelfRenderer)
                if 'musicShelfRenderer' in section:
                    shelf = section['musicShelfRenderer']
                    
                    # Check if there are actual song contents
                    if 'contents' in shelf and shelf['contents']:
                        try:
                            tab_result['songs'] = format_get_artist_topsongs(section)
                        except:
                            tab_result['songs'] = {
                                'browseId': None,
                                'results': [],
                                'params': None
                            }
                    else:
                        songs_data = {
                            'browseId': None,
                            'results': [],
                            'params': None
                        }
                        
                        # Extract browse info from title or bottom endpoint
                        if 'title' in shelf and 'runs' in shelf['title']:
                            title_run = shelf['title']['runs'][0]
                            if 'navigationEndpoint' in title_run:
                                if 'browseEndpoint' in title_run['navigationEndpoint']:
                                    songs_data['browseId'] = title_run['navigationEndpoint']['browseEndpoint'].get('browseId')
                                    songs_data['params'] = title_run['navigationEndpoint']['browseEndpoint'].get('params')
                        
                        if not songs_data['browseId'] and 'bottomEndpoint' in shelf:
                            if 'browseEndpoint' in shelf['bottomEndpoint']:
                                songs_data['browseId'] = shelf['bottomEndpoint']['browseEndpoint'].get('browseId')
                                songs_data['params'] = shelf['bottomEndpoint']['browseEndpoint'].get('params')
                        
                        tab_result['songs'] = songs_data
                
                # Handle carousel sections
                elif 'musicCarouselShelfRenderer' in section:
                    carousel = section['musicCarouselShelfRenderer']
                    
                    # Get header text to determine section type
                    header_text = None
                    browse_id = None
                    params = None
                    
                    if 'header' in carousel and 'musicCarouselShelfBasicHeaderRenderer' in carousel['header']:
                        header = carousel['header']['musicCarouselShelfBasicHeaderRenderer']
                        if 'title' in header and 'runs' in header['title']:
                            header_run = header['title']['runs'][0]
                            header_text = header_run.get('text', '').lower()
                            
                            # Extract browse info from header if available
                            if 'navigationEndpoint' in header_run:
                                if 'browseEndpoint' in header_run['navigationEndpoint']:
                                    browse_id = header_run['navigationEndpoint']['browseEndpoint'].get('browseId')
                                    params = header_run['navigationEndpoint']['browseEndpoint'].get('params')
                    
                    # Check if there are actual contents
                    has_contents = 'contents' in carousel and carousel['contents']
                    
                    # Determine section type based on header text
                    section_type = None
                    format_func = None
                    
                    if header_text:
                        if 'top song' in header_text:
                            section_type = 'songs'
                            format_func = format_get_artist_topsongs
                        elif 'album' in header_text:
                            section_type = 'albums'
                            format_func = format_get_artist_albums
                        elif 'single' in header_text or 'ep' in header_text:
                            section_type = 'singles'
                            format_func = format_get_artist_albums
                        elif 'video' in header_text:
                            section_type = 'videos'
                            format_func = format_get_artist_videos
                        elif 'playlist' in header_text:
                            section_type = 'playlists'
                            format_func = format_get_artist_playlists
                        elif 'related' in header_text or 'fans might also like' in header_text or 'fans also like' in header_text:
                            section_type = 'related'
                            format_func = format_get_artist_related
                        else:
                            # Default to albums if unknown
                            section_type = 'albums'
                            format_func = format_get_artist_albums
                    
                    # Process the section if we have a type and function
                    if section_type and format_func:
                        if section_type not in tab_result:
                            if has_contents:
                                try:
                                    tab_result[section_type] = format_func(section)
                                except:
                                    tab_result[section_type] = {
                                        'browseId': browse_id,
                                        'results': [],
                                        'params': params
                                    }
                            else:
                                # Empty section, just store browse info
                                tab_result[section_type] = {
                                    'browseId': browse_id,
                                    'results': [],
                                    'params': params
                                }
            
            # Ensure all expected keys exist with proper defaults
            expected_sections = ['songs', 'albums', 'singles', 'videos', 'playlists', 'related']
            for section in expected_sections:
                if section not in tab_result:
                    tab_result[section] = {
                        'browseId': None,
                        'results': [],
                        'params': None
                    }
    
    except (KeyError, IndexError, AttributeError) as e:
        print(f"Error parsing artist data: {e}")
        # Return basic artist info without content sections
        tab_result = {
            'songs': {'browseId': None, 'results': [], 'params': None},
            'albums': {'browseId': None, 'results': [], 'params': None},
            'singles': {'browseId': None, 'results': [], 'params': None},
            'videos': {'browseId': None, 'results': [], 'params': None},
            'playlists': {'browseId': None, 'results': [], 'params': None},
            'related': {'browseId': None, 'results': [], 'params': None}
        }
    
    # Extract artist information from header (same as before)
    header = data.get('header', {})
    
    # Try different header types
    header_renderer = None
    if 'musicImmersiveHeaderRenderer' in header:
        header_renderer = header['musicImmersiveHeaderRenderer']
    elif 'musicVisualHeaderRenderer' in header:
        header_renderer = header['musicVisualHeaderRenderer']
    
    name = None
    channel_id = None
    subscribers = None
    thumbnails = []
    
    if header_renderer:
        # Extract name
        if 'title' in header_renderer and 'runs' in header_renderer['title']:
            name = header_renderer['title']['runs'][0].get('text')
        
        # Extract channel ID and subscriber count
        if 'subscriptionButton' in header_renderer:
            sub_button = header_renderer['subscriptionButton'].get('subscribeButtonRenderer', {})
            channel_id = sub_button.get('channelId')
            
            # Try multiple paths for subscriber count
            if 'subscriberCountText' in sub_button and 'runs' in sub_button['subscriberCountText']:
                subscribers = sub_button['subscriberCountText']['runs'][0].get('text')
            elif 'longSubscriberCountText' in sub_button and 'runs' in sub_button['longSubscriberCountText']:
                subscribers = sub_button['longSubscriberCountText']['runs'][0].get('text')
        
        # Extract thumbnails
        if 'thumbnail' in header_renderer:
            thumbnail = header_renderer['thumbnail']
            if 'musicThumbnailRenderer' in thumbnail:
                if 'thumbnail' in thumbnail['musicThumbnailRenderer']:
                    if 'thumbnails' in thumbnail['musicThumbnailRenderer']['thumbnail']:
                        thumbnails = thumbnail['musicThumbnailRenderer']['thumbnail']['thumbnails']
    
    # Get description from microformat if available
    description = None
    if 'microformat' in data and 'microformatDataRenderer' in data['microformat']:
        description = data['microformat']['microformatDataRenderer'].get('description')
    
    result = {
        'description': description,
        'name': name,
        'channelId': channel_id,
        'subscribers': subscribers,
        'thumbnails': thumbnails,
        'songs': tab_result['songs'],
        'albums': tab_result['albums'],
        'singles': tab_result['singles'],
        'videos': tab_result['videos'],
        'playlists': tab_result['playlists'],
        'related': tab_result['related'],
    }
    
    return result

def format_get_artist_albums_data(data):
    size = len(data)
    if(size==0):
        return None
    result = []
    page = data[0]['contents']['singleColumnBrowseResultsRenderer']['tabs'][0]['tabRenderer']['content']['sectionListRenderer']['contents'][0]['gridRenderer']['items']
    for item in page:
        result.append(format_get_album(item))
    i = 1
    while(i<size):
        page = data[i]['continuationContents']['gridContinuation']['items']
        for item in page:
            result.append(format_get_album(item))
        i += 1
    
    return result