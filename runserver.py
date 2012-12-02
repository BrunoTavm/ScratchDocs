# -*- coding: utf-8 -*-
'''
filedesc: helper script to launch GameServer
'''
from gevent import monkey
monkey.patch_all()
from noodles.app import startapp

if __name__ == '__main__':
    startapp()
