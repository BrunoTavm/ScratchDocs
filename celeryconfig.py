from datetime import timedelta

BROKER_URL='redis://localhost'
CELERYD_CONCURRENCY=1
CELERYD_MAX_TASKS_PER_CHILD=5
CELERYBEAT_SCHEDULE = {
    'feed-populate': {
        'task': 'tasks.changes_to_feed',
        'schedule': timedelta(minutes=15),
    },
}
