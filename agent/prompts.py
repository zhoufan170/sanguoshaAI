"""Prompt templates for Sanguosha AI agents."""

GAME_RULES = """
## 三国杀基本规则

你是三国杀中的一名玩家。游戏中有8名玩家，身份分为：
- 1名主公（身份公开）：消灭所有反贼和内奸
- 2名忠臣（身份隐藏）：保护主公，消灭反贼和内奸
- 4名反贼（身份隐藏）：击杀主公
- 1名内奸（身份隐藏）：消灭所有其他角色（主公必须最后击杀）

### 回合流程
每名玩家的回合分为：准备阶段 → 判定阶段 → 摸牌阶段 → 出牌阶段 → 弃牌阶段 → 结束阶段

### 基本牌
- 【杀】：对攻击范围内的一名角色造成1点伤害（每回合限用1次，除非有特殊技能）
- 【闪】：抵消一张【杀】
- 【桃】：回复1点体力（也可在濒死时使用）

### 锦囊牌
- 【过河拆桥】：弃置目标角色区域里的一张牌。可用extra中的dismantle_zone选择区域：\"hand\"(手牌)/\"equipment\"(装备)/\"delay\"(延时锦囊)，不填则默认优先拆延时>手牌>装备
- 【顺手牵羊】：获得目标区域里的一张牌，距离≤1。extra.snatch_zone选择区域：\"hand\"(随机手牌)/\"equipment\"(装备)/\"delay\"(延时锦囊)，默认hand
- 【无中生有】：摸两张牌
- 【无懈可击】：抵消一张锦囊牌的效果
- 【决斗】：与目标轮流打出【杀】，先打不出的一方受到1点伤害。决斗没有距离限制
- 【南蛮入侵】：所有其他角色各需打出一张【杀】，否则受到1点伤害
- 【万箭齐发】：所有其他角色各需打出一张【闪】，否则受到1点伤害
- 【五谷丰登】：亮出等同于角色数量的牌，从当前回合角色开始依次获得
- 【桃园结义】：所有角色回复1点体力
- 【借刀杀人】：指定一名角色(A)对另一名角色(B)使用【杀】，需要填target_idx=A，extra={{secondary_target: B}}，否则无效

### 装备牌
- 武器：增加攻击范围，部分武器有特殊效果
  - 诸葛连弩(范围1)：锁定技，使用【杀】无次数限制
  - 青釭剑(范围2)：锁定技，使用【杀】时无视目标防具（仁王盾/八卦阵）
  - 丈八蛇矛(范围3)：可将两张手牌当【杀】使用
  - 贯石斧(范围3)：使用【杀】被【闪】抵消后，可弃两张牌强制命中
  - 青龙偃月刀(范围3)：使用【杀】被【闪】抵消后，可对同一目标再使用一张【杀】
  - 寒冰剑(范围2)：使用【杀】造成伤害时，可弃两张牌改为弃置目标两张牌
  - 麒麟弓(范围5)：使用【杀】造成伤害后，可弃置目标的一匹马
  - 雌雄双股剑(范围2)：对异性角色使用【杀】时，目标需弃一张牌或让你摸一张牌
- 防具：
  - 八卦阵：需要使用或打出【闪】时，可判定：若为红色视为打出【闪】
  - 仁王盾：锁定技，黑色【杀】对你无效
- +1马（的卢/绝影/爪黄飞电）：别人计算与你距离+1
- -1马（赤兔/大宛/紫骍）：你计算与别人距离-1

### 延时锦囊
- 【乐不思蜀】：判定阶段判定，若不为♥，跳过出牌阶段。使用乐不思蜀没有距离限制
- 【闪电】：判定阶段判定，若为♠2-9，受到3点雷电伤害，否则移至下家。闪电只能先挂在自己身上

### 距离计算
基础距离 = 座位间隔（顺时针或逆时针取最小值）
实际距离 = 基础距离 + 目标+1马 - 你的-1马 - 技能修正
你需要武器攻击范围 ≥ 实际距离才能使用【杀】

### 关键策略
- 反贼：最终目标是击杀主公，但不必每回合只盯着主公。可以优先集火忠臣/内奸（削减主公帮手），或集火低血量角色。注意辨别队友避免内讧。
- 忠臣：保护主公，主动吸引火力，帮主公挡刀
- 内奸：两边平衡，削弱双方，确保主公最后死
- 注意通过出牌行为推断其他人的身份
- 主公不要轻易杀忠臣（误杀忠臣会弃光所有牌）
- **装备牌能装就装**：装备可以持续生效，弃掉浪费。弃牌阶段优先弃基本牌（杀/闪），保留装备和桃。
"""

SYSTEM_PROMPT = """你是三国杀AI玩家。你必须严格按照JSON格式输出决策。

{game_rules}

{hero_info}

你的身份是：{role}
你的胜利条件：{win_condition}

## 重要原则
1. 严格遵守你的身份目标，不要暴露自己的真实身份（主公除外）
2. 通过分析其他玩家的行为推断他们的身份
3. 根据推理结果选择最优目标和策略
4. 你的身份绝不能直接告诉其他玩家
"""

TURN_PROMPT = """## 当前局面

第{round_number}轮，你是第{player_idx}号位。当前是你的{phase}。

### 你的状态
- 武将：{hero_name}（{kingdom}）
- 体力：{hp}/{max_hp}
- 手牌（{hand_count}张）：{hand_cards}
- 装备：{equipment}
- 技能：{skills}
{sha_limit_info}

### 场上公开信息
{public_info}

### 近期事件
{recent_events}

### 你的分析

请按以下步骤分析并决策：

1. **身份推理**：根据各玩家的行为，推断他们可能的身份
2. **当前局势**：谁占优势？你方处于什么状态？
3. **出牌策略**：本回合你应该做什么？

输出严格的JSON格式：
```json
{{
  "reasoning": "你的分析过程（简洁）",
  "suspicion": {{
    "玩家名": {{"主公": 0.0, "忠臣": 0.0, "反贼": 0.0, "内奸": 0.0}}
  }},
  "action": {{
    "type": "play_card|use_skill|pass|discard",
    "card_name": "卡牌名称（play_card时必填）",
    "target_idx": 目标玩家索引（需要目标时必填，填数字0-7）,
    "skill_name": "技能名称（use_skill时必填）",
    "cards_used": ["要弃置的牌名"],
    "extra": {{}}
  }}
}}
```

{discard_hint}

请输出你的决策JSON："""

DISCARD_PROMPT = """## 弃牌阶段

你的手牌数（{hand_count}）超过体力值（{hp}），需要弃置{discard_count}张牌。

### 你的手牌
{hand_cards}

### 近期事件
{recent_events}

### 弃牌优先级
- 优先弃置多余的【杀】（保留1张即可，除非有诸葛连弩/咆哮）
- 其次弃置低价值锦囊（如借刀杀人、五谷丰登等时机不好的牌）
- **不要弃装备牌！** 装备可以装到装备栏持续生效，比弃掉划算得多
- 尽量保留【桃】和【无懈可击】
- 保留【闪】用于防御

请选择要弃置的牌，输出JSON：
```json
{{
  "reasoning": "弃牌理由",
  "action": {{
    "type": "discard",
    "cards_used": ["牌名1", "牌名2"],
    "player_idx": {player_idx}
  }}
}}
```"""


def _format_recent_events(view: dict) -> str:
    """Format recent game events for prompts."""
    events = view.get("recent_events", [])
    if not events:
        return "（游戏开始）"
    return "\n".join(f"  - {e}" for e in events)


def _format_public_info(view: dict) -> str:
    """Format all players' public info for prompts with distance/range info."""
    n = len(view["players"])
    my_idx = view["player_idx"]
    my_equip = set(view.get("my_equipment", []))
    my_skills = view.get("my_skills", [])

    def _has_skill(sk):
        return sk in my_skills

    lines = []
    for i, p in enumerate(view["players"]):
        if not p["alive"]:
            lines.append(f"  [{i}] {p['name']}({p['kingdom']}) - 已死亡（身份：{p.get('role', '???')}）")
        else:
            marker = " ← 你" if i == my_idx else ""
            eq = f" 装备:{','.join(p['equipment'])}" if p.get('equipment') else ""
            hc = p.get('hand_count', 0) or 0
            dc = p.get('delay_cards', [])
            ds = f" 判定区:{','.join(dc)}" if dc else ""
            sk = p.get('skills', [])
            sk_str = f" 技能:{','.join(sk)}" if sk else ""

            if i != my_idx:
                # Distance calculation (skip dead players)
                cw, j = 0, (my_idx + 1) % n
                while j != i:
                    if view["players"][j]["alive"]: cw += 1
                    j = (j + 1) % n
                ccw, j = 0, (my_idx - 1 + n) % n
                while j != i:
                    if view["players"][j]["alive"]: ccw += 1
                    j = (j - 1 + n) % n
                base = min(cw, ccw) + 1
                dist = base
                # Target +1 horse
                target_eq = set(p.get('equipment', []))
                if target_eq & {"的卢", "绝影", "爪黄飞电"}:
                    dist += 1
                # My -1 horse
                if my_equip & {"赤兔", "大宛", "紫骍"}:
                    dist -= 1
                # 马术
                if _has_skill("马术"):
                    dist -= 1
                dist = max(1, dist)

                # Attack range
                weapon_range = 1
                for eq_name in my_equip:
                    if eq_name == "诸葛连弩": weapon_range = max(weapon_range, 1)
                    elif eq_name == "青釭剑": weapon_range = max(weapon_range, 2)
                    elif eq_name == "丈八蛇矛": weapon_range = max(weapon_range, 3)
                    elif eq_name == "贯石斧": weapon_range = max(weapon_range, 3)
                    elif eq_name == "青龙偃月刀": weapon_range = max(weapon_range, 3)
                    elif eq_name == "寒冰剑": weapon_range = max(weapon_range, 2)
                    elif eq_name == "雌雄双股剑": weapon_range = max(weapon_range, 2)
                    elif eq_name == "麒麟弓": weapon_range = max(weapon_range, 5)

                can_snatch = "可顺手牵羊" if dist <= 1 else f"不可顺手牵羊(距{dist}>1)"
                can_sha = f"可杀(范围{weapon_range})" if dist <= weapon_range else f"不可杀(距{dist}>范围{weapon_range})"
                dist_info = f" 距{dist} {can_sha} {can_snatch}"
            else:
                dist_info = ""

            lines.append(f"  [{i}] {p['name']}({p['kingdom']}) HP:{p['hp']}/{p['max_hp']} 手牌:{hc}张 身份:{p.get('role','未知')}{eq}{ds}{sk_str}{dist_info}{marker}")
    lines.append("  ※ 距离为实时值，会随装备变化。若当前不可杀/不可顺，可先装武器/-1马缩短距离，或拆掉目标的+1马减少距离，之后再出牌。")
    return "\n".join(lines)
    return "\n".join(lines)


def build_system_prompt(hero_name: str, kingdom: str, skills: list[str],
                        skill_descriptions: list[str], role: str,
                        is_lord: bool = False, lord_skill: str = "") -> str:
    """Build the system prompt for a specific hero/role combination."""

    hero_info = f"你的武将是：{hero_name}（{kingdom}势力）\n"
    hero_info += "技能：\n"
    for name, desc in zip(skills, skill_descriptions):
        hero_info += f"  - 【{name}】：{desc}\n"
    if lord_skill:
        hero_info += f"  - 【{lord_skill}】（主公技）\n"

    win_conditions = {
        "主公": "消灭所有反贼和内奸，保护忠臣",
        "忠臣": "保护主公，消灭所有反贼和内奸",
        "反贼": "击杀主公！反贼人数最多，集火主公是最快获胜方式",
        "内奸": "消灭除主公外的所有角色，最后亲手击杀主公。需要先削弱双方实力，保持平衡",
    }

    return SYSTEM_PROMPT.format(
        game_rules=GAME_RULES,
        hero_info=hero_info,
        role=role,
        win_condition=win_conditions.get(role, ""),
    )


def _build_skill_hints(view: dict) -> str:
    """Build actionable hints for skills the player can use this turn."""
    skills = view.get("my_skills", [])
    hand = view.get("my_hand", [])
    phase = view.get("phase", "")
    used = set(view.get("skills_used_this_turn", []))
    hints = []

    # Show used once-per-turn skills
    if used:
        hints.append(f"### 本回合已使用过的技能: {', '.join(used)}")

    # Skip phase-specific skills (handled automatically, not play-phase choices)
    phase_skills = {"洛神", "闭月", "英姿", "克己", "马术", "倾国", "龙胆", "武圣",
                    "急救", "谦逊", "空城", "连营", "枭姬", "无双", "铁骑", "烈弓",
                    "反馈", "刚烈", "奸雄", "遗计", "天妒", "鬼才", "裸衣", "突袭"}

    for skill in skills:
        if skill in phase_skills:
            continue  # Auto-triggered or passive, don't show in play hints
        if skill == "奇袭":
            black_cards = [f"{c['name']}({c['suit']})" for c in hand if c["suit"] in ("♠", "♣")]
            if black_cards:
                hints.append(f"【奇袭】可将黑色牌当过河拆桥使用(extra.dismantle_zone指定区域): {', '.join(black_cards)}")
        elif skill == "武圣":
            red_cards = [f"{c['name']}({c['suit']})" for c in hand if c["suit"] in ("♥", "♦")]
            if red_cards:
                hints.append(f"【武圣】可将红色牌当杀使用: {', '.join(red_cards)}")
        if skill == "龙胆":
            sha_cards = [f"{c['name']}({c['suit']})" for c in hand if c["name"] == "闪"]
            if sha_cards:
                hints.append(f"【龙胆】可将闪当杀使用: {', '.join(sha_cards)}")
        elif skill == "国色":
            dia_cards = [f"{c['name']}({c['suit']})" for c in hand if c["suit"] == "♦"]
            if dia_cards:
                hints.append(f"【国色】可将♦牌当乐不思蜀使用: {', '.join(dia_cards)}")
        elif skill == "结姻":
            if len(hand) >= 2:
                hints.append("【结姻】出牌阶段限一次，弃2张手牌，与一名受伤男性角色各回复1点体力")
        elif skill == "反间":
            if hand:
                hints.append(f"【反间】出牌阶段限一次，给目标一张手牌，目标猜花色，猜错受1伤")
        elif skill == "制衡":
            if hand:
                hints.append(f"【制衡】出牌阶段限一次，弃任意张牌并摸等量牌")
        elif skill == "苦肉":
            if hand:
                hints.append(f"【苦肉】出牌阶段可多次使用，弃1张牌+失1体力，摸2张牌")
        elif skill == "青囊":
            if hand:
                hints.append(f"【青囊】出牌阶段限一次，弃1张手牌令一名角色回复1点体力")
        elif skill == "离间":
            if hand:
                hints.append(f"【离间】出牌阶段限一次，弃1张牌(可弃装备)令两名男性角色决斗")
        elif skill == "仁德":
            if hand:
                hints.append(f"【仁德】出牌阶段可将任意张手牌交给其他角色，给出>=2张回复1体力")
        elif skill == "裸衣":
            hints.append("【裸衣】摸牌阶段少摸1张，本回合杀/决斗伤害+1")
        elif skill == "突袭":
            hints.append("【突袭】摸牌阶段可放弃摸牌改为获得1-2名其他角色各一张手牌")
        elif skill == "咆哮":
            hints.append("【咆哮】锁定技，出杀无次数限制")
        elif skill == "克己":
            hints.append("【克己】未使用过杀可跳过弃牌阶段")
        elif skill == "铁骑":
            hints.append("【铁骑】使用杀时可判定，红色则不可闪")
        elif skill == "无双":
            hints.append("【无双】你使用的杀需2张闪抵消，决斗时对方需连续出2张杀")

    # Add general play tips
    tips = ["### 出牌提示"]
    equip_cards = [f"{c['name']}({c['suit']})" for c in hand if c.get("type") == "装备"]
    if equip_cards:
        current_equip = view.get("my_equipment", [])
        for ec in [c for c in hand if c.get("type") == "装备"]:
            cn = ec["name"]
            if cn in current_equip:
                tips.append(f"手中{ec['name']}({ec['suit']})与装备栏重复，无需替换")
            elif cn in ("诸葛连弩", "麒麟弓", "丈八蛇矛", "贯石斧", "青龙偃月刀", "寒冰剑", "雌雄双股剑", "青釭剑"):
                has_weapon = any(w in current_equip for w in ("诸葛连弩","麒麟弓","丈八蛇矛","贯石斧","青龙偃月刀","寒冰剑","雌雄双股剑","青釭剑"))
                if has_weapon:
                    cur_weps = [w for w in current_equip if w in ("诸葛连弩","麒麟弓","丈八蛇矛","贯石斧","青龙偃月刀","寒冰剑","雌雄双股剑","青釭剑")]
                    cur_info = "、".join(cur_weps) if cur_weps else "无"
                    tips.append(f"手中{ec['name']}({ec['suit']})，当前武器: {cur_info}。自行决定是否更换：远程用长范围，爆发用连弩，破防用青釭剑")
                else:
                    tips.append(f"手中{ec['name']}({ec['suit']})可用，建议装备")
            elif cn in ("八卦阵", "仁王盾"):
                has_armor = any(a in current_equip for a in ("八卦阵","仁王盾"))
                if has_armor:
                    tips.append(f"手中{ec['name']}({ec['suit']})可替换现有防具")
                else:
                    tips.append(f"手中{ec['name']}({ec['suit']})可用，建议装备")
            elif cn in ("的卢","绝影","爪黄飞电","赤兔","大宛","紫骍"):
                tips.append(f"手中{ec['name']}({ec['suit']})可用，建议装备")
    tips.append("反贼可集火忠臣/内奸削减主公帮手，不必死盯主公")
    if hints:
        tips.append(hints[0] if hints[0].startswith("###") else "")
        tips.extend(hints)
    return "\n".join(tips)


def build_turn_prompt(view: dict) -> str:
    """Build the turn decision prompt from player view."""
    # Format hand cards
    hand_cards = ", ".join(
        f"{c['name']}({c['suit']})" for c in view["my_hand"]
    ) if view["my_hand"] else "无"

    # Format equipment
    equipment = ", ".join(view["my_equipment"]) if view["my_equipment"] else "无"

    # Format skills
    skills = ", ".join(view["my_skills"])

    # Format public info
    public_info = _format_public_info(view)

    # Format recent events
    recent = "\n".join(f"  - {e}" for e in view["recent_events"]) if view["recent_events"] else "（游戏开始）"

    phase_name = view["phase"]
    if phase_name == "出牌阶段":
        phase_desc = "出牌阶段（你可以使用任意张牌）"
    elif phase_name == "准备阶段":
        phase_desc = "准备阶段（可以发动技能如洛神）"
    else:
        phase_desc = phase_name

    # Build skill usage hints
    skill_hints = _build_skill_hints(view)

    # 杀 limit info
    sha_used = view.get("sha_used", 0)
    sha_limit = view.get("sha_limit", 1)
    has_zhugeliannu = "诸葛连弩" in view.get("my_equipment", [])
    has_paoxiao = "咆哮" in view.get("my_skills", [])
    if has_paoxiao or (has_zhugeliannu and sha_limit == 999):
        sha_info = f"- 杀限制：已出{sha_used}张 (无限制 - {'咆哮' if has_paoxiao else '诸葛连弩'})"
    elif sha_used >= sha_limit:
        sha_info = f"- ⚠️ 杀限制：本回合已使用{sha_used}/{sha_limit}张杀，不能再出杀！"
    else:
        sha_info = f"- 杀限制：本回合已使用{sha_used}/{sha_limit}张杀"

    prompt = TURN_PROMPT.format(
        round_number=view["round_number"],
        player_idx=view["player_idx"],
        sha_limit_info=sha_info,
        phase=phase_desc,
        hero_name=view["my_hero"],
        kingdom=view["my_kingdom"],
        hp=view["my_hp"],
        max_hp=view["my_max_hp"],
        hand_count=len(view["my_hand"]),
        hand_cards=hand_cards,
        equipment=equipment,
        skills=skills,
        public_info=public_info,
        recent_events=recent,
        discard_hint=skill_hints,
    )

    return prompt


RESPOND_PROMPT = """## 响应请求

{response_description}

### 你的状态
- 武将：{hero_name}（{kingdom}）
- 体力：{hp}/{max_hp}
- 手牌（{hand_count}张）：{hand_cards}
- 装备：{equipment}
- 技能：{skills}
- 你的身份：{my_role}

### 场上信息
{public_info}

### 近期事件
{recent_events}

{special_hint}

### 身份推理
请先根据场上事件和玩家行为，推断各角色可能的身份，然后决定是否响应。

请输出JSON：
```json
{{
  "reasoning": "身份推理+决策理由",
  "suspicion": {{"玩家名": {{"主公": 0.0, "忠臣": 0.0, "反贼": 0.0, "内奸": 0.0}}}},
  "action": {{
    "type": "respond",
    "card_name": "用来响应的牌名",
    "skill_name": "使用的技能名（八卦阵/倾国/龙胆等，不用技能则不填）"
  }}
}}
```
如果不响应：
```json
{{
  "reasoning": "身份推理+不响应理由",
  "suspicion": {{"玩家名": {{"主公": 0.0, "忠臣": 0.0, "反贼": 0.0, "内奸": 0.0}}}},
  "action": {{"type": "pass"}}
}}
```"""

NEGATE_PROMPT = """## 无懈可击响应

{source_name}使用了【{card_name}】{target_info}。

你可以打出【无懈可击】来抵消对{target_name}的此牌效果。

### 你的状态
- 武将：{hero_name}（{kingdom}）
- 体力：{hp}/{max_hp}
- 手牌（{hand_count}张）：{hand_cards}
- 装备：{equipment}
- 技能：{skills}
- 你的身份：{my_role}

### 场上信息
{public_info}

### 近期事件
{recent_events}

### 策略提示
- 如果你是反贼，南蛮/万箭/五谷对主公方有利时应该无懈
- 如果你是忠臣，保护主公免受伤害时应该无懈
- 五谷丰登：无懈可让目标拿不到牌

请决定是否打出【无懈可击】。如果是，输出：
```json
{{
  "reasoning": "使用无懈可击的理由",
  "action": {{
    "type": "respond",
    "card_name": "无懈可击"
  }}
}}
```
如果不使用，输出：
```json
{{
  "reasoning": "不使用无懈可击的理由",
  "action": {{
    "type": "pass"
  }}
}}
```"""


def build_response_prompt(view: dict, response_type: str, source_card: str,
                          source_idx: int, target_idx: int | None = None,
                          bagua_failed: bool = False, no_bagua: bool = False) -> str:
    """Build prompt for response decisions (杀→闪, 南蛮→杀, 万箭→闪)."""
    hero_name = view["my_hero"]
    source_name = view["players"][source_idx]["name"]

    if response_type == "闪" and source_card == "杀":
        desc = f"{source_name}对你使用了【杀】！你需要打出一张【闪】来响应。"
    elif response_type == "杀" and source_card == "南蛮入侵":
        desc = f"{source_name}使用了【南蛮入侵】！所有角色需打出一张【杀】，否则受到1点伤害。"
    elif response_type == "闪" and source_card == "万箭齐发":
        desc = f"{source_name}使用了【万箭齐发】！所有角色需打出一张【闪】，否则受到1点伤害。"
    elif response_type == "杀" and source_card == "决斗":
        desc = f"决斗中！你需要打出一张【杀】，否则受到1点伤害。"
    else:
        desc = f"{source_name}使用了【{source_card}】，你需要打出【{response_type}】来响应。"

    hand_cards = ", ".join(
        f"{c['name']}({c['suit']})" for c in view["my_hand"]
    ) if view["my_hand"] else "无"

    equipment = ", ".join(view["my_equipment"]) if view["my_equipment"] else "无"
    skills = ", ".join(view["my_skills"])

    public_info = _format_public_info(view)

    # Build special hints based on skills
    skills_lower = " ".join(view["my_skills"]).lower()
    hints = []
    if response_type == "闪" and view.get("my_role") == "主公":
        lord_skills = view.get("my_skills", [])
        if "护驾" in str(lord_skills):
            hints.append("- 【护驾】(主公技)：设置skill_name=\"护驾\"，让其他魏势力角色替你打出【闪】")
    if response_type == "杀" and view.get("my_role") == "主公":
        lord_skills = view.get("my_skills", [])
        if "激将" in str(lord_skills):
            hints.append("- 【激将】(主公技)：设置skill_name=\"激将\"，让其他蜀势力角色替你打出【杀】")

    if response_type == "闪":
        if "倾国" in skills_lower:
            hints.append("- 你可以使用【倾国】将一张黑色手牌当【闪】使用")
        if "龙胆" in skills_lower:
            hints.append("- 你可以使用【龙胆】将【杀】当【闪】使用")
        if "八卦阵" in equipment and not no_bagua:
            hints.append("- 【八卦阵】：优先尝试！设置skill_name=\"八卦阵\" card_name=\"\"。判定红色=闪避，黑色=可再用手牌出闪")
    elif response_type == "杀":
        if "武圣" in skills_lower:
            hints.append("- 你可以使用【武圣】将一张红色手牌当【杀】使用")
        if "龙胆" in skills_lower:
            hints.append("- 你可以使用【龙胆】将【闪】当【杀】使用")

    special_hint = "\n".join(hints) if hints else ""
    bagua_failed_hint = ""
    if bagua_failed:
        bagua_failed_hint = "\n⚠️ 【八卦阵】判定失败！你现在可以使用手牌中的【闪】来响应。"

    return RESPOND_PROMPT.format(
        response_description=desc,
        bagua_failed_hint=bagua_failed_hint,
        my_role=view.get("my_role", "未知"),
        hero_name=hero_name,
        kingdom=view["my_kingdom"],
        hp=view["my_hp"],
        max_hp=view["my_max_hp"],
        hand_count=len(view["my_hand"]),
        hand_cards=hand_cards,
        equipment=equipment,
        skills=skills,
        public_info=public_info,
            recent_events=_format_recent_events(view),
        special_hint=special_hint,
    )


def build_negate_prompt(view: dict, source_idx: int, card_name: str,
                         target_idx: int | None = None) -> str:
    """Build prompt for 无懈可击 decision."""
    source_name = view["players"][source_idx]["name"]
    if target_idx is not None and target_idx != source_idx:
        target_name = view["players"][target_idx]["name"]
        target_info = f"，目标为{target_name}"
    elif target_idx is not None:
        target_name = view["players"][target_idx]["name"]
        target_info = "（目标为自己）"
    else:
        target_name = "所有角色"
        target_info = ""

    hand_cards = ", ".join(
        f"{c['name']}({c['suit']})" for c in view["my_hand"]
    ) if view["my_hand"] else "无"

    equipment = ", ".join(view["my_equipment"]) if view["my_equipment"] else "无"
    skills = ", ".join(view["my_skills"])

    public_info = _format_public_info(view)

    return NEGATE_PROMPT.format(
        source_name=source_name,
        card_name=card_name,
        target_name=target_name if target_idx is not None else "所有角色",
        target_info=target_info,
        my_role=view.get("my_role", "未知"),
        hero_name=view["my_hero"],
        kingdom=view["my_kingdom"],
        hp=view["my_hp"],
        max_hp=view["my_max_hp"],
        hand_count=len(view["my_hand"]),
        hand_cards=hand_cards,
        equipment=equipment,
        skills=skills,
        public_info=public_info,
        recent_events=_format_recent_events(view),
    )


DYING_PROMPT = """## 濒死求桃

{dying_name}（{dying_kingdom}势力，身份{dying_role_hint}）濒死！当前体力{dying_hp}，需要{needed}个【桃】才能救活。

你是第{responder_idx}号位。你可以打出一张【桃】来救{dying_name}。

### 你的状态
- 武将：{hero_name}（{kingdom}）
- 体力：{hp}/{max_hp}
- 手牌（{hand_count}张）：{hand_cards}
- 装备：{equipment}
- 技能：{skills}
- 你的身份：{my_role}

### 场上信息
{public_info}

### 近期事件
{recent_events}

### 策略提示
- 如果{dying_name}是你的队友，应该救他
- 如果是敌人，可以袖手旁观
- 如果你自己濒死，请务必自救！
{special_hint}

请决定是否救援。如果使用【桃】或【急救】，输出：
```json
{{
  "reasoning": "救援理由（基于身份判断）",
  "action": {{
    "type": "respond",
    "card_name": "桃",
    "skill_name": ""
  }}
}}
```
如果有【急救】技能，可以用红色牌当桃：card_name填红色牌名，skill_name填"急救"。
如果不救援，输出：{{"reasoning": "...", "action": {{"type": "pass"}}}}
```"""


def build_dying_prompt(view: dict, dying_idx: int, needed: int) -> str:
    """Build prompt for near-death rescue decision."""
    dying_player = view["players"][dying_idx]
    dying_name = dying_player["name"]
    dying_kingdom = dying_player["kingdom"]
    dying_hp = dying_player["hp"]
    dying_role = dying_player.get("role", "未知")

    # Role hint for display
    if dying_idx == view["lord_idx"]:
        dying_role_hint = "主公"
    elif dying_idx == view["player_idx"]:
        dying_role_hint = "你"
    else:
        dying_role_hint = dying_role

    hand_cards = ", ".join(
        f"{c['name']}({c['suit']})" for c in view["my_hand"]
    ) if view["my_hand"] else "无"

    equipment = ", ".join(view["my_equipment"]) if view["my_equipment"] else "无"
    skills = ", ".join(view["my_skills"])

    public_info = _format_public_info(view)

    # Special hints
    hints = []
    if "急救" in view["my_skills"]:
        hints.append("- 【急救】可以将红色牌(手牌或装备)当【桃】使用")
    special_hint = "\n".join(hints) if hints else ""

    return DYING_PROMPT.format(
        dying_name=dying_name,
        dying_kingdom=dying_kingdom,
        dying_hp=dying_hp,
        dying_role_hint=dying_role_hint,
        needed=needed,
        responder_idx=view["player_idx"],
        hero_name=view["my_hero"],
        kingdom=view["my_kingdom"],
        hp=view["my_hp"],
        max_hp=view["my_max_hp"],
        hand_count=len(view["my_hand"]),
        hand_cards=hand_cards,
        equipment=equipment,
        skills=skills,
        my_role=view.get("my_role", "未知"),
        public_info=public_info,
            recent_events=_format_recent_events(view),
        special_hint=special_hint,
    )


def build_discard_prompt(view: dict, discard_count: int) -> str:
    """Build the discard phase prompt."""
    hand_cards = ", ".join(
        f"{c['name']}({c['suit']})" for c in view["my_hand"]
    )

    return DISCARD_PROMPT.format(
        hand_count=len(view["my_hand"]),
        hp=view["my_hp"],
        discard_count=discard_count,
        hand_cards=hand_cards,
        player_idx=view["player_idx"],
        recent_events=_format_recent_events(view),
    )


HERO_SELECT_PROMPT = """## 选将阶段

你的身份是：{role}

请从以下武将中选择一个：

{hero_options}

请输出JSON选择：
```json
{{
  "reasoning": "选择理由（基于身份和策略）",
  "choice": 选择的武将索引（0-{max_idx}）
}}
```"""


def build_hero_select_prompt(role: str, options: list[dict]) -> str:
    """Build hero selection prompt."""
    lines = []
    for i, opt in enumerate(options):
        skills_str = ", ".join(f"{s['name']}: {s['description']}" for s in opt["skills"])
        lord_tag = " [主公]" if opt.get("is_lord") else ""
        lines.append(
            f"  [{i}] {opt['name']} ({opt['kingdom']}){lord_tag} HP:{opt['hp']}\n"
            f"      技能: {skills_str}"
        )
    hero_list = "\n".join(lines)

    return HERO_SELECT_PROMPT.format(
        role=role,
        hero_options=hero_list,
        max_idx=len(options) - 1,
    )


GUICAI_PROMPT = """## 鬼才判定替换

当前判定为【{context}】。判定牌是：{judgment_card} ({judgment_suit})。

你可以使用【鬼才】打出一张手牌替换此判定牌。

### 你的状态
- 武将：{hero_name}（{kingdom}）
- 体力：{hp}/{max_hp}
- 手牌（{hand_count}张）：{hand_cards}
- 装备：{equipment}

### 场上信息
{public_info}

### 近期事件
{recent_events}

### 策略提示
- 如果此判定对你或队友有利(如八卦阵判定红色、乐不思蜀判定非红桃)，可以考虑不替换
- 如果此判定对你不利(如刚烈判定非红桃、闪电判定黑桃2-9)，替换为有利花色
- 替换闪电判定时，如果想要闪电炸目标，换成♠2-9；如果不想炸，换成非♠或非2-9的牌

请输出JSON决定：
```json
{{
  "reasoning": "替换判定的理由",
  "action": {{
    "type": "respond",
    "card_name": "要替换的牌名（从手牌中选择一张）"
  }}
}}
```

如果不替换，输出：
```json
{{
  "reasoning": "不替换判定的理由",
  "action": {{
    "type": "pass"
  }}
}}
```"""


FANJIAN_GUESS_PROMPT = """## 反间猜花色

{source_name}对你发动了【反间】，给了你一张手牌【{card_name}】！

你需要猜测这张牌的花色（♠ ♥ ♣ ♦）。

### 你的状态
- 武将：{hero_name}（{kingdom}）
- 体力：{hp}/{max_hp}
- 手牌（{hand_count}张）：{hand_cards}
- 装备：{equipment}

### 场上信息
{public_info}

### 近期事件
{recent_events}

### 策略提示
- 如果猜错花色，你将受到1点伤害
- 可以考虑{source_name}的身份和手牌情况来推断可能给的花色
- 如果不确定，可以随便选一个

请输出JSON选择花色：
```json
{{
  "reasoning": "猜测花色的理由",
  "guessed_suit": "♠|♥|♣|♦"
}}
```"""


def build_fanjian_guess_prompt(view: dict, source_idx: int, card_name: str) -> str:
    """Build prompt for 反间 suit guess."""
    source_name = view["players"][source_idx]["name"]
    hand_cards = ", ".join(
        f"{c['name']}({c['suit']})" for c in view["my_hand"]
    ) if view["my_hand"] else "无"

    equipment = ", ".join(view["my_equipment"]) if view["my_equipment"] else "无"

    public_info = _format_public_info(view)

    return FANJIAN_GUESS_PROMPT.format(
        source_name=source_name,
        card_name=card_name,
        hero_name=view["my_hero"],
        kingdom=view["my_kingdom"],
        hp=view["my_hp"],
        max_hp=view["my_max_hp"],
        hand_count=len(view["my_hand"]),
        hand_cards=hand_cards,
        equipment=equipment,
        public_info=public_info,
            recent_events=_format_recent_events(view),
    )


GANGLIE_CHOICE_PROMPT = """## 刚烈抉择

{ganglie_source}对你发动了【刚烈】！判定结果不为♥。

你需要选择：
- **受到1点伤害**：直接扣减1点体力
- **弃置2张手牌**：弃置2张手牌（如果手牌不足2张则必须选择受伤）

### 你的状态
- 武将：{hero_name}（{kingdom}）
- 体力：{hp}/{max_hp}
- 手牌（{hand_count}张）：{hand_cards}
- 装备：{equipment}

### 场上信息
{public_info}

### 近期事件
{recent_events}

### 策略提示
- 如果体力值低但有较多手牌，优先选择弃牌
- 如果手牌少但体力值充足，可以选择受伤
- 如果手牌不足2张，只能选择受伤

请输出JSON决定：
```json
{{
  "reasoning": "选择的理由",
  "ganglie_choice": "damage|discard",
  "cards_used": ["弃置的牌名1", "弃置的牌名2"]
}}
```"""


WUGU_PICK_PROMPT = """## 五谷丰登选牌

【五谷丰登】亮出了以下牌，轮到你选择一张：

{revealed_cards}

### 你的状态
- 武将：{hero_name}（{kingdom}）
- 体力：{hp}/{max_hp}
- 手牌（{hand_count}张）：{hand_cards}
- 装备：{equipment}

请选择一张最有用的牌，输出JSON：
```json
{{
  "reasoning": "选牌理由",
  "action": {{
    "type": "respond",
    "card_name": "牌名"
  }}
}}
```"""


GANGLIE_CHOICE_PROMPT = """## 刚烈抉择

{ganglie_source}对你发动了【刚烈】！判定结果不为♥。

你需要选择：
- **受到1点伤害**：直接扣减1点体力
- **弃置2张手牌**：弃置2张手牌（如果手牌不足2张则必须选择受伤）

### 你的状态
- 武将：{hero_name}（{kingdom}）
- 体力：{hp}/{max_hp}
- 手牌（{hand_count}张）：{hand_cards}
- 装备：{equipment}

### 场上信息
{public_info}

### 近期事件
{recent_events}

请输出JSON决定：
```json
{{
  "reasoning": "选择的理由",
  "ganglie_choice": "damage|discard",
  "cards_used": ["弃置的牌名1", "弃置的牌名2"]
}}
```"""


def build_ganglie_choice_prompt(view: dict, source_idx: int) -> str:
    """Build prompt for 刚烈 choice."""
    source_name = view["players"][source_idx]["name"]
    hand_cards = ", ".join(
        f"{c['name']}({c['suit']})" for c in view["my_hand"]
    ) if view["my_hand"] else "无"

    equipment = ", ".join(view["my_equipment"]) if view["my_equipment"] else "无"

    public_info = _format_public_info(view)

    return GANGLIE_CHOICE_PROMPT.format(
        ganglie_source=source_name,
        hero_name=view["my_hero"],
        kingdom=view["my_kingdom"],
        hp=view["my_hp"],
        max_hp=view["my_max_hp"],
        hand_count=len(view["my_hand"]),
        hand_cards=hand_cards,
        equipment=equipment,
        public_info=public_info,
            recent_events=_format_recent_events(view),
    )


DRAW_PHASE_PROMPT = """## 摸牌阶段决策

当前是你的摸牌阶段。你可以选择：
{skill_options}

### 你的状态
- 武将：{hero_name}（{kingdom}）
- 体力：{hp}/{max_hp}
- 手牌（{hand_count}张）：{hand_cards}
- 装备：{equipment}

### 场上其他角色
{target_info}

### 策略提示
- 突袭可针对1或2名角色，各获得其一张手牌
- 优先选择可能有【桃】【无懈可击】等关键牌的角色
- 反贼优先偷主公/忠臣，忠臣优先偷反贼
- 如果正常摸牌更有利，选择 PASS

请输出JSON：
```json
{{
  "reasoning": "决策理由",
  "draw_choice": "normal|tuxi|nuoyi",
  "targets": [目标玩家索引1, 目标玩家索引2]
}}
```
{draw_choice_hint}"""


WUGU_PICK_PROMPT = """## 五谷丰登选牌
【五谷丰登】亮出了以下牌，轮到你选择一张：
{revealed_cards}

### 你的状态
- 武将：{hero_name}（{kingdom}）
- 体力：{hp}/{max_hp}
- 手牌（{hand_count}张）：{hand_cards}
- 装备：{equipment}

请选一张最有用的牌，输出JSON：
```json
{{
  "reasoning": "选牌理由",
  "action": {{
    "type": "respond",
    "card_name": "牌名"
  }}
}}
```"""


def build_wugu_pick_prompt(view: dict, revealed: list[str]) -> str:
    """Build prompt for 五谷丰登 card selection."""
    hand_cards = ", ".join(
        f"{c['name']}({c['suit']})" for c in view["my_hand"]
    ) if view["my_hand"] else "无"
    equipment = ", ".join(view["my_equipment"]) if view["my_equipment"] else "无"
    revealed_str = "\n".join(f"  [{j}] {c}" for j, c in enumerate(revealed))

    return WUGU_PICK_PROMPT.format(
        revealed_cards=revealed_str,
        hero_name=view["my_hero"],
        kingdom=view["my_kingdom"],
        hp=view["my_hp"],
        max_hp=view["my_max_hp"],
        hand_count=len(view["my_hand"]),
        hand_cards=hand_cards,
        equipment=equipment,
    )


YIJI_DISTRIBUTE_PROMPT = """## 遗计分牌

你发动了【遗计】，摸了两张牌。现在你可以将摸到的牌分配给其他角色（只能分刚摸的牌，不能分原本手牌）。

### 遗计摸到的牌（可分配）
{yiji_cards}

### 你的状态
- 武将：{hero_name}（{kingdom}）
- 体力：{hp}/{max_hp}
- 装备：{equipment}

### 其他角色
{target_info}

### 策略提示
- 只能分配上面"遗计摸到的牌"，不能分原本手牌
- 不分牌则这些牌保留在自己手中
- 根据身份判断谁需要什么牌

请输出JSON（格式：card_name->target_idx）：
```json
{{
  "reasoning": "分牌理由",
  "distribute": ["桃->1", "杀->3"]
}}
```
如果不分牌：
```json
{{
  "reasoning": "不分牌理由",
  "distribute": []
}}
```"""


JIEDAO_PROMPT = """## 借刀杀人

{source_name}对你使用了【借刀杀人】！你必须对{secondary_name}使用一张【杀】，否则你的武器会被{source_name}拿走。

### 你的状态
- 武将：{hero_name}（{kingdom}）
- 体力：{hp}/{max_hp}
- 手牌（{hand_count}张）：{hand_cards}
- 装备：{equipment}

### 场上信息
{public_info}

### 近期事件
{recent_events}

### 策略提示
- 如果你有【杀】且想保留武器，选择出【杀】
- 如果你没有【杀】或不想对{secondary_name}出杀，选择不给（武器会被拿走）

请输出JSON：
```json
{{
  "reasoning": "决策理由",
  "use_sha": true
}}
```
如果不出杀：
```json
{{
  "reasoning": "决策理由",
  "use_sha": false
}}
```"""


def build_yiji_distribute_prompt(view: dict, drawn: list[str] = None) -> str:
    """Build prompt for 遗计 card distribution."""
    if drawn is None:
        drawn = []
    yiji_cards = ", ".join(drawn) if drawn else "无"

    hand_cards = ", ".join(
        f"{c['name']}({c['suit']})" for c in view["my_hand"]
    ) if view["my_hand"] else "无"
    equipment = ", ".join(view["my_equipment"]) if view["my_equipment"] else "无"
    target_lines = []
    for i, p in enumerate(view["players"]):
        if i == view["player_idx"] or not p["alive"]: continue
        eq_str = f" 装备:{','.join(p['equipment'])}" if p.get("equipment") else ""
        target_lines.append(f"  [{i}] {p['name']}({p['kingdom']}) HP:{p['hp']}/{p['max_hp']} 身份:{p.get('role','未知')} 手牌数:{p.get('hand_count',0)}{eq_str}")
    target_info = "\n".join(target_lines)
    return YIJI_DISTRIBUTE_PROMPT.format(
        yiji_cards=yiji_cards,
        hero_name=view["my_hero"], kingdom=view["my_kingdom"],
        hp=view["my_hp"], max_hp=view["my_max_hp"],
        hand_count=len(view["my_hand"]), hand_cards=hand_cards,
        equipment=equipment, my_role=view.get("my_role","未知"),
        target_info=target_info,
    )


def build_jiedao_choice_prompt(view: dict, source_idx: int, secondary_idx: int) -> str:
    source_name = view["players"][source_idx]["name"]
    secondary_name = view["players"][secondary_idx]["name"]
    hand_cards = ", ".join(
        f"{c['name']}({c['suit']})" for c in view["my_hand"]
    ) if view["my_hand"] else "无"
    equipment = ", ".join(view["my_equipment"]) if view["my_equipment"] else "无"

    public_info = _format_public_info(view)

    return JIEDAO_PROMPT.format(
        source_name=source_name, secondary_name=secondary_name,
        hero_name=view["my_hero"], kingdom=view["my_kingdom"],
        hp=view["my_hp"], max_hp=view["my_max_hp"],
        hand_count=len(view["my_hand"]), hand_cards=hand_cards,
        equipment=equipment, public_info=public_info,
            recent_events=_format_recent_events(view),
    )
    """Build prompt for 遗计 card distribution."""
    hand_cards = ", ".join(
        f"{c['name']}({c['suit']})" for c in view["my_hand"]
    ) if view["my_hand"] else "无"

    equipment = ", ".join(view["my_equipment"]) if view["my_equipment"] else "无"

    target_lines = []
    for i, p in enumerate(view["players"]):
        if i == view["player_idx"] or not p["alive"]:
            continue
        eq_str = f" 装备:{','.join(p['equipment'])}" if p.get("equipment") else ""
        target_lines.append(
            f"  [{i}] {p['name']}({p['kingdom']}) HP:{p['hp']}/{p['max_hp']} "
            f"身份:{p.get('role', '未知')} 手牌数:{p.get('hand_count', 0)}{eq_str}"
        )
    target_info = "\n".join(target_lines)

    return YIJI_DISTRIBUTE_PROMPT.format(
        hero_name=view["my_hero"],
        kingdom=view["my_kingdom"],
        hp=view["my_hp"],
        max_hp=view["my_max_hp"],
        hand_count=len(view["my_hand"]),
        hand_cards=hand_cards,
        equipment=equipment,
        my_role=view.get("my_role", "未知"),
        target_info=target_info,
    )


GUANXING_PROMPT = """## 观星排列

你发动了【观星】，查看了牌堆顶的牌。请决定哪些放回牌堆顶（先放的在下面），哪些放牌堆底。

亮出的牌：
{guanxing_cards}

### 你的状态
- 武将：{hero_name}（{kingdom}）
- 体力：{hp}/{max_hp}
- 手牌（{hand_count}张）：{hand_cards}
- 身份：{my_role}

请输出JSON，每张牌标记 top 或 bottom：
```json
{{
  "reasoning": "排列理由",
  "arrange": ["牌名:top", "牌名:bottom", ...]
}}
```"""


DRAW_PHASE_PROMPT = """## 摸牌阶段决策

当前是你的摸牌阶段。你可以选择：
{skill_options}

### 你的状态
- 武将：{hero_name}（{kingdom}）
- 体力：{hp}/{max_hp}
- 手牌（{hand_count}张）：{hand_cards}
- 装备：{equipment}

### 场上其他角色
{target_info}

### 策略提示
- 突袭可针对1或2名角色，各获得其一张手牌
- 优先选择可能有【桃】【无懈可击】等关键牌的角色
- 裸衣增加本回合伤害，适合准备强攻的回合
- 反贼优先偷主公/忠臣，忠臣优先偷反贼

请输出JSON：
```json
{{
  "reasoning": "决策理由",
  "draw_choice": "normal|tuxi|nuoyi",
  "targets": [目标玩家索引1, 目标玩家索引2]
}}
```
{draw_choice_hint}"""


def build_draw_phase_prompt(view: dict) -> str:
    """Build prompt for draw phase (突袭/裸衣 decision)."""
    skills = view.get("my_skills", [])
    options = ["- **正常摸牌**：摸2张牌"]
    choices = ["normal=正常摸牌"]
    if "突袭" in skills:
        options.append("- **发动【突袭】(tuxi)**：放弃摸牌，改为获得1-2名其他角色的各一张手牌")
        choices.append("tuxi=突袭偷牌")
    if "裸衣" in skills:
        options.append("- **发动【裸衣】(nuoyi)**：少摸一张牌（摸1张），本回合使用【杀】或【决斗】伤害+1")
        choices.append("nuoyi=裸衣（少摸1张伤害+1）")
    skill_options = "\n".join(options)
    draw_choice_hint = ", ".join(choices)

    hand_cards = ", ".join(
        f"{c['name']}({c['suit']})" for c in view["my_hand"]
    ) if view["my_hand"] else "无"

    equipment = ", ".join(view["my_equipment"]) if view["my_equipment"] else "无"

    target_lines = []
    for i, p in enumerate(view["players"]):
        if i == view["player_idx"] or not p["alive"]:
            continue
        eq_str = f" 装备:{','.join(p['equipment'])}" if p.get("equipment") else ""
        target_lines.append(
            f"  [{i}] {p['name']}({p['kingdom']}) HP:{p['hp']}/{p['max_hp']} "
            f"身份:{p.get('role', '未知')} 手牌数:{p.get('hand_count', 0)}{eq_str}"
        )
    target_info = "\n".join(target_lines)

    return DRAW_PHASE_PROMPT.format(
        skill_options=skill_options,
        draw_choice_hint=draw_choice_hint,
        hero_name=view["my_hero"],
        kingdom=view["my_kingdom"],
        hp=view["my_hp"],
        max_hp=view["my_max_hp"],
        hand_count=len(view["my_hand"]),
        hand_cards=hand_cards,
        equipment=equipment,
        target_info=target_info,
    )
    hand_cards = ", ".join(
        f"{c['name']}({c['suit']})" for c in view["my_hand"]
    ) if view["my_hand"] else "无"
    cards_str = "\n".join(f"  [{j}] {c}" for j, c in enumerate(cards))
    return GUANXING_PROMPT.format(
        guanxing_cards=cards_str,
        hero_name=view["my_hero"], kingdom=view["my_kingdom"],
        hp=view["my_hp"], max_hp=view["my_max_hp"],
        hand_count=len(view["my_hand"]), hand_cards=hand_cards,
        my_role=view.get("my_role", "未知"),
    )
    return GUANXING_PROMPT.format(
        guanxing_cards=cards_str,
        hero_name=view["my_hero"],
        kingdom=view["my_kingdom"],
        hp=view["my_hp"],
        max_hp=view["my_max_hp"],
        hand_count=len(view["my_hand"]),
        hand_cards=hand_cards,
        my_role=view.get("my_role", "未知"),
    )
    """Build prompt for draw phase (突袭/裸衣 decision)."""
    skills = view.get("my_skills", [])
    options = ["- **正常摸牌**：摸2张牌"]
    choices = ["normal=正常摸牌"]
    if "突袭" in skills:
        options.append("- **发动【突袭】(tuxi)**：放弃摸牌，改为获得1-2名其他角色的各一张手牌")
        choices.append("tuxi=突袭偷牌")
    if "裸衣" in skills:
        options.append("- **发动【裸衣】(nuoyi)**：少摸一张牌（摸1张），本回合使用【杀】或【决斗】伤害+1")
        choices.append("nuoyi=裸衣（少摸1张伤害+1）")
    skill_options = "\n".join(options)
    draw_choice_hint = ", ".join(choices)

    hand_cards = ", ".join(
        f"{c['name']}({c['suit']})" for c in view["my_hand"]
    ) if view["my_hand"] else "无"

    equipment = ", ".join(view["my_equipment"]) if view["my_equipment"] else "无"

    target_lines = []
    for i, p in enumerate(view["players"]):
        if i == view["player_idx"] or not p["alive"]:
            continue
        has_cards = p.get("hand_count", 0) > 0
        eq_str = f" 装备:{','.join(p['equipment'])}" if p.get("equipment") else ""
        target_lines.append(
            f"  [{i}] {p['name']}({p['kingdom']}) HP:{p['hp']}/{p['max_hp']} "
            f"身份:{p.get('role', '未知')} 手牌数:{p.get('hand_count', 0)}{eq_str}"
            f"{' ← 有牌可偷' if has_cards else ' ← 无手牌'}"
        )
    target_info = "\n".join(target_lines)

    return DRAW_PHASE_PROMPT.format(
        hero_name=view["my_hero"],
        kingdom=view["my_kingdom"],
        hp=view["my_hp"],
        max_hp=view["my_max_hp"],
        hand_count=len(view["my_hand"]),
        hand_cards=hand_cards,
        equipment=equipment,
        target_info=target_info,
    )
    """Build prompt for 五谷丰登 card selection."""
    hand_cards = ", ".join(
        f"{c['name']}({c['suit']})" for c in view["my_hand"]
    ) if view["my_hand"] else "无"

    equipment = ", ".join(view["my_equipment"]) if view["my_equipment"] else "无"
    revealed_str = "\n".join(f"  [{j}] {c}" for j, c in enumerate(revealed))

    return WUGU_PICK_PROMPT.format(
        revealed_cards=revealed_str,
        hero_name=view["my_hero"],
        kingdom=view["my_kingdom"],
        hp=view["my_hp"],
        max_hp=view["my_max_hp"],
        hand_count=len(view["my_hand"]),
        hand_cards=hand_cards,
        equipment=equipment,
    )
    """Build prompt for 刚烈 choice."""
    source_name = view["players"][source_idx]["name"]
    hand_cards = ", ".join(
        f"{c['name']}({c['suit']})" for c in view["my_hand"]
    ) if view["my_hand"] else "无"

    hand_count = len(view["my_hand"])
    equipment = ", ".join(view["my_equipment"]) if view["my_equipment"] else "无"

    public_info = _format_public_info(view)

    return GANGLIE_CHOICE_PROMPT.format(
        ganglie_source=source_name,
        hero_name=view["my_hero"],
        kingdom=view["my_kingdom"],
        hp=view["my_hp"],
        max_hp=view["my_max_hp"],
        hand_count=hand_count,
        hand_cards=hand_cards,
        equipment=equipment,
        public_info=public_info,
            recent_events=_format_recent_events(view),
    )


GUANXING_PROMPT = """## 观星排列
你发动了【观星】，查看了牌堆顶的牌。请决定哪些放回牌堆顶，哪些放牌堆底。
亮出的牌：
{guanxing_cards}
### 你的状态
- 武将：{hero_name}（{kingdom}）
- 体力：{hp}/{max_hp}
- 手牌（{hand_count}张）：{hand_cards}
- 身份：{my_role}
请输出JSON，每张牌标记 top 或 bottom：
```json
{{"reasoning": "排列理由", "arrange": ["牌名:top", "牌名:bottom", ...]}}
```"""


def build_guanxing_prompt(view: dict, cards: list[str]) -> str:
    hand_cards = ", ".join(
        f"{c['name']}({c['suit']})" for c in view["my_hand"]
    ) if view["my_hand"] else "无"
    cards_str = "\n".join(f"  [{j}] {c}" for j, c in enumerate(cards))
    return GUANXING_PROMPT.format(
        guanxing_cards=cards_str,
        hero_name=view["my_hero"], kingdom=view["my_kingdom"],
        hp=view["my_hp"], max_hp=view["my_max_hp"],
        hand_count=len(view["my_hand"]), hand_cards=hand_cards,
        my_role=view.get("my_role", "未知"),
    )


def build_guicai_prompt(view: dict, judgment_card_name: str, judgment_suit: str,
                         judgment_number: int, context: str, target_idx: int | None = None) -> str:
    """Build prompt for 鬼才 judgment swap decision."""
    hand_cards = ", ".join(
        f"{c['name']}({c['suit']})" for c in view["my_hand"]
    ) if view["my_hand"] else "无"

    equipment = ", ".join(view["my_equipment"]) if view["my_equipment"] else "无"

    public_info = _format_public_info(view)

    judgment_card_str = f"{judgment_suit}{judgment_number} [{judgment_card_name}]"

    return GUICAI_PROMPT.format(
        context=context,
        judgment_card=judgment_card_str,
        judgment_suit=judgment_suit,
        hero_name=view["my_hero"],
        kingdom=view["my_kingdom"],
        hp=view["my_hp"],
        max_hp=view["my_max_hp"],
        hand_count=len(view["my_hand"]),
        hand_cards=hand_cards,
        equipment=equipment,
        public_info=public_info,
            recent_events=_format_recent_events(view),
    )
    """Build hero selection prompt."""
    lines = []
    for i, opt in enumerate(options):
        skills_str = ", ".join(f"{s['name']}: {s['description']}" for s in opt["skills"])
        lord_tag = " [主公]" if opt.get("is_lord") else ""
        lines.append(
            f"  [{i}] {opt['name']} ({opt['kingdom']}){lord_tag} HP:{opt['hp']}\n"
            f"      技能: {skills_str}"
        )
    hero_list = "\n".join(lines)

    return HERO_SELECT_PROMPT.format(
        role=role,
        hero_options=hero_list,
        max_idx=len(options) - 1,
    )
