"use strict";

let eventSource = null;
let gameRunning = false;
let currentState = null;
let awaitingDecision = false;

// -- SSE connection --
function connectSSE() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource("/stream");
  eventSource.onmessage = function(e) {
    const msg = JSON.parse(e.data);
    handleMessage(msg);
  };
  eventSource.onerror = function() {
    document.getElementById("status").textContent = "SSE 连接中断";
  };
}

function handleMessage(msg) {
  switch (msg.type) {
    case "status":
      addLog("status", msg.data);
      document.getElementById("status").textContent = msg.data;
      break;

    case "state":
      currentState = msg.data;
      renderPlayers(msg.data);
      break;

    case "turn_start":
      document.getElementById("turn-label").textContent =
        `第${msg.data.round}轮 - ${msg.data.player_name} (${msg.data.role})`;
      addLog("turn", `━━━ 第${msg.data.round}轮 ${msg.data.player_name}的回合 ━━━`);
      highlightActive(msg.data.player_idx);
      break;

    case "awaiting_decision":
      awaitingDecision = true;
      const d = msg.data;
      document.getElementById("status").textContent =
        `等待 [${d.player_idx}] ${d.player_name} 决策: ${d.context}`;
      document.getElementById("btn-step").disabled = false;
      highlightActive(d.player_idx);
      document.getElementById("await-indicator").style.display = "block";
      document.getElementById("await-indicator").textContent =
        `[${d.player_idx}] ${d.player_name}: ${d.context}`;
      break;

    case "decision_made":
      awaitingDecision = false;
      const dm = msg.data;
      document.getElementById("btn-step").disabled = true;
      document.getElementById("await-indicator").style.display = "none";

      let actionDesc = `[${dm.player_idx}] ${dm.player_name} `;
      if (dm.phase === "play_phase") {
        if (dm.action_type === "pass") {
          actionDesc += "选择过（不出牌）";
        } else if (dm.skill_name) {
          actionDesc += `发动【${dm.skill_name}】`;
          if (dm.card_name && dm.action_type === "play_card") {
            actionDesc += ` — 将手牌当【${dm.card_name}】使用`;
          }
          if (dm.target_idx !== null && dm.target_idx !== undefined) {
            const t = currentState && currentState.players[dm.target_idx];
            actionDesc += ` → ${t ? t.name : dm.target_idx}`;
          }
        } else if (dm.card_name) {
          actionDesc += `使用【${dm.card_name}】`;
          if (dm.target_idx !== null && dm.target_idx !== undefined && dm.target_idx !== dm.player_idx) {
            const t = currentState && currentState.players[dm.target_idx];
            actionDesc += ` → ${t ? t.name : dm.target_idx}`;
          }
        }
      } else if (dm.phase === "response") {
        actionDesc += dm.card_name
          ? (dm.skill_name ? `用【${dm.skill_name}】打出【${dm.card_name}】` : `打出【${dm.card_name}】`)
          : "选择不响应";
      } else if (dm.phase === "discard_phase") {
        actionDesc += dm.cards_used && dm.cards_used.length
          ? `弃置: ${dm.cards_used.join(", ")}`
          : "无需弃牌";
      } else if (dm.phase === "dying") {
        actionDesc += dm.card_name ? `使用【桃】救援` : "不救援";
      } else if (dm.phase === "negate") {
        actionDesc += dm.card_name ? "打出【无懈可击】" : "不使用无懈可击";
      } else if (dm.phase === "guicai") {
        actionDesc += dm.card_name ? `替换判定牌为【${dm.card_name}】` : "不替换判定牌";
      } else if (dm.phase === "fanjian_guess") {
        actionDesc += `猜花色: ${dm.card_name}`;
      } else if (dm.phase === "ganglie_choice") {
        actionDesc += dm.skill_name === "discard" ? "选择弃2张手牌" : "选择受到1点伤害";
      } else if (dm.phase === "guanxing") {
        actionDesc += `观星排列：${dm.cards_used ? dm.cards_used.join(", ") : ""}`;
      } else {
        actionDesc += `${dm.action_type}`;
        if (dm.skill_name) actionDesc += ` [${dm.skill_name}]`;
      }

      addLog("action", actionDesc);
      if (dm.reasoning) {
        addLog("thinking", `💭 ${dm.player_name}: ${dm.reasoning}`);
      }
      if (dm.suspicion && Object.keys(dm.suspicion).length > 0) {
        let suspLines = [];
        for (const [name, probs] of Object.entries(dm.suspicion)) {
          if (probs && typeof probs === "object") {
            const parts = [];
            for (const [role, pct] of Object.entries(probs)) {
              if (pct > 0.2) parts.push(`${role}:${(pct*100).toFixed(0)}%`);
            }
            if (parts.length > 0) suspLines.push(`${name}→${parts.join(" ")}`);
          }
        }
        if (suspLines.length > 0) {
          addLog("suspicion", `🔍 ${dm.player_name}身份推理: ${suspLines.join(" | ")}`);
        }
      }
      document.getElementById("status").textContent = "运行中...";
      break;

    case "event":
      addLog("event", `  ${msg.data.description}`);
      break;

    case "game_over":
      addLog("gameover", `🎉 游戏结束！胜利方: ${msg.data.winner}`);
      document.getElementById("status").textContent = `游戏结束 - 胜利: ${msg.data.winner}`;
      document.getElementById("btn-step").disabled = true;
      document.getElementById("btn-start").disabled = false;
      document.getElementById("chk-auto").disabled = false;
      document.getElementById("chk-god").disabled = false;
      gameRunning = false;
      break;

    case "hero_select":
      const hs = msg.data;
      addLog("turn", `━━━ 选将阶段：[${hs.player_idx}] 身份: ${hs.role} ━━━`);
      addLog("event", `可选武将:\n${hs.options}`);
      break;
    case "hero_pick":
      const hp = msg.data;
      addLog("action", `[${hp.player_idx}] 选择【${hp.hero}】`);
      if (hp.reasoning) addLog("thinking", `💭 ${hp.reasoning}`);
      break;
    case "heartbeat":
      break;
  }
}

// -- Log rendering --
function addLog(type, text) {
  const log = document.getElementById("event-log");
  const div = document.createElement("div");
  div.className = "log-" + type;
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

// -- Player panel rendering --
function renderPlayers(data) {
  const container = document.getElementById("players");
  container.innerHTML = "";

  for (const p of data.players) {
    const card = document.createElement("div");
    card.className = "player-card";
    card.id = "player-" + p.idx;
    if (p.idx === data.active_player) card.classList.add("active");
    if (!p.alive) card.classList.add("dead");

    // HP bar
    const hpPct = (p.hp / p.max_hp) * 100;
    let hpClass = "";
    if (p.hp <= 1) hpClass = "low";
    else if (p.hp <= 2) hpClass = "mid";

    // Kingdom badge
    const kingdomClass = "kingdom-" + p.kingdom;

    // Role badge
    const roleClass = "role-" + p.role;

    // Equipment
    let eqStr = "";
    if (p.equipment && p.equipment.length > 0) {
      eqStr = p.equipment.map(e => e.name).join(", ");
    }

    // Hand cards
    let handStr = "";
    if (p.hand && p.hand.length > 0) {
      handStr = p.hand.map(c =>
        `<span class="card-tag suit-${c.suit}">${c.name}(${c.suit})</span>`
      ).join(" ");
    } else if (p.hand_count !== undefined && p.hand_count > 0) {
      handStr = `<span class="card-tag">${p.hand_count}张手牌</span>`;
    } else {
      handStr = "无";
    }

    // Delay cards
    let delayStr = "";
    if (p.delay_cards && p.delay_cards.length > 0) {
      delayStr = `<span class="card-tag" style="background:#4a1a6b">${p.delay_cards.join(", ")}</span>`;
    }

    card.innerHTML = `
      <div class="p-header">
        <span class="p-name">[${p.idx}] ${p.name}</span>
        <span class="p-kingdom ${kingdomClass}">${p.kingdom}</span>
      </div>
      <div class="p-hp">
        <div class="p-hp-bar"><div class="p-hp-fill ${hpClass}" style="width:${hpPct}%"></div></div>
        <span class="p-hp-text">${p.hp}/${p.max_hp}</span>
        <span class="p-role ${roleClass}">${p.role}</span>
      </div>
      ${delayStr ? `<div class="p-section"><span class="p-label">判定:</span>${delayStr}</div>` : ""}
      <div class="p-section"><span class="p-label">手牌:</span><span class="p-cards">${handStr}</span></div>
      <div class="p-section"><span class="p-label">装备:</span>${eqStr || "无"}</div>
      <div class="p-section p-skills">${p.skills.join(", ")}${p.lord_skill ? " | 主公:" + p.lord_skill : ""}</div>
    `;
    container.appendChild(card);
  }

  // Discard pile display
  const discardDiv = document.getElementById("discard-pile") || document.createElement("div");
  discardDiv.id = "discard-pile";
  discardDiv.style.cssText = "padding:8px 10px;border-top:1px solid #0f3460;font-size:12px;color:#888;";
  let discardHTML = `<span class="p-label">牌堆 ${data.draw_pile_count || 0}张 | 弃牌堆 ${data.discard_total || 0}张:</span> `;
  if (data.discard_cards && data.discard_cards.length > 0) {
    discardHTML += `<br><span style="color:#666;">${data.discard_cards.join(" ")}</span>`;
    if (data.discard_total > 20) discardHTML += ` <span style="color:#555;">...共${data.discard_total}张</span>`;
  } else {
    discardHTML += "空";
  }
  discardDiv.innerHTML = discardHTML;
  container.appendChild(discardDiv);
}

function highlightActive(idx) {
  document.querySelectorAll(".player-card").forEach(el => {
    const pid = parseInt(el.id.replace("player-", ""));
    el.classList.toggle("active", pid === idx);
  });
}

// -- Controls --
async function startGame() {
  if (gameRunning) return;

  document.getElementById("event-log").innerHTML = "";
  document.getElementById("btn-start").disabled = true;
  document.getElementById("btn-step").disabled = true;
  document.getElementById("status").textContent = "启动中...";

  const stepMode = !document.getElementById("chk-auto").checked;  // auto is default (checked)
  const godView = document.getElementById("chk-god").checked;
  const model = document.getElementById("sel-model").value;
  const useRandom = (model === "random");

  try {
    const resp = await fetch("/api/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        step_mode: stepMode,
        god_view: godView,
        use_random: useRandom,
        model: useRandom ? null : model,
        seed: Math.floor(Math.random()*99999),
        auto_delay: 0.1,
      }),
    });
    const result = await resp.json();
    if (result.status === "started") {
      gameRunning = true;
      connectSSE();
      document.getElementById("chk-auto").disabled = true;
      document.getElementById("chk-god").disabled = true;
    }
  } catch (err) {
    document.getElementById("status").textContent = "启动失败: " + err;
    document.getElementById("btn-start").disabled = false;
  }
}

async function doStep() {
  document.getElementById("btn-step").disabled = true;
  try {
    await fetch("/api/step", { method: "POST" });
  } catch (err) {
    document.getElementById("status").textContent = "步进失败";
  }
}

async function toggleAuto(on) {
  if (gameRunning) {
    // Toggle mid-game
    try {
      await fetch("/api/mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ step_mode: !on }),
      });
      document.getElementById("btn-step").disabled = on;
    } catch (err) {}
  }
}

async function toggleGod(on) {
  if (gameRunning) {
    try {
      await fetch("/api/mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ god_view: on }),
      });
    } catch (err) {}
  }
}
