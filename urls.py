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
    mp = Mapper()
    # Add routes here

    urlmap(mp, [

        (URL_PREFIX+'/', 'controllers#index'),
        (URL_PREFIX+'/feed', 'controllers#feed'),
        (URL_PREFIX+'/feed/{user}', 'controllers#feed'),
        (URL_PREFIX+'/q', 'controllers#queue',{'assignee':'me'}),
        (URL_PREFIX+'/q/archive', 'controllers#queue',{'assignee':'me','archive':True}),
        (URL_PREFIX+'/q/assignee/{assignee}', 'controllers#queue'),
        (URL_PREFIX+'/q/assignee/{assignee}/archive', 'controllers#queue',{'archive':True}),
        (URL_PREFIX+'/q/all', 'controllers#queue'),
        (URL_PREFIX+'/q/all/archive', 'controllers#queue',{'archive':True}),

        (URL_PREFIX+'/journal', 'controllers#global_journal'),
        (URL_PREFIX+'/journal/groupby/{groupby}', 'controllers#global_journal'),

        (URL_PREFIX+'/metastate-set','controllers#metastate_set'),

        (URL_PREFIX+'/tl', 'controllers#top_level'),
        (URL_PREFIX+'/latest', 'controllers#latest'),
        (URL_PREFIX+'/latest/{max_days}', 'controllers#latest'),
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
        (URL_PREFIX+'/favicon.ico', 'controllers#favicon'),
        (URL_PREFIX+'/assets/{r_type}/{r_file}', 'controllers#assets'),
    ])

    filters = ['day','creator','state']
    for flt in filters:
        url = URL_PREFIX+'/journal/filter'
        def mcnt(url,flt,mp,chain=[]):
            url+='/%s/{%s}'%(flt,flt)
            print 'connecting',url
            mp.connect(None,url,controller='controllers',action='global_journal')
            mp.connect(None,url+'/groupby/{groupby}',controller='controllers',action='global_journal')
            chain.append(flt)
            for flt2 in filters:
                if flt2 not in chain:
                    mcnt(url,flt2,mp,chain)
            return mp
        mp = mcnt(url,flt,mp)


        
    return mp
