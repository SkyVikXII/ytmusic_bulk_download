import yt_dlp
import os
#TODO: here only have browseid and download albums based on the browseid

def get_numbering(number):
    res = len(str(number))
    if res < 2:
        return 2
    return res

def padding_zero(lenght: int, char: str):
    res =''
    res = res + "0"*(lenght-len(char))
    res = res+char
    return res
        
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
        '--remote-components', 'ejs:github',#download deno
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
                #'ffmpeg_location': ffmpeg_path,
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