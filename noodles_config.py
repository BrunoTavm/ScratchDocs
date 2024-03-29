

#noodles settings:
import os

DEBUG = True
TESTING = True

NO_GEVENT_MONKEYPATCH=True
DONT_USE_GEVENT=True
AUTO_RELOAD = DONT_USE_GEVENT #only supported by paster

# Specify the server port
PORT = 8090
ENCODING = 'utf-8'  # default application encoding

APP_DIR = os.path.join(os.getcwd(),'sd')

# Specify URL resolver module, this must contain get_map
# function which returnes mapper object
# urls.py module is default
URL_RESOLVER = 'urls'

# Specify controllers modules
CONTROLLERS = ['controllers', 'noodles.utils.static']

# Specify Redis-server host there
REDIS_HOST = 'localhost'

# Specify root dir for static content here
STATIC_ROOT = os.path.join(os.getcwd(), 'static')

# Specify here a template directories
TEMPLATE_DIRS = [
    os.path.join(APP_DIR, 'n_templates'),
# Add here other directories if you need
]

# Specify here mako temporary dir for precompiled templates
MAKO_TMP_DIR = os.path.join(APP_DIR, 'tmp/modules')

MIDDLEWARES = [
    # Specify list of middlewares used in your application here
    #'session.SessionMiddleware',
]

SERVER_LOGTYPE = 'default'
####Mail parameters
NOODLES_ERROR_RECIPIENT = [
    #List with default error mail recipient
]
NOODLES_ERROR_SENDER = 'noodles_error@mail.domain.com'
MAIL_SERVER = 'smtp.example.com'
MAIL_PORT = 587
MAIL_LOGIN = 'your smtp mail login'
MAIL_PASSWORD = 'your smtp mail password'
URL_PREFIX=''
WEBAPP_FORCE_IDENTITY=False
NOPUSH=True
NOCOMMIT=False
