"""Flask web server for Sanguosha game visualization with event-level stepping."""
from __future__ import annotations
import json
import queue
import threading
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, Response, render_template, request, jsonify
from engine.cards import build_standard_deck, shuffle_and_deal
from engine.heroes import assign_roles, select_heroes, Role, ALL_HEROES, hero_option_to_dict
from engine.game import SanguoshaGame, random_agent, get_player_view, create_game
from engine.rules import Action, ActionType

app = Flask(__name__)


class StepController:
    """Controls game stepping: wraps agent_callback to pause at each decision point."""

    def __init__(self, event_queue: queue.Queue, step_mode: bool = True, auto_delay: float = 0.1):
        self.q = event_queue
        self.step_mode = step_mode
        self.auto_delay = auto_delay
        self.step_event = threading.Event()
        self.log_len = 0  # track which events have been pushed

    def set_step_mode(self, on: bool):
        self.step_mode = on

    def do_step(self):
        """Signal the game thread to advance one step."""
        self.step_event.set()

    def wait_for_step(self):
        """Block until user clicks step."""
        self.step_event.clear()
        self.step_event.wait(timeout=300)

    def push_new_events(self):
        """Push any game events that haven't been sent yet."""
        g = game_state.get("game")
        if not g or not g.state:
            return
        log = g.state.log
        for evt in log[self.log_len:]:
            self.q.put({
                "type": "event",
                "data": {
                    "description": evt.description,
                    "actor_idx": evt.actor_idx,
                    "target_idx": evt.target_idx,
                }
            })
        self.log_len = len(log)

    def wrap_agent(self, real_agent):
        """Wrap an agent callback with step barriers at each decision point."""

        def wrapped(view: dict, phase: str, **kwargs) -> Action | None:
            player_idx = view["player_idx"]
            player_name = view["my_hero"]

            # Push accumulated events before this decision
            self.push_new_events()

            # Build decision context
            ctx = self._build_context(view, phase, kwargs)

            # Push pre-decision state
            self.q.put({
                "type": "awaiting_decision",
                "data": {
                    "player_idx": player_idx,
                    "player_name": player_name,
                    "phase": phase,
                    "context": ctx,
                }
            })
            self.q.put({
                "type": "state",
                "data": _build_state_snapshot(game_state.get("game").state if game_state.get("game") else None,
                                              god_view=game_state["god_view"])
            })

            # Wait for user (step mode) or brief delay (auto mode)
            if self.step_mode:
                self.wait_for_step()
            else:
                time.sleep(self.auto_delay)

            if not game_state.get("running", False):
                return None

            # Call the real agent
            action = real_agent(view, phase, **kwargs)

            # Push decision result
            if action:
                self.q.put({
                    "type": "decision_made",
                    "data": {
                        "player_idx": player_idx,
                        "player_name": player_name,
                        "phase": phase,
                        "action_type": action.type.value,
                        "card_name": action.card_name,
                        "skill_name": action.skill_name,
                        "target_idx": action.target_idx,
                        "reasoning": action.reasoning or "",
                        "suspicion": action.suspicion or {},
                        "cards_used": action.cards_used,
                    }
                })
                # Push events that happened as result of this action
                self.push_new_events()
                # Push state update after decision + events
                if game_state.get("game"):
                    self.q.put({
                        "type": "state",
                        "data": _build_state_snapshot(game_state["game"].state,
                                                      god_view=game_state["god_view"])
                    })
            return action

        return wrapped

    def _build_context(self, view: dict, phase: str, kwargs: dict) -> str:
        """Build human-readable context for the current decision."""
        player_name = view["my_hero"]
        if phase == "play_phase":
            return f"{player_name}的出牌阶段 — 选择出牌或发动技能"
        elif phase == "response":
            rt = kwargs.get("response_type", "")
            sc = kwargs.get("source_card", "")
            si = kwargs.get("source_idx", 0)
            src_name = view["players"][si]["name"] if si < len(view["players"]) else "?"
            return f"{src_name}使用了【{sc}】，{player_name}需要打出【{rt}】"
        elif phase == "negate":
            cn = kwargs.get("card_name", "")
            si = kwargs.get("source_idx", 0)
            src_name = view["players"][si]["name"] if si < len(view["players"]) else "?"
            return f"{src_name}使用了【{cn}】，{player_name}是否打出【无懈可击】？"
        elif phase == "dying":
            di = kwargs.get("dying_idx", -1)
            dn = view["players"][di]["name"] if di < len(view["players"]) else "?"
            return f"{dn}濒死，{player_name}是否使用【桃】救援？"
        elif phase == "discard_phase":
            dc = kwargs.get("discard_count", 0)
            return f"{player_name}的弃牌阶段 — 需要弃置{dc}张牌"
        elif phase == "prepare_phase":
            return f"{player_name}的准备阶段 — 是否发动【洛神】？"
        elif phase == "draw_phase":
            return f"{player_name}的摸牌阶段 — 是否发动【突袭】？"
        elif phase == "guicai":
            ctx = kwargs.get("context", "")
            return f"判定【{ctx}】，{player_name}是否发动【鬼才】替换判定牌？"
        elif phase == "fanjian_guess":
            si = kwargs.get("source_idx", 0)
            src_name = view["players"][si]["name"] if si < len(view["players"]) else "?"
            cn = kwargs.get("card_name", "")
            return f"{src_name}发动【反间】给了【{cn}】，{player_name}猜花色"
        elif phase == "ganglie_choice":
            si = kwargs.get("source_idx", 0)
            src_name = view["players"][si]["name"] if si < len(view["players"]) else "?"
            return f"{src_name}发动【刚烈】，{player_name}选择受1伤还是弃2牌？"
        elif phase == "liuli_redirect":
            si = kwargs.get("source_idx", 0)
            src_name = view["players"][si]["name"] if si < len(view["players"]) else "?"
            return f"{src_name}对你使用【杀】，是否发动【流离】转移？"
        elif phase == "wugu_pick":
            return f"【五谷丰登】选牌 — {player_name}选择一张牌"
        elif phase == "yiji_distribute":
            return f"【遗计】分牌 — {player_name}选择分配手牌给其他角色"
        elif phase == "jiedao_choice":
            si = kwargs.get("source_idx", 0)
            src = view["players"][si]["name"] if si < len(view["players"]) else "?"
            si2 = kwargs.get("secondary_idx", 0)
            sec = view["players"][si2]["name"] if si2 < len(view["players"]) else "?"
            return f"{src}借刀杀人 — {player_name}选择对{sec}出【杀】还是给武器？"
        elif phase == "cxt_option":
            si = kwargs.get("source_idx", 0)
            src = view["players"][si]["name"] if si < len(view["players"]) else "?"
            return f"【雌雄双股剑】— {player_name}选择弃1张牌或让{src}摸1张牌？"
        elif phase == "guanshi_axe":
            ti = kwargs.get("target_idx", 0)
            tgt = view["players"][ti]["name"] if ti < len(view["players"]) else "?"
            return f"【贯石斧】— {player_name}弃2张牌强制命中{tgt}？"
        elif phase == "qinglong_blade":
            ti = kwargs.get("target_idx", 0)
            tgt = view["players"][ti]["name"] if ti < len(view["players"]) else "?"
            return f"【青龙偃月刀】— {player_name}追加一张【杀】对{tgt}？"
        elif phase == "hanbing_sword":
            ti = kwargs.get("target_idx", 0)
            tgt = view["players"][ti]["name"] if ti < len(view["players"]) else "?"
            return f"【寒冰剑】— {player_name}弃2张牌改为弃{tgt}的牌？"
        elif phase == "qilin_bow":
            ti = kwargs.get("target_idx", 0)
            tgt = view["players"][ti]["name"] if ti < len(view["players"]) else "?"
            mt = kwargs.get("mounts", [])
            return f"【麒麟弓】— {player_name}是否弃置{tgt}的{'/'.join(mt)}？"
        elif phase == "guanxing":
            cards = kwargs.get("cards", [])
            return f"【观星】— {player_name}排列牌堆顶: {', '.join(cards)}"
        elif phase == "fankui":
            si = kwargs.get("source_idx", 0)
            src = view["players"][si]["name"] if si < len(view["players"]) else "?"
            return f"【反馈】— {player_name}是否从{src}获得一张牌？"
        return f"{player_name}的{phase}决策"


# Global game state
game_state = {
    "running": False,
    "god_view": True,
    "event_queue": queue.Queue(),
    "game": None,
    "agents": None,
    "controller": None,
}


def get_god_view(state) -> dict:
    """Build full god-view of all players (reveals hands and roles)."""
    if state is None:
        return {"players": []}
    players = []
    for p in state.players:
        players.append({
            "idx": p.idx,
            "name": p.hero.name,
            "kingdom": p.hero.kingdom.value,
            "gender": p.hero.gender,
            "role": p.role.value,
            "hp": p.hp,
            "max_hp": p.max_hp,
            "alive": p.alive,
            "hand": [{"name": c.name, "suit": c.suit.value, "type": c.type.value} for c in p.hand],
            "equipment": [{"name": c.name, "suit": c.suit.value} for c in p.equipment],
            "delay_cards": [c.name for c in p.delay_cards],
            "skills": [s.name for s in p.hero.skills],
            "lord_skill": p.hero.lord_skill.name if p.hero.lord_skill else "",
        })
    return {
        "players": players,
        "active_player": state.active_player,
        "phase": state.phase.value,
        "turn_number": state.turn_number,
        "round_number": state.round_number,
        "game_over": state.game_over,
        "winner": state.winner.value if state.winner else None,
        "alive_count": sum(1 for p in state.players if p.alive),
        "draw_pile_count": len(state.draw_pile),
        "discard_pile_count": len(state.discard_pile),
        "discard_cards": [str(c) for c in state.discard_pile[-20:]],
        "discard_total": len(state.discard_pile),
    }


def get_public_view(state) -> dict:
    """Build public-only view (hides hands and non-lord roles)."""
    if state is None:
        return {"players": []}
    players = []
    for p in state.players:
        pub = {
            "idx": p.idx,
            "name": p.hero.name,
            "kingdom": p.hero.kingdom.value,
            "gender": p.hero.gender,
            "role": "主公" if p.role == Role.LORD else "???",
            "hp": p.hp,
            "max_hp": p.max_hp,
            "alive": p.alive,
            "hand": [],
            "hand_count": len(p.hand),
            "equipment": [{"name": c.name, "suit": c.suit.value} for c in p.equipment],
            "delay_cards": [c.name for c in p.delay_cards],
            "skills": [s.name for s in p.hero.skills],
            "lord_skill": p.hero.lord_skill.name if p.hero.lord_skill else "",
        }
        players.append(pub)
    return {
        "players": players,
        "active_player": state.active_player,
        "phase": state.phase.value,
        "turn_number": state.turn_number,
        "round_number": state.round_number,
        "game_over": state.game_over,
        "winner": state.winner.value if state.winner else None,
        "alive_count": sum(1 for p in state.players if p.alive),
        "draw_pile_count": len(state.draw_pile),
        "discard_pile_count": len(state.discard_pile),
        "discard_cards": [str(c) for c in state.discard_pile[-20:]],
        "discard_total": len(state.discard_pile),
    }


def _build_state_snapshot(state, god_view: bool = True) -> dict:
    if god_view:
        return get_god_view(state)
    return get_public_view(state)


def _game_runner(seed: int = None, max_turns: int = 500, use_random: bool = True,
                 model: str = None, api_key: str = None):
    """Run game in background thread, pushing events to queue."""
    import random as _random
    import traceback

    q = game_state["event_queue"]
    ctrl = game_state["controller"]

    try:
        if seed is not None:
            _random.seed(seed)

        q.put({"type": "status", "data": "正在初始化游戏..."})

        # 1. Assign roles
        roles = assign_roles(8)
        _random.shuffle(roles)
        lord_idx = next(i for i, r in enumerate(roles) if r == Role.LORD)
        if lord_idx != 0:
            roles[0], roles[lord_idx] = roles[lord_idx], roles[0]

        # 2. Select heroes
        if use_random:
            heroes = select_heroes(8)
            q.put({"type": "status", "data": "使用随机AI模式"})
            base_agent = random_agent
        else:
            try:
                from agent.client import LLMClient
                from agent.agent import create_agents_from_game, agent_game_callback
                from agent.prompts import build_hero_select_prompt
                from engine.heroes import ALL_HEROES, hero_option_to_dict
                q.put({"type": "status", "data": f"连接LLM: {model}..."})
                llm = LLMClient(model=model, api_key=api_key)
                q.put({"type": "status", "data": f"LLM就绪: provider={llm.provider}, model={llm.model}"})

                # LLM hero selection
                q.put({"type": "status", "data": "===== 武将选择 ====="})
                selected_heroes = [None] * 8
                lord_heroes = [h for h in ALL_HEROES if h.is_lord]
                non_lord = [h for h in ALL_HEROES if not h.is_lord]
                _random.shuffle(non_lord)

                # Lord: 5 options
                lord_opts = lord_heroes + non_lord[:2]
                _random.shuffle(lord_opts)
                opt_dicts = [hero_option_to_dict(h) for h in lord_opts]
                opt_lines = []
                for j, o in enumerate(opt_dicts):
                    skills_str = ", ".join(f"{s['name']}" for s in o["skills"])
                    opt_lines.append(f"[{j}] {o['name']} ({o['kingdom']}) HP:{o['hp']} | {skills_str}")
                q.put({"type": "hero_select", "data": {"player_idx": 0, "role": "主公", "options": "\n".join(opt_lines)}})
                q.put({"type": "status", "data": "主公选择武将中..."})

                prompt = build_hero_select_prompt(role="主公", options=opt_dicts)
                print(f"\n[LLM PROMPT] 主公选将\n{'-'*40}\n{prompt[:2000]}\n[LLM WAIT] calling API...")
                resp = llm.chat("你是三国杀玩家。只输出JSON。", prompt, temperature=0.8, max_tokens=512)
                print(f"[LLM RESPONSE] {resp.content[:500]}")
                choice = 0; reasoning = ""
                if resp.parsed_json:
                    choice = resp.parsed_json.get("choice", 0)
                    reasoning = resp.parsed_json.get("reasoning", "")
                if not isinstance(choice, int) or choice < 0 or choice >= len(lord_opts):
                    choice = _random.randint(0, len(lord_opts) - 1)
                    reasoning = "(解析失败，随机选择)"
                lord_pick = lord_opts[choice]
                selected_heroes[0] = lord_pick
                q.put({"type": "hero_pick", "data": {"player_idx": 0, "hero": lord_pick.name, "reasoning": reasoning}})

                # Others: 3 each
                remaining = [h for h in ALL_HEROES if h is not lord_pick]
                _random.shuffle(remaining)
                pool = remaining[:]
                for i in range(1, 8):
                    role_name = roles[i].value
                    opts = pool[:3]
                    opt_dicts2 = [hero_option_to_dict(h) for h in opts]
                    opt_lines2 = []
                    for j, o in enumerate(opt_dicts2):
                        skills_str = ", ".join(f"{s['name']}" for s in o["skills"])
                        opt_lines2.append(f"[{j}] {o['name']} ({o['kingdom']}) HP:{o['hp']} | {skills_str}")
                    q.put({"type": "hero_select", "data": {"player_idx": i, "role": role_name, "options": "\n".join(opt_lines2)}})
                    q.put({"type": "status", "data": f"[{i}] {role_name}选择武将中..."})

                    prompt2 = build_hero_select_prompt(role=role_name, options=opt_dicts2)
                    print(f"\n[LLM PROMPT] Player {i} ({role_name}) 选将\n{'-'*40}\n{prompt2[:2000]}\n[LLM WAIT] calling API...")
                    resp2 = llm.chat("你是三国杀玩家。只输出JSON。", prompt2, temperature=0.8, max_tokens=512)
                    print(f"[LLM RESPONSE] {resp2.content[:500]}")
                    choice2 = 0; reasoning2 = ""
                    if resp2.parsed_json:
                        choice2 = resp2.parsed_json.get("choice", 0)
                        reasoning2 = resp2.parsed_json.get("reasoning", "")
                    if not isinstance(choice2, int) or choice2 < 0 or choice2 >= len(opts):
                        choice2 = _random.randint(0, len(opts) - 1)
                        reasoning2 = "(解析失败，随机选择)"
                    pick = opts[choice2]
                    selected_heroes[i] = pick
                    q.put({"type": "hero_pick", "data": {"player_idx": i, "hero": pick.name, "reasoning": reasoning2}})
                    pool.remove(pick)
                    for h in opts:
                        if h is not pick and h in pool:
                            pool.remove(h); pool.append(h)

                heroes = selected_heroes
                q.put({"type": "status", "data": "LLM Agent初始化..."})

                game_temp = SanguoshaGame(
                    agent_callback=lambda *a, **kw: None,
                    num_players=8, heroes=heroes, roles=roles, verbose=False,
                )
                agents = create_agents_from_game(
                    [p.hero for p in game_temp.state.players],
                    [p.role for p in game_temp.state.players],
                    llm)
                game_state["agents"] = agents
                base_agent = agent_game_callback(agents)
                q.put({"type": "status", "data": "LLM Agent初始化完成"})
            except Exception as e:
                traceback.print_exc()
                q.put({"type": "status", "data": f"LLM初始化失败: {e}"})
                q.put({"type": "status", "data": "回退随机AI模式"})
                heroes = select_heroes(8)
                base_agent = random_agent

        # Wrap with step controller
        wrapped_callback = ctrl.wrap_agent(base_agent)

        # 4. Create game
        q.put({"type": "status", "data": "创建游戏..."})
        game = SanguoshaGame(
            agent_callback=wrapped_callback,
            num_players=8,
            heroes=heroes,
            roles=roles,
            verbose=False,
        )
        game_state["game"] = game

        q.put({"type": "status", "data": "游戏开始！"})
        q.put({"type": "state", "data": _build_state_snapshot(game.state, god_view=game_state["god_view"])})

        # 5. Game loop
        for turn_idx in range(max_turns):
            if not game_state["running"]:
                break

            player = game.state.players[game.state.active_player]
            q.put({
                "type": "turn_start",
                "data": {
                    "player_idx": game.state.active_player,
                    "player_name": player.name,
                    "role": player.role.value,
                    "round": game.state.round_number,
                    "turn": game.state.turn_number,
                }
            })

            game.run_turn()

            ctrl.push_new_events()
            q.put({
                "type": "state",
                "data": _build_state_snapshot(game.state, god_view=game_state["god_view"])
            })

            if game.state.game_over:
                q.put({
                    "type": "game_over",
                    "data": {
                        "winner": game.state.winner.value,
                        "total_turns": game.state.turn_number,
                        "total_rounds": game.state.round_number,
                    }
                })
                break

    except Exception as e:
        traceback.print_exc()
        q.put({"type": "status", "data": f"游戏异常: {e}"})
        q.put({"type": "game_over", "data": {"winner": "异常终止", "total_turns": 0, "total_rounds": 0}})

    game_state["running"] = False
    q.put({"type": "status", "data": "游戏结束"})


# === Flask Routes ===

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/stream")
def stream():
    """SSE endpoint for real-time game events."""
    def event_stream():
        q = game_state["event_queue"]
        while True:
            try:
                event = q.get(timeout=30)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("type") == "game_over":
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                if not game_state["running"]:
                    break
    return Response(event_stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/start", methods=["POST"])
def api_start():
    """Start a new game."""
    data = request.get_json() or {}
    step_mode = data.get("step_mode", True)
    game_state["god_view"] = data.get("god_view", True)
    game_state["running"] = True

    # Create step controller
    ctrl = StepController(
        game_state["event_queue"],
        step_mode=step_mode,
        auto_delay=data.get("auto_delay", 0.4),
    )
    game_state["controller"] = ctrl

    use_random = data.get("use_random", True)
    thread = threading.Thread(
        target=_game_runner,
        kwargs={
            "seed": data.get("seed"),
            "max_turns": data.get("max_turns", 500),
            "use_random": use_random,
            "model": data.get("model"),
            "api_key": data.get("api_key"),
        },
        daemon=True,
    )
    thread.start()
    return jsonify({"status": "started"})


@app.route("/api/step", methods=["POST"])
def api_step():
    """Advance one step (one agent decision)."""
    ctrl = game_state.get("controller")
    if ctrl:
        ctrl.do_step()
    return jsonify({"status": "stepping"})


@app.route("/api/mode", methods=["POST"])
def api_mode():
    """Toggle step/auto mode or god/public view."""
    data = request.get_json() or {}
    ctrl = game_state.get("controller")
    if "step_mode" in data and ctrl:
        ctrl.set_step_mode(data["step_mode"])
        # If switching to auto, release any pending step
        if not data["step_mode"]:
            ctrl.do_step()
    if "god_view" in data:
        game_state["god_view"] = data["god_view"]
        if game_state["game"]:
            snap = _build_state_snapshot(game_state["game"].state,
                                        god_view=game_state["god_view"])
            game_state["event_queue"].put({"type": "state", "data": snap})
    return jsonify({
        "step_mode": ctrl.step_mode if ctrl else True,
        "god_view": game_state["god_view"],
    })


@app.route("/api/state", methods=["GET"])
def api_state():
    """Get current full state."""
    if game_state["game"]:
        snap = _build_state_snapshot(game_state["game"].state,
                                    god_view=game_state["god_view"])
        return jsonify(snap)
    return jsonify({"error": "no game"})


def run_server(port: int = 5000, open_browser: bool = True):
    """Start the Flask web server."""
    if open_browser:
        import webbrowser
        webbrowser.open(f"http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
