# -*- coding: utf-8 -*-
'''
filedesc: default url mapping
'''
from routes import Mapper
from config import DEBUG,URL_PREFIX,METASTATE_URLS,DATADIR
from noodles.utils.maputils import urlmap,include
from routes.route import Route
import os

def get_map():
    " This function returns mapper object for dispatcher "
    mp = Mapper()
    # Add routes here

    urlmap(mp, [

        (URL_PREFIX+'/', 'controllers#index'),
        (URL_PREFIX+'/tr', 'controllers#index',{'gethours':True}),

        (URL_PREFIX+'/feed', 'controllers#feed'),
        (URL_PREFIX+'/feed/fs', 'controllers#feed_fs'),
        (URL_PREFIX+'/feed/{user}', 'controllers#feed'),
        (URL_PREFIX+'/feed/{user}/fs', 'controllers#feed_fs'),

        (URL_PREFIX+'/tracking/{rng}','controllers#tracking'),

        (URL_PREFIX+'/journal', 'controllers#global_journal'),
        (URL_PREFIX+'/journal/groupby/{groupby}', 'controllers#global_journal'),

        (URL_PREFIX+'/metastate-set','controllers#metastate_set'),

        (URL_PREFIX+'/tl', 'controllers#top_level'),
        (URL_PREFIX+'/st', 'controllers#storage'),
        (URL_PREFIX+'/iterations', 'controllers#iterations'),
        (URL_PREFIX+'/participants', 'controllers#participants'),
        (URL_PREFIX+'/tags', 'controllers#tags'),
        (URL_PREFIX+'/tag/{tag}', 'controllers#bytag'),
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

        (URL_PREFIX+'/gantt_tasks/{tid}','controllers#gantt_tasks'),
        (URL_PREFIX+'/gantt/{path_info:.*}', 'noodles.utils.static#index',{'path':os.path.join(DATADIR,'sd','gantt')}),
    ])

    for pf,gethours in {'/tr':True,'':False}.items():
        mp.connect(None,URL_PREFIX+'/assignments/{person}'+pf, controller='controllers',action='assignments',gethours=gethours)
        mp.connect(None,URL_PREFIX+'/created/{person}'+pf, controller='controllers',action='created',gethours=gethours),
        mp.connect(None,URL_PREFIX+'/assignments/{person}/{mode}'+pf, controller='controllers',action='assignments_mode',gethours=gethours)
        mp.connect(None,URL_PREFIX+'/latest'+pf, controller='controllers',action='latest',gethours=gethours),
        mp.connect(None,URL_PREFIX+'/latest/{max_days}'+pf, controller='controllers',action='latest',gethours=gethours)
        
    for msabbr,msgroup in METASTATE_URLS.items():

        def mcnt(msabbr,mp):
            url = URL_PREFIX+'/'+msabbr
            # (URL_PREFIX+'/q', 'controllers#queue',{'assignee':'me'}),
            mp.connect(None,url,controller='controllers',action='queue',metastate_group=msgroup,assignee='me')
            # (URL_PREFIX+'/q/archive', 'controllers#queue',{'assignee':'me','archive':True}),
            mp.connect(None,url+'/archive',controller='controllers',action='queue',assignee='me',archive=True,metastate_group=msgroup)
            # (URL_PREFIX+'/q/assignee/{assignee}', 'controllers#queue'),
            mp.connect(None,url+'/assignee/{assignee}',controller='controllers',action='queue',metastate_group=msgroup)
            # (URL_PREFIX+'/q/assignee/{assignee}/archive', 'controllers#queue',{'archive':True}),
            mp.connect(None,url+'/assignee/{assignee}/archive',controller='controllers',action='queue',metastate_group=msgroup,archive=True)
            # (URL_PREFIX+'/q/all', 'controllers#queue'),
            mp.connect(None,url+'/all',controller='controllers',action='queue',metastate_group=msgroup)
            # (URL_PREFIX+'/q/all/archive', 'controllers#queue',{'archive':True}),
            mp.connect(None,url+'/all/archive',controller='controllers',action='queue',metastate_group=msgroup,archive=True)
            return mp

        mp = mcnt(msabbr,mp)

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
