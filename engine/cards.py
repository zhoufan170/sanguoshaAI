"""Standard pack card definitions for Sanguosha (三国杀)."""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional
import random

# Card number constants
A = 1
J = 11
Q = 12
K = 13


class CardType(Enum):
    BASIC = "基本"
    STRATEGY = "锦囊"
    EQUIPMENT = "装备"
    DELAY = "延时锦囊"


class CardSuit(Enum):
    SPADE = "♠"
    HEART = "♥"
    CLUB = "♣"
    DIAMOND = "♦"


@dataclass(frozen=True)
class Card:
    id: int
    name: str
    type: CardType
    suit: CardSuit
    number: int  # 1-13, A=1, J=11, Q=12, K=13
    range_bonus: int = 0  # for weapons / horses
    description: str = ""

    def __repr__(self):
        return f"{self.suit.value}{self.number} [{self.name}]"


def _c(card_id, name, ctype, suit, number, range_bonus=0, description=""):
    return Card(id=card_id, name=name, type=ctype, suit=suit, number=number,
                range_bonus=range_bonus, description=description)


def build_standard_deck() -> list[Card]:
    """Build the standard 104-card deck (standard pack + expansions base).
    Actually returns the standard set used in base Sanguosha: ~108 cards.
    """
    cards: list[Card] = []
    cid = 0

    S = CardSuit.SPADE
    H = CardSuit.HEART
    C = CardSuit.CLUB
    D = CardSuit.DIAMOND
    B = CardType.BASIC
    ST = CardType.STRATEGY
    EQ = CardType.EQUIPMENT
    DE = CardType.DELAY

    # === Basic Cards ===
    # 杀 (Attack) ×30
    sha_specs = [
        (S, 7), (S, 8), (S, 8), (S, 9), (S, 9), (S, 10), (S, 10),  # 7 spades
        (H, 10), (H, 10), (H, J),                                    # 3 hearts
        (C, 2), (C, 3), (C, 4), (C, 5), (C, 6), (C, 7), (C, 8),
        (C, 8), (C, 9), (C, 9), (C, 10), (C, 10), (C, J), (C, J),  # 14 clubs
        (D, 6), (D, 7), (D, 8), (D, 9), (D, 10), (D, K),            # 6 diamonds
    ]
    for suit, num in sha_specs:
        cid += 1; cards.append(_c(cid, "杀", B, suit, num, description="对一名角色造成1点伤害"))

    # 闪 (Dodge) ×15
    shan_specs = [
        (H, 2), (H, 2), (H, K),                           # 3 hearts
        (D, 2), (D, 2), (D, 3), (D, 4), (D, 5), (D, 6),
        (D, 7), (D, 8), (D, 9), (D, 10), (D, J), (D, J),  # 12 diamonds
    ]
    for suit, num in shan_specs:
        cid += 1; cards.append(_c(cid, "闪", B, suit, num, description="抵消一张【杀】的效果"))

    # 桃 (Peach) ×8
    tao_specs = [
        (H, 3), (H, 4), (H, 6), (H, 7), (H, 8), (H, 9), (H, Q),  # 7 hearts
        (D, Q),                                                     # 1 diamond
    ]
    for suit, num in tao_specs:
        cid += 1; cards.append(_c(cid, "桃", B, suit, num, description="回复1点体力"))

    # === Strategy Cards (锦囊) ===
    # 过河拆桥 (Dismantle) ×6
    for suit, num in [(S, 3), (S, 4), (S, Q), (H, Q), (C, 3), (C, 4)]:
        cid += 1; cards.append(_c(cid, "过河拆桥", ST, suit, num, description="弃置目标角色区域里的一张牌"))

    # 顺手牵羊 (Snatch) ×5
    for suit, num in [(S, 3), (S, 4), (S, J), (D, 3), (D, 4)]:
        cid += 1; cards.append(_c(cid, "顺手牵羊", ST, suit, num, description="获得目标角色区域里的一张牌"))

    # 无中生有 (Something for Nothing) ×4
    for suit, num in [(H, 7), (H, 8), (H, 9), (H, J)]:
        cid += 1; cards.append(_c(cid, "无中生有", ST, suit, num, description="摸两张牌"))

    # 无懈可击 (Negate) ×7
    for suit, num in [(S, J), (S, K), (H, Q), (C, Q), (C, K), (D, Q), (H, K)]:
        cid += 1; cards.append(_c(cid, "无懈可击", ST, suit, num, description="抵消一张锦囊牌的效果"))

    # 决斗 (Duel) ×3
    for suit, num in [(S, A), (C, A), (D, A)]:
        cid += 1; cards.append(_c(cid, "决斗", ST, suit, num, description="与目标角色进行决斗：轮流打出【杀】，先打不出的一方受到1点伤害"))

    # 南蛮入侵 (Barbarian Invasion) ×3
    for suit, num in [(S, 7), (S, K), (C, 7)]:
        cid += 1; cards.append(_c(cid, "南蛮入侵", ST, suit, num, description="所有其他角色需打出一张【杀】，否则受到1点伤害"))

    # 万箭齐发 (Volley of Arrows) ×1
    cid += 1; cards.append(_c(cid, "万箭齐发", ST, H, A, description="所有其他角色需打出一张【闪】，否则受到1点伤害"))

    # 五谷丰登 (Bountiful Harvest) ×2
    for suit, num in [(H, 3), (H, 4)]:
        cid += 1; cards.append(_c(cid, "五谷丰登", ST, suit, num, description="亮出等同于角色数量的牌，从当前回合角色开始依次获得一张"))

    # 桃园结义 (Peach Garden Oath) ×1
    cid += 1; cards.append(_c(cid, "桃园结义", ST, H, A, description="所有角色回复1点体力"))

    # 借刀杀人 (Borrowed Blade) ×2
    for suit, num in [(C, Q), (C, K)]:
        cid += 1; cards.append(_c(cid, "借刀杀人", ST, suit, num, description="指定一名角色对另一名角色使用【杀】，否则将其武器交给你"))

    # === Delay Strategy Cards (延时锦囊) ===
    # 闪电 (Lightning) ×2
    for suit, num in [(S, A), (H, Q)]:
        cid += 1; cards.append(_c(cid, "闪电", DE, suit, num, description="判定：若为♠2-9，受到3点雷电伤害，否则移至下家"))

    # 乐不思蜀 (Indulgence) ×3
    for suit, num in [(H, 6), (S, 6), (C, 6)]:
        cid += 1; cards.append(_c(cid, "乐不思蜀", DE, suit, num, description="判定：若不为♥，跳过出牌阶段"))

    # === Equipment (装备) ===
    # Weapons
    cid += 1; cards.append(_c(cid, "诸葛连弩", EQ, S, A, range_bonus=1, description="锁定技：你使用【杀】无次数限制"))
    cid += 1; cards.append(_c(cid, "诸葛连弩", EQ, C, A, range_bonus=1, description="锁定技：你使用【杀】无次数限制"))
    cid += 1; cards.append(_c(cid, "青釭剑", EQ, S, 6, range_bonus=2, description="锁定技：你使用【杀】时无视目标防具"))
    cid += 1; cards.append(_c(cid, "丈八蛇矛", EQ, S, Q, range_bonus=3, description="可将两张手牌当【杀】使用"))
    cid += 1; cards.append(_c(cid, "贯石斧", EQ, D, 5, range_bonus=3, description="你使用【杀】被抵消后可弃两张牌强制命中"))
    cid += 1; cards.append(_c(cid, "麒麟弓", EQ, H, 5, range_bonus=5, description="你使用【杀】造成伤害后可弃置目标一匹马"))
    cid += 1; cards.append(_c(cid, "寒冰剑", EQ, S, 2, range_bonus=2, description="可弃两张牌改为弃置目标两张牌代替造成伤害"))
    cid += 1; cards.append(_c(cid, "青龙偃月刀", EQ, S, 5, range_bonus=3, description="你使用【杀】被抵消后可对同一目标再使用一张【杀】"))
    cid += 1; cards.append(_c(cid, "雌雄双股剑", EQ, S, 2, range_bonus=2, description="对异性角色使用【杀】时，目标需弃一张牌或让你摸一张牌"))

    # Armor
    cid += 1; cards.append(_c(cid, "八卦阵", EQ, S, 2, description="当你需要使用或打出【闪】时，可判定：若为红色视为打出【闪】"))
    cid += 1; cards.append(_c(cid, "八卦阵", EQ, C, 2, description="当你需要使用或打出【闪】时，可判定：若为红色视为打出【闪】"))
    cid += 1; cards.append(_c(cid, "仁王盾", EQ, C, 2, description="锁定技：黑色【杀】对你无效"))

    # Defensive horses (+1)
    cid += 1; cards.append(_c(cid, "的卢", EQ, H, 5, range_bonus=1, description="+1马：其他角色计算与你的距离时+1"))
    cid += 1; cards.append(_c(cid, "绝影", EQ, S, 5, range_bonus=1, description="+1马：其他角色计算与你的距离时+1"))
    cid += 1; cards.append(_c(cid, "爪黄飞电", EQ, H, K, range_bonus=1, description="+1马：其他角色计算与你的距离时+1"))

    # Offensive horses (-1)
    cid += 1; cards.append(_c(cid, "赤兔", EQ, H, 5, range_bonus=-1, description="-1马：你计算与其他角色的距离时-1"))
    cid += 1; cards.append(_c(cid, "大宛", EQ, S, K, range_bonus=-1, description="-1马：你计算与其他角色的距离时-1"))
    cid += 1; cards.append(_c(cid, "紫骍", EQ, D, K, range_bonus=-1, description="-1马：你计算与其他角色的距离时-1"))

    return cards


def shuffle_and_deal(deck: list[Card], num_players: int, hand_size: int = 4):
    """Shuffle deck and deal initial hands. Returns (draw_pile, hands)."""
    random.shuffle(deck)
    hands = []
    for i in range(num_players):
        hands.append(deck[i * hand_size:(i + 1) * hand_size])
    draw_pile = deck[num_players * hand_size:]
    return draw_pile, hands
