document.addEventListener("DOMContentLoaded", () => {
  const BANKROLL = 100;
  const MIN_BET_PER_WRESTLER = 5;
  const MAX_BET_PER_MATCH = 25;
  const pageRoot = document.querySelector("main.container");
  const matchCards = Array.from(document.querySelectorAll(".match-card"));
  const wrestlerRows = Array.from(document.querySelectorAll(".wrestler"));

  const playerNameInput = document.getElementById("player-name");
  const searchInput = document.getElementById("wrestler-search");
  const expandAllBtn = document.getElementById("expand-all");
  const collapseAllBtn = document.getElementById("collapse-all");
  const submitBtn = document.getElementById("submit-picks");
  const downloadBtn = document.getElementById("download-picks");
  const copySummaryBtn = document.getElementById("copy-picks-summary");
  const validationMessageEl = document.getElementById("validation-message");

  const totalAvailableEl = document.getElementById("total-available");
  const totalWageredEl = document.getElementById("total-wagered");
  const remainingPointsEl = document.getElementById("remaining-points");
  const matchesNotWageredEl = document.getElementById("matches-not-wagered");
  const avgWagerRemainingEl = document.getElementById("avg-wager-remaining");
  const totalProfitEl = document.getElementById("total-profit");
  const totalReturnEl = document.getElementById("total-return");
  const bankrollWarningEl = document.getElementById("bankroll-warning");
  const commitTotalWageredEl = document.getElementById("commit-total-wagered");
  const commitBankrollEl = document.getElementById("commit-bankroll");
  const submitFeedbackEl = document.getElementById("submit-feedback");

  let isSubmitted = false;
  let submittedPayload = null;
  let latestTotals = null;

  function formatNumber(value) {
    const rounded = Math.round(value * 10) / 10;
    if (Number.isInteger(rounded)) return String(rounded);
    return rounded.toFixed(1);
  }

  function setMessage(text, isError = false) {
    if (!validationMessageEl) return;
    validationMessageEl.hidden = !text;
    validationMessageEl.textContent = text;
    validationMessageEl.style.color = isError ? "#b42318" : "#8b3f00";
  }

  function parseOddsFromRow(row) {
    const raw = row.getAttribute("data-odds") || "";
    const odds = Number(raw);
    return Number.isFinite(odds) ? odds : null;
  }

  function getWagerValue(input) {
    const numeric = Number(input.value);
    if (!Number.isFinite(numeric) || numeric < 0) return 0;
    return numeric;
  }

  function parseWrestlerName(row) {
    const nameEl = row.querySelector(".name");
    if (!nameEl) return "Unknown Wrestler";
    const copy = nameEl.cloneNode(true);
    copy.querySelectorAll("img").forEach((img) => img.remove());
    return (copy.textContent || "").trim() || "Unknown Wrestler";
  }

  function isRealParticipant(row) {
    const name = parseWrestlerName(row).trim().toLowerCase();
    return name !== "" && name !== "tbd" && name !== "unknown wrestler";
  }

  function calculateProfit(wager, odds) {
    if (!Number.isFinite(wager) || wager <= 0 || odds === null) return 0;
    if (odds < 0) return wager * (100 / Math.abs(odds));
    return wager * (odds / 100);
  }

  function setMatchExpanded(card, expanded) {
    const toggle = card.querySelector(".match-toggle");
    const body = card.querySelector(".match-body");
    if (!toggle || !body) return;
    toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
    body.hidden = !expanded;
  }

  function updateSummary() {
    let totalWagered = 0;
    let totalProfit = 0;
    let matchesNotWagered = 0;

    matchCards.forEach((card) => {
      const rows = Array.from(card.querySelectorAll(".wrestler"));
      let matchWager = 0;

      rows.forEach((row) => {
        const input = row.querySelector(".wager-input");
        if (!input) return;
        const wager = getWagerValue(input);
        const odds = parseOddsFromRow(row);
        row.classList.toggle("wager-active", wager > 0);
        matchWager += wager;
        totalWagered += wager;
        totalProfit += calculateProfit(wager, odds);
      });

      if (matchWager <= 0) matchesNotWagered += 1;
    });

    const totalReturn = totalWagered + totalProfit;
    const overLimit = totalWagered > BANKROLL;
    const remainingRaw = BANKROLL - totalWagered;
    const remainingDisplay = Math.max(0, remainingRaw);
    const avgRemaining = matchesNotWagered > 0 ? remainingDisplay / matchesNotWagered : null;

    totalAvailableEl.textContent = formatNumber(BANKROLL);
    totalWageredEl.textContent = formatNumber(totalWagered);
    remainingPointsEl.textContent = formatNumber(remainingDisplay);
    matchesNotWageredEl.textContent = String(matchesNotWagered);
    avgWagerRemainingEl.textContent = avgRemaining === null ? "N/A" : formatNumber(avgRemaining);
    totalProfitEl.textContent = formatNumber(totalProfit);
    totalReturnEl.textContent = formatNumber(totalReturn);
    if (commitTotalWageredEl) commitTotalWageredEl.textContent = formatNumber(totalWagered);
    if (commitBankrollEl) commitBankrollEl.textContent = formatNumber(BANKROLL);

    bankrollWarningEl.hidden = !overLimit;
    totalWageredEl.classList.toggle("over-limit", overLimit);
    remainingPointsEl.classList.toggle("over-limit", overLimit);

    latestTotals = {
      totalWagered,
      totalProfit,
      totalReturn,
      remaining: remainingDisplay,
      matchesNotWagered,
      avgRemaining,
      overLimit,
    };
  }

  function setSubmitFeedback(text, isError = false) {
    if (!submitFeedbackEl) return;
    submitFeedbackEl.hidden = !text;
    submitFeedbackEl.textContent = text;
    submitFeedbackEl.style.color = isError ? "#2a4f67" : "#24516d";
  }

  function setupMatchRuleUI() {
    matchCards.forEach((card) => {
      const toggle = card.querySelector(".match-toggle");
      const title = toggle?.querySelector("h2");
      if (!toggle || !title) return;

      const participants = Array.from(card.querySelectorAll(".wrestler")).filter(isRealParticipant).length;
      const maxSelections = Math.floor(participants / 2);
      card.dataset.participants = String(participants);
      card.dataset.maxSelections = String(maxSelections);

      let meta = toggle.querySelector(".match-toggle-meta");
      if (!meta) {
        meta = document.createElement("div");
        meta.className = "match-toggle-meta";
        toggle.insertBefore(meta, title);
        meta.appendChild(title);
      }

      let hint = toggle.querySelector(".match-limit-hint");
      if (!hint) {
        hint = document.createElement("span");
        hint.className = "match-limit-hint";
        meta.appendChild(hint);
      }
      hint.textContent = `Limits: max ${MAX_BET_PER_MATCH} pts • pick up to ${maxSelections} of ${participants}`;

      if (!card.querySelector(".match-rule-message")) {
        const message = document.createElement("div");
        message.className = "match-rule-message";
        message.hidden = true;
        const body = card.querySelector(".match-body");
        if (body) body.insertAdjacentElement("afterend", message);
      }
    });
  }

  function validateAll() {
    const results = [];
    matchCards.forEach((card) => {
      const rows = Array.from(card.querySelectorAll(".wrestler"));
      const participants = Number(card.dataset.participants || "0");
      const maxSelections = Number(card.dataset.maxSelections || "0");

      let matchTotal = 0;
      let selections = 0;
      let hasLowBet = false;

      rows.forEach((row) => {
        const input = row.querySelector(".wager-input");
        if (!input || input.disabled) return;
        const wager = getWagerValue(input);
        matchTotal += wager;
        if (wager > 0) selections += 1;
        if (wager > 0 && wager < MIN_BET_PER_WRESTLER) {
          hasLowBet = true;
        }
      });

      const messages = [];
      if (hasLowBet) messages.push(`Minimum bet is ${MIN_BET_PER_WRESTLER} points (or 0).`);
      if (matchTotal > MAX_BET_PER_MATCH) messages.push(`Max points per match is ${MAX_BET_PER_MATCH}.`);
      if (selections > maxSelections) {
        messages.push(`You can only wager on ${maxSelections} of ${participants} participants in this match.`);
      }

      const messageEl = card.querySelector(".match-rule-message");
      const invalid = messages.length > 0;
      card.classList.toggle("rule-invalid", invalid);
      if (messageEl) {
        messageEl.hidden = !invalid;
        messageEl.textContent = messages.join(" ");
      }

      if (invalid) {
        results.push({
          match: card.querySelector("h2")?.textContent?.trim() || "Unknown Match",
          messages,
        });
      }
    });
    return {
      valid: results.length === 0,
      errors: results,
    };
  }

  function filterWrestlers() {
    const query = (searchInput?.value || "").trim().toLowerCase();
    matchCards.forEach((card) => {
      const rows = Array.from(card.querySelectorAll(".wrestler"));
      let visible = 0;
      rows.forEach((row) => {
        const text = row.textContent.toLowerCase();
        const shouldShow = query === "" || text.includes(query);
        row.hidden = !shouldShow;
        if (shouldShow) visible += 1;
      });
      card.hidden = visible === 0;
    });
  }

  function collectPicks() {
    const picks = [];
    matchCards.forEach((card) => {
      const matchName = card.querySelector("h2")?.textContent?.trim() || "Unknown Match";
      const rows = Array.from(card.querySelectorAll(".wrestler"));
      rows.forEach((row) => {
        const input = row.querySelector(".wager-input");
        if (!input) return;
        const wager = getWagerValue(input);
        if (wager <= 0) return;
        const oddsText = row.querySelector(".odds")?.textContent?.replace("Odds:", "").trim() || "TBD";
        picks.push({
          match: matchName,
          wrestler: parseWrestlerName(row),
          odds: oddsText,
          wager: Number(formatNumber(wager)),
        });
      });
    });
    return picks;
  }

  function buildPayload() {
    const eventId = pageRoot?.dataset?.eventId || "UNKNOWN";
    const playerName = (playerNameInput?.value || "").trim();
    const picks = collectPicks();
    return {
      eventId,
      playerName,
      submittedAt: new Date().toISOString(),
      bankroll: BANKROLL,
      picks,
      totals: {
        totalWagered: Number(formatNumber(latestTotals?.totalWagered || 0)),
        totalProfit: Number(formatNumber(latestTotals?.totalProfit || 0)),
        totalReturn: Number(formatNumber(latestTotals?.totalReturn || 0)),
      },
    };
  }

  function buildReadableSummary(payload) {
    const lines = [];
    lines.push(`EventID: ${payload.eventId}`);
    lines.push(`Player Name: ${payload.playerName}`);
    lines.push(`Submitted At: ${payload.submittedAt}`);
    lines.push("");
    lines.push("Picks:");

    if (payload.picks.length === 0) {
      lines.push("- No picks submitted");
    } else {
      const grouped = {};
      payload.picks.forEach((pick) => {
        if (!grouped[pick.match]) grouped[pick.match] = [];
        grouped[pick.match].push(pick);
      });
      Object.keys(grouped).forEach((match) => {
        lines.push(`- ${match}`);
        grouped[match].forEach((pick) => {
          lines.push(`  - ${pick.wrestler} | ${formatNumber(pick.wager)} pts @ ${pick.odds}`);
        });
      });
    }

    lines.push("");
    lines.push(`Total Wagered: ${formatNumber(payload.totals.totalWagered)}`);
    lines.push(`Total Potential Profit: ${formatNumber(payload.totals.totalProfit)}`);
    lines.push(`Total Potential Return: ${formatNumber(payload.totals.totalReturn)}`);
    return lines.join("\n");
  }

  function sanitizeFilePart(value) {
    return (value || "unknown").trim().replace(/[^a-zA-Z0-9_-]+/g, "_");
  }

  function validateBeforeSubmit() {
    const playerName = (playerNameInput?.value || "").trim();
    if (!playerName) return "Please enter a player name before submitting.";
    if (!latestTotals) return "Totals are not ready yet. Try again.";
    if (latestTotals.overLimit) return `Total wagered cannot exceed ${BANKROLL} points.`;

    const invalidInput = wrestlerRows.some((row) => {
      const input = row.querySelector(".wager-input");
      if (!input || input.disabled) return false;
      if (input.value.trim() === "") return false;
      const value = Number(input.value);
      return !Number.isFinite(value) || value < 0;
    });
    if (invalidInput) return "Please fix invalid wager values (must be 0 or greater).";
    return "";
  }

  function lockWagerInputs() {
    wrestlerRows.forEach((row) => {
      const input = row.querySelector(".wager-input");
      if (!input) return;
      input.readOnly = true;
      input.disabled = true;
    });
    if (playerNameInput) playerNameInput.readOnly = true;
  }

  function downloadPayload(payload) {
    const eventId = sanitizeFilePart(payload.eventId);
    const player = sanitizeFilePart(payload.playerName);
    const fileName = `picks_${eventId}_${player}.json`;
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  matchCards.forEach((card) => {
    setMatchExpanded(card, true);
    const toggle = card.querySelector(".match-toggle");
    toggle?.addEventListener("click", () => {
      const expanded = toggle.getAttribute("aria-expanded") === "true";
      setMatchExpanded(card, !expanded);
    });
  });

  expandAllBtn?.addEventListener("click", () => {
    matchCards.forEach((card) => setMatchExpanded(card, true));
  });

  collapseAllBtn?.addEventListener("click", () => {
    matchCards.forEach((card) => setMatchExpanded(card, false));
  });

  wrestlerRows.forEach((row) => {
    const input = row.querySelector(".wager-input");
    if (!input) return;
    input.addEventListener("input", () => {
      if (isSubmitted) return;
      updateSummary();
      validateAll();
      setSubmitFeedback("");
    });
    input.addEventListener("change", () => {
      if (isSubmitted) return;
      updateSummary();
      validateAll();
      setSubmitFeedback("");
    });
  });

  searchInput?.addEventListener("input", filterWrestlers);

  submitBtn?.addEventListener("click", () => {
    if (isSubmitted) return;
    updateSummary();
    const ruleValidation = validateAll();
    if (!ruleValidation.valid) {
      setSubmitFeedback("Fix the highlighted matches before submitting.", true);
      return;
    }
    const error = validateBeforeSubmit();
    if (error) {
      setMessage(error, true);
      setSubmitFeedback("");
      return;
    }

    submittedPayload = buildPayload();
    isSubmitted = true;
    lockWagerInputs();
    submitBtn.disabled = true;
    submitBtn.textContent = "Submitted";
    downloadBtn.hidden = false;
    copySummaryBtn.hidden = false;
    setMessage("Picks submitted locally. You can now download or copy the submission.");
    setSubmitFeedback("");
  });

  downloadBtn?.addEventListener("click", () => {
    if (!submittedPayload) return;
    downloadPayload(submittedPayload);
  });

  copySummaryBtn?.addEventListener("click", async () => {
    if (!submittedPayload) return;
    const originalText = copySummaryBtn.textContent;
    try {
      await navigator.clipboard.writeText(buildReadableSummary(submittedPayload));
      copySummaryBtn.textContent = "Copied!";
      setTimeout(() => {
        copySummaryBtn.textContent = originalText;
      }, 1200);
    } catch {
      setMessage("Could not copy to clipboard. Please try again.", true);
    }
  });

  setupMatchRuleUI();
  updateSummary();
  validateAll();
});
