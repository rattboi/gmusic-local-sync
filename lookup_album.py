#!/usr/bin/env python

import sys
import os
import getpass
import pprint
import string
import re
import traceback
import logging
from unidecode import unidecode

from gmusicapi import Mobileclient, Musicmanager
from gmusicapi_wrapper import MusicManagerWrapper

QUIET = 25
logging.addLevelName(25, "QUIET")

logger = logging.getLogger('gmusicapi_wrapper')
sh = logging.StreamHandler()
logger.addHandler(sh)
logger.setLevel(logging.INFO)

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
    ratio = (distance / max(len(a_filtered), len(b_filtered), 1))

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
    year_filter = re.sub(r'\d{4}', '', punc_filter)
    unicode_filter = unidecode(year_filter)
    return unicode_filter


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
            print("Oops, some error searching:")
            print('-'*60)
            traceback.print_exc(file=sys.stdout)
            print('-'*60)
            retries = retries - 1
    sys.exit(2)


# Return list of tuples (title, track #, store id) for album
def get_tracks_from_album(mob, album_id):
    album_info = mob.get_album_info(album_id,include_tracks=True)
    return [(t['title'], t['trackNumber'], t['storeId']) for t in album_info['tracks']]

def add_matched_album_to_library(mob, artist, album, album_id):
    album_tracks = get_tracks_from_album(mob, album_id)
    for track in album_tracks:
        print("Adding to Library: '{0} - {1} - {2} - {3}'".format(artist, album, track[1], track[0]))
        mob.add_store_track(track[2])

def add_matched_albums_to_library(mob, matched_albums):
    total_matched_albums = len(matched_albums)
    print("Adding {} matched albums:".format(total_matched_albums))
    for i, album_tuple in enumerate(matched_albums):
        (artist, album, album_id) = album_tuple
        print("Adding album {0}/{1} :".format(i+1,total_matched_albums))
        add_matched_album_to_library(mob, artist, album, album_id)

def upload_unmatched_album_to_library(mmw, artist, album, songs_to_upload):
    print("Uploading to Library: '{0} - {1}'".format(artist, album))
    print("Uploading {0} song(s) to Google Music\n".format(len(songs_to_upload)))
    mmw.upload(songs_to_upload, enable_matching=False, delete_on_success=False)

def upload_unmatched_albums_to_library(mmw, base_path, unmatched_albums):
    total_unmatched_albums = len(unmatched_albums)
    print("Uploading {} unmatched albums:".format(total_unmatched_albums))
    for i, album_tuple in enumerate(unmatched_albums):
        (artist, album) = album_tuple
        print("Uploading album {0}/{1} :".format(i+1, total_unmatched_albums))
        song_dir_path = "{0}/{1}/{2}".format(base_path, artist, album)
        local_songs_tuple = mmw.get_local_songs(song_dir_path, exclude_patterns=[], max_depth=0)
        local_tracks_to_upload, songs_to_filter_ignored, songs_to_exclude_ignored = local_songs_tuple
        upload_unmatched_album_to_library(mmw, artist, album, local_tracks_to_upload)

def confirmation_dialog(prompt_text):
    valid = False
    while not valid:
        confirm = input("{}: ".format(prompt_text)).lower()
        if confirm == 'y' or confirm == 'n':
            valid = True
    if confirm == 'y':
        return True
    else:
        return False

def process_manual_albums(manual_albums):
    manual_accepted = []
    manual_rejected = []
    for album_tuple in manual_albums:
        (s_artist, s_album, artist, album, album_id) = album_tuple
        print("Best match for '{0} - {1}' is '{2} - {3}'".format(s_artist, s_album, artist, album))
        if confirmation_dialog("Use match? (y/n)"):
            manual_accepted.append((artist, album, album_id))
        else:
            manual_rejected.append((s_artist, s_album))
    return (manual_accepted, manual_rejected)

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

def print_summary(total_items, partial_accepted_items, partial_rejected_items, partial_manual_items, exact_items, no_items):
    print('----- Summary ------')
    print("Total Items: {}".format(total_items))
    print_summary_line("Partial Matches (Accepted)", partial_accepted_items, total_items)
    print_summary_line("Partial Matches (Rejected)", partial_rejected_items, total_items)
    print_summary_line("Partial Matches (Manual)", partial_manual_items, total_items)
    print_summary_line("Exact Matches", exact_items, total_items)
    print_summary_line("No Matches", no_items, total_items)

def print_partial(description, ratio, artist, album, search_artist, search_album):
    print("{0: <30}: ({1:.0f}%) {2} - {3} for {4} - {5}".format(description, percent(1. - ratio, 1), artist, album, search_artist, search_album))

def print_help():
    print("{0} v{1}".format(sys.argv[0],__version__))
    print("  To use: {} <username> <path>".format(sys.argv[0]))
    print("   where: <username> = Google Play username")
    print("          <path>     = root directory containing subdirectories named after artists")
    print("                       (Imagine the root of your music directory)")

def test_process_manual_albums():
    manual_albums = []
    manual_albums.append(("Nirvana" , "Nevermind", "Nirvana", "Nevermind (Extended Release)", 12345))
    manual_albums.append(("NOFX" , "Something", "NOFX", "Something Else", 24134))
    manual_albums.append(("Abba" , "hello", "Abba", "goodbye", 34123))
    manual_albums.append(("Lastone" , "matchme", "Lastone", "matchmeplease", 45123))
    (matched, unmatched) = process_manual_albums(manual_albums)
    print(matched)
    print(unmatched)

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

    mmw = MusicManagerWrapper(enable_logging=True)
    mmw.login()

    if not mmw.is_authenticated:
        sys.exit()

    total_items = 0
    partial_accepted_items = 0
    partial_rejected_items = 0
    partial_manual_items = 0
    exact_items = 0
    no_items = 0

    ACCEPT_RATIO = 0.33
    REJECT_RATIO = 0.66

    matched_albums = []
    unmatched_albums = []
    manual_albums = []

    for item in local_list:
        search_artist = item['artist']
        for search_album in item['albums']:
            total_items += 1
            albums = search_for_artist_and_album(mob, search_artist, search_album)
            sorted_albums = sorted(albums, key=lambda k:k[2])

            if len(sorted_albums) > 0:
                (artist, album, ratio, album_id) = sorted_albums[0]

                if ratio > 0:
                    if ratio < ACCEPT_RATIO:
                        partial_accepted_items += 1
                        partial_description = 'Partial Match (Accepted)'
                        matched_albums.append((artist, album, album_id))
                    elif ratio > REJECT_RATIO:
                        partial_rejected_items += 1
                        partial_description = 'Partial Match (Rejected)'
                        unmatched_albums.append((search_artist, search_album))
                    else:
                        partial_manual_items += 1
                        partial_description = 'Partial Match (Manual)'
                        manual_albums.append((search_artist, search_album, artist, album, album_id))
                    print_partial(partial_description, ratio, artist, album, search_artist, search_album)
                else:
                    exact_items += 1
                    print("{0: <30}: Artist: {1}, Album: {2}".format('Exact Match', artist, album))
                    matched_albums.append((artist, album, album_id))
            else:
                no_items += 1
                print("{0: <30}: Artist: {1}, Album: {2}".format('No Match', search_artist, search_album))
                unmatched_albums.append((search_artist, search_album))

    print_summary(total_items, partial_accepted_items, partial_rejected_items, partial_manual_items, exact_items, no_items)

    if (confirmation_dialog("Ok to proceed? (y/n)")):
        (manual_matched, manual_unmatched) = process_manual_albums(manual_albums)
        matched_albums += manual_matched
        unmatched_albums += manual_unmatched
        add_matched_albums_to_library(mob, matched_albums)
        upload_unmatched_albums_to_library(mmw, path, unmatched_albums)

if __name__ == '__main__':
    sys.exit(main())
