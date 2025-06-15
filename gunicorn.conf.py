# Gunicorn configuration for production
# This file is only used in production, not in local development

import multiprocessing
import os

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = 2  # As requested: 2 workers
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000  # Restart workers after 1000 requests to prevent memory leaks
max_requests_jitter = 50  # Add randomness to prevent all workers restarting at once

# Timeouts
timeout = 120  # 2 minutes for long operations (file uploads, etc.)
keepalive = 2
graceful_timeout = 30

# Process naming
proc_name = "quiz-app-backend"

# User and group (matches Dockerfile)
user = "fastapi"
group = "fastapi"

# Logging
loglevel = "info"
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process management
preload_app = True  # Load application code before forking workers (better memory usage)
reload = False      # Disable auto-reload in production
daemon = False      # Don't daemonize (Docker handles this)

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Performance tuning
worker_tmp_dir = "/dev/shm"  # Use shared memory for better performance

# Hooks for application lifecycle
def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Starting Quiz App Backend with Gunicorn")

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("Reloading Quiz App Backend")

def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    server.log.info(f"Worker {worker.pid} is being forked")

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info(f"Worker {worker.pid} has been forked")

def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    worker.log.info(f"Worker {worker.pid} received SIGABRT signal") 