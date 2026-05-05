"""Game replay recording and playback for Sanguosha."""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ReplayEvent:
    turn: int
    round_num: int
    player_idx: int
    player_name: str
    phase: str
    description: str
    actor_idx: int | None = None
    target_idx: int | None = None
    card_name: str | None = None


@dataclass
class ReplayTurn:
    turn_number: int
    round_number: int
    player_idx: int
    player_name: str
    player_role: str
    events: list[ReplayEvent] = field(default_factory=list)
    agent_reasoning: list[str] = field(default_factory=list)


@dataclass
class ReplayData:
    version: int = 1
    timestamp: str = ""
    seed: int = 0
    num_players: int = 8
    players: list[dict] = field(default_factory=list)
    turns: list[ReplayTurn] = field(default_factory=list)
    winner: str = ""
    total_turns: int = 0
    total_rounds: int = 0


class GameRecorder:
    """Records game events for later replay."""

    def __init__(self, state, seed: int = 0):
        self.state = state
        self.data = ReplayData(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            seed=seed,
            num_players=len(state.players),
            players=[
                {
                    "idx": p.idx,
                    "name": p.hero.name,
                    "kingdom": p.hero.kingdom.value,
                    "role": p.role.value,
                    "hp": p.hero.hp,
                    "skills": [s.name for s in p.hero.skills],
                    "gender": p.hero.gender,
                }
                for p in state.players
            ],
        )
        self.current_turn: ReplayTurn | None = None

    def start_turn(self, player_idx: int, player_name: str, player_role: str,
                   turn_number: int, round_number: int):
        self.current_turn = ReplayTurn(
            turn_number=turn_number,
            round_number=round_number,
            player_idx=player_idx,
            player_name=player_name,
            player_role=player_role,
        )

    def record_event(self, description: str, actor_idx: int | None = None,
                     target_idx: int | None = None, card_name: str | None = None,
                     phase: str = ""):
        if self.current_turn is None:
            return
        self.current_turn.events.append(ReplayEvent(
            turn=self.current_turn.turn_number,
            round_num=self.current_turn.round_number,
            player_idx=self.current_turn.player_idx,
            player_name=self.current_turn.player_name,
            phase=phase,
            description=description,
            actor_idx=actor_idx,
            target_idx=target_idx,
            card_name=card_name,
        ))

    def record_reasoning(self, reasoning: str):
        if self.current_turn and reasoning:
            self.current_turn.agent_reasoning.append(reasoning[:200])

    def end_turn(self):
        if self.current_turn:
            self.data.turns.append(self.current_turn)
            self.current_turn = None

    def set_winner(self, winner: str, total_turns: int, total_rounds: int):
        self.data.winner = winner
        self.data.total_turns = total_turns
        self.data.total_rounds = total_rounds

    def to_dict(self) -> dict:
        return asdict(self.data)

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @staticmethod
    def load(path: str) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


def print_replay(data: dict, show_reasoning: bool = True):
    """Print a human-readable replay from saved replay data."""
    meta = data
    print("=" * 60)
    print(f"  三国杀 AI 对战回放")
    print("=" * 60)
    print(f"时间: {meta.get('timestamp', 'unknown')}")
    print(f"种子: {meta.get('seed', '?')}  |  玩家: {meta.get('num_players', '?')}人")
    print(f"胜利方: {meta.get('winner', '?')}")
    print(f"总回合: {meta.get('total_turns', '?')}  |  总轮数: {meta.get('total_rounds', '?')}")
    print()

    print("[身份分配]")
    for p in meta.get("players", []):
        kingdom = p.get("kingdom", "")
        skills = ", ".join(p.get("skills", []))
        print(f"  [{p['idx']}] {p['name']} ({kingdom}) HP:{p['hp']} - {p['role']} | {skills}")
    print()

    for turn in meta.get("turns", []):
        rn = turn["round_number"]
        tn = turn["turn_number"]
        pname = turn["player_name"]
        prole = turn["player_role"]
        print(f"--- 第{rn}轮 T{tn} | {pname} ({prole}) ---")

        if show_reasoning:
            for r in turn.get("agent_reasoning", []):
                if r:
                    print(f"  [推理] {r[:150]}")

        for evt in turn.get("events", []):
            phase = evt.get("phase", "")
            desc = evt.get("description", "")
            if phase:
                print(f"  [{phase}] {desc}")
            else:
                print(f"  {desc}")
        print()

    print(f"[游戏结束] 胜利方: {meta.get('winner', '?')}")
