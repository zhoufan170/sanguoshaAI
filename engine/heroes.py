"""Standard pack heroes (24 + 4 lords) for Sanguosha."""
from dataclasses import dataclass, field
from enum import Enum
import random


class Kingdom(Enum):
    WEI = "魏"
    SHU = "蜀"
    WU = "吴"
    QUN = "群"


class Role(Enum):
    LORD = "主公"
    LOYALIST = "忠臣"
    REBEL = "反贼"
    TRAITOR = "内奸"


@dataclass
class Skill:
    name: str
    description: str


@dataclass
class Hero:
    name: str
    kingdom: Kingdom
    hp: int
    gender: str = "male"
    is_lord: bool = False  # can be selected as 主公
    skills: list[Skill] = field(default_factory=list)
    lord_skill: Skill | None = None  # extra skill when playing as lord


# ==========================================
# Wei (魏) — 7 heroes
# ==========================================

CAOCAO = Hero("曹操", Kingdom.WEI, 4, is_lord=True, skills=[
    Skill("奸雄", "当你受到伤害后，你可以获得造成此伤害的牌"),
], lord_skill=Skill("护驾", "主公技：当你需要使用或打出【闪】时，你可以令其他魏势力角色打出一张【闪】（视为由你使用或打出）"))

SIMAYI = Hero("司马懿", Kingdom.WEI, 3, skills=[
    Skill("反馈", "当你受到伤害后，你可以获得伤害来源的一张牌"),
    Skill("鬼才", "当一名角色的判定牌生效前，你可以打出一张手牌代替之"),
])

XIAOHOUDUN = Hero("夏侯惇", Kingdom.WEI, 4, skills=[
    Skill("刚烈", "当你受到伤害后，你可以进行判定：若结果不为♥，伤害来源弃置两张手牌或受到1点伤害"),
])

ZHANGLIAO = Hero("张辽", Kingdom.WEI, 4, skills=[
    Skill("突袭", "摸牌阶段，你可以放弃摸牌改为获得一至两名其他角色的各一张手牌"),
])

XUCHU = Hero("许褚", Kingdom.WEI, 4, skills=[
    Skill("裸衣", "摸牌阶段，你可以少摸一张牌，本回合你使用【杀】或【决斗】造成的伤害+1"),
])

GUOJIA = Hero("郭嘉", Kingdom.WEI, 3, skills=[
    Skill("天妒", "当你的判定牌生效后，你可以获得此牌"),
    Skill("遗计", "当你受到1点伤害后，你可以摸两张牌，然后你可以在至多两名角色的武将牌旁分别分配至多两张手牌"),
])

ZHENJI = Hero("甄姬", Kingdom.WEI, 3, gender="female", skills=[
    Skill("洛神", "准备阶段，你可以进行判定：若为黑色，你获得此牌并可以重复此流程；若为红色，你获得此牌"),
    Skill("倾国", "你可以将一张黑色手牌当【闪】使用或打出"),
])

# ==========================================
# Shu (蜀) — 7 heroes
# ==========================================

LIUBEI = Hero("刘备", Kingdom.SHU, 4, is_lord=True, skills=[
    Skill("仁德", "出牌阶段，你可以将任意张手牌交给其他角色，若此阶段你给出的牌张数达到两张或更多，你回复1点体力"),
], lord_skill=Skill("激将", "主公技：当你需要使用或打出【杀】时，你可以令其他蜀势力角色打出一张【杀】（视为由你使用或打出）"))

GUANYU = Hero("关羽", Kingdom.SHU, 4, skills=[
    Skill("武圣", "你可以将一张红色牌当【杀】使用或打出"),
])

ZHANGFEI = Hero("张飞", Kingdom.SHU, 4, skills=[
    Skill("咆哮", "锁定技：你使用【杀】无次数限制"),
])

ZHUGE_LIANG = Hero("诸葛亮", Kingdom.SHU, 3, skills=[
    Skill("观星", "摸牌阶段开始时，你可以观看牌堆顶的X张牌（X为存活角色数且至多为5），然后以任意顺序放回牌堆顶或牌堆底"),
    Skill("空城", "锁定技：若你没有手牌，你不能成为【杀】或【决斗】的目标"),
])

ZHAOYUN = Hero("赵云", Kingdom.SHU, 4, skills=[
    Skill("龙胆", "你可以将【杀】当【闪】使用或打出，也可以将【闪】当【杀】使用或打出"),
])

MACHAO = Hero("马超", Kingdom.SHU, 4, skills=[
    Skill("马术", "锁定技：你计算与其他角色的距离-1"),
    Skill("铁骑", "当你使用【杀】指定目标后，你可以进行判定：若为红色，此【杀】不可被【闪】响应"),
])

HUANGZHONG = Hero("黄忠", Kingdom.SHU, 4, skills=[
    Skill("烈弓", "当你使用【杀】指定目标后，若你的手牌数不小于目标的手牌数或体力值不小于目标的体力值，此【杀】不可被【闪】响应"),
])

# ==========================================
# Wu (吴) — 8 heroes
# ==========================================

SUNQUAN = Hero("孙权", Kingdom.WU, 4, is_lord=True, skills=[
    Skill("制衡", "出牌阶段限一次，你可以弃置任意张牌并摸等量的牌"),
], lord_skill=Skill("救援", "主公技：其他吴势力角色可以在他们各自的回合内对你使用【桃】"))

ZHOUYU = Hero("周瑜", Kingdom.WU, 3, skills=[
    Skill("英姿", "锁定技：摸牌阶段你多摸一张牌"),
    Skill("反间", "出牌阶段限一次，你可以令一名其他角色选择一种花色后获得你的一张手牌并展示：若与所选不同，其受到1点伤害"),
])

GANNING = Hero("甘宁", Kingdom.WU, 4, skills=[
    Skill("奇袭", "你可以将一张黑色牌当【过河拆桥】使用"),
])

LYUMENG = Hero("吕蒙", Kingdom.WU, 4, skills=[
    Skill("克己", "若你于出牌阶段未使用或弃置过【杀】，你可以跳过弃牌阶段"),
])

HUANGGAI = Hero("黄盖", Kingdom.WU, 4, skills=[
    Skill("苦肉", "出牌阶段，你可以弃置一张牌并失去1点体力，然后摸两张牌"),
])

LUXUN = Hero("陆逊", Kingdom.WU, 3, skills=[
    Skill("谦逊", "当你成为【顺手牵羊】或【乐不思蜀】的目标时，取消之"),
    Skill("连营", "当你失去最后一张手牌时，你可以摸一张牌"),
])

DAQIAO = Hero("大乔", Kingdom.WU, 3, gender="female", skills=[
    Skill("国色", "你可以将一张♦牌当【乐不思蜀】使用"),
    Skill("流离", "当你成为【杀】的目标时，你可以弃置一张牌并将此【杀】转移给你攻击范围内的一名其他角色"),
])

SUNSHANGXIANG = Hero("孙尚香", Kingdom.WU, 3, gender="female", skills=[
    Skill("结姻", "出牌阶段限一次，你可以弃置两张手牌并选择一名受伤的男性角色：你与其各回复1点体力"),
    Skill("枭姬", "当你失去一张坐骑区或武器区的牌后，你可以摸两张牌"),
])

# ==========================================
# Qun (群) — 3 heroes
# ==========================================

HUATUO = Hero("华佗", Kingdom.QUN, 3, skills=[
    Skill("青囊", "出牌阶段限一次，你可以弃置一张手牌并令一名角色回复1点体力"),
    Skill("急救", "你的回合外，你可以将一张红色牌当【桃】使用"),
])

LVBU = Hero("吕布", Kingdom.QUN, 4, skills=[
    Skill("无双", "锁定技：当你使用【杀】指定目标后，该角色需连续使用两张【闪】才能抵消；与你进行【决斗】的角色每次需连续打出两张【杀】"),
])

DIAOCHAN = Hero("貂蝉", Kingdom.QUN, 3, gender="female", skills=[
    Skill("离间", "出牌阶段限一次，你可以弃置一张牌并令两名男性角色决斗"),
    Skill("闭月", "结束阶段，你可以摸一张牌"),
])


# Master list
ALL_HEROES: list[Hero] = [
    CAOCAO, SIMAYI, XIAOHOUDUN, ZHANGLIAO, XUCHU, GUOJIA, ZHENJI,
    LIUBEI, GUANYU, ZHANGFEI, ZHUGE_LIANG, ZHAOYUN, MACHAO, HUANGZHONG,
    SUNQUAN, ZHOUYU, GANNING, LYUMENG, HUANGGAI, LUXUN, DAQIAO, SUNSHANGXIANG,
    HUATUO, LVBU, DIAOCHAN,
]

LORD_HEROES: list[Hero] = [h for h in ALL_HEROES if h.is_lord]


def assign_roles(num_players: int = 8) -> list[Role]:
    """Assign roles for an N-player game.
    Standard 8-player: 1 Lord, 2 Loyalists, 4 Rebels, 1 Traitor.
    """
    if num_players == 5:
        return [Role.LORD, Role.LOYALIST, Role.REBEL, Role.REBEL, Role.TRAITOR]
    if num_players == 6:
        return [Role.LORD, Role.LOYALIST, Role.REBEL, Role.REBEL, Role.REBEL, Role.TRAITOR]
    if num_players == 7:
        return [Role.LORD, Role.LOYALIST, Role.LOYALIST, Role.REBEL, Role.REBEL, Role.REBEL, Role.TRAITOR]
    # 8-player default
    return [Role.LORD, Role.LOYALIST, Role.LOYALIST,
            Role.REBEL, Role.REBEL, Role.REBEL, Role.REBEL,
            Role.TRAITOR]


def select_heroes(num_players: int = 8) -> list[Hero]:
    """Select heroes for each player. Uses global random state.
    Lord (index 0) gets: 曹操/刘备/孙权 (all 3 lord heroes) + 2 random → pick 1.
    Others get 3 random heroes → pick 1."""
    pool = list(ALL_HEROES)
    random.shuffle(pool)

    selected = []

    # Lord: 3 lord heroes (曹操/刘备/孙权) + 2 non-lord = 5 options, pick 1
    lord_heroes = list(LORD_HEROES)
    others = [h for h in pool if h not in lord_heroes]
    lord_options = lord_heroes + others[:2]
    random.shuffle(lord_options)
    lord_choice = lord_options[0]
    selected.append(lord_choice)
    pool.remove(lord_choice)

    # Others: 3 random each
    for i in range(num_players - 1):
        options = pool[:3]
        choice = random.choice(options)
        selected.append(choice)
        pool.remove(choice)

    return selected


def build_hero_options(roles: list[Role]) -> list[list[Hero]]:
    """Build hero option pools for each player based on their role.
    Lord gets: 曹操/刘备/孙权 + 2 random non-lord (5 options).
    Others get: 3 unique random heroes each (3 options).
    No hero appears in more than one player's option pool."""
    pool = list(ALL_HEROES)
    random.shuffle(pool)

    lord_heroes = list(LORD_HEROES)
    non_lord_pool = [h for h in pool if h not in lord_heroes]
    random.shuffle(non_lord_pool)
    options_per_player = []
    cursor = 2  # lord takes first 2 non-lord heroes as options

    for role in roles:
        if role == Role.LORD:
            # Lord: 3 lord heroes + 2 non-lord = 5 options
            opts = lord_heroes + non_lord_pool[:2]
        else:
            # Others: 3 unique non-lord heroes each (or fewer if pool exhausted)
            opts = non_lord_pool[cursor:cursor + 3]
            cursor += len(opts)
        random.shuffle(opts)
        options_per_player.append(opts[:])

    return options_per_player


def hero_option_to_dict(hero: Hero) -> dict:
    """Convert a Hero to a dict for LLM prompts."""
    return {
        "name": hero.name,
        "kingdom": hero.kingdom.value,
        "hp": hero.hp,
        "is_lord": hero.is_lord,
        "skills": [{"name": s.name, "description": s.description} for s in hero.skills],
    }
