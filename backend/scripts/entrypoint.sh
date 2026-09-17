#!/bin/sh
set -e

echo "Starting AI Office IT Help Desk..."

# Run database initialization & migrations
python scripts/init_db.py

# Execute the main container command (e.g. uvicorn)
exec "$@"
