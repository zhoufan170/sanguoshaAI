# 三国杀 AI 对战

8人三国杀 AI 对战引擎，支持 LLM Agent（DeepSeek）和随机 Agent，含 Web 可视化界面。

## 快速开始

```bash
# Mac/Linux
./run.sh --web

# Windows
.\run.ps1 --web
```

浏览器打开 `http://localhost:5000`，选择模型，点击开始游戏。

## 运行模式

```bash
# LLM 模式（命令行）
./run.sh --model deepseek-v4-pro --max-turns 50 --seed 42

# 随机AI测试
./run.sh --random --seed 42

# Web 界面（自动模式）
./run.sh --web

# Web 界面（步进模式，每步暂停）
./run.sh --web --web-step

# 回放
./run.sh --replay replay.json
./run.sh --random --seed 42 --record replay.json
```

## 配置

API Key 通过环境变量设置：

```bash
export ANTHROPIC_API_KEY="sk-..."
```

支持模型：`deepseek-v4-pro`、`deepseek-v4-flash`、`deepseek-chat`、`claude-sonnet-4-6`

## 功能

- 104 张标准牌 + 7 武器特效 + 2 防具
- 35 个武将技能 + 3 个主公技
- 完整响应系统（闪/八卦阵/无懈可击连锁/濒死求桃）
- 距离计算（跳过死亡角色，-1/+1马，马术）
- AOE 逐人结算（无懈→响应→扣血→下一位）
- LLM Agent：身份推理、策略决策、流式输出
- Web UI：上帝/公开视角、自动/步进模式、LLM 推理展示
- 回放录制/播放

## 项目结构

```
sanguosha/
  engine/        # 游戏引擎
    cards.py     # 104张标准牌
    heroes.py    # 25武将 + 技能
    game.py      # 状态机、出牌、结算
    rules.py     # 距离、伤害、判定、技能触发
    skills.py    # 主动技能处理
    responses.py # 闪/八卦阵/无懈/濒死响应
    replay.py    # 回放系统
  agent/         # AI Agent
    client.py    # LLM API (流式)
    agent.py     # LLM 决策
    prompts.py   # Prompt 模板
  web/           # Web UI
    server.py    # Flask + SSE
    templates/
    static/
  main.py        # 入口
```

## 武将一览

| 势力 | 武将 | 技能 |
|------|------|------|
| 魏 | 曹操 | 奸雄（护驾） |
| 魏 | 司马懿 | 反馈、鬼才 |
| 魏 | 夏侯惇 | 刚烈 |
| 魏 | 张辽 | 突袭 |
| 魏 | 许褚 | 裸衣 |
| 魏 | 郭嘉 | 天妒、遗计 |
| 魏 | 甄姬 | 洛神、倾国 |
| 蜀 | 刘备 | 仁德（激将） |
| 蜀 | 关羽 | 武圣 |
| 蜀 | 张飞 | 咆哮 |
| 蜀 | 诸葛亮 | 观星、空城 |
| 蜀 | 赵云 | 龙胆 |
| 蜀 | 马超 | 马术、铁骑 |
| 蜀 | 黄忠 | 烈弓 |
| 吴 | 孙权 | 制衡（救援） |
| 吴 | 周瑜 | 英姿、反间 |
| 吴 | 甘宁 | 奇袭 |
| 吴 | 吕蒙 | 克己 |
| 吴 | 黄盖 | 苦肉 |
| 吴 | 陆逊 | 谦逊、连营 |
| 吴 | 大乔 | 国色、流离 |
| 吴 | 孙尚香 | 结姻、枭姬 |
| 群 | 华佗 | 青囊、急救 |
| 群 | 吕布 | 无双 |
| 群 | 貂蝉 | 离间、闭月 |
