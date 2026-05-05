#!/bin/bash
# 三国杀 AI 对战 启动脚本 (Mac/Linux)
export PYTHONIOENCODING=utf-8

# API Key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    export ANTHROPIC_API_KEY="your-api-key-here"
fi

# Install dependencies if needed
# pip3 install flask openai anthropic

python3 sanguosha/main.py "$@"
