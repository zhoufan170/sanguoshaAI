"""Game state machine and main loop for Sanguosha."""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Any

from engine.cards import Card, CardType, build_standard_deck, shuffle_and_deal
from engine.heroes import Hero, Role, assign_roles, select_heroes, Kingdom
from engine.rules import (
    Action, ActionType, GameEvent, calculate_distance, validate_action,
    deal_damage, check_victory, do_judgment, has_skill,
    remove_from_hand, remove_equipment, check_lianying,
)
from engine.skills import resolve_skill
from engine.responses import (
    can_respond, try_baguazhen, auto_dodge_check,
    request_response, resolve_negate_chain,
)


class Phase(Enum):
    PREPARE = "准备阶段"
    JUDGMENT = "判定阶段"
    DRAW = "摸牌阶段"
    PLAY = "出牌阶段"
    DISCARD = "弃牌阶段"
    END = "结束阶段"
    GAME_OVER = "游戏结束"


@dataclass
class PlayerState:
    idx: int
    hero: Hero
    role: Role
    hp: int
    max_hp: int
    hand: list[Card] = field(default_factory=list)
    equipment: list[Card] = field(default_factory=list)
    alive: bool = True
    delay_cards: list[Card] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.hero.name

    @property
    def hand_size(self) -> int:
        return len(self.hand)

    @property
    def public_info(self) -> dict:
        info = {
            "name": self.hero.name,
            "kingdom": self.hero.kingdom.value,
            "gender": self.hero.gender,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "equipment": [c.name for c in self.equipment],
            "alive": self.alive,
        }
        return info


AgentCallback = Callable[..., Any]


@dataclass
class GameState:
    players: list[PlayerState]
    turn_order: list[int]
    active_player: int
    phase: Phase
    draw_pile: list[Card]
    discard_pile: list[Card]
    log: list[GameEvent]
    turn_number: int = 0
    round_number: int = 0
    sha_used_this_turn: dict[int, int] = field(default_factory=dict)
    sha_limit: dict[int, int] = field(default_factory=dict)
    skills_used_this_turn: dict[int, set] = field(default_factory=dict)
    game_over: bool = False
    winner: Role | None = None

    def _draw(self, player_idx: int, count: int = 1) -> list[Card]:
        drawn = []
        for _ in range(count):
            if not self.draw_pile:
                if not self.discard_pile:
                    self.add_event("牌堆和弃牌堆均已空，无法摸牌")
                    break
                import random
                random.shuffle(self.discard_pile)
                self.draw_pile = self.discard_pile
                self.discard_pile = []
                self.add_event(f"牌堆已空，弃牌堆({len(self.draw_pile)}张)洗入牌堆")
            card = self.draw_pile.pop()
            self.players[player_idx].hand.append(card)
            drawn.append(card)
        return drawn

    def _draw_raw(self, count: int = 1) -> list[Card]:
        """Draw cards from pile without adding to any player's hand."""
        drawn = []
        for _ in range(count):
            if not self.draw_pile:
                if not self.discard_pile:
                    break
                import random
                random.shuffle(self.discard_pile)
                self.draw_pile = self.discard_pile
                self.discard_pile = []
                self.add_event(f"牌堆已空，弃牌堆({len(self.draw_pile)}张)洗入牌堆")
            if self.draw_pile:
                drawn.append(self.draw_pile.pop())
        return drawn

    def add_event(self, desc: str, actor: int | None = None, target: int | None = None, card: str | None = None):
        self.log.append(GameEvent(desc, actor, target, card))


def create_game(heroes: list[Hero], roles: list[Role], deck: list[Card] | None = None) -> GameState:
    n = len(heroes)
    if deck is None:
        deck = build_standard_deck()
    draw_pile, hands = shuffle_and_deal(deck, n, hand_size=4)

    players = []
    for i in range(n):
        ps = PlayerState(
            idx=i, hero=heroes[i], role=roles[i],
            hp=heroes[i].hp, max_hp=heroes[i].hp, hand=hands[i],
        )
        players.append(ps)

    lord_idx = next(i for i, r in enumerate(roles) if r == Role.LORD)
    players[lord_idx].hp += 1
    players[lord_idx].max_hp += 1
    turn_order = [(lord_idx + i) % n for i in range(n)]

    state = GameState(
        players=players, turn_order=turn_order,
        active_player=lord_idx, phase=Phase.PREPARE,
        draw_pile=draw_pile, discard_pile=[], log=[],
        sha_used_this_turn={i: 0 for i in range(n)},
        sha_limit={i: 1 for i in range(n)},
        skills_used_this_turn={i: set() for i in range(n)},
    )

    for i in range(n):
        if has_skill(players[i], "咆哮"):
            state.sha_limit[i] = 999

    state.add_event(f"游戏开始！共{n}名玩家", actor=None)
    state.add_event(f"主公是{players[lord_idx].hero.name}（{players[lord_idx].role.value}）", actor=lord_idx)
    return state


def get_player_view(state: GameState, player_idx: int) -> dict:
    player = state.players[player_idx]
    public_players = []
    for p in state.players:
        pub = p.public_info.copy()
        if p.role == Role.LORD or not p.alive:
            pub["role"] = p.role.value
        else:
            pub["role"] = "未知"
        pub["skills"] = [s.name for s in p.hero.skills]
        pub["delay_cards"] = [c.name for c in p.delay_cards]
        pub["hand_count"] = len(p.hand)
        public_players.append(pub)

    # Filter events: only show card details for own actions
    import re
    filtered_events = []
    for e in state.log:
        desc = e.description
        if e.actor_idx != player_idx:
            # Other player's action: hide specific card details
            # Strip card detail suffix like ": ♠1 [card] ♥2 [card]"
            desc = re.sub(r':\s*[♠♥♣♦]\d+\s*\[.+?\](\s*[♠♥♣♦]\d+\s*\[.+?\])*', '', desc)
            # Strip bracket notation like " [♠8 [杀]]"
            desc = re.sub(r'\s*\[[♠♥♣♦][^\]]*\]+', '的手牌', desc)
            # Clean up leftovers
            desc = re.sub(r'(摸|获得|给)\s*$', r'\1手牌', desc)
            desc = re.sub(r'的手牌的手牌', '的手牌', desc)
        filtered_events.append(desc)

    return {
        "player_idx": player_idx,
        "my_hero": player.hero.name,
        "my_kingdom": player.hero.kingdom.value,
        "my_hp": player.hp, "my_max_hp": player.max_hp,
        "my_role": player.role.value,
        "my_skills": [s.name for s in player.hero.skills],
        "my_hand": [{"name": c.name, "suit": c.suit.value, "type": c.type.value} for c in player.hand],
        "my_equipment": [c.name for c in player.equipment],
        "my_delay_cards": [c.name for c in player.delay_cards],
        "players": public_players,
        "active_player": state.active_player,
        "phase": state.phase.value,
        "turn_number": state.turn_number, "round_number": state.round_number,
        "recent_events": filtered_events,
        "alive_count": sum(1 for p in state.players if p.alive),
        "lord_idx": next(i for i, p in enumerate(state.players) if p.role == Role.LORD),
        "sha_used": state.sha_used_this_turn[player_idx],
        "sha_limit": state.sha_limit[player_idx],
        "skills_used_this_turn": list(state.skills_used_this_turn[player_idx]),
    }


def execute_action(state: GameState, action: Action,
                   agent_callback: AgentCallback | None = None) -> list[GameEvent]:
    events = []
    player = state.players[action.player_idx]

    if action.type == ActionType.PLAY_CARD:
        skill_name = action.skill_name
        card = None
        from_equip = False
        if skill_name == "奇袭":
            from_equip = False
            card = next((c for c in player.hand if c.suit.value in ("♠", "♣")), None)
            if card is None:
                card = next((c for c in player.equipment if c.suit.value in ("♠", "♣")), None)
                from_equip = card is not None
            action.card_name = "过河拆桥"
        elif skill_name == "武圣":
            card = next((c for c in player.hand if c.suit.value in ("♥", "♦")), None)
            action.card_name = "杀"
        elif skill_name == "国色":
            card = next((c for c in player.hand if c.suit.value == "♦"), None)
            action.card_name = "乐不思蜀"
        elif skill_name == "龙胆" and action.card_name == "杀":
            card = next((c for c in player.hand if c.name == "闪"), None)
        elif skill_name == "丈八蛇矛" and action.card_name == "杀":
            cards_for_sha = []
            for cn in action.cards_used[:2]:
                c2 = next((x for x in player.hand if x.name == cn), None)
                if c2: cards_for_sha.append(c2)
            if len(cards_for_sha) >= 2:
                card = cards_for_sha[0]
                # Remove both cards now (normal remove below only handles the first)
                player.hand.remove(cards_for_sha[1])
                state.discard_pile.append(cards_for_sha[1])
            else:
                card = None
        else:
            card = next((c for c in player.hand if c.name == action.card_name), None)

        if card is None:
            events.append(GameEvent(f"错误：{player.name}手牌中没有{action.card_name}"))
            return events

        if from_equip:
            player.equipment.remove(card)
            state.discard_pile.append(card)
            # Reset 诸葛连弩 if removed
            if card.name == "诸葛连弩" and not has_skill(player, "咆哮"):
                state.sha_limit[action.player_idx] = 1
        else:
            player.hand.remove(card)
            state.discard_pile.append(card)
        # Only show skill conversion for actual card-conversion skills
        conversion_skills = {"武圣", "奇袭", "国色", "龙胆", "丈八蛇矛"}
        if skill_name in conversion_skills:
            events.append(GameEvent(
                f"{player.name}发动【{skill_name}】将【{card.name}】当【{action.card_name}】使用",
                actor_idx=action.player_idx, card_name=card.name))
        else:
            events.append(GameEvent(
                f"{player.name}使用了【{card.name}】", actor_idx=action.player_idx, card_name=card.name))

        # 无懈可击：单目标锦囊在此判定，AOE（南蛮/万箭/五谷）内部逐人结算
        aoe_cards = {"南蛮入侵", "万箭齐发", "五谷丰登"}
        if card.type == CardType.STRATEGY and card.name not in aoe_cards and agent_callback:
            negated = resolve_negate_chain(state, action, card, agent_callback)
            if negated:
                events.append(GameEvent(f"【{card.name}】被【无懈可击】抵消"))
                return events

        card_events = _resolve_card(state, action, card, agent_callback)
        events.extend(card_events)

        if card.name == "杀":
            state.sha_used_this_turn[action.player_idx] += 1

    elif action.type == ActionType.DISCARD:
        discarded = []
        for cn in action.cards_used:
            c = next((x for x in player.hand if x.name == cn), None)
            if c:
                player.hand.remove(c)
                state.discard_pile.append(c)
                discarded.append(str(c))
        if discarded:
            events.append(GameEvent(f"{player.name}弃置了{len(discarded)}张牌: {' '.join(discarded)}"))

    elif action.type == ActionType.USE_SKILL:
        # Card conversion skills (国色/武圣/奇袭/龙胆/丈八) should use PLAY_CARD path
        conv_skills = {"国色", "武圣", "奇袭", "龙胆", "丈八蛇矛"}
        if action.skill_name in conv_skills:
            action.type = ActionType.PLAY_CARD
            # recurse through PLAY_CARD logic above
            skill_name2 = action.skill_name
            card2 = None
            from_equip2 = False
            if skill_name2 == "奇袭":
                card2 = next((c for c in player.hand if c.suit.value in ("♠", "♣")), None)
                if card2 is None:
                    card2 = next((c for c in player.equipment if c.suit.value in ("♠", "♣")), None)
                    from_equip2 = card2 is not None
                action.card_name = "过河拆桥"
            elif skill_name2 == "武圣":
                card2 = next((c for c in player.hand if c.suit.value in ("♥", "♦")), None)
                action.card_name = "杀"
            elif skill_name2 == "国色":
                card2 = next((c for c in player.hand if c.suit.value == "♦"), None)
                action.card_name = "乐不思蜀"
            elif skill_name2 == "龙胆" and action.card_name == "杀":
                card2 = next((c for c in player.hand if c.name == "闪"), None)
            elif skill_name2 == "丈八蛇矛":
                action.card_name = "杀"
                cards_for_sha = []
                for cn in action.cards_used[:2]:
                    c2 = next((x for x in player.hand if x.name == cn), None)
                    if c2: cards_for_sha.append(c2)
                if len(cards_for_sha) >= 2:
                    card2 = cards_for_sha[0]
                    player.hand.remove(cards_for_sha[1])
                    state.discard_pile.append(cards_for_sha[1])
            if card2 is None:
                events.append(GameEvent(f"错误：{player.name}无法发动【{action.skill_name}】"))
                return events
            if from_equip2:
                player.equipment.remove(card2)
                state.discard_pile.append(card2)
            else:
                player.hand.remove(card2)
                state.discard_pile.append(card2)
            events.append(GameEvent(
                f"{player.name}发动【{skill_name2}】将【{card2.name}】当【{action.card_name}】使用",
                actor_idx=action.player_idx, card_name=card2.name))
            card_events = _resolve_card(state, action, card2, agent_callback)
            events.extend(card_events)
        else:
            events.append(GameEvent(f"{player.name}发动了【{action.skill_name}】"))
            state.skills_used_this_turn[action.player_idx].add(action.skill_name)
            skill_events = resolve_skill(state, action, agent_callback)
            events.extend(skill_events)

    elif action.type == ActionType.PASS:
        pass

    elif action.type == ActionType.RESPOND:
        if action.card_name:
            card = next((c for c in player.hand if c.name == action.card_name), None)
            if card:
                player.hand.remove(card)
                state.discard_pile.append(card)
                events.append(GameEvent(f"{player.name}打出了【{card.name}】"))

    check_lianying(state, action.player_idx, events)
    return events


def _resolve_card(state: GameState, action: Action, card: Card,
                  agent_callback: AgentCallback | None = None) -> list[GameEvent]:
    events = []
    player = state.players[action.player_idx]

    # 技能转换时用逻辑牌名（武圣桃→杀、奇袭黑牌→过河拆桥、国色♦→乐不思蜀）
    effective = action.card_name or card.name

    if effective == "杀":
        target = state.players[action.target_idx]
        events.append(GameEvent(f"{player.name}对{target.name}使用了【杀】",
                                actor_idx=action.player_idx, target_idx=action.target_idx))
        # 青釭剑: 无视防具
        has_qinggang = any(eq.name == "青釭剑" for eq in player.equipment)
        # 仁王盾: black 杀 is negated (unless 青釭剑)
        if not has_qinggang and any(eq.name == "仁王盾" for eq in target.equipment) and card.suit.value in ("♠", "♣"):
            events.append(GameEvent(f"{target.name}的【仁王盾】抵挡了黑色【杀】"))
            return events
        # 雌雄双股剑: 对异性出杀
        if any(eq.name == "雌雄双股剑" for eq in player.equipment) and player.hero.gender != target.hero.gender:
            if agent_callback:
                v = get_player_view(state, action.target_idx)
                resp = agent_callback(v, "cxt_option", source_idx=action.player_idx)
                if resp and resp.skill_name == "discard" and target.hand:
                    c = target.hand.pop(0); state.discard_pile.append(c)
                    events.append(GameEvent(f"{target.name}弃置一张牌以响应【雌雄双股剑】"))
                elif resp and resp.skill_name == "draw":
                    state._draw(action.player_idx, 1)
                    events.append(GameEvent(f"{player.name}摸一张牌（【雌雄双股剑】）"))
            elif target.hand:
                c = target.hand.pop(0); state.discard_pile.append(c)
                events.append(GameEvent(f"{target.name}弃置一张牌以响应【雌雄双股剑】"))
        # 流离 redirect
        if has_skill(target, "流离") and agent_callback:
            view = get_player_view(state, action.target_idx)
            redirect = agent_callback(view, "liuli_redirect",
                                       source_idx=action.player_idx, source_card="杀")
            if redirect and redirect.skill_name == "流离":
                new_tgt = redirect.target_idx
                if new_tgt is not None and new_tgt != action.target_idx:
                    if redirect.cards_used:
                        rc = next((x for x in target.hand if x.name == redirect.cards_used[0]), None)
                        if rc:
                            target.hand.remove(rc); state.discard_pile.append(rc)
                    events.append(GameEvent(f"{target.name}发动【流离】，将【杀】转移给{state.players[new_tgt].name}"))
                    action.target_idx = new_tgt; target = state.players[new_tgt]

        unblockable = False
        if has_skill(player, "铁骑"):
            j_card = do_judgment(state, action.player_idx, events, agent_callback, "铁骑")
            events.append(GameEvent(f"{player.name}发动【铁骑】，判定: {j_card}"))
            if j_card.suit.value in ("♥", "♦"):
                unblockable = True
                events.append(GameEvent("判定为红色，【杀】不可被【闪】响应"))
        if has_skill(player, "烈弓"):
            if len(player.hand) >= len(target.hand) or player.hp >= target.hp:
                unblockable = True
                events.append(GameEvent(f"{player.name}发动【烈弓】，【杀】不可被【闪】响应"))

        # 青釭剑: 无视防具（仁王盾上面已处理，这里禁用八卦阵自动判定）

        if not unblockable:
            if has_skill(player, "无双"):
                events.append(GameEvent(f"{player.name}发动【无双】，{target.name}需要连续使用两张【闪】"))
                if agent_callback:
                    d1 = request_response(state, action.target_idx, "闪", "杀", action.player_idx, agent_callback, events)
                else:
                    d1 = auto_dodge_check(state, action.target_idx)
                if d1:
                    if agent_callback:
                        d2 = request_response(state, action.target_idx, "闪", "杀", action.player_idx, agent_callback, events)
                    else:
                        d2 = auto_dodge_check(state, action.target_idx)
                    dodged = d2
                else:
                    dodged = False
            else:
                if agent_callback:
                    dodged = request_response(state, action.target_idx, "闪", "杀", action.player_idx, agent_callback, events, no_bagua=has_qinggang)
                else:
                    dodged = auto_dodge_check(state, action.target_idx)
        else:
            dodged = False

        # 贯石斧: 被闪后可弃2张牌强制命中
        if dodged and any(eq.name == "贯石斧" for eq in player.equipment) and len(player.hand) >= 2:
            if agent_callback:
                v = get_player_view(state, action.player_idx)
                resp = agent_callback(v, "guanshi_axe", target_idx=action.target_idx)
                if resp and resp.type == ActionType.RESPOND:
                    for cn in resp.cards_used[:2]:
                        c2 = next((x for x in player.hand if x.name == cn), None)
                        if c2: player.hand.remove(c2); state.discard_pile.append(c2)
                    events.append(GameEvent(f"{player.name}发动【贯石斧】，弃2张牌强制命中"))
                    dodged = False
            elif len(player.hand) >= 2:
                # Random: 50% chance to force hit
                import random
                if random.random() < 0.5:
                    picked = player.hand[:2]
                    for c2 in picked: player.hand.remove(c2); state.discard_pile.append(c2)
                    events.append(GameEvent(f"{player.name}发动【贯石斧】，弃2张牌强制命中"))
                    dodged = False

        # 青龙偃月刀: 被闪后可再出一张杀
        if dodged and any(eq.name == "青龙偃月刀" for eq in player.equipment):
            extra_sha = next((c for c in player.hand if c.name == "杀"), None)
            if extra_sha:
                if agent_callback:
                    v = get_player_view(state, action.player_idx)
                    resp = agent_callback(v, "qinglong_blade", target_idx=action.target_idx)
                    if resp and resp.type == ActionType.RESPOND:
                        player.hand.remove(extra_sha); state.discard_pile.append(extra_sha)
                        events.append(GameEvent(f"{player.name}发动【青龙偃月刀】，追加一张【杀】"))
                        # Resolve the extra 杀 (simple: ask target again)
                        if agent_callback:
                            dodged2 = request_response(state, action.target_idx, "闪", "杀", action.player_idx, agent_callback, events)
                        else:
                            dodged2 = auto_dodge_check(state, action.target_idx)
                        if not dodged2:
                            bonus = 1 if hasattr(state, '_nuoyi_bonus') and state._nuoyi_bonus == action.player_idx else 0
                            events.extend(deal_damage(state, action.player_idx, action.target_idx, 1 + bonus, agent_callback, source_card=card))
                        dodged = False
                else:
                    player.hand.remove(extra_sha); state.discard_pile.append(extra_sha)
                    events.append(GameEvent(f"{player.name}发动【青龙偃月刀】，追加一张【杀】"))
                    dodged2 = auto_dodge_check(state, action.target_idx)
                    if not dodged2:
                        bonus = 1 if hasattr(state, '_nuoyi_bonus') and state._nuoyi_bonus == action.player_idx else 0
                        events.extend(deal_damage(state, action.player_idx, action.target_idx, 1 + bonus, agent_callback, source_card=card))
                    dodged = False

        if not dodged:
            bonus = 1 if hasattr(state, '_nuoyi_bonus') and state._nuoyi_bonus == action.player_idx else 0
            # 寒冰剑: 可弃2张牌改为弃目标2张牌
            has_hanbing = any(eq.name == "寒冰剑" for eq in player.equipment)
            if has_hanbing and agent_callback and len(player.hand) >= 2:
                v = get_player_view(state, action.player_idx)
                resp = agent_callback(v, "hanbing_sword", target_idx=action.target_idx)
                if resp and resp.type == ActionType.RESPOND:
                    for cn in resp.cards_used[:2]:
                        c2 = next((x for x in player.hand if x.name == cn), None)
                        if c2: player.hand.remove(c2); state.discard_pile.append(c2)
                    discarded = 0
                    for _ in range(2):
                        if target.hand:
                            c2 = target.hand.pop(0); state.discard_pile.append(c2); discarded += 1
                        elif target.equipment:
                            c2 = target.equipment[0]; remove_equipment(state, i, c2, events); discarded += 1
                    events.append(GameEvent(f"{player.name}发动【寒冰剑】，弃2张牌，改为弃置{target.name}的{discarded}张牌"))
                    return events
            # Deal damage normally
            events.extend(deal_damage(state, action.player_idx, action.target_idx, 1 + bonus, agent_callback, source_card=card))
            # 麒麟弓: 造成伤害后弃目标一匹马
            if any(eq.name == "麒麟弓" for eq in player.equipment):
                mounts = [c for c in target.equipment if c.name in ("的卢","绝影","爪黄飞电","赤兔","大宛","紫骍")]
                if mounts:
                    m = mounts[0]; remove_equipment(state, action.target_idx, m, events)
                    events.append(GameEvent(f"{player.name}发动【麒麟弓】，弃置了{target.name}的【{m.name}】"))

    elif effective == "桃":
        # 出牌阶段只能自回，濒死救援走 _resolve_dying 独立流程
        player.hp = min(player.hp + 1, player.max_hp)
        events.append(GameEvent(f"{player.name}回复了1点体力"))

    elif effective == "过河拆桥":
        target = state.players[action.target_idx]
        zone = action.extra.get("dismantle_zone", "")  # "delay"/"hand"/"equipment"/""
        # If zone specified, only dismantle that zone
        if zone == "delay" and target.delay_cards:
            c = target.delay_cards.pop(0); state.discard_pile.append(c)
            events.append(GameEvent(f"{player.name}过河拆桥：弃置了{target.name}的延时锦囊【{c.name}】"))
        elif zone == "hand" and target.hand:
            c = target.hand[0]; target.hand.remove(c); state.discard_pile.append(c)
            events.append(GameEvent(f"{player.name}过河拆桥：弃置了{target.name}的手牌 [{c}]"))
        elif zone == "equipment" and target.equipment:
            c = target.equipment[0]; remove_equipment(state, action.target_idx, c, events)
            events.append(GameEvent(f"{player.name}过河拆桥：弃置了{target.name}的装备【{c.name}】"))
        elif not zone:
            # Default priority: delay → hand → equipment
            if target.delay_cards:
                c = target.delay_cards.pop(0); state.discard_pile.append(c)
                events.append(GameEvent(f"{player.name}过河拆桥：弃置了{target.name}的延时锦囊【{c.name}】"))
            elif target.hand:
                c = target.hand[0]; target.hand.remove(c); state.discard_pile.append(c)
                events.append(GameEvent(f"{player.name}过河拆桥：弃置了{target.name}的手牌 [{c}]"))
            elif target.equipment:
                c = target.equipment[0]; remove_equipment(state, action.target_idx, c, events)
                events.append(GameEvent(f"{player.name}过河拆桥：弃置了{target.name}的装备【{c.name}】"))
            else:
                events.append(GameEvent(f"{target.name}没有可弃置的牌"))
        else:
            events.append(GameEvent(f"{target.name}指定的区域没有可弃置的牌"))

    elif effective == "顺手牵羊":
        target = state.players[action.target_idx]
        if has_skill(target, "谦逊"):
            events.append(GameEvent(f"{target.name}发动【谦逊】，【顺手牵羊】对其无效"))
            return events
        zone = action.extra.get("snatch_zone", "hand")
        if zone == "delay" and target.delay_cards:
            c = target.delay_cards.pop(0); player.hand.append(c)
            msg = f"{player.name}顺手牵羊：拿走了{target.name}的延时锦囊【{c.name}】"
            events.append(GameEvent(msg, actor_idx=action.player_idx))
            state.add_event(msg, actor=action.player_idx)
        elif zone == "equipment" and target.equipment:
            c = target.equipment[0]; target.equipment.remove(c); player.hand.append(c)
            # 枭姬 check
            is_weapon = c.range_bonus > 0 and c.name not in ("的卢", "绝影", "爪黄飞电")
            is_mount = c.name in ("的卢", "绝影", "爪黄飞电", "赤兔", "大宛", "紫骍")
            if (is_weapon or is_mount) and has_skill(target, "枭姬"):
                for _ in range(2):
                    if state.draw_pile:
                        target.hand.append(state.draw_pile.pop())
                events.append(GameEvent(f"{target.name}发动【枭姬】，摸2张牌", actor_idx=action.target_idx))
            msg = f"{player.name}顺手牵羊：拿走了{target.name}的装备【{c.name}】"
            events.append(GameEvent(msg, actor_idx=action.player_idx))
            state.add_event(msg, actor=action.player_idx)
        elif zone == "hand" and target.hand:
            import random
            c = random.choice(target.hand)
            target.hand.remove(c); player.hand.append(c)
            events.append(GameEvent(f"{player.name}顺手牵羊：从{target.name}获得 [{c}]",
                                    actor_idx=action.player_idx))
        else:
            events.append(GameEvent(f"{target.name}没有可顺的牌"))

    elif effective == "无中生有":
        drawn = state._draw(action.player_idx, 2)
        card_str = " ".join(str(c) for c in drawn)
        events.append(GameEvent(f"{player.name}使用【无中生有】摸了2张牌: {card_str}"))

    elif effective == "南蛮入侵":
        events.append(GameEvent(f"{player.name}使用了【南蛮入侵】，所有其他角色需打出【杀】"))
        n = len(state.players)
        ask_order = [(action.player_idx + i) % n for i in range(1, n)]
        for i in ask_order:
            p = state.players[i]
            if not p.alive: continue
            # 1. 无懈响应
            state.add_event(f"【南蛮入侵】生效于{p.name}，先进行无懈响应")
            negated = False
            if agent_callback:
                tmp_action = Action(type=ActionType.PLAY_CARD, player_idx=action.player_idx,
                                    card_name="南蛮入侵", target_idx=i)
                negated = resolve_negate_chain(state, tmp_action, card, agent_callback)
            if negated:
                state.add_event(f"【无懈可击】抵消了对{p.name}的【南蛮入侵】效果")
                continue
            # 2. 出杀响应
            if agent_callback:
                state.add_event(f"无懈响应完成，{p.name}需要打出【杀】")
                responded = request_response(state, i, "杀", "南蛮入侵", action.player_idx, agent_callback, events)
            else:
                responded = any(c.name == "杀" for c in p.hand)
                if responded:
                    for c in p.hand:
                        if c.name == "杀": p.hand.remove(c); state.discard_pile.append(c); events.append(GameEvent(f"{p.name}打出了【杀】")); break
            if not responded:
                events.extend(deal_damage(state, action.player_idx, i, 1, agent_callback, source_card=card))

    elif effective == "万箭齐发":
        events.append(GameEvent(f"{player.name}使用了【万箭齐发】，所有其他角色需打出【闪】"))
        n = len(state.players)
        ask_order = [(action.player_idx + i) % n for i in range(1, n)]
        for i in ask_order:
            p = state.players[i]
            if not p.alive: continue
            # 1. 无懈
            state.add_event(f"【万箭齐发】生效于{p.name}，先进行无懈响应")
            if agent_callback:
                tmp_action = Action(type=ActionType.PLAY_CARD, player_idx=action.player_idx,
                                    card_name="万箭齐发", target_idx=i)
                if resolve_negate_chain(state, tmp_action, card, agent_callback):
                    state.add_event(f"【无懈可击】抵消了对{p.name}的【万箭齐发】效果")
                    continue
            # 2. 出闪/八卦阵
            if agent_callback:
                state.add_event(f"无懈响应完成，{p.name}需要打出【闪】")
                responded = request_response(state, i, "闪", "万箭齐发", action.player_idx, agent_callback, events)
            else:
                responded = auto_dodge_check(state, i)
                if not responded:
                    responded = try_baguazhen(state, i, events, agent_callback)
            if not responded:
                events.extend(deal_damage(state, action.player_idx, i, 1, agent_callback, source_card=card))

    elif effective == "决斗":
        target = state.players[action.target_idx]
        events.append(GameEvent(f"{player.name}对{target.name}发起【决斗】"))
        responders = [(action.target_idx, action.player_idx), (action.player_idx, action.target_idx)]
        current_responder = 0
        for _ in range(10):
            resp_idx, other_idx = responders[current_responder]
            resp_player = state.players[resp_idx]
            other_player = state.players[other_idx]
            if not resp_player.alive: break
            # 无双：对手需连续出2张杀
            need_double = has_skill(other_player, "无双")
            if need_double:
                events.append(GameEvent(f"{other_player.name}发动【无双】，{resp_player.name}需要连续打出两张【杀】"))
            if agent_callback:
                r1 = request_response(state, resp_idx, "杀", "决斗", other_idx, agent_callback, events)
                if need_double and r1:
                    r2 = request_response(state, resp_idx, "杀", "决斗", other_idx, agent_callback, events)
                    responded = r2
                else:
                    responded = r1
            else:
                r1 = False
                for c in resp_player.hand:
                    if c.name == "杀":
                        resp_player.hand.remove(c); state.discard_pile.append(c)
                        events.append(GameEvent(f"{resp_player.name}打出了【杀】"))
                        r1 = True; break
                if need_double and r1:
                    r2 = False
                    for c in resp_player.hand:
                        if c.name == "杀":
                            resp_player.hand.remove(c); state.discard_pile.append(c)
                            events.append(GameEvent(f"{resp_player.name}打出了【杀】"))
                            r2 = True; break
                    responded = r2
                else:
                    responded = r1
            if not responded:
                bonus = 1 if hasattr(state, '_nuoyi_bonus') and state._nuoyi_bonus == other_idx else 0
                events.extend(deal_damage(state, other_idx, resp_idx, 1 + bonus, agent_callback, source_card=card))
                break
            current_responder = 1 - current_responder

    elif effective == "五谷丰登":
        alive_count = sum(1 for p in state.players if p.alive)
        revealed = state._draw_raw(alive_count)
        actual_count = len(revealed)
        if actual_count == 0:
            events.append(GameEvent("【五谷丰登】无牌可亮出"))
            return events
        revealed_names = [str(c) for c in revealed]
        state.add_event(f"【五谷丰登】亮出{actual_count}张牌: {' '.join(revealed_names)}，从{player.name}开始依次获取")

        n = len(state.players)
        pick_order = [(action.player_idx + i) % n for i in range(n)]
        for i in pick_order:
            p = state.players[i]
            if not p.alive: continue
            if not revealed: break
            # 1. 无懈
            state.add_event(f"【五谷丰登】生效于{p.name}，先进行无懈响应")
            if agent_callback:
                tmp_action = Action(type=ActionType.PLAY_CARD, player_idx=action.player_idx,
                                    card_name="五谷丰登", target_idx=i)
                if resolve_negate_chain(state, tmp_action, card, agent_callback):
                    state.add_event(f"【无懈可击】抵消了{p.name}获取【五谷丰登】牌")
                    continue
            # 2. 选牌
            if agent_callback:
                state.add_event(f"无懈响应完成，{p.name}从【五谷丰登】选牌")
                view = get_player_view(state, i)
                pick_action = agent_callback(view, "wugu_pick",
                                             revealed=[str(c) for c in revealed])
                chosen_idx = 0
                if pick_action and pick_action.card_name:
                    for ri, rc in enumerate(revealed):
                        if rc.name == pick_action.card_name:
                            chosen_idx = ri
                            break
            else:
                chosen_idx = random.randint(0, len(revealed) - 1)
            if 0 <= chosen_idx < len(revealed):
                picked = revealed.pop(chosen_idx)
                p.hand.append(picked)
                events.append(GameEvent(f"{p.name}从【五谷丰登】获得了【{picked.name}】"))
            elif revealed:
                picked = revealed.pop(0)
                p.hand.append(picked)
                events.append(GameEvent(f"{p.name}从【五谷丰登】获得了【{picked.name}】"))
        # Remaining cards go to discard
        if revealed:
            state.discard_pile.extend(revealed)
            remaining = " ".join(str(c) for c in revealed)
            events.append(GameEvent(f"【五谷丰登】剩余牌弃置: {remaining}"))

    elif effective == "桃园结义":
        n = len(state.players)
        ask_order = [(action.player_idx + i) % n for i in range(n)]
        for i in ask_order:
            p = state.players[i]
            if not p.alive: continue
            # 1. 无懈
            state.add_event(f"【桃园结义】生效于{p.name}，先进行无懈响应")
            if agent_callback:
                tmp_action = Action(type=ActionType.PLAY_CARD, player_idx=action.player_idx,
                                    card_name="桃园结义", target_idx=i)
                if resolve_negate_chain(state, tmp_action, card, agent_callback):
                    state.add_event(f"【无懈可击】抵消了对{p.name}的【桃园结义】效果")
                    continue
            # 2. 回血（无需响应）
            if p.hp < p.max_hp:
                p.hp += 1
                state.add_event(f"{p.name}回复1点体力（【桃园结义】）")
        events.append(GameEvent("【桃园结义】结算完成"))

    elif effective == "借刀杀人":
        target = state.players[action.target_idx]
        sec_idx = action.extra.get("secondary_target", 0)
        secondary = state.players[sec_idx] if sec_idx < len(state.players) else None
        if not secondary or not target.alive or not secondary.alive:
            return events
        # Check if target has 杀
        has_sha = any(c.name == "杀" for c in target.hand)
        if has_sha and agent_callback:
            # Ask target's agent: use 杀 on secondary or give weapon?
            view = get_player_view(state, action.target_idx)
            resp = agent_callback(view, "jiedao_choice",
                                  source_idx=action.player_idx,
                                  secondary_idx=sec_idx)
            use_sha = resp and resp.type == ActionType.RESPOND and resp.card_name == "杀"
            if use_sha:
                # Target uses 杀 on secondary
                sha_card = next((c for c in target.hand if c.name == "杀"), None)
                if sha_card:
                    target.hand.remove(sha_card)
                    state.discard_pile.append(sha_card)
                    state.add_event(f"{target.name}响应【借刀杀人】，对{secondary.name}使用了【杀】")
                    # Resolve the 杀
                    sha_action = Action(type=ActionType.PLAY_CARD, player_idx=action.target_idx,
                                        card_name="杀", target_idx=sec_idx)
                    sha_events = _resolve_card(state, sha_action, sha_card, agent_callback)
                    for evt in sha_events:
                        state.add_event(evt.description, actor=evt.actor_idx, target=evt.target_idx, card=evt.card_name)
                    events.extend(sha_events)
                    return events
        # Target can't/won't use 杀 → caster takes weapon
        weapons = [c for c in target.equipment if c.range_bonus > 0 and c.name not in ("的卢", "绝影", "爪黄飞电")]
        if weapons:
            w = weapons[0]
            remove_equipment(state, action.target_idx, w, events)
            player.hand.append(w)
            events.append(GameEvent(f"{target.name}的武器【{w.name}】被{player.name}借走（置入手牌）"))
        else:
            events.append(GameEvent(f"{target.name}没有武器可借"))

    elif effective == "闪电":
        player.delay_cards.append(card)
        events.append(GameEvent(f"{player.name}挂起了【闪电】"))

    elif effective == "乐不思蜀":
        target = state.players[action.target_idx]
        if has_skill(target, "谦逊"):
            events.append(GameEvent(f"{target.name}发动【谦逊】，【乐不思蜀】对其无效"))
            return events
        target.delay_cards.append(card)
        events.append(GameEvent(f"【乐不思蜀】置于{target.name}的判定区"))

    elif card.type == CardType.EQUIPMENT:
        # Replace existing equipment in same slot
        def _eq_slot(c):
            if c.name in ("八卦阵","仁王盾"): return "armor"
            if c.name in ("的卢","绝影","爪黄飞电"): return "def_horse"
            if c.name in ("赤兔","大宛","紫骍"): return "off_horse"
            if c.range_bonus > 0: return "weapon"
            return "other"
        slot = _eq_slot(card)
        for eq in list(player.equipment):
            if _eq_slot(eq) == slot:
                remove_equipment(state, action.player_idx, eq, events)
        player.equipment.append(card)
        if card.name == "诸葛连弩":
            state.sha_limit[action.player_idx] = 999
        events.append(GameEvent(f"{player.name}装备了【{card.name}】"))

    return events


class SanguoshaGame:
    def __init__(self, agent_callback: AgentCallback, num_players: int = 8,
                 heroes: list[Hero] | None = None, roles: list[Role] | None = None,
                 verbose: bool = True, recorder=None):
        self.agent_callback = agent_callback; self.verbose = verbose; self.recorder = recorder
        if heroes is None: heroes = select_heroes(num_players)
        if roles is None: roles = assign_roles(num_players); random.shuffle(roles)
        lord_idx = next(i for i, r in enumerate(roles) if r == Role.LORD)
        if lord_idx != 0:
            roles[0], roles[lord_idx] = roles[lord_idx], roles[0]
            heroes[0], heroes[lord_idx] = heroes[lord_idx], heroes[0]
        self.state = create_game(heroes, roles); self.num_players = num_players

    def log(self, msg: str):
        if self.verbose: print(msg)

    def run_turn(self) -> bool:
        state = self.state; player = state.players[state.active_player]
        if not player.alive: self._next_player(); return True
        self.log(f"\n{'='*60}")
        self.log(f"第{state.round_number}轮 - {player.name}的回合 (身份: {player.role.value})")
        self.log(f"{'='*60}")
        if self.recorder:
            self.recorder.start_turn(state.active_player, player.name, player.role.value, state.turn_number, state.round_number)
        state.sha_used_this_turn[state.active_player] = 0
        state.skills_used_this_turn[state.active_player] = set()
        state._skip_play_phase = False; state._nuoyi_bonus = None
        if not has_skill(player, "咆哮"): state.sha_limit[state.active_player] = 1
        for eq in player.equipment:
            if eq.name == "诸葛连弩": state.sha_limit[state.active_player] = 999

        state.phase = Phase.PREPARE
        if has_skill(player, "洛神"):
            view = get_player_view(state, state.active_player)
            act = self.agent_callback(view, "prepare_phase")
            if act and act.type == ActionType.USE_SKILL and act.skill_name == "洛神":
                count = 0
                while state.draw_pile:
                    card = do_judgment(state, state.active_player, None, self.agent_callback, "洛神")
                    if card.suit.value in ("♥", "♦"):
                        state.add_event(f"{player.name}洛神：判定红色停止，共获得{count}张牌", actor=state.active_player)
                        break
                    else:
                        if card in state.discard_pile: state.discard_pile.remove(card)
                        player.hand.append(card); count += 1
                else:
                    state.add_event(f"{player.name}洛神：获得{count}张牌")

        state.phase = Phase.JUDGMENT; self._resolve_delay_cards()
        player = state.players[state.active_player]
        if not player.alive: state.turn_number += 1; self._next_player(); return True

        state.phase = Phase.DRAW
        if has_skill(player, "观星"):
            alive_cnt = sum(1 for p in state.players if p.alive); X = min(alive_cnt, 5)
            top = []
            for _ in range(X):
                if state.draw_pile: top.append(state.draw_pile.pop())
            if top:
                top.reverse()  # popped from top, so reverse to get actual order
                cards_str = ' '.join(str(c) for c in top)
                self.log(f"    {player.name}观星：查看了牌堆顶{X}张牌: {cards_str}")
                state.add_event(f"{player.name}观星：查看了牌堆顶{X}张牌: {cards_str}",
                                actor=state.active_player)
                if self.agent_callback:
                    view = get_player_view(state, state.active_player)
                    card_names = [c.name for c in top]
                    resp = self.agent_callback(view, "guanxing", cards=card_names)
                    if resp and resp.cards_used:
                        top_cards = []
                        bottom_cards = []
                        for item in resp.cards_used:
                            if ":" in item:
                                cn, pos = item.split(":", 1)
                                matched = [c for c in top if c.name == cn.strip()]
                                if matched:
                                    if pos.strip() == "top": top_cards.append(matched[0])
                                    else: bottom_cards.append(matched[0])
                        # Put cards back: bottom first, then top (top will be drawn next)
                        for c in reversed(bottom_cards):
                            state.draw_pile.insert(0, c)
                        for c in reversed(top_cards):
                            state.draw_pile.append(c)
                        top_str = ' '.join(str(c) for c in top_cards)
                        bot_str = ' '.join(str(c) for c in bottom_cards) if bottom_cards else "无"
                        self.log(f"    {player.name}观星：牌堆顶-> {top_str} | 牌堆底-> {bot_str}")
                        state.add_event(
                            f"{player.name}观星排列：牌堆顶-> {top_str} | 牌堆底-> {bot_str}",
                            actor=state.active_player)
                        top = []  # already handled
                # If no agent or no response, put all back on top
                for c in reversed(top):
                    state.draw_pile.append(c)
        # 裸衣/突袭: LLM decides at draw phase
        has_nuoyi = has_skill(player, "裸衣")
        has_tuxi = has_skill(player, "突袭")
        if has_nuoyi or has_tuxi:
            view = get_player_view(state, state.active_player)
            act = self.agent_callback(view, "draw_phase")
            if act and act.skill_name == "裸衣" and has_nuoyi:
                state._nuoyi_bonus = state.active_player
                state.sha_limit[state.active_player] = 1
                drawn = state._draw(state.active_player, 1)
                card_str = " ".join(str(c) for c in drawn) if drawn else "无"
                self.log(f"    {player.name}裸衣：少摸一张牌，本回合伤害+1，摸了: {card_str}")
                state.add_event(f"{player.name}裸衣：摸1张牌: {card_str}", actor=state.active_player)
            elif act and act.skill_name == "突袭" and has_tuxi and act.cards_used:
                seen = set()
                for t_str in act.cards_used:
                    ti = int(t_str) if isinstance(t_str, str) else t_str
                    if ti in seen: continue
                    t = state.players[ti]
                    if t.alive and t.hand:
                        seen.add(ti)
                        c = t.hand.pop(0); player.hand.append(c)
                        self.log(f"    {player.name}突袭：从{t.name}获得 [{c}]")
                        state.add_event(f"{player.name}突袭：从{t.name}获得 [{c}]", actor=state.active_player, target=ti)
            else:
                dc = 2
                if has_skill(player, "英姿"): dc = 3
                drawn = state._draw(state.active_player, dc)
                card_str = " ".join(str(c) for c in drawn)
                self.log(f"    {player.name}摸了{len(drawn)}张牌: {card_str}")
                state.add_event(f"{player.name}摸了{len(drawn)}张牌: {card_str}", actor=state.active_player)
        else:
            dc = 2
            if has_skill(player, "英姿"): dc = 3
            drawn = state._draw(state.active_player, dc)
            card_str = " ".join(str(c) for c in drawn)
            self.log(f"    {player.name}摸了{len(drawn)}张牌: {card_str}")
            state.add_event(f"{player.name}摸了{len(drawn)}张牌: {card_str}",
                            actor=state.active_player)

        state.phase = Phase.PLAY
        eq_names = [c.name for c in player.equipment]
        hand_names = [f"{c.name}({c.suit.value})" for c in player.hand]
        self.log(f"    [状态] HP:{player.hp}/{player.max_hp} 手牌:{hand_names} 装备:{eq_names or '无'}")
        if getattr(state, '_skip_play_phase', False):
            self.log(f"  [{Phase.PLAY.value}] 跳过（乐不思蜀）")
        else:
            self.log(f"  [{Phase.PLAY.value}]")
            play_count, fails = 0, 0
            while play_count < 20 and fails < 3:
                player = state.players[state.active_player]
                if not player.hand: break
                view = get_player_view(state, state.active_player)
                action = self.agent_callback(view, "play_phase")
                if action is None or action.type == ActionType.PASS: break
                valid, reason = validate_action(state, action)
                if not valid: self.log(f"    [INVALID] {reason}"); fails += 1; continue
                fails = 0; play_count += 1
                events = execute_action(state, action, self.agent_callback)
                for e in events:
                    self.log(f"    [EVENT] {e.description}")
                    state.add_event(e.description, e.actor_idx, e.target_idx, e.card_name)
                    if self.recorder: self.recorder.record_event(e.description, e.actor_idx, e.target_idx, e.card_name, "出牌")
                player = state.players[state.active_player]
                eq_names = [c.name for c in player.equipment]
                self.log(f"    [状态] HP:{player.hp}/{player.max_hp} 手牌:{len(player.hand)} 装备:{eq_names or '无'}")

                if check_victory(state):
                    state.game_over = True; state.winner = check_victory(state)
                    self.log(f"\n[WINNER] Game over! {state.winner.value} wins!")
                    self._reveal_all_roles()
                    if self.recorder: self.recorder.set_winner(state.winner.value, state.turn_number, state.round_number)
                    return False

        state.phase = Phase.DISCARD
        hand_limit = player.hp
        if has_skill(player, "克己") and state.sha_used_this_turn[state.active_player] == 0:
            self.log(f"    {player.name}克己：跳过弃牌阶段")
        else:
            dc = len(player.hand) - hand_limit
            while dc > 0:
                view = get_player_view(state, state.active_player)
                action = self.agent_callback(view, "discard_phase", discard_count=dc)
                if action and action.type == ActionType.DISCARD:
                    valid, reason = validate_action(state, action)
                    if valid:
                        events = execute_action(state, action, self.agent_callback)
                        for e in events:
                            self.log(f"    [EVENT] {e.description}")
                            state.add_event(e.description, e.actor_idx)
                            if self.recorder: self.recorder.record_event(e.description, e.actor_idx, phase="弃牌")
                dc = len(player.hand) - hand_limit
                # Safety: if agent keeps failing, auto-discard remaining
                if dc > 0:
                    priority = {"桃": 5, "闪": 4, "无懈可击": 4, "杀": 1}
                    sorted_hand = sorted(player.hand, key=lambda c: priority.get(c.name, 2))
                    auto_discarded = []
                    for c in sorted_hand[:dc]:
                        player.hand.remove(c)
                        state.discard_pile.append(c)
                        auto_discarded.append(str(c))
                    self.log(f"    [EVENT] {player.name}弃置了{dc}张牌: {' '.join(auto_discarded)} (自动补弃)")
                    break
            self.log(f"    手牌: {len(player.hand)}/{hand_limit}")

        state.phase = Phase.END
        if has_skill(player, "闭月"):
            drawn = state._draw(state.active_player, 1)
            c_str = str(drawn[0]) if drawn else "无"
            state.add_event(f"{player.name}闭月：摸一张牌 [{c_str}]")
            self.log(f"    {player.name}闭月：摸一张牌 [{c_str}]")

        state.turn_number += 1
        if self.recorder: self.recorder.end_turn()
        self._next_player(); return True

    def _next_player(self):
        state = self.state; n = len(state.players)
        for _ in range(n):
            state.active_player = (state.active_player + 1) % n
            if state.players[state.active_player].alive: break
        if state.active_player == state.turn_order[0]: state.round_number += 1

    def _resolve_delay_cards(self):
        state = self.state; player = state.players[state.active_player]; resolved = []
        for card in player.delay_cards:
            if card.name == "闪电":
                negated = False
                if self.agent_callback:
                    tmp_action = Action(type=ActionType.PLAY_CARD, player_idx=state.active_player,
                                        card_name="闪电", target_idx=state.active_player)
                    negated = resolve_negate_chain(state, tmp_action, card, self.agent_callback)
                if negated:
                    self.log(f"    【无懈可击】抵消了{player.name}的【闪电】")
                    state.add_event(f"【无懈可击】抵消了{player.name}的【闪电】", actor=state.active_player)
                else:
                    j_card = do_judgment(state, state.active_player, None, self.agent_callback, "闪电")
                    self.log(f"    闪电判定: {j_card}")
                    state.add_event(f"{player.name}闪电判定: {j_card}",
                                    actor=state.active_player)
                    if j_card.suit.value == "♠" and 2 <= j_card.number <= 9:
                        deal_damage(state, state.active_player, state.active_player, 3, self.agent_callback)
                        self.log(f"    [LIGHTNING] {player.name} takes 3 lightning damage!")
                    else:
                        nxt = (state.active_player + 1) % len(state.players)
                        state.players[nxt].delay_cards.append(card)
                        self.log(f"    闪电移至{state.players[nxt].name}")
                resolved.append(card)
            elif card.name == "乐不思蜀":
                # 无懈 check first
                negated = False
                if self.agent_callback:
                    tmp_action = Action(type=ActionType.PLAY_CARD, player_idx=state.active_player,
                                        card_name="乐不思蜀", target_idx=state.active_player)
                    negated = resolve_negate_chain(state, tmp_action, card, self.agent_callback)
                if negated:
                    self.log(f"    【无懈可击】抵消了{player.name}的【乐不思蜀】")
                    state.add_event(f"【无懈可击】抵消了{player.name}的【乐不思蜀】", actor=state.active_player)
                else:
                    j_card = do_judgment(state, state.active_player, None, self.agent_callback, "乐不思蜀")
                    self.log(f"    乐不思蜀判定: {j_card}")
                    state.add_event(f"{player.name}乐不思蜀判定: {j_card}",
                                    actor=state.active_player)
                    if j_card.suit.value != "♥":
                        self.log(f"    {player.name}被乐不思蜀，跳过出牌阶段"); state._skip_play_phase = True
                        state.add_event(f"{player.name}被乐不思蜀，跳过出牌阶段",
                                        actor=state.active_player)
                    else:
                        state.add_event(f"{player.name}乐不思蜀判定为♥，无效",
                                        actor=state.active_player)
                resolved.append(card)
        for card in resolved:
            if card in player.delay_cards: player.delay_cards.remove(card); state.discard_pile.append(card)

    def _reveal_all_roles(self):
        for p in self.state.players:
            self.log(f"  {p.name}: {p.role.value} ({'存活' if p.alive else '死亡'})")


def random_agent(view: dict, phase: str, **kwargs) -> Action | None:
    import random
    player_idx = view["player_idx"]

    def _act(**fields) -> Action:
        """Build Action with auto-generated reasoning."""
        a = Action(player_idx=player_idx, **fields)
        # Auto-generate pseudo-reasoning
        parts = []
        if a.type == ActionType.PLAY_CARD:
            parts.append(f"使用【{a.card_name}】")
            if a.skill_name:
                parts[-1] = f"发动【{a.skill_name}】将手牌当【{a.card_name}】使用"
            if a.target_idx is not None:
                tname = view["players"][a.target_idx]["name"]
                parts.append(f"目标: {tname}")
        elif a.type == ActionType.USE_SKILL:
            parts.append(f"发动【{a.skill_name}】")
            if a.target_idx is not None:
                tname = view["players"][a.target_idx]["name"]
                parts.append(f"目标: {tname}")
        elif a.type == ActionType.RESPOND:
            if a.skill_name:
                parts.append(f"使用【{a.skill_name}】打出【{a.card_name or a.skill_name}】")
            elif a.card_name:
                parts.append(f"打出【{a.card_name}】")
        elif a.type == ActionType.DISCARD:
            parts.append(f"弃置{len(a.cards_used)}张牌")
        elif a.type == ActionType.PASS:
            parts.append("跳过（无合适操作）")
        a.reasoning = " | ".join(parts) if parts else "随机AI决策"
        return a

    if phase == "play_phase":
        hand = view["my_hand"]
        if not hand: return _act(type=ActionType.PASS)
        sha_limit = view.get("sha_limit", 1); sha_used = view.get("sha_used", 0)
        skills_lower = [s.lower() for s in view.get("my_skills", [])]
        n = len(view["players"])
        alive_targets = [i for i, p in enumerate(view["players"]) if p["alive"] and i != player_idx]
        nearest = min(alive_targets, key=lambda t: min((t-player_idx)%n, (player_idx-t)%n)) if alive_targets else None

        # === Card substitution (奇袭/武圣/国色/丈八蛇矛) ===
        if "奇袭" in skills_lower and nearest is not None:
            for c in hand:
                if c["suit"] in ("♠","♣"):
                    return _act(type=ActionType.PLAY_CARD, card_name="过河拆桥", skill_name="奇袭", target_idx=nearest)
        if "国色" in skills_lower and nearest is not None:
            for c in hand:
                if c["suit"] == "♦":
                    return _act(type=ActionType.PLAY_CARD, card_name="乐不思蜀", skill_name="国色", target_idx=nearest)
        if "武圣" in skills_lower and sha_used < sha_limit and nearest is not None:
            for c in hand:
                if c["suit"] in ("♥","♦"):
                    return _act(type=ActionType.PLAY_CARD, card_name="杀", skill_name="武圣", target_idx=nearest)
        if "龙胆" in skills_lower and sha_used < sha_limit and nearest is not None:
            for c in hand:
                if c["name"] == "闪":
                    return _act(type=ActionType.PLAY_CARD, card_name="杀", skill_name="龙胆", target_idx=nearest)
        # 丈八蛇矛: use 2 hand cards as 杀
        if "丈八蛇矛" in view.get("my_equipment", []) and sha_used < sha_limit and nearest is not None and len(hand) >= 2:
            return _act(type=ActionType.PLAY_CARD, card_name="杀", skill_name="丈八蛇矛",
                        target_idx=nearest, cards_used=[hand[0]["name"], hand[1]["name"]])

        # === Skill activation (USE_SKILL) ===
        if "反间" in skills_lower and hand and nearest is not None:
            return _act(type=ActionType.USE_SKILL, skill_name="反间",
                        target_idx=nearest, cards_used=[hand[0]["name"]])
        if "离间" in skills_lower and hand and nearest is not None:
            males = [i for i, p in enumerate(view["players"]) if p["alive"] and i != player_idx
                     and p.get("gender", "male") == "male"]
            if len(males) >= 2:
                return _act(type=ActionType.USE_SKILL, skill_name="离间",
                            target_idx=males[0], cards_used=[hand[0]["name"]],
                            extra={"secondary_target": males[1]})
        if "制衡" in skills_lower and len(hand) >= 3:
            return _act(type=ActionType.USE_SKILL, skill_name="制衡",
                        cards_used=[c["name"] for c in hand[:3]])
        if "苦肉" in skills_lower and view["my_hp"] > 1 and hand:
            return _act(type=ActionType.USE_SKILL, skill_name="苦肉",
                        cards_used=[hand[0]["name"]])
        if "结姻" in skills_lower and len(hand) >= 2 and view["my_hp"] < view["my_max_hp"]:
            males = [i for i, p in enumerate(view["players"]) if p["alive"] and p.get("gender", "male") == "male"
                     and p["hp"] < p["max_hp"]]
            if males:
                return _act(type=ActionType.USE_SKILL, skill_name="结姻",
                            target_idx=males[0], cards_used=[hand[0]["name"], hand[1]["name"]])
        if "青囊" in skills_lower and hand:
            injured = [i for i, p in enumerate(view["players"]) if p["alive"] and p["hp"] < p["max_hp"]]
            if injured:
                return _act(type=ActionType.USE_SKILL, skill_name="青囊",
                            target_idx=injured[0], cards_used=[hand[0]["name"]])
        if "仁德" in skills_lower and len(hand) >= 2 and nearest is not None:
            return _act(type=ActionType.USE_SKILL, skill_name="仁德",
                        target_idx=nearest, cards_used=[c["name"] for c in hand[:2]])

        shuffled = list(hand); random.shuffle(shuffled)

        for card_info in shuffled:
            cn = card_info["name"]; ct = card_info["type"]
            if cn == "杀" and sha_used >= sha_limit: continue
            if cn == "桃" and view["my_hp"] < view["my_max_hp"]:
                return _act(type=ActionType.PLAY_CARD, card_name="桃", target_idx=player_idx)
            if ct == "装备":
                return _act(type=ActionType.PLAY_CARD, card_name=cn)
            if cn in ("无中生有","五谷丰登","桃园结义","南蛮入侵","万箭齐发"):
                return _act(type=ActionType.PLAY_CARD, card_name=cn)
            if cn == "借刀杀人" and nearest is not None:
                sec = next((i for i in alive_targets if i != nearest), None)
                if sec is not None:
                    return _act(type=ActionType.PLAY_CARD, card_name=cn, target_idx=nearest,
                                extra={"secondary_target": sec})
            if cn == "闪电":
                return _act(type=ActionType.PLAY_CARD, card_name=cn)
            if not nearest: continue
            if cn in ("杀","决斗","过河拆桥","顺手牵羊","乐不思蜀"):
                return _act(type=ActionType.PLAY_CARD, card_name=cn, target_idx=nearest)
        return _act(type=ActionType.PASS)

    if phase == "discard_phase":
        dc = kwargs.get("discard_count", 0); hand = view["my_hand"]
        if hand and dc > 0:
            priority = {"桃":5,"闪":4,"无懈可击":4,"杀":1}
            sorted_hand = sorted(hand, key=lambda c: priority.get(c["name"], 2))
            return _act(type=ActionType.DISCARD,
                        cards_used=[c["name"] for c in sorted_hand[:dc]])
        return None

    if phase == "response":
        rt = kwargs.get("response_type",""); hand = view["my_hand"]
        skills = [s.lower() for s in view.get("my_skills", [])]
        if rt == "闪":
            for c in hand:
                if c["name"] == "闪": return _act(type=ActionType.RESPOND, card_name="闪")
            if "倾国" in skills:
                for c in hand:
                    if c["suit"] in ("♠","♣"): return _act(type=ActionType.RESPOND, card_name=c["name"], skill_name="倾国")
            if "龙胆" in skills:
                for c in hand:
                    if c["name"] == "杀": return _act(type=ActionType.RESPOND, card_name="杀", skill_name="龙胆")
            return None
        if rt == "杀":
            for c in hand:
                if c["name"] == "杀": return _act(type=ActionType.RESPOND, card_name="杀")
            if "武圣" in skills:
                for c in hand:
                    if c["suit"] in ("♥","♦"): return _act(type=ActionType.RESPOND, card_name=c["name"], skill_name="武圣")
            if "龙胆" in skills:
                for c in hand:
                    if c["name"] == "闪": return _act(type=ActionType.RESPOND, card_name="闪", skill_name="龙胆")
            return None
        return None

    if phase == "negate":
        hand = view["my_hand"]; target_idx = kwargs.get("target_idx"); card_name = kwargs.get("card_name","")
        has_wx = any(c["name"] == "无懈可击" for c in hand)
        if card_name == "无懈可击":
            if has_wx and (sum(1 for c in hand if c["name"]=="无懈可击") >= 2 or random.random() < 0.5):
                return _act(type=ActionType.RESPOND, card_name="无懈可击")
        else:
            should = target_idx == player_idx and card_name in ("过河拆桥","顺手牵羊","决斗","乐不思蜀")
            should = should or (card_name in ("南蛮入侵","万箭齐发"))
            if should and has_wx:
                return _act(type=ActionType.RESPOND, card_name="无懈可击")
        return None

    if phase == "guicai":
        if random.random() < 0.4 and view["my_hand"]:
            return _act(type=ActionType.RESPOND, card_name=view["my_hand"][0]["name"])
        return None

    if phase == "dying":
        hand = view["my_hand"]; dying_idx = kwargs.get("dying_idx", -1)
        my_role = view.get("my_role","")
        if dying_idx == player_idx:
            for c in hand:
                if c["name"] == "桃": return _act(type=ActionType.RESPOND, card_name="桃")
            if "急救" in [s.lower() for s in view.get("my_skills",[])]:
                for c in hand:
                    if c["suit"] in ("♥","♦"): return _act(type=ActionType.RESPOND, card_name=c["name"], skill_name="急救")
                # also check equipment (view only shows names, not suits, but try anyway)
                for eq in view.get("my_equipment", []):
                    pass  # can't check suit from view, hand check is primary
            return None
        lord_idx = view.get("lord_idx", 0); save = False
        if my_role == "主公": save = True
        elif my_role == "忠臣" and dying_idx == lord_idx: save = True
        elif my_role == "反贼" and dying_idx != lord_idx: save = True
        if save:
            for c in hand:
                if c["name"] == "桃": return _act(type=ActionType.RESPOND, card_name="桃")
            if "急救" in [s.lower() for s in view.get("my_skills",[])]:
                for c in hand:
                    if c["suit"] in ("♥","♦"): return _act(type=ActionType.RESPOND, card_name=c["name"], skill_name="急救")
                # also check equipment (view only shows names, not suits, but try anyway)
                for eq in view.get("my_equipment", []):
                    pass  # can't check suit from view, hand check is primary
        return None

    if phase == "draw_phase":
        skills = [s.lower() for s in view.get("my_skills",[])]
        if "裸衣" in skills and view["my_hp"] > 1:
            return _act(type=ActionType.USE_SKILL, skill_name="裸衣")
        if "突袭" in skills:
            alive = [i for i,p in enumerate(view["players"]) if p["alive"] and i != player_idx and p.get("hand_count",0) > 0]
            if alive:
                targets = random.sample(alive, min(2, len(alive)))
                return _act(type=ActionType.USE_SKILL, skill_name="突袭", cards_used=targets)
        return None

    if phase == "liuli_redirect":
        skills = [s.lower() for s in view.get("my_skills",[])]
        if "流离" in skills:
            alive = [i for i,p in enumerate(view["players"]) if p["alive"] and i != player_idx]
            if alive and view["my_hand"]:
                return _act(type=ActionType.USE_SKILL, skill_name="流离",
                            target_idx=alive[0], cards_used=[view["my_hand"][0]["name"]])
        return None

    if phase == "jiedao_choice":
        # Random: use 杀 if available, else give weapon
        if any(c["name"] == "杀" for c in view.get("my_hand", [])):
            return _act(type=ActionType.RESPOND, card_name="杀")
        return None

    if phase == "fankui":
        return _act(type=ActionType.RESPOND, skill_name="trigger")

    if phase == "fanjian_guess":
        suits = ["♠", "♥", "♣", "♦"]
        guess = random.choice(suits)
        return _act(type=ActionType.RESPOND, card_name=guess)

    if phase == "ganglie_choice":
        hand = view.get("my_hand", [])
        if len(hand) >= 2 and random.random() < 0.5:
            return _act(type=ActionType.RESPOND, skill_name="discard",
                        cards_used=[c["name"] for c in random.sample(hand, 2)])
        return _act(type=ActionType.RESPOND, skill_name="damage")

    # Weapon interaction phases (random defaults)
    if phase == "guanxing":
        cards = kwargs.get("cards", [])
        if cards:
            return Action(type=ActionType.USE_SKILL, player_idx=player_idx,
                         skill_name="观星", cards_used=[f"{c}:top" for c in cards])
        return None

    if phase == "cxt_option":
        # 雌雄双股剑: target chooses discard or let attacker draw
        if view["my_hand"]:
            return _act(type=ActionType.RESPOND, skill_name="discard")
        return _act(type=ActionType.RESPOND, skill_name="draw")

    if phase == "guanshi_axe":
        # 贯石斧: 50% chance to discard 2 to force hit
        if len(view.get("my_hand", [])) >= 2 and random.random() < 0.5:
            return _act(type=ActionType.RESPOND,
                        cards_used=[c["name"] for c in view["my_hand"][:2]])
        return None

    if phase == "qinglong_blade":
        # 青龙偃月刀: use another 杀 if available
        return _act(type=ActionType.RESPOND)

    if phase == "hanbing_sword":
        # 寒冰剑: 50% chance to discard 2 for discard effect
        if len(view.get("my_hand", [])) >= 2 and random.random() < 0.5:
            return _act(type=ActionType.RESPOND,
                        cards_used=[c["name"] for c in view["my_hand"][:2]])
        return None

    if phase == "wugu_pick":
        revealed = kwargs.get("revealed", [])
        if revealed:
            import re
            # Pick highest-value card: 无懈可击 > 桃 > 顺手牵羊 > 过河拆桥 > 杀 > 闪
            priority = {"无懈可击": 10, "桃": 9, "顺手牵羊": 8, "过河拆桥": 7,
                       "无中生有": 7, "决斗": 6, "南蛮入侵": 5, "万箭齐发": 5,
                       "五谷丰登": 4, "桃园结义": 4, "借刀杀人": 3, "乐不思蜀": 2,
                       "闪电": 1, "杀": 1, "闪": 0}
            best = max(revealed, key=lambda s: priority.get(s.split(" ")[0].split("[")[-1].rstrip("]") if "[" in s else s, 0))
            # Extract just the card name
            cn = best.split("[")[-1].rstrip("]") if "[" in best else best
            return Action(type=ActionType.RESPOND, player_idx=player_idx, card_name=cn)

    return None


