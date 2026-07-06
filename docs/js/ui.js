window.BalticUI = (() => {
  function formatDate(dateString) {
    if (!dateString) return "—";
    const date = new Date(dateString);
    return date.toLocaleString("hu-HU", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    });
  }

  function formatNumber(value, digits = 0) {
    const number = Number(value || 0);
    if (!Number.isFinite(number)) return "—";
    return number.toLocaleString("hu-HU", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits
    });
  }

  function titleCase(value) {
    return String(value || "")
      .replaceAll("_", " ")
      .replace(/\b\w/g, char => char.toUpperCase());
  }

  function setText(id, value) {
    const element = document.getElementById(id);
    if (!element) return;
    element.textContent = value;
  }

  function updateHeader(data) {
    setText("lastUpdate", formatDate(data.latest_update || data.generated_at));
    setText("engineVersion", data.version || "Threat Intelligence Engine");
  }

  function updateKpis(data) {
    const summary = data.summary || {};
    setText("overallScore", formatNumber(summary.threat_index, 2));
    setText("overallLevel", `Threat level: ${String(summary.threat_level || "—").toUpperCase()}`);
    setText("incidentCount", formatNumber(summary.incident_count));
    setText("activityCount", formatNumber(summary.activity_count));
    setText("indicatorCount", formatNumber(summary.indicator_count));
    setText("assessmentCount", formatNumber(summary.assessment_count));
  }

  function maxValue(items, key) {
    return Math.max(1, ...items.map(item => Number(item[key] || 0)));
  }

  function renderBars(targetId, items, nameKey) {
    const target = document.getElementById(targetId);
    if (!target) return;

    const maxScore = maxValue(items, "score_total");

    target.innerHTML = items.slice(0, 10).map(item => {
      const name = item[nameKey] || item.name || "Unknown";
      const width = Math.round((Number(item.score_total || 0) / maxScore) * 100);

      return `
        <div class="bar-row">
          <div class="bar-row-top">
            <span>${titleCase(name)}</span>
            <strong>${formatNumber(item.event_count)} events</strong>
          </div>
          <div class="bar-track">
            <div class="bar-fill" style="width:${width}%"></div>
          </div>
          <small>${formatNumber(item.score_total)} score · avg ${formatNumber(item.average_score, 2)}</small>
        </div>
      `;
    }).join("");
  }

  function renderCountries(data) {
    const target = document.getElementById("countryOverview");
    if (!target) return;

    const countries = data.country_cards || [];

    target.innerHTML = countries.map(country => `
      <article class="country-card">
        <div class="country-card-top">
          <h3>${country.country}</h3>
          <span>${String(country.level || "low").toUpperCase()}</span>
        </div>
        <strong>${formatNumber(country.average_score, 2)}</strong>
        <p>Threat score average</p>
        <div class="country-stats">
          <span>${formatNumber(country.event_count)} events</span>
          <span>${formatNumber(country.incident_count)} incidents</span>
          <span>Highest ${formatNumber(country.highest_score)}</span>
        </div>
      </article>
    `).join("");
  }

  function eventRows(events, limit = 10) {
    return events.slice(0, limit).map(event => `
      <div class="event-row">
        <div class="event-score">${formatNumber(event.hybrid_threat_score)}</div>
        <div>
          <a href="${event.url || "#"}" target="_blank" rel="noopener noreferrer">
            ${event.title || "Untitled event"}
          </a>
          <small>
            ${event.primary_country || "Regional"} ·
            ${titleCase(event.event_subtype)} ·
            ${formatNumber(event.source_count)} sources ·
            confidence ${formatNumber(event.confidence_score)}
          </small>
        </div>
      </div>
    `).join("");
  }

  function renderEvents(data) {
    const critical = document.getElementById("criticalEvents");
    const latest = document.getElementById("latestEvents");

    if (critical) {
      critical.innerHTML = eventRows(data.top_events || [], 10);
    }

    if (latest) {
      latest.innerHTML = eventRows(data.recent_events || [], 10);
    }
  }

  function renderMethodology(data) {
    const methodology = data.methodology || {};
    const pipeline = document.getElementById("methodPipeline");
    const ontology = document.getElementById("eventOntology");

    if (pipeline) {
      pipeline.innerHTML = (methodology.pipeline || [])
        .map(item => `<li>${item}</li>`)
        .join("");
    }

    if (ontology) {
      ontology.innerHTML = Object.entries(methodology.event_subtypes || {})
        .map(([key, value]) => `
          <div class="ontology-card">
            <strong>${titleCase(key)}</strong>
            <span>${value}</span>
          </div>
        `)
        .join("");
    }

    setText("methodWarning", methodology.warning || "");
  }

  function updateDashboard(data) {
    updateHeader(data);
    updateKpis(data);
    renderBars("categoryDrivers", data.category_drivers || [], "category");
    renderBars("actorDrivers", data.actor_drivers || [], "actor");
    renderCountries(data);
    renderEvents(data);
    renderMethodology(data);
  }

  return {
    updateDashboard
  };
})();
