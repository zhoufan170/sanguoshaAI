"""Response system for Sanguosha: dodge, negate chains, bagua formation."""
from __future__ import annotations
from typing import Any

from engine.cards import Card, CardType
from engine.heroes import Hero, Role, Kingdom
from engine.rules import (
    Action, ActionType, GameEvent, deal_damage, has_skill,
    do_judgment,
)

AgentCallback = Any


def can_respond(state, player_idx: int, response_type: str) -> bool:
    """Check if a player has any possible way to respond."""
    player = state.players[player_idx]

    if response_type == "闪":
        for c in player.hand:
            if c.name == "闪":
                return True
        if has_skill(player, "倾国"):
            for c in player.hand:
                if c.suit.value in ("♠", "♣"):
                    return True
        if has_skill(player, "龙胆"):
            for c in player.hand:
                if c.name == "杀":
                    return True
        for eq in player.equipment:
            if eq.name == "八卦阵":
                return True
        return False

    elif response_type == "杀":
        for c in player.hand:
            if c.name == "杀":
                return True
        if has_skill(player, "武圣"):
            for c in player.hand:
                if c.suit.value in ("♥", "♦"):
                    return True
        if has_skill(player, "龙胆"):
            for c in player.hand:
                if c.name == "闪":
                    return True
        return False

    return True


def try_baguazhen(state, player_idx: int, events: list[GameEvent],
                  agent_callback=None) -> bool:
    """Auto-trigger 八卦阵 judgment when player needs 闪."""
    player = state.players[player_idx]
    has_bagua = any(eq.name == "八卦阵" for eq in player.equipment)
    if not has_bagua:
        return False

    j_card = do_judgment(state, player_idx, events, agent_callback, "八卦阵")
    is_red = j_card.suit.value in ("♥", "♦")
    events.append(GameEvent(
        f"{player.name}的【八卦阵】判定：{j_card} {'成功' if is_red else '失败'}"))
    return is_red


def auto_dodge_check(state, player_idx: int) -> bool:
    """Auto-check if player can dodge (used when no agent callback available)."""
    player = state.players[player_idx]
    for c in player.hand:
        if c.name == "闪":
            player.hand.remove(c)
            state.discard_pile.append(c)
            return True
    if has_skill(player, "倾国"):
        for c in player.hand:
            if c.suit.value in ("♠", "♣"):
                player.hand.remove(c)
                state.discard_pile.append(c)
                return True
    if has_skill(player, "龙胆"):
        for c in player.hand:
            if c.name == "杀":
                player.hand.remove(c)
                state.discard_pile.append(c)
                return True
    return False


def request_response(state, responder_idx: int, response_type: str,
                     source_card: str, source_idx: int,
                     agent_callback, events: list[GameEvent],
                     no_bagua: bool = False) -> bool:
    """Ask a player's agent to respond to a card. Returns True if responded."""
    player = state.players[responder_idx]
    if not player.alive:
        return False

    if not can_respond(state, responder_idx, response_type):
        return False

    from engine.game import get_player_view
    view = get_player_view(state, responder_idx)
    response = agent_callback(view, "response",
                              response_type=response_type,
                              source_card=source_card,
                              source_idx=source_idx,
                              no_bagua=no_bagua)

    # 主公技: lord explicitly chose 护驾/激将
    lord_skill_name = response.skill_name if response else None
    if lord_skill_name in ("护驾", "激将"):
        lord_responded = _try_lord_skill(state, responder_idx, response_type,
                                          source_card, source_idx, agent_callback, events)
        if lord_responded:
            return True

    if response is None or response.type != ActionType.RESPOND:
        # Auto 八卦阵 (unless 青釭剑 disables it)
        if response_type == "闪" and not no_bagua:
            result = try_baguazhen(state, responder_idx, events, agent_callback)
            if result:
                return True
            # 八卦阵失败 → ask agent again for 闪 from hand
            if agent_callback:
                from engine.game import get_player_view
                view2 = get_player_view(state, responder_idx)
                resp2 = agent_callback(view2, "response",
                                       response_type="闪",
                                       source_card=source_card,
                                       source_idx=source_idx,
                                       bagua_failed=True,
                                       no_bagua=True)
                if resp2 and resp2.type == ActionType.RESPOND and resp2.card_name:
                    card = next((c for c in player.hand if c.name == resp2.card_name), None)
                    if card:
                        player.hand.remove(card)
                        state.discard_pile.append(card)
                        events.append(GameEvent(f"{player.name}打出了【{card.name}】"))
                        from engine.rules import check_lianying
                        check_lianying(state, responder_idx, events)
                        return True
            return False
        return False

    card_name = response.card_name
    skill_name = response.skill_name

    # 八卦阵: LLM explicitly chose to trigger it (unless 青釭剑 disables)
    if response_type == "闪" and skill_name == "八卦阵" and not no_bagua:
        result = try_baguazhen(state, responder_idx, events, agent_callback)
        if result:
            return True
        # 八卦阵失败 → ask LLM again: still want to use 闪 from hand?
        if agent_callback:
            view2 = get_player_view(state, responder_idx)
            resp2 = agent_callback(view2, "response",
                                   response_type="闪",
                                   source_card=source_card,
                                   source_idx=source_idx,
                                   bagua_failed=True, no_bagua=True)
            if resp2 and resp2.type == ActionType.RESPOND and resp2.card_name:
                card = next((c for c in player.hand if c.name == resp2.card_name), None)
                if card:
                    player.hand.remove(card)
                    state.discard_pile.append(card)
                    events.append(GameEvent(f"{player.name}打出了【{card.name}】"))
                    from engine.rules import check_lianying
                    check_lianying(state, responder_idx, events)
                    return True
        return False

    if card_name:
        card = next((c for c in player.hand if c.name == card_name), None)
        if card is None:
            if response_type == "闪" and not no_bagua:
                return try_baguazhen(state, responder_idx, events, agent_callback)
            return False

        # Validate skill substitution
        if skill_name == "倾国":
            if card.suit.value not in ("♠", "♣"):
                return False
        elif skill_name == "龙胆":
            if response_type == "闪" and card_name != "杀":
                return False
            if response_type == "杀" and card_name != "闪":
                return False
        elif skill_name == "武圣":
            if card.suit.value not in ("♥", "♦"):
                return False
        elif skill_name:
            return False
        else:
            if card_name != response_type:
                return False

        player.hand.remove(card)
        state.discard_pile.append(card)
        if skill_name:
            events.append(GameEvent(
                f"{player.name}使用【{skill_name}】将【{card_name}】当【{response_type}】打出"))
        else:
            events.append(GameEvent(f"{player.name}打出了【{card_name}】"))
        from engine.rules import check_lianying
        check_lianying(state, responder_idx, events)
        return True

    return False


def resolve_negate_chain(state, action: Action, card: Card,
                         agent_callback) -> bool:
    """Ask all players (clockwise) if they want to play 无懈可击.
    Supports chains: 无懈可击 can be negated by another 无懈可击.
    Returns True if the original card is ultimately negated (odd chain)."""
    n = len(state.players)
    chain_count = 0
    negate_source_idx = action.player_idx
    negate_card_name = card.name
    negate_target_idx = action.target_idx

    from engine.game import get_player_view

    for _ in range(6):  # safety limit
        ask_order = [(negate_source_idx + i) % n for i in range(n)]
        someone_played = False

        for ask_idx in ask_order:
            player = state.players[ask_idx]
            if not player.alive or ask_idx == negate_source_idx:
                continue
            has_wuxie = any(c.name == "无懈可击" for c in player.hand)
            if not has_wuxie:
                continue

            view = get_player_view(state, ask_idx)
            response = agent_callback(view, "negate",
                                      source_idx=negate_source_idx,
                                      card_name=negate_card_name,
                                      target_idx=negate_target_idx)
            if response and response.type == ActionType.RESPOND and response.card_name == "无懈可击":
                wx_card = next((c for c in player.hand if c.name == "无懈可击"), None)
                if wx_card:
                    player.hand.remove(wx_card)
                    state.discard_pile.append(wx_card)
                    msg = f"{player.name}打出【无懈可击】"
                    if chain_count > 0:
                        msg += "抵消上一张【无懈可击】"
                    state.add_event(msg, actor=ask_idx)
                    chain_count += 1
                    negate_source_idx = ask_idx
                    negate_card_name = "无懈可击"
                    someone_played = True
                    break

        if not someone_played:
            break

    return chain_count % 2 == 1


def _try_lord_skill(state, lord_idx: int, response_type: str,
                     source_card: str, source_idx: int,
                     agent_callback, events: list[GameEvent]) -> bool:
    """Try lord skills: 护驾 (Wei players give 闪) or 激将 (Shu players give 杀)."""
    lord = state.players[lord_idx]
    if lord.role != Role.LORD or not lord.hero.lord_skill:
        return False

    lord_skill_name = lord.hero.lord_skill.name
    needed_kingdom = None

    if lord_skill_name == "护驾" and response_type == "闪":
        needed_kingdom = Kingdom.WEI
    elif lord_skill_name == "激将" and response_type == "杀":
        needed_kingdom = Kingdom.SHU
    else:
        return False

    n = len(state.players)
    ask_order = [(lord_idx + i) % n for i in range(1, n)]
    for ask_idx in ask_order:
        p = state.players[ask_idx]
        if not p.alive or p.idx == lord_idx:
            continue
        if p.hero.kingdom != needed_kingdom:
            continue

        # Check if player has the needed response card
        has_response = False
        if response_type == "闪":
            has_response = any(c.name == "闪" for c in p.hand)
            if not has_response and has_skill(p, "倾国"):
                has_response = any(c.suit.value in ("♠", "♣") for c in p.hand)
            if not has_response and has_skill(p, "龙胆"):
                has_response = any(c.name == "杀" for c in p.hand)
        else:  # 杀
            has_response = any(c.name == "杀" for c in p.hand)
            if not has_response and has_skill(p, "武圣"):
                has_response = any(c.suit.value in ("♥", "♦") for c in p.hand)
            if not has_response and has_skill(p, "龙胆"):
                has_response = any(c.name == "闪" for c in p.hand)

        if not has_response:
            continue

        from engine.game import get_player_view
        view = get_player_view(state, ask_idx)
        response = agent_callback(view, "response",
                                  response_type=response_type,
                                  source_card=f"{lord_skill_name}(主公技)",
                                  source_idx=source_idx)

        if response is not None and response.type == ActionType.RESPOND:
            card_name = response.card_name
            skill_name = response.skill_name
            card = None
            if card_name:
                card = next((c for c in p.hand if c.name == card_name), None)
            if not card:
                continue

            if skill_name == "倾国" and card.suit.value not in ("♠", "♣"):
                continue
            if skill_name == "龙胆":
                if response_type == "闪" and card_name != "杀":
                    continue
                if response_type == "杀" and card_name != "闪":
                    continue
            if skill_name == "武圣" and card.suit.value not in ("♥", "♦"):
                continue

            p.hand.remove(card)
            state.discard_pile.append(card)
            if skill_name:
                events.append(GameEvent(
                    f"{p.name}响应主公技【{lord_skill_name}】，用【{skill_name}】将【{card_name}】当【{response_type}】打出"))
            else:
                events.append(GameEvent(
                    f"{p.name}响应主公技【{lord_skill_name}】，打出【{card_name}】"))
            from engine.rules import check_lianying
            check_lianying(state, ask_idx, events)
            return True

    return False
