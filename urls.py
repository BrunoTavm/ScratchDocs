# -*- coding: utf-8 -*-
'''
filedesc: default url mapping
'''
from routes import Mapper
from config import DEBUG,URL_PREFIX
from noodles.utils import urlmap,include
from routes.route import Route
import os

def get_map():
    " This function returns mapper object for dispatcher "
    map = Mapper()
    # Add routes here
    urlmap(map, [
        (URL_PREFIX+'/', 'controllers#index'),
        (URL_PREFIX+'/iterations', 'controllers#iterations'),
        (URL_PREFIX+'/participants', 'controllers#participants'),
        (URL_PREFIX+'/iteration/{iteration}', 'controllers#iteration'),
        (URL_PREFIX+'/iteration/{iteration}/all', 'controllers#iteration_all'),
        (URL_PREFIX+'/iteration/{iteration}/notdone', 'controllers#iteration_notdone'),
        (URL_PREFIX+'/iteration/{iteration}/commits/{branch}', 'controllers#iteration_commits'),
        (URL_PREFIX+'/assignments/{person}', 'controllers#assignments'),
        (URL_PREFIX+'/assignments/{person}/{iteration}', 'controllers#assignments_itn'),
        (URL_PREFIX+'/assignments/{person}/{iteration}/{mode}', 'controllers#assignments_itn'),
        (URL_PREFIX+'/s/{task:.*}','controllers#task'),
        (URL_PREFIX+'/repr/{task:.*}','controllers#rpr'),
        #('/route/url', 'controllerName.actionName')
    ])

    return map
