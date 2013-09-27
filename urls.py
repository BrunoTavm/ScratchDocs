# -*- coding: utf-8 -*-
'''
filedesc: default url mapping
'''
from routes import Mapper
from config import DEBUG,URL_PREFIX
from noodles.utils.maputils import urlmap,include
from routes.route import Route
import os

def get_map():
    " This function returns mapper object for dispatcher "
    map = Mapper()
    # Add routes here
    urlmap(map, [

        (URL_PREFIX+'/', 'controllers#index'),
        (URL_PREFIX+'/journal', 'controllers#global_journal'),
        (URL_PREFIX+'/q', 'controllers#queue'),
        (URL_PREFIX+'/journal/by/{creator}', 'controllers#global_journal'),
        (URL_PREFIX+'/tl', 'controllers#top_level'),
        (URL_PREFIX+'/iterations', 'controllers#iterations'),
        (URL_PREFIX+'/participants', 'controllers#participants'),
        (URL_PREFIX+'/assignments/{person}', 'controllers#assignments'),
        (URL_PREFIX+'/created/{person}', 'controllers#created'),
        (URL_PREFIX+'/tags', 'controllers#tags'),
        (URL_PREFIX+'/tag/{tag}', 'controllers#bytag'),
        (URL_PREFIX+'/assignments/{person}/{mode}', 'controllers#assignments_mode'),
        (URL_PREFIX+'/s/{task:.*}/log','controllers#history'),
        (URL_PREFIX+'/s/{task:.*}/j','controllers#journal'),
        (URL_PREFIX+'/s/{task:.*}/j/{jid}','controllers#journal_edit'),
        (URL_PREFIX+'/s/{task:.*}','controllers#task'),

        (URL_PREFIX+'/{task:[\d\/]+}/log','controllers#history'),
        (URL_PREFIX+'/{task:[\d\/]+}/j','controllers#journal'),
        (URL_PREFIX+'/{task:[\d\/]+}/j/{jid}','controllers#journal_edit'),
        (URL_PREFIX+'/{task:[\d\/]+}','controllers#task'),


        (URL_PREFIX+'/repr/{task:.*}','controllers#rpr'),
        (URL_PREFIX+'/search','controllers#search'),
        ('/favicon.ico', 'controllers#favicon')
    ])

    return map
