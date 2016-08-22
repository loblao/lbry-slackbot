#!/usr/bin/python

'''
LBRY SlackBOT v1.0
Author: Nacib Neme
Date: 8/20/2016

License:
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

This script is meant to fullfil the requirements for this bounty:
https://lbry.io/bounty/slack-lbry-url-handler

Usage:
1 - Create a slack bot user for your team
2 - Add it to the wanted channels
3 - Get a client_id on imgur
4 - Create config.json with the following syntax:

{
    "SLACK_BOT_TOKEN": "xoxb-XXX-XXX",
    "IMGUR_CLIENT_ID": "xxxxxxxxxxx"
}

5 - Leave bot.py running
'''

from slackclient import SlackClient
from jsonrpc.proxy import JSONRPCProxy

import pyimgur

import json
import time
import os

try:
    from lbrynet.conf import API_CONNECTION_STRING

except:
      print "You don't have lbrynet installed!"
      API_CONNECTION_STRING = "http://localhost:5279/lbryapi"

if os.path.isfile('config.json'):
    with open('config.json', 'rb') as f:
        CONFIG = json.loads(f.read())

else:
    print 'config.json not found'
    exit(1)

SLACK_BOT_TOKEN = CONFIG.get('SLACK_BOT_TOKEN')
if not SLACK_BOT_TOKEN:
    print 'Required config SLACK_BOT_TOKEN not set in config.json'
    exit(1)

IMGUR_CLIENT_ID = CONFIG.get('IMGUR_CLIENT_ID')
if not IMGUR_CLIENT_ID:
    print 'Required config IMGUR_CLIENT_ID not set in config.json'
    exit(1)

OUTPUT_DIR = CONFIG.get('OUTPUT_DIR', 'files')
if not os.path.isdir(OUTPUT_DIR):
    os.mkdir(OUTPUT_DIR)

CACHE = {}
CACHE_TIMEOUT = CONFIG.get('CACHE_TIMEOUT', 3600) # 1 hour

def handle_msg(msg):
    urls = []

    words = msg.split()
    for word in words:
        if word.startswith('<lbry://'):
            url = word[1:]
            url = url[:url.find('>')]
            urls.append(url)

    return urls

def upload_to_imgur(filename, url):
    uploaded_image = im.upload_image(filename, title=url)
    return uploaded_image.link

def check_url(name):
    '''
    Returns True if lbry://<name> is a fee-less gif, False otherwise.
    '''

    if name.startswith('lbry://'):
        name = name[7:]

    resolved = api.resolve_name({'name': name})
    if 'fee' in resolved:
        return False

    # Thanks @jack for this snippet below
    meta_version = resolved.get('ver', '0.0.1')
    if meta_version in ('0.0.1', '0.0.2'):
        content_type = resolved.get('content-type')

    else:
        content_type = resolved.get('content_type')

    return content_type == 'image/gif'

def fetch_url(url):
    if url.startswith('lbry://'):
        url = url[7:]

    try:
        result = api.get({'name': url, 'download_directory': OUTPUT_DIR})
        return (True, result['path'])

    except Exception as e:
        print 'Failed to fetch URL', e
        return (False, None)

def handle_url(url, channel):
    if url in CACHE:
        if channel in CACHE[url]:
            elapsed = time.time() - CACHE[url][channel]
            if elapsed < CACHE_TIMEOUT:
                return

    else:
        CACHE[url] = {}

    CACHE[url][channel] = time.time()
    if not check_url(url):
        return

    success, filename = fetch_url(url)
    if not success:
        slack_client.api_call('chat.postMessage', channel=channel,
                              text='Unable to fetch URL [%s]. Insufficient funds?' % url,
                              as_user=True)

    else:
        link = upload_to_imgur(filename, url)
        attachments = [{'image_url': link, 'title': url}]

        slack_client.api_call('chat.postMessage', channel=channel,
                              attachments=json.dumps(attachments))

api = JSONRPCProxy.from_url(API_CONNECTION_STRING)
slack_client = SlackClient(SLACK_BOT_TOKEN)
im = pyimgur.Imgur(IMGUR_CLIENT_ID)

if not slack_client.rtm_connect():
    print 'Failed to connect.'
    exit(1)

print 'Connected'
while True:
    for event in slack_client.rtm_read():
        if event.get('type') == 'message':
            channel = event['channel']

            urls = []
            if event.get('subtype') == 'message_changed':
                msg = event['message']['text']
                prev = event['previous_message']['text']

                prev_urls = handle_msg(prev)
                urls = handle_msg(msg)

                for prev in prev_urls:
                    if prev in urls:
                        urls.remove(prev)

            else:
                urls = handle_msg(event['text'])

            for url in urls:
                handle_url(url, channel)

    time.sleep(1)
