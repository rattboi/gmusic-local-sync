#!/usr/bin/env python

import sys
import os
import getpass
import pprint
import string
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

def find_ratio(a, b):
    a_filtered = cleanup(a)
    b_filtered = cleanup(b)

    distance = levenshtein(a_filtered, b_filtered)
    ratio = (distance / max(len(a_filtered), len(b_filtered))) 
    
    # if either string is a subset of the other, that is a better fit
    if a in b:
        ratio /= 2
    if b in a:
        ratio /= 2
    return ratio

def similarity(artist_a, artist_b, album_a, album_b):
    artist_ratio = find_ratio(artist_a, artist_b)
    album_ratio = find_ratio(album_a, album_b)

    ratio = artist_ratio + album_ratio

    return ratio

def cleanup(s):
    exclude = set(string.punctuation)

    extra_words_filter = ''.join(
             s.lower()
              .replace('the','',-1)
              .replace('deluxe','',-1)
              .replace('expanded','',-1)
              .replace('edition','',-1)
              .replace('remastered','',-1)
              .replace('reissue','',-1)
              .replace('version','',-1)
              .replace('bonus','',-1)
              .replace('tracks','',-1)
              .replace('track','',-1)
              .split())

    punc_filter = ''.join(ch for ch in extra_words_filter if ch not in exclude)
    return punc_filter


def filter_hits(hits, artist_name, album_name):
    album_hits = hits['album_hits']
    return [(a['album']['artist'], 
             a['album']['name'], 
             similarity(a['album']['artist'], artist_name, a['album']['name'], album_name),
             a['album']['albumId']) 
             for a in album_hits]

def search_for_artist_and_album(mob, artist, album):
    retries = 2
    while retries > 0:
        try: 
            hits = mob.search("{0} {1}".format(artist, album))
            return filter_hits(hits, artist, album)
        except:
            print("Oops, some error searching")
            retries = retries - 1
    sys.exit(2)


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

def percent(num, denom):
    return ((num / denom) * 100)

def print_summary_line(description, count, total):
    print("{0: <30}: {1} ({2:.0f}%)".format(description, count, percent(count, total)))

def print_summary(total_items, partial_accepted_items, partial_rejected_items, exact_items, no_items):
    print('----- Summary ------')
    print("Total Items: {}".format(total_items))
    print_summary_line("Partial Matches (Accepted)", partial_accepted_items, total_items)
    print_summary_line("Partial Matches (Rejected)", partial_rejected_items, total_items)
    print_summary_line("Exact Matches", exact_items, total_items)
    print_summary_line("No Matches", no_items, total_items)

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

    mob = Mobileclient()
    mob.login(username, password, Mobileclient.FROM_MAC_ADDRESS)
    if not mob.is_authenticated():
        sys.exit(1)

    total_items = 0
    partial_accepted_items = 0
    partial_rejected_items = 0
    exact_items = 0
    no_items = 0

    ACCEPT_RATIO = 0.45

    for item in local_list:
        search_artist = item['artist']
        for search_album in item['albums']:
            # print("Searching for {0} - {1}".format(search_artist, search_album))
            total_items += 1
            albums = search_for_artist_and_album(mob, search_artist, search_album)
            sorted_albums = sorted(albums, key=lambda k:k[2])

            # for (artist, album, ratio, full_details) in sorted_albums:
            if len(sorted_albums) > 0:
                (artist, album, ratio, album_id) = sorted_albums[0]

                if ratio > 0:
                    if ratio < ACCEPT_RATIO:
                        partial_accepted_items += 1
                        print("Partial Match (Accepted): ({2:.0f}%) {0} - {1} for {3} - {4}".format(artist, album, ((1. - ratio) * 100), search_artist, search_album))
                    else:
                        partial_rejected_items += 1
                        print("Partial Match (Rejected): ({2:.0f}%) {0} - {1} for {3} - {4}".format(artist, album, ((1. - ratio) * 100), search_artist, search_album))
                else:
                    exact_items += 1
                    print("Exact Match             : Artist: {0}, Album: {1}".format(artist, album))

                # album_tracks = get_tracks_from_album(mob, album_id)
                # pp.pprint(album_tracks)
                # for each track in album, mob.add_store_track(store_song_id)
            else:
                no_items += 1
                print("No Match                : Artist: {0}, Album: {1}".format(search_artist, search_album))

    print_summary(total_items, partial_accepted_items, partial_rejected_items, exact_items, no_items)

if __name__ == '__main__':
    sys.exit(main())
