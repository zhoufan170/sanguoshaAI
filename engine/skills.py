"""Hero skill resolution for Sanguosha."""
from __future__ import annotations
from typing import Any

from engine.cards import Card, CardType
from engine.heroes import Hero, Role, Kingdom
from engine.rules import (
    Action, ActionType, GameEvent, deal_damage, has_skill,
    remove_from_hand, check_lianying,
)
from engine.responses import request_response

AgentCallback = Any


def resolve_skill(state, action: Action, agent_callback: Any = None) -> list[GameEvent]:
    """Resolve a hero skill activation. Returns list of events."""
    events = []
    player = state.players[action.player_idx]

    if action.skill_name == "苦肉":
        if action.cards_used:
            c = next((x for x in player.hand if x.name == action.cards_used[0]), None)
            if c:
                player.hand.remove(c)
                state.discard_pile.append(c)
        player.hp -= 1
        drawn = state._draw(action.player_idx, 2)
        c_str = " ".join(str(c) for c in drawn)
        events.append(GameEvent(f"{player.name}苦肉：弃1张牌，失去1点体力，摸: {c_str}"))

    elif action.skill_name == "制衡":
        discarded = 0
        for cn in action.cards_used:
            c = next((x for x in player.hand if x.name == cn), None)
            if c:
                player.hand.remove(c)
                state.discard_pile.append(c)
                discarded += 1
        if discarded > 0:
            drawn = state._draw(action.player_idx, discarded)
            c_str = " ".join(str(c) for c in drawn)
            events.append(GameEvent(f"{player.name}制衡：弃{discarded}张牌，摸: {c_str}"))

    elif action.skill_name == "青囊":
        if action.target_idx is not None and action.cards_used:
            c = next((x for x in player.hand if x.name == action.cards_used[0]), None)
            if c:
                player.hand.remove(c)
                state.discard_pile.append(c)
            target = state.players[action.target_idx]
            target.hp = min(target.hp + 1, target.max_hp)
            events.append(GameEvent(f"{player.name}青囊：令{target.name}回复1点体力"))

    elif action.skill_name == "离间":
        if action.cards_used:
            c = next((x for x in player.hand if x.name == action.cards_used[0]), None)
            if c is None:
                c = next((x for x in player.equipment if x.name == action.cards_used[0]), None)
            if c:
                if c in player.hand:
                    player.hand.remove(c)
                else:
                    player.equipment.remove(c)
                state.discard_pile.append(c)
        if action.target_idx is not None and "secondary_target" in action.extra:
            t1 = state.players[action.target_idx]
            t2 = state.players[action.extra["secondary_target"]]
            events.append(GameEvent(f"{player.name}离间：令{t1.name}与{t2.name}决斗"))
            state.add_event(f"{player.name}离间：令{t1.name}与{t2.name}决斗", actor=action.player_idx)
            # Full 决斗 flow: t1 vs t2, t1 responds first
            responders = [(action.target_idx, action.extra["secondary_target"]),
                         (action.extra["secondary_target"], action.target_idx)]
            current = 0
            for _ in range(10):
                resp_idx, other_idx = responders[current]
                resp_player = state.players[resp_idx]
                other_player = state.players[other_idx]
                if not resp_player.alive: break
                need_double = has_skill(other_player, "无双")
                if need_double:
                    state.add_event(f"{other_player.name}发动【无双】，{resp_player.name}需要连续打出两张【杀】", actor=other_idx)
                if agent_callback:
                    r1 = request_response(state, resp_idx, "杀", "决斗", other_idx, agent_callback, events)
                    if need_double and r1:
                        r2 = request_response(state, resp_idx, "杀", "决斗", other_idx, agent_callback, events)
                        responded = r2
                    else:
                        responded = r1
                else:
                    r1 = any(c.name == "杀" for c in resp_player.hand)
                    if r1:
                        for c in resp_player.hand:
                            if c.name == "杀":
                                resp_player.hand.remove(c); state.discard_pile.append(c)
                                events.append(GameEvent(f"{resp_player.name}打出了【杀】"))
                                state.add_event(f"{resp_player.name}打出了【杀】", actor=resp_idx)
                                break
                    if need_double and r1:
                        r2 = any(c.name == "杀" for c in resp_player.hand)
                        if r2:
                            for c in resp_player.hand:
                                if c.name == "杀":
                                    resp_player.hand.remove(c); state.discard_pile.append(c)
                                    events.append(GameEvent(f"{resp_player.name}打出了【杀】"))
                                    state.add_event(f"{resp_player.name}打出了【杀】", actor=resp_idx)
                                    break
                        responded = r2
                    else:
                        responded = r1
                if not responded:
                    events.extend(deal_damage(state, other_idx, resp_idx, 1, agent_callback))
                    break
                current = 1 - current

    elif action.skill_name == "仁德":
        if action.target_idx is not None and action.cards_used:
            count = 0
            for cn in action.cards_used:
                c = next((x for x in player.hand if x.name == cn), None)
                if c:
                    player.hand.remove(c)
                    state.players[action.target_idx].hand.append(c)
                    count += 1
            if count > 0:
                events.append(GameEvent(f"{player.name}仁德：交给{state.players[action.target_idx].name}{count}张牌"))
            if count >= 2:
                player.hp = min(player.hp + 1, player.max_hp)
                events.append(GameEvent(f"{player.name}回复1点体力"))

    elif action.skill_name == "结姻":
        for cn in action.cards_used[:2]:
            c = next((x for x in player.hand if x.name == cn), None)
            if c:
                player.hand.remove(c)
                state.discard_pile.append(c)
        target = state.players[action.target_idx] if action.target_idx is not None else None
        if target and target.hero.gender == "male" and target.hp < target.max_hp:
            target.hp = min(target.hp + 1, target.max_hp)
            player.hp = min(player.hp + 1, player.max_hp)
            events.append(GameEvent(f"{player.name}发动【结姻】，与{target.name}各回复1点体力"))

    elif action.skill_name == "反间":
        if action.cards_used and action.target_idx is not None:
            cn = action.cards_used[0]
            c = next((x for x in player.hand if x.name == cn), None)
            if c:
                player.hand.remove(c)
                target = state.players[action.target_idx]
                actual_suit = c.suit.value
                # Target guesses suit (before receiving the card)
                guessed = action.extra.get("guessed_suit") if action.extra else None
                if agent_callback and not guessed:
                    from engine.game import get_player_view
                    view = get_player_view(state, action.target_idx)
                    resp = agent_callback(view, "fanjian_guess",
                                          source_idx=action.player_idx,
                                          card_name=cn)
                    if resp:
                        guessed = resp.card_name
                if not guessed:
                    import random as _rnd
                    suits = ["♠", "♥", "♣", "♦"]
                    guessed = _rnd.choice(suits)
                target.hand.append(c)
                msg = f"{player.name}反间：{target.name}猜花色{guessed}（实际{actual_suit}），获得【{c.name}】"
                events.append(GameEvent(msg))
                state.add_event(msg, actor=action.player_idx)
                if guessed != actual_suit:
                    events.extend(deal_damage(state, action.player_idx, action.target_idx, 1, agent_callback))

    elif action.skill_name == "裸衣":
        state.sha_limit[action.player_idx] = 1
        state._nuoyi_bonus = action.player_idx
        events.append(GameEvent(f"{player.name}裸衣：少摸一张牌，本回合伤害+1"))

    check_lianying(state, action.player_idx, events)
    return events
