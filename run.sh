#!/bin/bash
# 三国杀 AI 对战 启动脚本 (Mac/Linux)
export PYTHONIOENCODING=utf-8
cd "$(dirname "$0")"

# Parse --api-key
API_KEY=""
ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --api-key) API_KEY="$2"; shift 2 ;;
        --api-key=*) API_KEY="${1#*=}"; shift ;;
        *) ARGS+=("$1"); shift ;;
    esac
done

if [ -n "$API_KEY" ]; then
    export ANTHROPIC_API_KEY="$API_KEY"
elif [ -z "$ANTHROPIC_API_KEY" ]; then
    export ANTHROPIC_API_KEY="your-api-key-here"
fi

python3 sanguosha/main.py "${ARGS[@]}"
