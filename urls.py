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
        (URL_PREFIX+'/tl', 'controllers#top_level'),
        (URL_PREFIX+'/iterations', 'controllers#iterations'),
        (URL_PREFIX+'/participants', 'controllers#participants'),
        (URL_PREFIX+'/assignments/{person}', 'controllers#assignments'),
        (URL_PREFIX+'/created/{person}', 'controllers#created'),
        (URL_PREFIX+'/tags', 'controllers#tags'),
        (URL_PREFIX+'/tag/{tag}', 'controllers#bytag'),
        (URL_PREFIX+'/assignments/{person}/{mode}', 'controllers#assignments_mode'),
        (URL_PREFIX+'/s/{task:.*}/log','controllers#history'),
        (URL_PREFIX+'/s/{task:.*}','controllers#task'),
        (URL_PREFIX+'/repr/{task:.*}','controllers#rpr'),
        (URL_PREFIX+'/search','controllers#search'),
        ('/favicon.ico', 'controllers#favicon')
    ])

    return map
