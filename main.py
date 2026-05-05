#!/usr/bin/env python3
"""Sanguosha 8-Agent AI Battle — 三国杀八人AI对战

Usage:
    python main.py                          # Run with LLM agents
    python main.py --random                 # Run with random agents
    python main.py --model deepseek-chat    # Use a specific model
    python main.py --record replay.json     # Save replay to file
    python main.py --replay replay.json     # Replay a saved game
"""

import argparse
import os
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.cards import build_standard_deck
from engine.heroes import assign_roles, select_heroes, Role, ALL_HEROES, hero_option_to_dict
from engine.game import SanguoshaGame, random_agent, get_player_view
from engine.replay import GameRecorder, print_replay
from agent.client import LLMClient
from agent.agent import create_agents_from_game, agent_game_callback
from agent.prompts import build_hero_select_prompt


def print_banner():
    print("=" * 50)
    print("  Sanguosha: 8-Agent AI Battle")
    print("=" * 50)


def run_random_game(num_players=8, max_turns=500, verbose=True, record_path=None):
    """Run a game with random agents for engine testing."""
    print_banner()
    print("[RANDOM] Agent mode - engine testing")
    print(f"玩家数: {num_players}\n")

    # 1. Assign roles first
    roles = assign_roles(num_players)
    random.shuffle(roles)
    # Move lord to index 0
    lord_idx = next(i for i, r in enumerate(roles) if r == Role.LORD)
    if lord_idx != 0:
        roles[0], roles[lord_idx] = roles[lord_idx], roles[0]

    # 2. Select heroes based on finalized role order (lord at index 0)
    heroes = select_heroes(num_players)

    game = SanguoshaGame(
        agent_callback=random_agent,
        num_players=num_players,
        heroes=heroes,
        roles=roles,
        verbose=verbose,
    )

    # Create recorder after game state exists
    recorder = GameRecorder(game.state, seed=0) if record_path else None
    game.recorder = recorder

    # Print from game state (accurate)
    print("[INFO] 身份分配：")
    for p in game.state.players:
        print(f"  [{p.idx}] {p.hero.name} ({p.hero.kingdom.value}) - {p.role.value}")
    print()

    # Game loop
    for _ in range(max_turns):
        if not game.run_turn():
            break

    print(f"\n[STATS] Turns: {game.state.turn_number}, Rounds: {game.state.round_number}")
    if recorder:
        recorder.set_winner(game.state.winner.value if game.state.winner else "平局",
                            game.state.turn_number, game.state.round_number)
        recorder.save(record_path)
        print(f"[REPLAY] 已保存: {record_path}")
    return game


def run_llm_game(num_players=8, max_turns=500, verbose=True,
                 provider="anthropic", model=None, api_key=None,
                 record_path=None):
    """Run a game with LLM-powered agents."""
    print_banner()
    print("[LLM] AI Agent Mode")
    print(f"Provider: {provider}, Model: {model or 'default'}")
    print(f"玩家数: {num_players}\n")

    # Initialize LLM client
    llm = LLMClient(provider=provider, model=model, api_key=api_key)
    print(f"[OK] LLM client: model={llm.model}")

    # 1. Assign roles first
    roles = assign_roles(num_players)
    random.shuffle(roles)
    lord_idx = next(i for i, r in enumerate(roles) if r == Role.LORD)
    if lord_idx != 0:
        roles[0], roles[lord_idx] = roles[lord_idx], roles[0]

    # 2. Hero selection: lord first, then distribute remaining
    lord_heroes = [h for h in ALL_HEROES if h.is_lord]
    non_lord = [h for h in ALL_HEROES if not h.is_lord]
    random.shuffle(non_lord)

    print("[HERO] ====== 武将选择 ======")
    selected_heroes = [None] * num_players

    # --- Lord picks from 5 (3 lord + 2 non-lord) ---
    lord_opts = lord_heroes + non_lord[:2]
    random.shuffle(lord_opts)
    opt_dicts = [hero_option_to_dict(h) for h in lord_opts]

    print(f"\n[0] 身份: 主公  可选武将:")
    for j, o in enumerate(opt_dicts):
        skills_str = ", ".join(f"{s['name']}" for s in o["skills"])
        lord_tag = " [主公将]" if o.get("is_lord") else ""
        print(f"    [{j}] {o['name']} ({o['kingdom']}) HP:{o['hp']}{lord_tag} | {skills_str}")

    prompt = build_hero_select_prompt(role="主公", options=opt_dicts)
    resp = llm.chat("你是三国杀玩家。只输出JSON。", prompt, temperature=0.8, max_tokens=512)
    choice = 0; reasoning = ""
    if resp.parsed_json:
        choice = resp.parsed_json.get("choice", 0)
        reasoning = resp.parsed_json.get("reasoning", "")
    if not isinstance(choice, int) or choice < 0 or choice >= len(lord_opts):
        choice = random.randint(0, len(lord_opts) - 1)
        reasoning = "(解析失败，随机选择)"

    lord_pick = lord_opts[choice]
    selected_heroes[0] = lord_pick
    print(f"  => 选择 [{choice}] {lord_pick.name}")
    if reasoning:
        print(f"     理由: {reasoning[:200]}")

    # --- Remaining 24 heroes shuffled, dealt 3 each to other 7 players ---
    remaining = [h for h in ALL_HEROES if h is not lord_pick]
    random.shuffle(remaining)
    pool = remaining[:]  # all 24 available

    for i in range(1, num_players):
        role_name = roles[i].value
        opts = pool[:3]
        opt_dicts = [hero_option_to_dict(h) for h in opts]

        print(f"\n[{i}] 身份: {role_name}  可选武将:")
        for j, o in enumerate(opt_dicts):
            skills_str = ", ".join(f"{s['name']}" for s in o["skills"])
            print(f"    [{j}] {o['name']} ({o['kingdom']}) HP:{o['hp']} | {skills_str}")

        prompt = build_hero_select_prompt(role=role_name, options=opt_dicts)
        resp = llm.chat("你是三国杀玩家。只输出JSON。", prompt, temperature=0.8, max_tokens=512)
        choice = 0; reasoning = ""
        if resp.parsed_json:
            choice = resp.parsed_json.get("choice", 0)
            reasoning = resp.parsed_json.get("reasoning", "")
        if not isinstance(choice, int) or choice < 0 or choice >= len(opts):
            choice = random.randint(0, len(opts) - 1)
            reasoning = "(解析失败，随机选择)"

        pick = opts[choice]
        selected_heroes[i] = pick
        print(f"  => 选择 [{choice}] {pick.name}")
        if reasoning:
            print(f"     理由: {reasoning[:200]}")

        # Remove pick from pool
        pool.remove(pick)
        # Remove the other 2 options from front, put at back (rotate)
        for h in opts:
            if h is not pick and h in pool:
                pool.remove(h)
                pool.append(h)
    # Summary
    print(f"\n[INFO] 武将分配：")
    for i, h in enumerate(selected_heroes):
        role_hint = "主公" if roles[i] == Role.LORD else "???"
        skills_str = ", ".join(s.name for s in h.skills)
        print(f"  [{i}] {h.name} ({h.kingdom.value}) HP:{h.hp} - {role_hint} | {skills_str}")
    print()

    # Create game with selected heroes (lord already at index 0)
    game = SanguoshaGame(
        agent_callback=lambda *a, **kw: None,
        num_players=num_players,
        heroes=selected_heroes,
        roles=roles,
        verbose=False,
    )

    # Create agents from game state
    agents = create_agents_from_game(
        [p.hero for p in game.state.players],
        [p.role for p in game.state.players],
        llm)
    callback = agent_game_callback(agents)
    game.agent_callback = callback
    game.verbose = verbose

    # Create recorder after game state exists
    recorder = GameRecorder(game.state, seed=0) if record_path else None
    game.recorder = recorder

    # Game loop
    total_tokens = 0
    for turn in range(max_turns):
        if not game.run_turn():
            break

        # Print token usage periodically
        if verbose and turn > 0 and turn % 8 == 0:
            tokens = sum(a.total_tokens for a in agents)
            print(f"  [TOKENS] Total: {tokens}")

    # Final stats
    total_tokens = sum(a.total_tokens for a in agents)
    print(f"\n[STATS] Game over:")
    print(f"  回合数: {game.state.turn_number}")
    print(f"  轮数: {game.state.round_number}")
    print(f"  胜利方: {game.state.winner.value if game.state.winner else '平局'}")
    print(f"  Token消耗: ~{total_tokens}")

    if recorder:
        recorder.set_winner(game.state.winner.value if game.state.winner else "平局",
                            game.state.turn_number, game.state.round_number)
        recorder.save(record_path)
        print(f"[REPLAY] 已保存: {record_path}")

    return game


def main():
    parser = argparse.ArgumentParser(description="三国杀 AI Agent 对战")
    parser.add_argument("--random", action="store_true", help="使用随机Agent测试引擎")
    parser.add_argument("--players", type=int, default=8, help="玩家数量 (默认8)")
    parser.add_argument("--max-turns", type=int, default=500, help="最大回合数 (默认500)")
    parser.add_argument("--provider", default="anthropic", help="LLM provider (anthropic/openai)")
    parser.add_argument("--model", default=None, help="模型名称")
    parser.add_argument("--api-key", default=None, help="API Key")
    parser.add_argument("--quiet", action="store_true", help="减少输出")
    parser.add_argument("--seed", type=int, default=None, help="随机种子")
    parser.add_argument("--record", default=None, help="保存回放到指定文件")
    parser.add_argument("--replay", default=None, help="回放已保存的游戏文件")
    parser.add_argument("--web", type=int, const=5000, nargs="?", default=None,
                        help="启动Web UI服务器（可选端口，默认5000）")
    parser.add_argument("--web-step", action="store_true", help="Web默认手动步进模式")
    parser.add_argument("--web-god", action="store_true", help="Web默认上帝视角")

    args = parser.parse_args()

    # Web UI mode
    if args.web is not None:
        from web.server import run_server
        port = args.web if isinstance(args.web, int) else 5000
        print(f"[WEB] 启动Web服务器: http://localhost:{port}")
        print(f"[WEB] 步进模式: {'是' if args.web_step else '否'}, 上帝视角: {'是' if args.web_god else '否'}")
        run_server(port=port, open_browser=True)
        return

    # Replay mode
    if args.replay:
        data = GameRecorder.load(args.replay)
        print_replay(data)
        return

    if args.seed is not None:
        random.seed(args.seed)

    verbose = not args.quiet
    recorder = None
    if args.record:
        # Recorder will be initialized after game state is created
        pass

    record_path = args.record

    if args.random:
        run_random_game(
            num_players=args.players,
            max_turns=args.max_turns,
            verbose=verbose,
            record_path=record_path,
        )
    else:
        run_llm_game(
            num_players=args.players,
            max_turns=args.max_turns,
            verbose=verbose,
            provider=args.provider,
            model=args.model,
            api_key=args.api_key,
            record_path=record_path,
        )


if __name__ == "__main__":
    main()
