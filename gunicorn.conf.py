import os
import multiprocessing

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"
backlog = 2048

# Worker processes
workers = 1  # Fixed to 1 for Cloud Run
worker_class = 'sync'  # Using sync for Flask compatibility
threads = 4
worker_connections = 1000
timeout = 0
keepalive = 2

# Process naming
proc_name = 'asistente'

# Logging
loglevel = 'info'
accesslog = '-'
errorlog = '-'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# SSL
keyfile = None
certfile = None

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Debugging
reload = False
reload_engine = 'auto'
spew = False
check_config = False