"""Agent wrapper: perception filtering + LLM reasoning + action parsing."""
from __future__ import annotations
from typing import Any

from engine.rules import Action, ActionType
from engine.heroes import Role
from agent.client import LLMClient, LLMResponse
from agent.prompts import (
    build_system_prompt,
    build_turn_prompt,
    build_discard_prompt,
    build_response_prompt,
    build_negate_prompt,
    build_dying_prompt,
    build_guicai_prompt,
    build_fanjian_guess_prompt,
    build_ganglie_choice_prompt,
    build_wugu_pick_prompt,
    build_draw_phase_prompt,
    build_yiji_distribute_prompt,
    build_jiedao_choice_prompt,
    build_guanxing_prompt,
)


class Agent:
    """A single Sanguosha player agent backed by an LLM."""

    def __init__(self, player_idx: int, hero_name: str, kingdom: str,
                 skills: list[str], skill_descriptions: list[str],
                 role: Role, llm: LLMClient,
                 is_lord: bool = False, lord_skill: str = ""):
        self.player_idx = player_idx
        self.hero_name = hero_name
        self.kingdom = kingdom
        self.skills = skills
        self.skill_descriptions = skill_descriptions
        self.role = role
        self.is_lord = is_lord
        self.lord_skill = lord_skill
        self.llm = llm

        # Reasoning models need more tokens for thinking blocks
        model_lower = (llm.model or "").lower()
        self.is_thinking_model = any(x in model_lower for x in ("v4-pro", "reasoner", "r1"))
        self.play_tokens = 8192 if self.is_thinking_model else 8192

        self.system_prompt = build_system_prompt(
            hero_name=hero_name,
            kingdom=kingdom,
            skills=skills,
            skill_descriptions=skill_descriptions,
            role=role.value,
            is_lord=is_lord,
            lord_skill=lord_skill,
        )

        self.history: list[dict] = []  # conversation history
        self.total_tokens = 0
        self.verbose = True  # log prompts and responses to console

    def _chat_and_parse(self, prompt: str, temperature: float = 0.7, max_tokens: int = 2048) -> Action | None:
        """Call LLM and parse response, retrying up to 5 times on failure."""
        for attempt in range(5):
            response = self._llm_chat(prompt, temperature=temperature, max_tokens=max_tokens)
            action = self._parse_action(response, self.player_idx)
            if action is not None:
                return action
            if attempt == 0:
                retry_hint = "\n\n【重要】你上次的回复格式有误，无法解析。请严格按照JSON格式输出，不要输出多余文字。直接输出JSON对象。"
                prompt = prompt + retry_hint
                print(f"  [RETRY] Agent[{self.player_idx}] parse failed, retrying...")
        return None

    def _chat_json(self, prompt: str, temperature: float = 0.7, max_tokens: int = 2048) -> Any:
        """Call LLM and return parsed_json, retrying up to 5 times on failure."""
        for attempt in range(5):
            response = self._llm_chat(prompt, temperature=temperature, max_tokens=max_tokens)
            if response.parsed_json is not None:
                return response
            if attempt == 0:
                retry_hint = "\n\n【重要】你上次的回复格式有误，无法解析。请严格按照JSON格式输出。"
                prompt = prompt + retry_hint
                print(f"  [RETRY] Agent[{self.player_idx}] json parse failed, retrying...")
        return response  # return even if failed

    def _llm_chat(self, prompt: str, temperature: float = 0.7, max_tokens: int = 2048) -> Any:
        """Call LLM with console logging of prompt and response."""
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"[LLM PROMPT] Player {self.player_idx} ({self.hero_name})")
            print(f"{'='*60}")
            print(prompt)
            print(f"[LLM WAIT] calling API... (prompt {len(prompt)} chars)")
        response = self.llm.chat(self.system_prompt, prompt, temperature=temperature, max_tokens=max_tokens)
        self.total_tokens += sum(response.usage.values()) if response.usage else 0
        if self.verbose:
            print(f"\n[LLM RESPONSE] ({response.usage.get('input',0) if response.usage else 0}+{response.usage.get('output',0) if response.usage else 0} tokens)")
            print(response.content)
            print(f"{'='*60}\n")
        return response

    def decide(self, view: dict, phase: str, **kwargs) -> Action | None:
        """Make a decision based on the current game view."""
        if phase == "discard_phase":
            return self._handle_discard(view, kwargs.get("discard_count", 0))
        elif phase == "play_phase":
            return self._handle_play(view)
        elif phase == "prepare_phase":
            return self._handle_prepare(view)
        elif phase == "response":
            return self._handle_response(view, kwargs)
        elif phase == "negate":
            return self._handle_negate(view, kwargs)
        elif phase == "dying":
            return self._handle_dying(view, kwargs)
        elif phase == "draw_phase":
            return self._handle_draw_phase(view, kwargs)
        elif phase == "liuli_redirect":
            return self._handle_liuli(view, kwargs)
        elif phase == "guicai":
            return self._handle_guicai(view, kwargs)
        elif phase == "fanjian_guess":
            return self._handle_fanjian_guess(view, kwargs)
        elif phase == "ganglie_choice":
            return self._handle_ganglie_choice(view, kwargs)
        elif phase == "wugu_pick":
            return self._handle_wugu_pick(view, kwargs)
        elif phase == "yiji_distribute":
            return self._handle_yiji_distribute(view, kwargs)
        elif phase == "jiedao_choice":
            return self._handle_jiedao_choice(view, kwargs)
        elif phase == "guanxing":
            return self._handle_guanxing(view, kwargs)
        elif phase == "fankui":
            return self._handle_fankui(view, kwargs)
        else:
            return None

    def _handle_play(self, view: dict) -> Action | None:
        """Handle the play phase: choose card to play or pass."""
        prompt = build_turn_prompt(view)

        return self._chat_and_parse(prompt, temperature=0.8, max_tokens=self.play_tokens)

    def _handle_discard(self, view: dict, discard_count: int) -> Action | None:
        """Handle discard phase."""
        prompt = build_discard_prompt(view, discard_count)

        return self._chat_and_parse(prompt, temperature=0.3, max_tokens=1024)

    def _handle_prepare(self, view: dict) -> Action | None:
        """Handle prepare phase skill usage (e.g., 洛神)."""
        has_luoshen = "洛神" in self.skills
        if not has_luoshen:
            return None

        # Simple heuristic: always try 洛神 if available
        return Action(
            type=ActionType.USE_SKILL,
            player_idx=view["player_idx"],
            skill_name="洛神",
        )

    def _handle_response(self, view: dict, kwargs: dict) -> Action | None:
        """Handle a response request (e.g., 杀→闪, 南蛮→杀, 万箭→闪, 决斗→杀)."""
        response_type = kwargs.get("response_type", "")
        source_card = kwargs.get("source_card", "")
        source_idx = kwargs.get("source_idx", 0)

        prompt = build_response_prompt(
            view,
            response_type=response_type,
            source_card=source_card,
            source_idx=source_idx,
            target_idx=kwargs.get("target_idx"),
            bagua_failed=kwargs.get("bagua_failed", False),
            no_bagua=kwargs.get("no_bagua", False),
        )

        return self._chat_and_parse(prompt, temperature=0.5, max_tokens=1024)

    def _handle_negate(self, view: dict, kwargs: dict) -> Action | None:
        """Handle a 无懈可击 opportunity."""
        source_idx = kwargs.get("source_idx", 0)
        card_name = kwargs.get("card_name", "")
        target_idx = kwargs.get("target_idx")

        prompt = build_negate_prompt(
            view,
            source_idx=source_idx,
            card_name=card_name,
            target_idx=target_idx,
        )

        return self._chat_and_parse(prompt, temperature=0.5, max_tokens=1024)

    def _handle_dying(self, view: dict, kwargs: dict) -> Action | None:
        """Handle a near-death rescue decision."""
        dying_idx = kwargs.get("dying_idx", -1)
        needed = kwargs.get("needed", 1)

        prompt = build_dying_prompt(view, dying_idx=dying_idx, needed=needed)

        return self._chat_and_parse(prompt, temperature=0.7, max_tokens=1024)

    def _handle_draw_phase(self, view: dict, kwargs: dict) -> Action | None:
        """Handle draw phase skill choice (突袭, 裸衣)."""
        skills = view.get("my_skills", [])
        has_tuxi = "突袭" in skills
        has_nuoyi = "裸衣" in skills
        if not has_tuxi and not has_nuoyi:
            return None

        prompt = build_draw_phase_prompt(view)

        response = self._chat_json(prompt, temperature=0.6, max_tokens=1024)
        if not response.parsed_json:
            return None

        reasoning = response.parsed_json.get("reasoning", "")
        choice = response.parsed_json.get("draw_choice", "normal")  # "normal", "tuxi", "nuoyi"

        if choice == "nuoyi" and has_nuoyi:
            return Action(
                type=ActionType.USE_SKILL,
                player_idx=view["player_idx"],
                skill_name="裸衣",
                reasoning=reasoning,
            )

        if choice == "tuxi" and has_tuxi:
            targets = response.parsed_json.get("targets", [])
            valid_targets = []
            seen = set()
            player_idx = view["player_idx"]
            for t in targets:
                if isinstance(t, str):
                    try: t = int(t)
                    except: continue
                if not isinstance(t, int): continue
                if t < 0 or t >= len(view["players"]): continue
                p = view["players"][t]
                if not p["alive"]: continue
                if t == player_idx: continue
                if t in seen: continue
                if p.get("hand_count", 0) <= 0: continue
                seen.add(t)
                valid_targets.append(str(t))

            if valid_targets:
                return Action(
                    type=ActionType.USE_SKILL,
                    player_idx=view["player_idx"],
                    skill_name="突袭",
                    cards_used=valid_targets[:2],
                    reasoning=reasoning,
                )

        return None  # Normal draw

    def _handle_liuli(self, view: dict, kwargs: dict) -> Action | None:
        """Handle 流离 redirect decision."""
        return None

    def _handle_guicai(self, view: dict, kwargs: dict) -> Action | None:
        """Handle 鬼才 judgment swap decision."""
        hand = view.get("my_hand", [])
        if not hand:
            return None

        judgment_card_name = kwargs.get("judgment_card_name", "")
        judgment_suit = kwargs.get("judgment_suit", "")
        judgment_number = kwargs.get("judgment_number", 0)
        context = kwargs.get("context", "")

        prompt = build_guicai_prompt(
            view,
            judgment_card_name=judgment_card_name,
            judgment_suit=judgment_suit,
            judgment_number=judgment_number,
            context=context,
            target_idx=kwargs.get("target_idx"),
        )

        response = self._llm_chat(prompt, temperature=0.3, max_tokens=512)
        return self._parse_action(response, view["player_idx"])

    def _handle_fanjian_guess(self, view: dict, kwargs: dict) -> Action | None:
        """Handle 反间 suit guess."""
        source_idx = kwargs.get("source_idx", 0)
        card_name = kwargs.get("card_name", "")

        prompt = build_fanjian_guess_prompt(view, source_idx=source_idx, card_name=card_name)

        response = self._chat_json(prompt, temperature=0.5, max_tokens=512)
        if not response.parsed_json:
            return None

        guessed_suit = response.parsed_json.get("guessed_suit", "")
        reasoning = response.parsed_json.get("reasoning", "")

        valid_suits = {"♠", "♥", "♣", "♦"}
        if guessed_suit not in valid_suits:
            return None

        return Action(
            type=ActionType.RESPOND,
            player_idx=view["player_idx"],
            card_name=guessed_suit,
            reasoning=reasoning,
        )

    def _handle_ganglie_choice(self, view: dict, kwargs: dict) -> Action | None:
        """Handle 刚烈 choice: take 1 damage or discard 2 cards."""
        source_idx = kwargs.get("source_idx", 0)
        hand = view.get("my_hand", [])
        if len(hand) < 2:
            # Must take damage - return action indicating damage choice
            return Action(
                type=ActionType.RESPOND,
                player_idx=view["player_idx"],
                skill_name="damage",
            )

        prompt = build_ganglie_choice_prompt(view, source_idx=source_idx)

        response = self._chat_json(prompt, temperature=0.5, max_tokens=512)
        if not response.parsed_json:
            return Action(type=ActionType.RESPOND, player_idx=view["player_idx"], skill_name="damage")

        reasoning = response.parsed_json.get("reasoning", "")

        ganglie_choice = response.parsed_json.get("ganglie_choice", "damage")
        if ganglie_choice == "discard":
            cards_used = response.parsed_json.get("cards_used", [])
            valid = [cn for cn in cards_used if any(c["name"] == cn for c in hand)]
            if len(valid) >= 2:
                return Action(
                    type=ActionType.RESPOND,
                    player_idx=view["player_idx"],
                    skill_name="discard",
                    cards_used=valid[:2],
                    reasoning=reasoning,
                )

        return Action(
            type=ActionType.RESPOND,
            player_idx=view["player_idx"],
            skill_name="damage",
            reasoning=reasoning,
        )

    def _handle_wugu_pick(self, view: dict, kwargs: dict) -> Action | None:
        """Handle 五谷丰登 card selection."""
        revealed = kwargs.get("revealed", [])
        if not revealed:
            return None

        prompt = build_wugu_pick_prompt(view, revealed=revealed)

        response = self._llm_chat(prompt, temperature=0.3, max_tokens=512)
        return self._parse_action(response, view["player_idx"])

    def _handle_yiji_distribute(self, view: dict, kwargs: dict) -> Action | None:
        """Handle 遗计 card distribution."""
        hand = view.get("my_hand", [])
        if not hand:
            return None

        drawn = kwargs.get("drawn", [])
        prompt = build_yiji_distribute_prompt(view, drawn=drawn)

        response = self._chat_json(prompt, temperature=0.5, max_tokens=512)
        if not response.parsed_json:
            return None

        reasoning = response.parsed_json.get("reasoning", "")
        distribute = response.parsed_json.get("distribute", [])

        if not distribute:
            return None

        return Action(
            type=ActionType.USE_SKILL,
            player_idx=view["player_idx"],
            skill_name="遗计",
            cards_used=distribute[:2],
            reasoning=reasoning,
        )

    def _handle_fankui(self, view: dict, kwargs: dict) -> Action | None:
        """Handle 反馈: choose trigger or skip."""
        source_idx = kwargs.get("source_idx", 0)
        source = view["players"][source_idx] if source_idx < len(view["players"]) else {}
        has_hand = source.get("hand_count", 0) > 0 if source else False
        has_equip = bool(source.get("equipment", [])) if source else False
        if not has_hand and not has_equip:
            return Action(type=ActionType.RESPOND, player_idx=view["player_idx"], skill_name="skip")

        prompt = f"""## 反馈抉择
你受到伤害后可以发动【反馈】，从伤害来源获得一张牌。
伤害来源: {source.get('name', '?')} (手牌:{source.get('hand_count', 0)}张 装备:{','.join(source.get('equipment', []))})
你的身份: {view.get('my_role', '未知')}
选择: trigger=获得手牌 / equipment=获得装备 / skip=不发动
输出JSON: {{"reasoning": "...", "choice": "trigger|equipment|skip"}}"""

        response = self._chat_json(prompt, temperature=0.3, max_tokens=256)
        if not response.parsed_json:
            return Action(type=ActionType.RESPOND, player_idx=view["player_idx"], skill_name="trigger")

        reasoning = response.parsed_json.get("reasoning", "")
        choice = response.parsed_json.get("choice", "trigger")
        return Action(type=ActionType.RESPOND, player_idx=view["player_idx"],
                      skill_name=choice, reasoning=reasoning)

    def _handle_guanxing(self, view: dict, kwargs: dict) -> Action | None:
        """Handle 观星 card arrangement."""
        cards = kwargs.get("cards", [])
        if not cards:
            return None

        prompt = build_guanxing_prompt(view, cards=cards)

        response = self._chat_json(prompt, temperature=0.3, max_tokens=512)
        if not response.parsed_json:
            return None

        reasoning = response.parsed_json.get("reasoning", "")
        arrange = response.parsed_json.get("arrange", [])

        return Action(
            type=ActionType.USE_SKILL,
            player_idx=view["player_idx"],
            skill_name="观星",
            cards_used=arrange,
            reasoning=reasoning,
        )

    def _handle_jiedao_choice(self, view: dict, kwargs: dict) -> Action | None:
        """Handle 借刀杀人: use 杀 or give weapon."""
        source_idx = kwargs.get("source_idx", 0)
        secondary_idx = kwargs.get("secondary_idx", 0)

        has_sha = any(c["name"] == "杀" for c in view.get("my_hand", []))
        if not has_sha:
            return None  # No 杀 to use

        prompt = build_jiedao_choice_prompt(view, source_idx=source_idx, secondary_idx=secondary_idx)

        response = self._chat_json(prompt, temperature=0.5, max_tokens=512)
        if not response.parsed_json:
            return None

        reasoning = response.parsed_json.get("reasoning", "")
        use_sha = response.parsed_json.get("use_sha", False)

        if use_sha:
            return Action(
                type=ActionType.RESPOND,
                player_idx=view["player_idx"],
                card_name="杀",
                reasoning=reasoning,
            )
        return None

    def _parse_action(self, response: LLMResponse, player_idx: int) -> Action | None:
        """Parse LLM response into a game Action."""
        if not response.parsed_json:
            if response.content:
                preview = response.content[:200].replace('\n', ' ')
                print(f"  [PARSE FAIL] Agent[{player_idx}] raw: {preview}...")
            return None

        data = response.parsed_json
        reasoning = data.get("reasoning", "")

        action_data = data.get("action", {})
        # v4-pro sometimes wraps action in a list
        if isinstance(action_data, list) and len(action_data) > 0:
            action_data = action_data[0]
        if not action_data or not isinstance(action_data, dict):
            return None

        action_type_str = action_data.get("type", "pass")

        try:
            action_type = ActionType(action_type_str)
        except ValueError:
            return None

        # Clean card names: strip suit suffix "闪(♦)" → "闪"
        def _clean(cn):
            return cn.split("(")[0] if isinstance(cn, str) and "(" in cn else cn

        # Only these skills convert cards in PLAY_CARD; strip passive skills
        conversion_skills = {"武圣", "奇袭", "国色", "龙胆", "丈八蛇矛"}
        skill_name_raw = action_data.get("skill_name") or ""
        if action_type_str != "use_skill" and skill_name_raw not in conversion_skills:
            skill_name_raw = None

        card_name = _clean(action_data.get("card_name"))
        cards_used_raw = action_data.get("cards_used") or []
        cards_used = [_clean(c) for c in cards_used_raw]

        return Action(
            type=action_type,
            player_idx=player_idx,
            card_name=card_name,
            skill_name=skill_name_raw,
            target_idx=action_data.get("target_idx"),
            cards_used=cards_used,
            extra=action_data.get("extra", {}),
            reasoning=reasoning,
            suspicion=data.get("suspicion", {}),
        )


def create_agents_from_game(heroes, roles, llm: LLMClient) -> list[Agent]:
    """Create Agent instances for all players in the game."""
    agents = []
    for i, (hero, role) in enumerate(zip(heroes, roles)):
        skill_names = [s.name for s in hero.skills]
        skill_descs = [s.description for s in hero.skills]
        lord_skill_desc = hero.lord_skill.description if hero.lord_skill and role == Role.LORD else ""

        agent = Agent(
            player_idx=i,
            hero_name=hero.name,
            kingdom=hero.kingdom.value,
            skills=skill_names,
            skill_descriptions=skill_descs,
            role=role,
            llm=llm,
            is_lord=(role == Role.LORD),
            lord_skill=lord_skill_desc,
        )
        agents.append(agent)
    return agents


def agent_game_callback(agents: list[Agent]):
    """Create a callback function compatible with the game engine."""
    def callback(view: dict, phase: str, **kwargs) -> Action | None:
        agent = agents[view["player_idx"]]
        action = agent.decide(view, phase, **kwargs)
        if action:
            # Print reasoning if available
            pass  # reasoning is printed in game loop
        return action
    return callback
