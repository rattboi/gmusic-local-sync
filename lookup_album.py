#!/usr/bin/env python

import sys
import os
import getpass
import pprint
from gmusicapi import Mobileclient

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
def get_tracks_from_album(album_id):
  album_info = mob.get_album_info(album_id,include_tracks=True)
  return [(t['title'], t['trackNumber'], t['storeId']) for t in album_info['tracks']]

pp = pprint.PrettyPrinter(indent=4)
username = input("username: ")
password = getpass.getpass()

mob = Mobileclient()
mob.login(username, password, Mobileclient.FROM_MAC_ADDRESS)
while True:
    search_artist = input("Artist: ")
    search_album = input("Album: ")

    albums = search_for_artist_and_album(mob, search_artist, search_album)
    sorted_albums = sorted(albums, key=lambda k:k[2])

    # for (artist, album, distance, full_details) in sorted_albums:
    if len(sorted_albums) > 0:
        (artist, album, distance, album_id) = sorted_albums[0]

        print("Results: Artist: {0}, Album: {1}, Distance {2}".format(artist, album, distance))
        album_tracks = get_tracks_from_album(album_id)
        pp.pprint(album_tracks)
# for each track in album, mob.add_store_track(store_song_id)
