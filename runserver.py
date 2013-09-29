#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
filedesc: helper script to launch GameServer
'''
from config import NO_GEVENT_MONKEYPATCH
if not NO_GEVENT_MONKEYPATCH:
    from gevent import monkey
    monkey.patch_all()
from noodles.app import startapp

if __name__ == '__main__':
    startapp()
