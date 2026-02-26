#!/bin/bash

trap 'kill 0' EXIT

echo "Starting backend..."
python main.py &

echo "Starting frontend..."
cd frontend && pnpm run dev &

wait
