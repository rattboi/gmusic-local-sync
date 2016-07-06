#!/usr/bin/env python

import sys
import os
import getpass
import pprint
from gmusicapi import Mobileclient

__version__ = '0.1'

def levenshtein(a,b):
    "Calculates the Levenshtein distance between a and b."
    n, m = len(a), len(b)
    if n > m:
        # Make sure n <= m, to use O(min(n,m)) space
        a,b = b,a
        n,m = m,n

    current = range(n+1)
    for i in range(1,m+1):
        previous, current = current, [i]+[0]*n
        for j in range(1,n+1):
            add, delete = previous[j]+1, current[j-1]+1
            change = previous[j-1]
            if a[j-1] != b[i-1]:
                change = change + 1
            current[j] = min(add, delete, change)

    return current[n]

def cleanup(s):
    return s.lower().replace('the ','',-1)

def filter_hits(hits, album_name):
    album_hits = hits['album_hits']
    return [(a['album']['artist'], 
             a['album']['name'], 
             levenshtein(cleanup(a['album']['name']), cleanup(album_name)), 
             a['album']['albumId']) 
             for a in album_hits]

def search_for_artist_and_album(mob, artist, album):
    hits = mob.search("{0} {1}".format(artist, album))
    return filter_hits(hits, album)

# Return list of tuples (title, track #, store id) for album
def get_tracks_from_album(mob, album_id):
  album_info = mob.get_album_info(album_id,include_tracks=True)
  return [(t['title'], t['trackNumber'], t['storeId']) for t in album_info['tracks']]

def get_local_dirs(path):
    artist_album_list = []
    artist_dirs = [f for f in os.listdir(path) if os.path.isdir(os.path.join(path,f)) and not f.startswith('.')]
    for artist_dir in artist_dirs:
        album_dirs = [d for d in os.listdir(os.path.join(path, artist_dir)) if os.path.isdir(os.path.join(path, artist_dir, d)) and not d.startswith('.')]
        artist_album_dict = {}
        artist_album_dict['artist'] = artist_dir
        artist_album_dict['albums'] = album_dirs
        artist_album_list.append(artist_album_dict)
    return artist_album_list

def print_help():
    print("{0} v{1}".format(sys.argv[0],__version__))
    print("  To use: {} <username> <path>".format(sys.argv[0]))
    print("   where: <username> = Google Play username")
    print("          <path>     = root directory containing subdirectories named after artists")
    print("                       (Imagine the root of your music directory)")

def main():
    if len(sys.argv) != 3:
        print_help()
        sys.exit(1)
    else:
        username = sys.argv[1]
        path = sys.argv[2]
    password = getpass.getpass()

    pp = pprint.PrettyPrinter(indent=4)

    local_list = get_local_dirs(path)
    pp.pprint(local_list)

    mob = Mobileclient()
    mob.login(username, password, Mobileclient.FROM_MAC_ADDRESS)
    if not mob.is_authenticated():
        sys.exit(1)

    for item in local_list:
        search_artist = item['artist']
        for search_album in item['albums']:
            # print("Searching for {0} - {1}".format(search_artist, search_album))
            albums = search_for_artist_and_album(mob, search_artist, search_album)
            sorted_albums = sorted(albums, key=lambda k:k[2])

            # for (artist, album, distance, full_details) in sorted_albums:
            if len(sorted_albums) > 0:
                (artist, album, distance, album_id) = sorted_albums[0]

                if distance > 0:
                    print("Results: ({2}) {0} - {1} for {3} - {4}".format(artist, album, distance, search_artist, search_album))
                #else:
                    #print("Exact Match: Artist: {0}, Album: {1}".format(artist, album))

                album_tracks = get_tracks_from_album(mob, album_id)
                # pp.pprint(album_tracks)
                # for each track in album, mob.add_store_track(store_song_id)
            else:
                print("No Results for Artist: {0}, Album: {1}".format(search_artist, search_album))


if __name__ == '__main__':
    sys.exit(main())
