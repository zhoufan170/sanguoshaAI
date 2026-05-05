"""Rule validation and resolution logic for Sanguosha."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any
import random

from engine.heroes import Role, Kingdom

if TYPE_CHECKING:
    from engine.cards import Card, CardType
    from engine.game import GameState, PlayerState


class ActionType(Enum):
    PLAY_CARD = "play_card"       # play a card from hand
    USE_SKILL = "use_skill"       # activate hero skill
    DISCARD = "discard"           # discard cards (end phase)
    PASS = "pass"                 # skip / do nothing
    RESPOND = "respond"           # respond to a pending request


@dataclass
class Action:
    type: ActionType
    player_idx: int
    card_name: str | None = None   # for play_card / respond
    skill_name: str | None = None  # for use_skill
    target_idx: int | None = None  # target player
    cards_used: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)
    reasoning: str = ""             # LLM thinking process
    suspicion: dict = field(default_factory=dict)  # 身份推理


@dataclass
class GameEvent:
    description: str
    actor_idx: int | None = None
    target_idx: int | None = None
    card_name: str | None = None


def calculate_distance(state: GameState, from_idx: int, to_idx: int) -> int:
    """Calculate attack distance between two players (skipping dead players)."""
    n = len(state.players)
    if from_idx == to_idx:
        return 0

    # Count alive players clockwise and counter-clockwise
    cw, i = 0, (from_idx + 1) % n
    while i != to_idx:
        if state.players[i].alive:
            cw += 1
        i = (i + 1) % n
    ccw, i = 0, (from_idx - 1 + n) % n
    while i != to_idx:
        if state.players[i].alive:
            ccw += 1
        i = (i - 1 + n) % n
    base = min(cw, ccw) + 1  # +1 for the target itself

    # Apply attacker's -1 horse and weapons
    attacker = state.players[from_idx]
    offset = 0
    weapon_range = 0
    for card in attacker.equipment:
        if card.range_bonus < 0:  # -1 horse
            offset -= 1
        elif card.range_bonus > 0 and card.name not in ("的卢", "绝影", "爪黄飞电"):
            weapon_range = max(weapon_range, card.range_bonus)

    # Apply defender's +1 horse
    defender = state.players[to_idx]
    for card in defender.equipment:
        if card.range_bonus > 0 and card.name in ("的卢", "绝影", "爪黄飞电"):
            offset += 1

    dist = base + offset

    # 马术 skill: permanent -1 distance
    if has_skill(attacker, "马术"):
        dist -= 1

    return max(1, dist)


def has_skill(player: PlayerState, skill_name: str) -> bool:
    """Check if a player has a specific skill."""
    for s in player.hero.skills:
        if s.name == skill_name:
            return True
    return False


def can_play_sha(state: GameState, player_idx: int, target_idx: int) -> tuple[bool, str]:
    """Check if a player can use 杀 on a target."""
    player = state.players[player_idx]
    target = state.players[target_idx]

    if player_idx == target_idx:
        return False, "不能对自己使用【杀】"
    if not target.alive:
        return False, "目标已死亡"

    # Check if player has used 杀 this turn (unless 咆哮)
    if state.sha_used_this_turn[player_idx] >= state.sha_limit[player_idx]:
        return False, "本回合已使用过【杀】"

    dist = calculate_distance(state, player_idx, target_idx)
    weapon_range = 1
    for card in player.equipment:
        if card.range_bonus > 0 and card.name not in ("的卢", "绝影", "爪黄飞电"):
            weapon_range = max(weapon_range, card.range_bonus)

    if dist > weapon_range:
        return False, f"目标距离为{dist}，超出攻击范围（当前范围{weapon_range}）"

    return True, ""


def can_play_tao(state: GameState, player_idx: int, target_idx: int | None = None) -> tuple[bool, str]:
    """Check if a player can use 桃. Target is optional (defaults to self)."""
    player = state.players[player_idx]
    tgt = state.players[target_idx] if target_idx is not None else player

    if not tgt.alive:
        return False, "目标已死亡"
    if tgt.hp >= tgt.max_hp:
        return False, "目标体力值已满"

    return True, ""


def validate_action(state: GameState, action: Action) -> tuple[bool, str]:
    """Validate if an action is legal. Returns (is_valid, reason)."""
    player = state.players[action.player_idx]

    if not player.alive:
        return False, "你已死亡"

    if action.type == ActionType.PLAY_CARD:
        card_name = action.card_name
        skill_name = action.skill_name

        # Card substitution validation
        if skill_name == "奇袭" and card_name == "过河拆桥":
            has_black = any(c.suit.value in ("♠", "♣") for c in player.hand)
            if not has_black:
                has_black = any(c.suit.value in ("♠", "♣") for c in player.equipment)
            if not has_black:
                return False, "手牌和装备栏都没有黑色牌发动【奇袭】"
        elif skill_name == "武圣" and card_name == "杀":
            if not any(c.suit.value in ("♥", "♦") for c in player.hand):
                return False, "没有红色牌发动【武圣】"
        elif skill_name == "国色" and card_name == "乐不思蜀":
            if not any(c.suit.value == "♦" for c in player.hand):
                return False, "没有♦牌发动【国色】"
        elif skill_name == "龙胆" and card_name == "杀":
            if not any(c.name == "闪" for c in player.hand):
                return False, "没有【闪】发动【龙胆】当【杀】"
        elif not skill_name and card_name not in [c.name for c in player.hand]:
            return False, f"手牌中没有【{card_name}】"

        if card_name == "杀":
            if action.target_idx is None:
                return False, "【杀】需要指定目标"
            tgt = state.players[action.target_idx]
            if has_skill(tgt, "空城") and len(tgt.hand) == 0:
                return False, "目标发动【空城】，无法成为【杀】的目标"
            # 丈八蛇矛: 2 hand cards as 杀
            if action.skill_name == "丈八蛇矛":
                if len(action.cards_used) < 2:
                    return False, "【丈八蛇矛】需要弃置2张手牌"
                for cn in action.cards_used[:2]:
                    if cn not in [c.name for c in player.hand]:
                        return False, f"手牌中没有【{cn}】"
            return can_play_sha(state, action.player_idx, action.target_idx)

        elif card_name == "桃":
            # 出牌阶段只能对自己用桃（濒死救援走独立流程 _resolve_dying）
            if action.target_idx is not None and action.target_idx != action.player_idx:
                return False, "出牌阶段不能对他人使用【桃】"
            return can_play_tao(state, action.player_idx, action.player_idx)

        elif card_name == "过河拆桥":
            if action.target_idx is None:
                return False, "【过河拆桥】需要指定目标"
            if action.target_idx == action.player_idx:
                return False, "不能对自己使用【过河拆桥】"
            tgt = state.players[action.target_idx]
            if not tgt.alive:
                return False, "目标已死亡"
            if not tgt.hand and not tgt.equipment and not tgt.delay_cards:
                return False, "目标没有可弃置的牌（手牌/装备/延时锦囊）"

        elif card_name == "顺手牵羊":
            if action.target_idx is None:
                return False, "【顺手牵羊】需要指定目标"
            if action.target_idx == action.player_idx:
                return False, "不能对自己使用【顺手牵羊】"
            tgt = state.players[action.target_idx]
            if not tgt.alive:
                return False, "目标已死亡"
            zone = action.extra.get("snatch_zone", "hand")  # "hand"/"equipment"/"delay"
            if zone == "hand" and not tgt.hand:
                return False, "目标没有手牌"
            if zone == "equipment" and not tgt.equipment:
                return False, "目标没有装备"
            if zone == "delay" and not tgt.delay_cards:
                return False, "目标没有延时锦囊"
            dist = calculate_distance(state, action.player_idx, action.target_idx)
            if dist > 1:
                return False, f"目标距离为{dist}，超出顺手牵羊范围（需要距离≤1）"

        elif card_name == "决斗":
            if action.target_idx is None:
                return False, "【决斗】需要指定目标"
            if action.target_idx == action.player_idx:
                return False, "不能对自己使用【决斗】"
            tgt = state.players[action.target_idx]
            if has_skill(tgt, "空城") and len(tgt.hand) == 0:
                return False, "目标发动【空城】，无法成为【决斗】的目标"

        elif card_name == "借刀杀人":
            if action.target_idx is None:
                return False, "【借刀杀人】需要指定目标"
            st = action.extra.get("secondary_target")
            if st is None:
                return False, "【借刀杀人】需要指定第二个目标（被借刀者要杀的目标）"
            if action.target_idx == action.player_idx:
                return False, "不能对自己使用【借刀杀人】"
            if st == action.target_idx:
                return False, "【借刀杀人】两个目标不能相同"
            tgt = state.players[action.target_idx]
            if not tgt.alive: return False, "目标已死亡"
            if not state.players[st].alive: return False, "第二个目标已死亡"
            # 目标必须有武器
            weapons = [c for c in tgt.equipment if c.range_bonus > 0 and c.name not in ("的卢", "绝影", "爪黄飞电")]
            if not weapons:
                return False, "目标没有武器，无法使用【借刀杀人】"

    elif action.type == ActionType.USE_SKILL:
        skill_name = action.skill_name
        skill_names = [s.name for s in player.hero.skills]
        if player.hero.lord_skill:
            skill_names.append(player.hero.lord_skill.name)
        if skill_name not in skill_names:
            return False, f"没有技能【{skill_name}】"

        # Phase-specific skills - can't be used during play phase
        PHASE_SKILLS = {"洛神", "闭月", "突袭"}
        if skill_name in PHASE_SKILLS:
            return False, f"【{skill_name}】不是出牌阶段技能"

        # Once-per-turn skill check
        ONCE_PER_TURN = {"制衡", "离间", "结姻", "反间", "青囊"}
        if skill_name == "离间":
            if "secondary_target" not in action.extra:
                return False, "【离间】需要指定两名男性角色（extra.secondary_target）"
        if skill_name in ONCE_PER_TURN:
            if skill_name in state.skills_used_this_turn[action.player_idx]:
                return False, f"本回合已使用过【{skill_name}】"

        # Validate cards_used are in hand or equipment (for skills like 离间)
        for cn in action.cards_used:
            in_hand = cn in [c.name for c in player.hand]
            in_equip = cn in [c.name for c in player.equipment]
            if not in_hand and not in_equip:
                return False, f"手牌和装备栏都没有【{cn}】"

    elif action.type == ActionType.DISCARD:
        for cn in action.cards_used:
            if cn not in [c.name for c in player.hand]:
                return False, f"手牌中没有【{cn}】"

    return True, ""


def _process_damage_triggers(state: GameState, source_idx: int, target_idx: int,
                              events: list[GameEvent], agent_callback: Any = None,
                              source_card=None):
    """After damage is dealt, check for trigger skills on the damaged player."""
    target = state.players[target_idx]
    source = state.players[source_idx]
    if not target.alive or target_idx == source_idx:
        return

    # 奸雄 (曹操): when damaged, gain the card that caused the damage
    if has_skill(target, "奸雄"):
        if source_card and source_card in state.discard_pile:
            state.discard_pile.remove(source_card)
            target.hand.append(source_card)
            events.append(GameEvent(f"{target.name}发动【奸雄】，获得造成伤害的牌 [{source_card}]", actor_idx=target_idx))
        elif state.discard_pile:
            c = state.discard_pile.pop()
            target.hand.append(c)
            events.append(GameEvent(f"{target.name}发动【奸雄】，获得造成伤害的牌 [{c}]", actor_idx=target_idx))

    # 遗计 (郭嘉): when damaged, draw 2 cards, then distribute up to 2 to others
    if has_skill(target, "遗计"):
        drawn_cards = []
        for _ in range(2):
            if state.draw_pile:
                c = state.draw_pile.pop()
                target.hand.append(c)
                drawn_cards.append(c)
        if drawn_cards:
            events.append(GameEvent(f"{target.name}发动【遗计】，摸了两张牌: {' '.join(str(c) for c in drawn_cards)}", actor_idx=target_idx))
        if agent_callback and drawn_cards:
            from engine.game import get_player_view
            view = get_player_view(state, target_idx)
            resp = agent_callback(view, "yiji_distribute", drawn=[c.name for c in drawn_cards])
            if resp and resp.cards_used:
                given = 0
                for item in resp.cards_used[:2]:
                    if "->" in str(item):
                        cn, ti_str = str(item).split("->", 1)
                        try: ti = int(ti_str.strip())
                        except: continue
                    else:
                        continue
                    # Only allow distributing the drawn cards
                    card = next((c for c in drawn_cards if c.name == cn.strip()), None)
                    if card and ti != target_idx and 0 <= ti < len(state.players):
                        tgt = state.players[ti]
                        if tgt.alive and card in target.hand:
                            target.hand.remove(card)
                            tgt.hand.append(card)
                            drawn_cards.remove(card)
                            events.append(GameEvent(
                                f"{target.name}发动【遗计】，将【{card.name}】交给{tgt.name}",
                                actor_idx=target_idx, target_idx=ti))
                            given += 1
                if given > 0:
                    events.append(GameEvent(
                        f"{target.name}遗计分牌：给出{given}张", actor_idx=target_idx))

    # 反馈 (司马懿): when damaged, choose whether to gain 1 card from damage source
    if has_skill(target, "反馈"):
        trigger = True
        zone = "hand"
        if agent_callback:
            from engine.game import get_player_view
            view = get_player_view(state, target_idx)
            resp = agent_callback(view, "fankui", source_idx=source_idx)
            if resp and resp.skill_name == "skip":
                trigger = False
            elif resp and resp.skill_name == "equipment" and source.equipment:
                zone = "equipment"
        if trigger:
            if zone == "equipment" and source.equipment:
                c = source.equipment.pop(0)
                target.hand.append(c)
                events.append(GameEvent(f"{target.name}发动【反馈】，获得了{source.name}的装备【{c.name}】",
                                        actor_idx=target_idx, target_idx=source_idx))
            elif source.hand:
                c = source.hand.pop(0)
                target.hand.append(c)
                events.append(GameEvent(f"{target.name}发动【反馈】，获得了{source.name}的一张手牌",
                                        actor_idx=target_idx, target_idx=source_idx))

    # 刚烈 (夏侯惇): judgment, if not heart -> source chooses damage or discard
    if has_skill(target, "刚烈"):
        j_card = do_judgment(state, target_idx, events, agent_callback, "刚烈")
        events.append(GameEvent(f"{target.name}发动【刚烈】，判定: {j_card}"))
        if j_card.suit.value != "♥":
            choice = "damage"  # default
            cards_to_discard = []
            if agent_callback:
                from engine.game import get_player_view
                view = get_player_view(state, source_idx)
                resp = agent_callback(view, "ganglie_choice", source_idx=target_idx)
                if resp and resp.skill_name == "discard" and resp.cards_used:
                    # Verify at least 2 cards specified and in hand
                    valid_cards = [cn for cn in resp.cards_used if cn in [c.name for c in source.hand]]
                    if len(valid_cards) >= 2:
                        choice = "discard"
                        cards_to_discard = valid_cards[:2]
            if choice == "discard" and len(cards_to_discard) >= 2:
                for cn in cards_to_discard[:2]:
                    c = next((x for x in source.hand if x.name == cn), None)
                    if c:
                        source.hand.remove(c)
                        state.discard_pile.append(c)
                events.append(GameEvent(f"{source.name}选择弃置2张手牌以回应{target.name}的【刚烈】"))
            else:
                source.hp -= 1
                events.append(GameEvent(f"{source.name}选择受到{target.name}【刚烈】造成的1点伤害",
                                        actor_idx=target_idx, target_idx=source_idx))
                while source.hp <= 0 and source.alive:
                    saved = _resolve_dying(state, source_idx, events, agent_callback)
                    if not saved:
                        _resolve_death(state, source_idx, target_idx, events)
                        break


def deal_damage(state: GameState, source_idx: int, target_idx: int, amount: int = 1,
                agent_callback: Any = None, source_card=None):
    """Deal damage from source to target. Returns list of events."""
    events = []
    target = state.players[target_idx]
    source = state.players[source_idx]

    if not target.alive:
        return events

    target.hp -= amount
    events.append(GameEvent(
        f"{target.hero.name}受到{source.hero.name}造成的{amount}点伤害",
        actor_idx=source_idx, target_idx=target_idx
    ))

    # Process damage-triggered skills
    _process_damage_triggers(state, source_idx, target_idx, events, agent_callback, source_card)

    # Check near-death: each round, every alive player gets one chance to use 桃
    while target.hp <= 0 and target.alive:
        saved = _resolve_dying(state, target_idx, events, agent_callback)
        if not saved:
            _resolve_death(state, target_idx, source_idx, events)
            break

    return events


def _resolve_dying(state: GameState, dying_idx: int, events: list[GameEvent],
                   agent_callback: Any = None) -> bool:
    """Resolve near-death state. With agent_callback, all players in turn order
    get a chance to use 桃. Returns True if saved (or partially saved),
    False if no one used 桃 this round (player dies)."""
    player = state.players[dying_idx]
    needed = 1 - player.hp
    events.append(GameEvent(f"{player.hero.name}濒死，需要{needed}个桃"))

    if agent_callback:
        from engine.game import get_player_view
        someone_used = False
        n = len(state.players)
        ask_order = [(state.active_player + i) % n for i in range(n)]

        for ask_idx in ask_order:
            p = state.players[ask_idx]
            if not p.alive:
                continue

            has_tao = any(c.name == "桃" for c in p.hand)
            has_jijiu = has_skill(p, "急救") and (
                any(c.suit.value in ("♥", "♦") for c in p.hand) or
                any(c.suit.value in ("♥", "♦") for c in p.equipment))
            if not has_tao and not has_jijiu:
                continue

            needed_now = 1 - state.players[dying_idx].hp
            view = get_player_view(state, ask_idx)
            response = agent_callback(view, "dying", dying_idx=dying_idx,
                                      needed=needed_now)

            if response and response.type == ActionType.RESPOND:
                card_name = response.card_name
                skill_name = response.skill_name

                card = None
                if skill_name == "急救":
                    card = next((c for c in p.hand
                                 if c.suit.value in ("♥", "♦")), None)
                    if card is None:
                        card = next((c for c in p.equipment
                                     if c.suit.value in ("♥", "♦")), None)
                elif card_name:
                    card = next((c for c in p.hand if c.name == card_name), None)

                if card:
                    if card in p.equipment:
                        p.equipment.remove(card)
                    else:
                        p.hand.remove(card)
                    state.discard_pile.append(card)
                    bonus = 0
                    if (player.role == Role.LORD and player.hero.lord_skill
                            and player.hero.lord_skill.name == "救援"
                            and p.hero.kingdom == Kingdom.WU):
                        bonus = 1
                    player.hp += 1 + bonus
                    someone_used = True
                    if skill_name:
                        events.append(GameEvent(
                            f"{p.name}使用【急救】将【{card.name}】当【桃】救了{player.name}"
                            + ("（救援+1）" if bonus else "")))
                    else:
                        events.append(GameEvent(
                            f"{p.name}使用【桃】救了{player.name}"
                            + ("（救援+1）" if bonus else "")))

            if player.hp > 0:
                return True

        if someone_used:
            return True
        player.alive = False
        return False
    else:
        # Fallback: dying player auto-uses own 桃
        tao_count = sum(1 for c in player.hand if c.name == "桃")
        if tao_count >= needed:
            for _ in range(needed):
                for c in player.hand:
                    if c.name == "桃":
                        player.hand.remove(c)
                        state.discard_pile.append(c)
                        break
            player.hp = 1
            events.append(GameEvent(f"{player.hero.name}使用【桃】自救，回复至1点体力"))
            return True

        player.alive = False
        return False


def _resolve_death(state: GameState, dead_idx: int, killer_idx: int, events: list[GameEvent]):
    """Handle death: discard equipment/hand, reward/penalty."""
    player = state.players[dead_idx]
    events.append(GameEvent(f"{player.hero.name}死亡，身份为{player.role.value}"))

    # Discard all cards
    state.discard_pile.extend(player.hand)
    state.discard_pile.extend(player.equipment)
    player.hand.clear()
    player.equipment.clear()

    killer = state.players[killer_idx]
    dead_role = player.role

    # Reward/penalty
    if dead_role == Role.REBEL:
        # Killer draws 3 cards
        for _ in range(3):
            if state.draw_pile:
                killer.hand.append(state.draw_pile.pop())
        events.append(GameEvent(f"{killer.hero.name}击杀反贼，摸三张牌"))

    elif dead_role == Role.LOYALIST and killer.role == Role.LORD:
        # Lord kills loyalist: discard all hand and equipment
        events.append(GameEvent(f"{killer.hero.name}误杀忠臣，弃置所有牌"))
        state.discard_pile.extend(killer.hand)
        state.discard_pile.extend(killer.equipment)
        killer.hand.clear()
        killer.equipment.clear()


def check_victory(state: GameState) -> Role | None:
    """Check if any side has won. Returns winning role or None."""
    alive = [p for p in state.players if p.alive]
    lord_alive = any(p.role == Role.LORD and p.alive for p in state.players)
    rebel_alive = any(p.role == Role.REBEL and p.alive for p in state.players)
    traitor_alive = any(p.role == Role.TRAITOR and p.alive for p in state.players)

    # Rebels win if lord is dead
    if not lord_alive:
        if len(alive) == 1 and alive[0].role == Role.TRAITOR:
            return Role.TRAITOR  # Traitor wins only if last standing after lord dies
        return Role.REBEL

    # Lord + Loyalists win if all rebels and traitor are dead
    if not rebel_alive and not traitor_alive:
        return Role.LORD

    return None


def remove_from_hand(state: GameState, player_idx: int, card, events=None):
    """Centralized hand card removal. Triggers 连营 if hand becomes empty."""
    player = state.players[player_idx]
    player.hand.remove(card)
    state.discard_pile.append(card)
    if has_skill(player, "连营") and len(player.hand) == 0 and player.alive:
        if state.draw_pile:
            new_card = state.draw_pile.pop()
            player.hand.append(new_card)
            if events is not None:
                events.append(GameEvent(
                    f"{player.name}发动【连营】，摸了一张牌", actor_idx=player_idx))
    return card


def remove_equipment(state: GameState, player_idx: int, card, events=None):
    """Centralized equipment removal. Triggers 枭姬 if card is mount/weapon."""
    player = state.players[player_idx]
    player.equipment.remove(card)
    state.discard_pile.append(card)
    # 诸葛连弩移除 → 杀限制恢复
    if card.name == "诸葛连弩" and not has_skill(player, "咆哮"):
        state.sha_limit[player_idx] = 1
    is_weapon = card.range_bonus > 0 and card.name not in ("的卢", "绝影", "爪黄飞电")
    is_mount = card.name in ("的卢", "绝影", "爪黄飞电", "赤兔", "大宛", "紫骍")
    if (is_weapon or is_mount) and has_skill(player, "枭姬"):
        drawn = 0
        for _ in range(2):
            if state.draw_pile:
                c = state.draw_pile.pop()
                player.hand.append(c)
                drawn += 1
        if events is not None and drawn > 0:
            events.append(GameEvent(
                f"{player.name}发动【枭姬】，摸{drawn}张牌", actor_idx=player_idx))
    return card


def check_lianying(state: GameState, player_idx: int, events: list | None = None):
    """Check 连营 trigger: if hand empty, draw 1 card."""
    player = state.players[player_idx]
    if has_skill(player, "连营") and len(player.hand) == 0 and player.alive:
        if state.draw_pile:
            new_card = state.draw_pile.pop()
            player.hand.append(new_card)
            if events is not None:
                events.append(GameEvent(
                    f"{player.name}发动【连营】，摸了一张牌", actor_idx=player_idx))


def do_judgment(state: GameState, context_player_idx: int | None = None,
                events: list | None = None, agent_callback: Any = None,
                context: str = "") -> Card:
    """Perform a judgment: flip top card of draw pile.
    Pre-hook: 鬼才 (司马懿) can swap the card with a hand card.
    Post-hook: 天妒 (郭嘉) gains the judgment card."""
    if not state.draw_pile:
        if not state.discard_pile:
            return None
        random.shuffle(state.discard_pile)
        state.draw_pile = state.discard_pile
        state.discard_pile = []

    card = state.draw_pile.pop()

    # 鬼才 pre-hook: any player with 鬼才 can swap before effect
    if agent_callback and context:
        n = len(state.players)
        for ask_idx in [(state.active_player + i) % n for i in range(n)]:
            p = state.players[ask_idx]
            if not p.alive or not has_skill(p, "鬼才"):
                continue
            if not p.hand:
                continue

            from engine.game import get_player_view
            view = get_player_view(state, ask_idx)
            response = agent_callback(view, "guicai",
                                      judgment_card_name=card.name,
                                      judgment_suit=card.suit.value,
                                      judgment_number=card.number,
                                      context=context,
                                      target_idx=context_player_idx)
            if response and response.type == ActionType.RESPOND and response.card_name:
                swap_card = next((c for c in p.hand if c.name == response.card_name), None)
                if swap_card:
                    p.hand.remove(swap_card)
                    p.hand.append(card)
                    if events is not None:
                        events.append(GameEvent(
                            f"{p.name}发动【鬼才】，将判定牌{card}替换为{swap_card}",
                            actor_idx=ask_idx))
                    card = swap_card
                    break  # Only one player can swap per judgment

    state.discard_pile.append(card)

    # 天妒 (郭嘉): gain the judgment card
    if context_player_idx is not None:
        ctx_player = state.players[context_player_idx]
        if has_skill(ctx_player, "天妒") and card in state.discard_pile:
            state.discard_pile.remove(card)
            ctx_player.hand.append(card)
            if events is not None:
                events.append(GameEvent(
                    f"{ctx_player.name}发动【天妒】，获得判定牌{card}",
                    actor_idx=context_player_idx))

    return card
