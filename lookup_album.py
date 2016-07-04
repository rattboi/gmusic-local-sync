#!/usr/bin/env python

import sys
import os
import getpass
import pprint
from gmusicapi import Mobileclient

pp = pprint.PrettyPrinter(indent=4)
username = input("Please enter your name: ")
password = getpass.getpass()

mob = Mobileclient()
mob.login(username, password, Mobileclient.FROM_MAC_ADDRESS)
while True:
  searchterm = input("Please enter your searchterm: ")
  hits = mob.search(searchterm)
  album_hits = hits['album_hits']

  for album in album_hits:
    a = album['album']
    print("Artist: {0}, Album: {1}".format(a['artist'], a['name']))
