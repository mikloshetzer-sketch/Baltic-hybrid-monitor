window.BalticUI = (() => {
  function formatDate(dateString) {
    if (!dateString) return "—";

    const date = new Date(dateString);

    if (Number.isNaN(date.getTime())) {
      return String(dateString);
    }

    return date.toLocaleString("hu-HU", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    });
  }

  function formatDay(dateString) {
    if (!dateString) return "—";

    const date = new Date(`${dateString}T00:00:00Z`);

    if (Number.isNaN(date.getTime())) {
      return String(dateString);
    }

    return date.toLocaleDateString("hu-HU", {
      month: "2-digit",
      day: "2-digit",
      timeZone: "UTC"
    });
  }

  function formatWeekday(dateString) {
    if (!dateString) return "";

    const date = new Date(`${dateString}T00:00:00Z`);

    if (Number.isNaN(date.getTime())) {
      return "";
    }

    return date.toLocaleDateString("hu-HU", {
      weekday: "short",
      timeZone: "UTC"
    });
  }

  function formatNumber(value, digits = 0) {
    if (value === null || typeof value === "undefined" || value === "") {
      return "—";
    }

    const number = Number(value);

    if (!Number.isFinite(number)) {
      return "—";
    }

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

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function safeUrl(value) {
    const url = String(value || "").trim();

    if (!url) {
      return "#";
    }

    if (
      url.startsWith("https://") ||
      url.startsWith("http://")
    ) {
      return escapeHtml(url);
    }

    return "#";
  }

  function setText(id, value) {
    const element = document.getElementById(id);

    if (element) {
      element.textContent = value;
    }
  }

  function asArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function firstDefined(...values) {
    return values.find(
      value =>
        value !== null &&
        typeof value !== "undefined" &&
        value !== ""
    );
  }

  function getSubtypeCount(data, subtype) {
    const card = asArray(data.subtype_cards).find(
      item =>
        String(
          firstDefined(
            item.subtype,
            item.event_subtype,
            item.name
          ) || ""
        ).toLowerCase() === subtype.toLowerCase()
    );

    if (!card) {
      return null;
    }

    return firstDefined(
      card.event_count,
      card.count,
      card.value
    );
  }

  function updateHeader(data) {
    setText(
      "lastUpdate",
      formatDate(
        data.latest_update ||
        data.generated_at
      )
    );

    setText(
      "engineVersion",
      data.version ||
      "Threat Intelligence Engine"
    );
  }

  function updateKpis(data) {
    const summary = data.summary || {};

    setText(
      "overallScore",
      formatNumber(summary.threat_index, 2)
    );

    setText(
      "overallLevel",
      `Threat level: ${String(
        summary.threat_level || "—"
      ).toUpperCase()}`
    );

    setText(
      "operationalIndex",
      formatNumber(
        firstDefined(
          summary.operational_index,
          data.operational_index
        ),
        2
      )
    );

    setText(
      "earlyWarningIndex",
      formatNumber(
        firstDefined(
          summary.early_warning_index,
          data.early_warning_index
        ),
        2
      )
    );

    setText(
      "incidentCount",
      formatNumber(
        firstDefined(
          summary.incident_count,
          getSubtypeCount(data, "incident"),
          0
        )
      )
    );

    setText(
      "activityCount",
      formatNumber(
        firstDefined(
          summary.activity_count,
          getSubtypeCount(data, "activity"),
          0
        )
      )
    );

    setText(
      "indicatorCount",
      formatNumber(
        firstDefined(
          summary.indicator_count,
          getSubtypeCount(data, "indicator"),
          0
        )
      )
    );

    setText(
      "assessmentCount",
      formatNumber(
        firstDefined(
          summary.assessment_count,
          getSubtypeCount(data, "assessment"),
          0
        )
      )
    );
  }

  function maxValue(items, key) {
    const values = asArray(items)
      .map(item => Number(item?.[key] || 0))
      .filter(Number.isFinite);

    return Math.max(1, ...values);
  }

  function renderBars(targetId, items, nameKey) {
    const target = document.getElementById(targetId);

    if (!target) {
      return;
    }

    const rows = asArray(items);

    if (!rows.length) {
      target.innerHTML = `
        <div class="empty-state">
          Nincs megjeleníthető adat.
        </div>
      `;
      return;
    }

    const maxScore = maxValue(rows, "score_total");

    target.innerHTML = rows
      .slice(0, 10)
      .map(item => {
        const name =
          item[nameKey] ||
          item.name ||
          "Unknown";

        const score = Number(
          item.score_total || 0
        );

        const width = Math.max(
          0,
          Math.min(
            100,
            Math.round(
              (score / maxScore) * 100
            )
          )
        );

        return `
          <div class="bar-row">
            <div class="bar-row-top">
              <span>${escapeHtml(titleCase(name))}</span>
              <strong>${formatNumber(item.event_count)} events</strong>
            </div>

            <div class="bar-track">
              <div
                class="bar-fill"
                style="width:${width}%"
              ></div>
            </div>

            <small>
              ${formatNumber(item.score_total)} score ·
              avg ${formatNumber(item.average_score, 2)}
            </small>
          </div>
        `;
      })
      .join("");
  }

  function renderCountries(data) {
    const target = document.getElementById(
      "countryOverview"
    );

    if (!target) {
      return;
    }

    const countries = asArray(
      data.country_cards
    );

    if (!countries.length) {
      target.innerHTML = `
        <div class="empty-state">
          Nincs országonkénti adat.
        </div>
      `;
      return;
    }

    target.innerHTML = countries
      .map(country => `
        <article class="country-card">
          <div class="country-card-top">
            <h3>${escapeHtml(country.country || "Unknown")}</h3>
            <span>
              ${escapeHtml(
                String(
                  country.level || "low"
                ).toUpperCase()
              )}
            </span>
          </div>

          <strong>
            ${formatNumber(country.average_score, 2)}
          </strong>

          <p>Threat score average</p>

          <div class="country-stats">
            <span>
              ${formatNumber(country.event_count)} events
            </span>

            <span>
              ${formatNumber(country.incident_count)} incidents
            </span>

            <span>
              Highest ${formatNumber(country.highest_score)}
            </span>
          </div>
        </article>
      `)
      .join("");
  }

  function eventRows(events, limit = 10) {
    const rows = asArray(events).slice(
      0,
      limit
    );

    if (!rows.length) {
      return `
        <div class="empty-state">
          Nincs megjeleníthető esemény.
        </div>
      `;
    }

    return rows
      .map(event => `
        <div class="event-row">
          <div class="event-score">
            ${formatNumber(event.hybrid_threat_score)}
          </div>

          <div>
            <a
              href="${safeUrl(event.url)}"
              target="_blank"
              rel="noopener noreferrer"
            >
              ${escapeHtml(
                event.title ||
                "Untitled event"
              )}
            </a>

            <small>
              ${escapeHtml(
                event.primary_country ||
                "Regional"
              )}
              ·
              ${escapeHtml(
                titleCase(
                  event.event_subtype
                )
              )}
              ·
              ${formatNumber(event.source_count)} sources
              · confidence
              ${formatNumber(event.confidence_score)}
            </small>
          </div>
        </div>
      `)
      .join("");
  }

  function renderEvents(data) {
    const critical = document.getElementById(
      "criticalEvents"
    );

    const latest = document.getElementById(
      "latestEvents"
    );

    if (critical) {
      critical.innerHTML = eventRows(
        data.top_events || [],
        10
      );
    }

    if (latest) {
      latest.innerHTML = eventRows(
        data.recent_events || [],
        10
      );
    }
  }

  function renderMethodology(data) {
    const methodology =
      data.methodology || {};

    const pipeline =
      document.getElementById(
        "methodPipeline"
      );

    const ontology =
      document.getElementById(
        "eventOntology"
      );

    if (pipeline) {
      pipeline.innerHTML = asArray(
        methodology.pipeline
      )
        .map(
          item =>
            `<li>${escapeHtml(item)}</li>`
        )
        .join("");
    }

    if (ontology) {
      ontology.innerHTML =
        Object.entries(
          methodology.event_subtypes || {}
        )
          .map(([key, value]) => `
            <div class="ontology-card">
              <strong>
                ${escapeHtml(titleCase(key))}
              </strong>

              <span>
                ${escapeHtml(value)}
              </span>
            </div>
          `)
          .join("");
    }

    setText(
      "methodWarning",
      methodology.warning || ""
    );
  }

  function findTopItem(items, nameKeys = []) {
    const rows = asArray(items);

    if (!rows.length) {
      return null;
    }

    const sorted = [...rows].sort(
      (a, b) =>
        Number(
          b.score_total ||
          b.event_count ||
          b.average_score ||
          0
        ) -
        Number(
          a.score_total ||
          a.event_count ||
          a.average_score ||
          0
        )
    );

    const item = sorted[0];

    for (const key of nameKeys) {
      if (item[key]) {
        return item[key];
      }
    }

    return (
      item.name ||
      null
    );
  }

  function renderCurrentThreatPicture(data) {
    const hotspot = findTopItem(
      data.country_cards,
      ["country"]
    );

    const keyDriver = findTopItem(
      data.category_drivers,
      ["category", "name"]
    );

    const dominantActor = findTopItem(
      data.actor_drivers,
      ["actor", "name"]
    );

    setText(
      "currentHotspot",
      hotspot || "—"
    );

    setText(
      "currentKeyDriver",
      keyDriver
        ? titleCase(keyDriver)
        : "—"
    );

    setText(
      "currentDominantActor",
      dominantActor
        ? titleCase(dominantActor)
        : "—"
    );

    const hotspotCountry =
      asArray(data.country_cards).find(
        country =>
          country.country === hotspot
      );

    if (hotspotCountry) {
      setText(
        "currentHotspotMeta",
        `${formatNumber(
          hotspotCountry.event_count
        )} events · ${String(
          hotspotCountry.level || "low"
        ).toUpperCase()}`
      );
    } else {
      setText(
        "currentHotspotMeta",
        "regional concentration"
      );
    }
  }

  function getDaySnapshot(day) {
    return (
      day.daily_snapshot ||
      day.snapshot ||
      day.data ||
      day
    );
  }

  function getDayEvents(day) {
    const snapshot = getDaySnapshot(day);

    const candidates = [
      snapshot.events,
      snapshot.top_events,
      snapshot.event_items,
      day.events,
      day.top_events
    ];

    for (const candidate of candidates) {
      if (Array.isArray(candidate)) {
        return candidate;
      }
    }

    return [];
  }

  function getDayValue(day, ...keys) {
    const snapshot = getDaySnapshot(day);

    for (const key of keys) {
      if (
        snapshot &&
        snapshot[key] !== null &&
        typeof snapshot[key] !==
          "undefined"
      ) {
        return snapshot[key];
      }

      if (
        day &&
        day[key] !== null &&
        typeof day[key] !==
          "undefined"
      ) {
        return day[key];
      }
    }

    return null;
  }

  function eventSubtype(event) {
    return String(
      firstDefined(
        event.event_subtype,
        event.subtype,
        event.type,
        ""
      )
    ).toLowerCase();
  }

  function filterEventsBySubtype(events, types) {
    const accepted = new Set(
      types.map(type =>
        type.toLowerCase()
      )
    );

    return asArray(events).filter(
      event =>
        accepted.has(
          eventSubtype(event)
        )
    );
  }

  function uniqueValues(items) {
    return [
      ...new Set(
        asArray(items)
          .filter(Boolean)
          .map(item =>
            String(item).trim()
          )
          .filter(Boolean)
      )
    ];
  }

  function summarizeEventTitles(events, limit = 2) {
    const rows = asArray(events);

    if (!rows.length) {
      return "";
    }

    return rows
      .slice(0, limit)
      .map(event => {
        const title =
          event.title ||
          event.name ||
          "Event";

        return escapeHtml(title);
      })
      .join("<br>");
  }

  function dayCountryMatches(day, country) {
    if (!country || country === "all") {
      return true;
    }

    const events = getDayEvents(day);

    if (!events.length) {
      return true;
    }

    return events.some(event => {
      const eventCountry = String(
        firstDefined(
          event.primary_country,
          event.country,
          event.region,
          ""
        )
      );

      return (
        eventCountry === country
      );
    });
  }

  function daySourceMatches(day, source) {
    if (!source || source === "all") {
      return true;
    }

    const events = getDayEvents(day);

    if (!events.length) {
      return true;
    }

    return events.some(event => {
      const candidates = [
        event.source,
        event.source_name,
        event.publisher
      ];

      return candidates.some(
        value =>
          String(value || "") === source
      );
    });
  }

  function collectSources(matrixData) {
    const sources = [];

    asArray(matrixData.daily_matrix)
      .forEach(day => {
        getDayEvents(day).forEach(
          event => {
            const value = firstDefined(
              event.source,
              event.source_name,
              event.publisher
            );

            if (value) {
              sources.push(value);
            }
          }
        );
      });

    return uniqueValues(sources).sort(
      (a, b) =>
        a.localeCompare(
          b,
          "hu"
        )
    );
  }

  function populateMatrixSourceFilter(matrixData) {
    const select =
      document.getElementById(
        "matrixSourceFilter"
      );

    if (!select) {
      return;
    }

    const current = select.value;
    const sources = collectSources(
      matrixData
    );

    select.innerHTML = `
      <option value="all">
        Minden forrás
      </option>
      ${sources
        .map(source => `
          <option value="${escapeHtml(source)}">
            ${escapeHtml(source)}
          </option>
        `)
        .join("")}
    `;

    if (
      [...select.options].some(
        option =>
          option.value === current
      )
    ) {
      select.value = current;
    }
  }

  function renderMissingCell() {
    return `
      <td class="matrix-cell status-missing">
        <strong>Missing</strong>
        <small>
          No historical snapshot
        </small>
      </td>
    `;
  }

  function renderZeroCell(label = "0") {
    return `
      <td class="matrix-cell status-zero">
        <strong>${escapeHtml(label)}</strong>
        <small>
          No relevant events detected
        </small>
      </td>
    `;
  }

  function renderInformationCell(day) {
    if (day.status === "missing") {
      return renderMissingCell();
    }

    const events = getDayEvents(day);
    const informationEvents =
      filterEventsBySubtype(
        events,
        [
          "information",
          "context",
          "background"
        ]
      );

    const count = firstDefined(
      getDayValue(
        day,
        "information_count"
      ),
      informationEvents.length
    );

    if (
      Number(count || 0) === 0
    ) {
      return renderZeroCell("0");
    }

    return `
      <td class="matrix-cell">
        <strong>${formatNumber(count)}</strong>
        <small>
          ${summarizeEventTitles(
            informationEvents,
            2
          ) || "Context signals"}
        </small>
      </td>
    `;
  }

  function renderWarningCell(day) {
    if (day.status === "missing") {
      return renderMissingCell();
    }

    const events = getDayEvents(day);

    const warningEvents =
      filterEventsBySubtype(
        events,
        ["indicator", "warning"]
      );

    const count = firstDefined(
      getDayValue(
        day,
        "indicator_count",
        "early_warning_count"
      ),
      warningEvents.length,
      0
    );

    const index = getDayValue(
      day,
      "early_warning_index"
    );

    if (
      Number(count || 0) === 0 &&
      Number(index || 0) === 0
    ) {
      return renderZeroCell("0");
    }

    return `
      <td class="matrix-cell">
        <strong>
          ${formatNumber(count)}
        </strong>

        <small>
          EW Index:
          ${formatNumber(index, 2)}
          ${
            warningEvents.length
              ? `<br>${summarizeEventTitles(
                  warningEvents,
                  2
                )}`
              : ""
          }
        </small>
      </td>
    `;
  }

  function renderOperationalCell(day) {
    if (day.status === "missing") {
      return renderMissingCell();
    }

    const events = getDayEvents(day);

    const operationalEvents =
      filterEventsBySubtype(
        events,
        ["incident", "activity"]
      );

    const incidentCount =
      firstDefined(
        getDayValue(
          day,
          "incident_count"
        ),
        filterEventsBySubtype(
          events,
          ["incident"]
        ).length,
        0
      );

    const activityCount =
      firstDefined(
        getDayValue(
          day,
          "activity_count"
        ),
        filterEventsBySubtype(
          events,
          ["activity"]
        ).length,
        0
      );

    const total =
      Number(incidentCount || 0) +
      Number(activityCount || 0);

    const operationalIndex =
      getDayValue(
        day,
        "operational_index"
      );

    if (
      total === 0 &&
      Number(
        operationalIndex || 0
      ) === 0
    ) {
      return renderZeroCell("0");
    }

    return `
      <td class="matrix-cell">
        <strong>
          ${formatNumber(total)}
        </strong>

        <small>
          ${formatNumber(incidentCount)}
          incident ·
          ${formatNumber(activityCount)}
          activity
          <br>
          Operational Index:
          ${formatNumber(
            operationalIndex,
            2
          )}
          ${
            operationalEvents.length
              ? `<br>${summarizeEventTitles(
                  operationalEvents,
                  2
                )}`
              : ""
          }
        </small>
      </td>
    `;
  }

  function renderActorCell(day) {
    if (day.status === "missing") {
      return renderMissingCell();
    }

    const events = getDayEvents(day);

    const actors = uniqueValues(
      events.flatMap(event => {
        const value = firstDefined(
          event.actor,
          event.primary_actor,
          event.attributed_actor,
          event.actors
        );

        return Array.isArray(value)
          ? value
          : value
            ? [value]
            : [];
      })
    );

    const explicitActor =
      getDayValue(
        day,
        "dominant_actor",
        "top_actor",
        "actor"
      );

    if (
      explicitActor &&
      !actors.includes(
        String(explicitActor)
      )
    ) {
      actors.unshift(
        String(explicitActor)
      );
    }

    if (!actors.length) {
      return renderZeroCell("—");
    }

    return `
      <td class="matrix-cell">
        <strong>
          ${escapeHtml(
            actors[0]
          )}
        </strong>

        <small>
          ${escapeHtml(
            actors
              .slice(1, 4)
              .join(" · ") ||
            "Observed actor exposure"
          )}
        </small>
      </td>
    `;
  }

  function renderHotspotCell(day) {
    if (day.status === "missing") {
      return renderMissingCell();
    }

    const events = getDayEvents(day);

    const countries =
      uniqueValues(
        events.map(event =>
          firstDefined(
            event.primary_country,
            event.country,
            event.region
          )
        )
      );

    const explicitHotspot =
      getDayValue(
        day,
        "hotspot",
        "top_country",
        "primary_country"
      );

    if (
      explicitHotspot &&
      !countries.includes(
        String(explicitHotspot)
      )
    ) {
      countries.unshift(
        String(explicitHotspot)
      );
    }

    if (!countries.length) {
      return renderZeroCell("—");
    }

    return `
      <td class="matrix-cell">
        <strong>
          ${escapeHtml(
            countries[0]
          )}
        </strong>

        <small>
          ${escapeHtml(
            countries
              .slice(1, 4)
              .join(" · ") ||
            "Regional concentration"
          )}
        </small>
      </td>
    `;
  }

  function threatLevelClass(level) {
    const normalized =
      String(
        level || "low"
      )
        .toLowerCase()
        .replaceAll(" ", "-");

    const allowed = new Set([
      "low",
      "guarded",
      "elevated",
      "high",
      "critical"
    ]);

    return allowed.has(normalized)
      ? normalized
      : "low";
  }

  function renderAssessmentCell(day) {
    if (day.status === "missing") {
      return renderMissingCell();
    }

    const threatIndex =
      getDayValue(
        day,
        "threat_index"
      );

    const threatLevel =
      String(
        getDayValue(
          day,
          "threat_level",
          "level"
        ) || "LOW"
      ).toUpperCase();

    const levelClass =
      threatLevelClass(
        threatLevel
      );

    return `
      <td class="matrix-cell level-${levelClass}">
        <span class="threat-badge ${levelClass}">
          ${escapeHtml(threatLevel)}
        </span>

        <strong>
          ${formatNumber(
            threatIndex,
            2
          )}
        </strong>

        <small>
          Daily Threat Index
        </small>
      </td>
    `;
  }

  function renderSummaryCell(day) {
    if (day.status === "missing") {
      return renderMissingCell();
    }

    const eventCount =
      firstDefined(
        getDayValue(
          day,
          "event_count"
        ),
        getDayEvents(day).length,
        0
      );

    const summary =
      getDayValue(
        day,
        "daily_summary",
        "summary_text",
        "assessment"
      );

    if (
      Number(eventCount || 0) === 0
    ) {
      return `
        <td class="matrix-cell status-zero">
          <strong>
            0 events
          </strong>

          <small>
            No relevant exact-day
            operational or warning
            events detected.
          </small>
        </td>
      `;
    }

    return `
      <td class="matrix-cell">
        <strong>
          ${formatNumber(eventCount)}
          events
        </strong>

        <small>
          ${escapeHtml(
            summary ||
            "Exact-day intelligence snapshot available."
          )}
        </small>
      </td>
    `;
  }

  function renderMatrixRow(
    label,
    description,
    rowClass,
    days,
    renderer
  ) {
    return `
      <tr class="${rowClass}">
        <td class="matrix-row-label">
          ${escapeHtml(label)}
          <small>
            ${escapeHtml(description)}
          </small>
        </td>

        ${days
          .map(renderer)
          .join("")}
      </tr>
    `;
  }

  function renderMatrixHeaders(days) {
    return days
      .map(day => `
        <th class="matrix-day-header">
          <strong>
            ${escapeHtml(
              formatDay(day.date)
            )}
          </strong>

          <small>
            ${escapeHtml(
              formatWeekday(day.date)
            )}
          </small>
        </th>
      `)
      .join("");
  }

  function renderMatrixCoverage(matrixData) {
    const coverage =
      matrixData.coverage || {};

    const available =
      Number(
        coverage.available_days || 0
      );

    const total =
      Number(
        firstDefined(
          coverage.total_days,
          matrixData.window?.window_days,
          7
        )
      );

    setText(
      "matrixCoverage",
      `${available}/${total}`
    );

    const start =
      matrixData.window?.start_date ||
      "—";

    const end =
      matrixData.window?.end_date ||
      "—";

    setText(
      "matrixWindowLabel",
      `${start} – ${end}`
    );
  }

  function renderMatrix(matrixData) {
    const target =
      document.getElementById(
        "intelligenceMatrix"
      );

    if (!target) {
      return;
    }

    const sourceFilter =
      document.getElementById(
        "matrixSourceFilter"
      )?.value || "all";

    const countryFilter =
      document.getElementById(
        "matrixCountryFilter"
      )?.value || "all";

    const days =
      asArray(
        matrixData.daily_matrix
      ).map(day => {
        if (
          day.status === "missing"
        ) {
          return day;
        }

        const matchesCountry =
          dayCountryMatches(
            day,
            countryFilter
          );

        const matchesSource =
          daySourceMatches(
            day,
            sourceFilter
          );

        if (
          matchesCountry &&
          matchesSource
        ) {
          return day;
        }

        return {
          ...day,
          __filteredOut: true
        };
      });

    const displayDays =
      days.map(day => {
        if (
          !day.__filteredOut
        ) {
          return day;
        }

        return {
          date: day.date,
          status: "available",
          event_count: 0,
          incident_count: 0,
          activity_count: 0,
          indicator_count: 0,
          assessment_count: 0,
          operational_index: 0,
          early_warning_index: 0,
          threat_index: 0,
          threat_level: "LOW",
          events: []
        };
      });

    target.innerHTML = `
      <table class="matrix-table">
        <thead>
          <tr>
            <th class="matrix-corner">
              Intelligence layer
            </th>

            ${renderMatrixHeaders(
              displayDays
            )}
          </tr>
        </thead>

        <tbody>
          ${renderMatrixRow(
            "Information",
            "context and background signals",
            "matrix-row-information",
            displayDays,
            renderInformationCell
          )}

          ${renderMatrixRow(
            "Early Warning",
            "indicator events and warning layer",
            "matrix-row-early-warning",
            displayDays,
            renderWarningCell
          )}

          ${renderMatrixRow(
            "Operational",
            "incident and activity events",
            "matrix-row-operational",
            displayDays,
            renderOperationalCell
          )}

          ${renderMatrixRow(
            "Actor",
            "observed or attributed actors",
            "matrix-row-actor",
            displayDays,
            renderActorCell
          )}

          ${renderMatrixRow(
            "Hotspot / Country",
            "geographic concentration",
            "matrix-row-hotspot",
            displayDays,
            renderHotspotCell
          )}

          ${renderMatrixRow(
            "Assessment",
            "exact-day Threat Index",
            "matrix-row-assessment",
            displayDays,
            renderAssessmentCell
          )}

          ${renderMatrixRow(
            "Daily summary",
            "exact-day intelligence summary",
            "matrix-row-summary",
            displayDays,
            renderSummaryCell
          )}
        </tbody>
      </table>
    `;
  }

  function bindMatrixFilters(matrixData) {
    const source =
      document.getElementById(
        "matrixSourceFilter"
      );

    const country =
      document.getElementById(
        "matrixCountryFilter"
      );

    if (
      source &&
      !source.dataset.bound
    ) {
      source.addEventListener(
        "change",
        () => renderMatrix(
          matrixData
        )
      );

      source.dataset.bound = "true";
    }

    if (
      country &&
      !country.dataset.bound
    ) {
      country.addEventListener(
        "change",
        () => renderMatrix(
          matrixData
        )
      );

      country.dataset.bound = "true";
    }
  }

  function updateMatrix(matrixData) {
    if (!matrixData) {
      const target =
        document.getElementById(
          "intelligenceMatrix"
        );

      if (target) {
        target.innerHTML = `
          <div class="error-state">
            A 7-Day Intelligence Matrix
            adatforrás nem érhető el.
          </div>
        `;
      }

      return;
    }

    renderMatrixCoverage(
      matrixData
    );

    populateMatrixSourceFilter(
      matrixData
    );

    bindMatrixFilters(
      matrixData
    );

    renderMatrix(
      matrixData
    );
  }

  function updateDashboard(data) {
    updateHeader(data);
    updateKpis(data);

    renderCurrentThreatPicture(
      data
    );

    renderBars(
      "categoryDrivers",
      data.category_drivers || [],
      "category"
    );

    renderBars(
      "actorDrivers",
      data.actor_drivers || [],
      "actor"
    );

    renderCountries(data);
    renderEvents(data);
    renderMethodology(data);
  }

  function updatePlatform(
    dashboardData,
    matrixData
  ) {
    updateDashboard(
      dashboardData
    );

    updateMatrix(
      matrixData
    );
  }

  return {
    updateDashboard,
    updateMatrix,
    updatePlatform
  };
})();
