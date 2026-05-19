#!/bin/sh
set -e
# Default backend if not provided
: "${BACKEND_URL:=http://localhost:8080}"

# Replace placeholder in the template and write final index.html
envsubst '$BACKEND_URL' < /usr/share/nginx/html/index.html.template > /usr/share/nginx/html/index.html

# Execute the container command (nginx)
exec "$@"
