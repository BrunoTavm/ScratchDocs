# -*- coding: utf-8 -*-
'''
filedesc: default controller file
'''
from noodles.http import Response


from tasks import parse_story_fn as parse_fn
from tasks import get_task_files as get_fns
from tasks import get_task,get_children,get_iterations

from noodles.templates import render_to

@render_to('index.html')
def index(request):
    its = get_iterations()
    return {'its':its}

@render_to('iteration.html')
def iteration(request,iteration):
    tasks = [parse_fn(fn,read=True) for fn in get_fns(iteration=iteration)]
    return {'tasks':tasks,'headline':'Iteration %s'%iteration}

@render_to('iteration.html')
def assignments(request,person):
    tasks = [parse_fn(fn,read=True) for fn in get_fns(assignee=person)]
    return {'tasks':tasks,'headline':'Assignments for %s'%person}
@render_to('task.html')
def task(request,task):
    t = get_task(task,read=True)
    cont = open(t['path'],'r').read()
    return {'task':t,'cont':cont}
