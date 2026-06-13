# ytmusic_bulk_download
## In development, Rewritten based on my old script
`ytmusic_core_download.py` process the download and handle some basic tag write
`ytmusic_core_normalizer.py` extract data to build a clean file for normlizer script
`ytmusic_core_normalizer` normalizer artist name
# detail
1. using youtube music api to get data and pass into yt-dlp + ffmpeg to download an albums
2. support range list of url or id.
3. get all albums form a channel and download it
4. include cache system to check which item have been download to avoid redownload again
5. option to choice which albums to download
6. include metadata writer and normalizer to write data into track

# why this exist?
1. yt-dlp can't get data at youtube music api, to download music at youtube music api too much effort, this tool make that process more easier.
2. cache system to track which item so if an artist release new albums just run this script and you don't manual check for each item.
3. yt-dlp write tag not that powerfull it write 1280x720 img, this can get better img 3000x3000 and write into track. metadata in track usually inconsistent, example this track using japanse character while other using english name, the normalizer will handle this base on data have been save before.
