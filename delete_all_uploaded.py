#!/usr/bin/env python

import getpass
import sys

from gmusicapi import Mobileclient
from gmusicapi import Musicmanager

__version__ = '0.1'


def chunks(l, n):
    n = max(1, n)
    return [l[i:i + n] for i in range(0, len(l), n)]

def print_help():
    print("{0} v{1}".format(sys.argv[0],__version__))
    print("  To use: {} <username>".format(sys.argv[0]))
    print("   where: <username> = Google Play username")

def main():
    if len(sys.argv) != 2:
        print_help()
        sys.exit(1)
    else:
        username = sys.argv[1]
    password = getpass.getpass()

    mc = Mobileclient()
    mc.login(username, password, Mobileclient.FROM_MAC_ADDRESS)

    mm = Musicmanager()
    mm.perform_oauth()
    mm.login()

    uploaded_songs = mm.get_uploaded_songs()
    uploaded_ids = [track['id'] for track in uploaded_songs]
    for part in chunks(uploaded_ids, 100):
        complete = mc.delete_songs(part)
        if len(complete) != len(part):
            print("Something is wrong")


if __name__ == '__main__':
    sys.exit(main())
