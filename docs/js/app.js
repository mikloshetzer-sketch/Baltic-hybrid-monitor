document.addEventListener("DOMContentLoaded", async () => {
  const HISTORY_URL =
    "./data/baltic_intelligence_matrix_history.json";

  const MATRIX_WINDOW_DAYS = 7;

  let matrixHistory = null;
  let latestMatrixData = null;
  let currentMatrixEndDate = null;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function showFatalError(error) {
    const message =
      error instanceof Error
        ? error.message
        : String(error || "Unknown error");

    document.body.innerHTML = `
      <main class="page-shell">
        <section
          class="dashboard-panel"
          style="
            max-width:900px;
            margin:80px auto;
            border-top:4px solid #e33d38;
          "
        >
          <div class="panel-heading">
            <p>PLATFORM ERROR</p>
            <h2>Dashboard loading error</h2>
          </div>

          <div class="error-state">
            <strong>
              The Baltic Hybrid Intelligence Platform
              could not be loaded.
            </strong>

            <p>
              ${escapeHtml(message)}
            </p>

            <p>
              Check whether
              <strong>
                docs/data/baltic_dashboard.json
              </strong>
              exists and contains valid JSON.
            </p>
          </div>
        </section>
      </main>
    `;
  }

  function parseIsoDate(value) {
    if (
      typeof value !== "string" ||
      !/^\d{4}-\d{2}-\d{2}$/.test(value)
    ) {
      return null;
    }

    const parts =
      value.split("-").map(Number);

    const parsed =
      new Date(
        Date.UTC(
          parts[0],
          parts[1] - 1,
          parts[2]
        )
      );

    if (
      Number.isNaN(
        parsed.getTime()
      )
    ) {
      return null;
    }

    return parsed;
  }

  function formatIsoDate(value) {
    return value
      .toISOString()
      .slice(0, 10);
  }

  function shiftIsoDate(
    value,
    dayOffset
  ) {
    const parsed =
      parseIsoDate(value);

    if (!parsed) {
      return null;
    }

    parsed.setUTCDate(
      parsed.getUTCDate() +
      dayOffset
    );

    return formatIsoDate(
      parsed
    );
  }

  function buildWindowDates(
    endDate,
    days = MATRIX_WINDOW_DAYS
  ) {
    const dates = [];

    for (
      let offset = days - 1;
      offset >= 0;
      offset -= 1
    ) {
      dates.push(
        shiftIsoDate(
          endDate,
          -offset
        )
      );
    }

    return dates.filter(Boolean);
  }

  function numberOrZero(value) {
    const parsed =
      Number(value);

    return Number.isFinite(parsed)
      ? parsed
      : 0;
  }

  function integerOrZero(value) {
    return Math.round(
      numberOrZero(value)
    );
  }

  function roundScore(value) {
    return Math.round(
      numberOrZero(value) * 100
    ) / 100;
  }

  function buildAvailableDay(snapshot) {
    const overall =
      snapshot?.overall_summary || {};

    return {
      date:
        snapshot.snapshot_date,

      status:
        "available",

      snapshot_generated_at:
        snapshot.generated_at ?? null,

      snapshot_version:
        snapshot.snapshot_version ?? null,

      score_engine_version:
        snapshot.score_engine_version ?? null,

      event_count:
        integerOrZero(
          overall.event_count
        ),

      incident_count:
        integerOrZero(
          overall.incident_count
        ),

      activity_count:
        integerOrZero(
          overall.activity_count
        ),

      indicator_count:
        integerOrZero(
          overall.indicator_count
        ),

      assessment_count:
        integerOrZero(
          overall.assessment_count
        ),

      score_total:
        roundScore(
          overall.score_total
        ),

      average_score:
        roundScore(
          overall.average_score
        ),

      highest_score:
        roundScore(
          overall.highest_score
        ),

      operational_index:
        roundScore(
          overall.operational_index
        ),

      early_warning_index:
        roundScore(
          overall.early_warning_index
        ),

      threat_index:
        roundScore(
          overall.threat_index
        ),

      overall_level:
        overall.overall_level ?? null,

      country_summary:
        snapshot.country_summary || {},

      category_summary:
        snapshot.category_summary || {},

      actor_summary:
        snapshot.actor_summary || {},

      subtype_summary:
        snapshot.subtype_summary || {},

      scope_summary:
        snapshot.scope_summary || {},

      hotspot:
        snapshot.hotspot ?? null,

      key_driver:
        snapshot.key_driver ?? null,

      dominant_actor:
        snapshot.dominant_actor ?? null,

      top_events:
        Array.isArray(
          snapshot.top_events
        )
          ? snapshot.top_events
          : [],

      events:
        Array.isArray(
          snapshot.events
        )
          ? snapshot.events
          : []
    };
  }

  function buildMissingDay(dateValue) {
    return {
      date:
        dateValue,

      status:
        "missing",

      snapshot_generated_at:
        null,

      snapshot_version:
        null,

      score_engine_version:
        null,

      event_count:
        null,

      incident_count:
        null,

      activity_count:
        null,

      indicator_count:
        null,

      assessment_count:
        null,

      score_total:
        null,

      average_score:
        null,

      highest_score:
        null,

      operational_index:
        null,

      early_warning_index:
        null,

      threat_index:
        null,

      overall_level:
        null,

      country_summary:
        null,

      category_summary:
        null,

      actor_summary:
        null,

      subtype_summary:
        null,

      scope_summary:
        null,

      hotspot:
        null,

      key_driver:
        null,

      dominant_actor:
        null,

      top_events:
        [],

      events:
        []
    };
  }

  function validateHistory(data) {
    if (
      !data ||
      !Array.isArray(
        data.snapshots
      )
    ) {
      throw new Error(
        "Intelligence matrix history is missing or invalid."
      );
    }

    const seen =
      new Set();

    data.snapshots.forEach(
      snapshot => {
        const snapshotDate =
          snapshot?.snapshot_date;

        if (
          !parseIsoDate(
            snapshotDate
          )
        ) {
          throw new Error(
            `Invalid historical snapshot date: ${snapshotDate}`
          );
        }

        if (
          seen.has(
            snapshotDate
          )
        ) {
          throw new Error(
            `Duplicate historical snapshot date: ${snapshotDate}`
          );
        }

        seen.add(
          snapshotDate
        );

        if (
          snapshot?.method?.rolling_window_used === true
        ) {
          throw new Error(
            `Historical snapshot ${snapshotDate} is not exact-day data.`
          );
        }
      }
    );

    return data;
  }

  async function loadMatrixHistory() {
    const response =
      await fetch(
        HISTORY_URL,
        {
          cache: "no-store"
        }
      );

    if (!response.ok) {
      throw new Error(
        `Failed to load ${HISTORY_URL}. Status: ${response.status}`
      );
    }

    const data =
      await response.json();

    return validateHistory(
      data
    );
  }

  function snapshotsByDate(history) {
    const map =
      new Map();

    history.snapshots.forEach(
      snapshot => {
        map.set(
          snapshot.snapshot_date,
          snapshot
        );
      }
    );

    return map;
  }

  function buildMatrixFromHistory(
    history,
    endDate
  ) {
    const dates =
      buildWindowDates(
        endDate
      );

    if (
      dates.length !==
      MATRIX_WINDOW_DAYS
    ) {
      throw new Error(
        "Could not build a seven-day matrix window."
      );
    }

    const snapshotMap =
      snapshotsByDate(
        history
      );

    const dailyMatrix =
      dates.map(
        dateValue => {
          const snapshot =
            snapshotMap.get(
              dateValue
            );

          return snapshot
            ? buildAvailableDay(
                snapshot
              )
            : buildMissingDay(
                dateValue
              );
        }
      );

    const availableDays =
      dailyMatrix.filter(
        day =>
          day.status ===
          "available"
      );

    const missingDates =
      dailyMatrix
        .filter(
          day =>
            day.status ===
            "missing"
        )
        .map(
          day => day.date
        );

    const observedThreatValues =
      availableDays
        .map(
          day =>
            Number(
              day.threat_index
            )
        )
        .filter(
          Number.isFinite
        );

    const eventTotal =
      availableDays.reduce(
        (sum, day) =>
          sum +
          integerOrZero(
            day.event_count
          ),
        0
      );

    const indicatorTotal =
      availableDays.reduce(
        (sum, day) =>
          sum +
          integerOrZero(
            day.indicator_count
          ),
        0
      );

    const incidentTotal =
      availableDays.reduce(
        (sum, day) =>
          sum +
          integerOrZero(
            day.incident_count
          ),
        0
      );

    const activityTotal =
      availableDays.reduce(
        (sum, day) =>
          sum +
          integerOrZero(
            day.activity_count
          ),
        0
      );

    const assessmentTotal =
      availableDays.reduce(
        (sum, day) =>
          sum +
          integerOrZero(
            day.assessment_count
          ),
        0
      );

    const topEvents =
      availableDays
        .flatMap(
          day =>
            Array.isArray(
              day.top_events
            )
              ? day.top_events
              : []
        )
        .sort(
          (a, b) =>
            numberOrZero(
              b.hybrid_threat_score
            ) -
            numberOrZero(
              a.hybrid_threat_score
            )
        )
        .slice(
          0,
          20
        );

    const averageThreat =
      observedThreatValues.length
        ? roundScore(
            observedThreatValues.reduce(
              (sum, value) =>
                sum + value,
              0
            ) /
            observedThreatValues.length
          )
        : null;

    const highestThreat =
      observedThreatValues.length
        ? roundScore(
            Math.max(
              ...observedThreatValues
            )
          )
        : null;

    return {
      project:
        history.project ||
        "baltic-hybrid-monitor",

      title:
        "7-Day Baltic Intelligence Matrix",

      region:
        history.region ||
        "Baltic states and Poland",

      generated_at:
        new Date().toISOString(),

      matrix_version:
        "baltic_7day_matrix_v1_0",

      source_history_version:
        history.history_version ||
        null,

      source_history_generated_at:
        history.generated_at ||
        null,

      window: {
        start_date:
          dates[0],

        end_date:
          dates[
            dates.length - 1
          ],

        window_days:
          MATRIX_WINDOW_DAYS
      },

      method: {
        construction:
          "Seven separate exact-day historical snapshots assembled in the browser from intelligence matrix history.",

        rolling_window_used:
          false,

        missing_day_rule:
          "Missing historical dates remain missing and are never converted into zero-event days."
      },

      coverage: {
        total_days:
          MATRIX_WINDOW_DAYS,

        available_days:
          availableDays.length,

        missing_days:
          missingDates.length,

        complete:
          missingDates.length === 0
      },

      missing_dates:
        missingDates,

      seven_day_summary: {
        event_count:
          eventTotal,

        incident_count:
          incidentTotal,

        activity_count:
          activityTotal,

        indicator_count:
          indicatorTotal,

        assessment_count:
          assessmentTotal,

        observed_day_average_threat_index:
          averageThreat,

        highest_daily_threat_index:
          highestThreat
      },

      top_events:
        topEvents,

      daily_matrix:
        dailyMatrix
    };
  }

  function getHistorySnapshotDates() {
    if (
      !matrixHistory ||
      !Array.isArray(
        matrixHistory.snapshots
      )
    ) {
      return [];
    }

    return matrixHistory.snapshots
      .map(
        snapshot =>
          snapshot?.snapshot_date
      )
      .filter(
        dateValue =>
          Boolean(
            parseIsoDate(
              dateValue
            )
          )
      )
      .sort();
  }

  function windowContainsSnapshot(
    endDate
  ) {
    const windowDates =
      new Set(
        buildWindowDates(
          endDate
        )
      );

    return getHistorySnapshotDates()
      .some(
        snapshotDate =>
          windowDates.has(
            snapshotDate
          )
      );
  }

  function resetMatrixFiltersForNewWindow() {
    [
      "matrixSourceFilter",
      "matrixCountryFilter"
    ].forEach(
      elementId => {
        const element =
          document.getElementById(
            elementId
          );

        if (!element) {
          return;
        }

        const replacement =
          element.cloneNode(
            true
          );

        replacement.dataset.bound =
          "";

        element.replaceWith(
          replacement
        );
      }
    );
  }

  function renderMatrixWindow(
    endDate,
    {
      resetFilters = false
    } = {}
  ) {
    if (!matrixHistory) {
      return;
    }

    const matrixData =
      buildMatrixFromHistory(
        matrixHistory,
        endDate
      );

    currentMatrixEndDate =
      endDate;

    if (resetFilters) {
      resetMatrixFiltersForNewWindow();
    }

    BalticUI.updateMatrix(
      matrixData
    );

    updateMatrixNavigationState();
  }

  function updateMatrixNavigationState() {
    const previousButton =
      document.getElementById(
        "matrixPrevious"
      );

    const currentButton =
      document.getElementById(
        "matrixCurrent"
      );

    const nextButton =
      document.getElementById(
        "matrixNext"
      );

    if (
      !latestMatrixData ||
      !currentMatrixEndDate
    ) {
      if (previousButton) {
        previousButton.disabled =
          true;
      }

      if (nextButton) {
        nextButton.disabled =
          true;
      }

      return;
    }

    const latestEndDate =
      latestMatrixData.window
        ?.end_date;

    const previousEndDate =
      shiftIsoDate(
        currentMatrixEndDate,
        -MATRIX_WINDOW_DAYS
      );

    const nextEndDate =
      shiftIsoDate(
        currentMatrixEndDate,
        MATRIX_WINDOW_DAYS
      );

    const canGoPrevious =
      Boolean(
        previousEndDate &&
        windowContainsSnapshot(
          previousEndDate
        )
      );

    const canGoNext =
      Boolean(
        nextEndDate &&
        latestEndDate &&
        nextEndDate <= latestEndDate
      );

    if (previousButton) {
      previousButton.disabled =
        !canGoPrevious;
    }

    if (nextButton) {
      nextButton.disabled =
        !canGoNext;
    }

    if (currentButton) {
      const isLatest =
        currentMatrixEndDate ===
        latestEndDate;

      currentButton.classList.toggle(
        "active",
        isLatest
      );
    }
  }

  function bindMatrixNavigation() {
    const previousButton =
      document.getElementById(
        "matrixPrevious"
      );

    const currentButton =
      document.getElementById(
        "matrixCurrent"
      );

    const nextButton =
      document.getElementById(
        "matrixNext"
      );

    if (
      previousButton &&
      !previousButton.dataset.bound
    ) {
      previousButton.addEventListener(
        "click",
        () => {
          const previousEndDate =
            shiftIsoDate(
              currentMatrixEndDate,
              -MATRIX_WINDOW_DAYS
            );

          if (
            !previousEndDate ||
            !windowContainsSnapshot(
              previousEndDate
            )
          ) {
            return;
          }

          renderMatrixWindow(
            previousEndDate,
            {
              resetFilters: true
            }
          );
        }
      );

      previousButton.dataset.bound =
        "true";
    }

    if (
      currentButton &&
      !currentButton.dataset.bound
    ) {
      currentButton.addEventListener(
        "click",
        () => {
          const latestEndDate =
            latestMatrixData
              ?.window
              ?.end_date;

          if (!latestEndDate) {
            return;
          }

          renderMatrixWindow(
            latestEndDate,
            {
              resetFilters: true
            }
          );
        }
      );

      currentButton.dataset.bound =
        "true";
    }

    if (
      nextButton &&
      !nextButton.dataset.bound
    ) {
      nextButton.addEventListener(
        "click",
        () => {
          const latestEndDate =
            latestMatrixData
              ?.window
              ?.end_date;

          const nextEndDate =
            shiftIsoDate(
              currentMatrixEndDate,
              MATRIX_WINDOW_DAYS
            );

          if (
            !nextEndDate ||
            !latestEndDate ||
            nextEndDate > latestEndDate
          ) {
            return;
          }

          renderMatrixWindow(
            nextEndDate,
            {
              resetFilters: true
            }
          );
        }
      );

      nextButton.dataset.bound =
        "true";
    }

    updateMatrixNavigationState();
  }

  function bindAnalystViewButton() {
    const button =
      document.getElementById(
        "analystViewButton"
      );

    const matrix =
      document.getElementById(
        "intelligenceMatrix"
      );

    if (!button || !matrix) {
      return;
    }

    button.addEventListener(
      "click",
      () => {
        matrix.scrollIntoView({
          behavior: "smooth",
          block: "start"
        });
      }
    );
  }

  function bindOverviewTabs() {
    const tabs = [
      ...document.querySelectorAll(
        ".overview-tab"
      )
    ];

    if (!tabs.length) {
      return;
    }

    tabs.forEach(tab => {
      tab.addEventListener(
        "click",
        () => {
          tabs.forEach(item =>
            item.classList.remove(
              "active"
            )
          );

          tab.classList.add(
            "active"
          );

          const mode =
            tab.dataset.overviewMode;

          if (
            mode === "seven-day"
          ) {
            const matrixPanel =
              document.querySelector(
                ".intelligence-matrix-panel"
              );

            matrixPanel?.scrollIntoView({
              behavior: "smooth",
              block: "start"
            });

            return;
          }

          if (
            mode === "history"
          ) {
            const chartPanel =
              document.querySelector(
                ".chart-panel"
              );

            chartPanel?.scrollIntoView({
              behavior: "smooth",
              block: "start"
            });

            return;
          }

          if (
            mode === "current"
          ) {
            const currentPanel =
              document.querySelector(
                ".threat-picture-panel"
              );

            currentPanel?.scrollIntoView({
              behavior: "smooth",
              block: "start"
            });

            return;
          }

          if (
            mode === "daily"
          ) {
            const matrixPanel =
              document.querySelector(
                ".intelligence-matrix-panel"
              );

            matrixPanel?.scrollIntoView({
              behavior: "smooth",
              block: "start"
            });
          }
        }
      );
    });
  }

  try {
    /*
      The main dashboard is the mandatory
      platform data source. If this fails,
      the dashboard cannot operate.
    */
    const dashboardData =
      await BalticAPI.loadDashboardData();

    BalticUI.updateDashboard(
      dashboardData
    );

    BalticChart.initialize(
      dashboardData
    );

    /*
      The current 7-day matrix and the exact-day
      intelligence history are loaded independently.
      The static matrix remains the latest-window
      source, while history enables real Previous /
      Next 7-day navigation in the browser.
    */
    try {
      const [
        matrixData,
        historyData
      ] = await Promise.all([
        BalticAPI.loadMatrixData(),
        loadMatrixHistory()
      ]);

      latestMatrixData =
        matrixData;

      matrixHistory =
        historyData;

      currentMatrixEndDate =
        matrixData.window
          ?.end_date ||
        historyData.last_snapshot_date ||
        null;

      BalticUI.updateMatrix(
        matrixData
      );

      bindMatrixNavigation();

      console.log(
        "7-Day Baltic Intelligence Matrix and history loaded successfully."
      );
    } catch (matrixError) {
      console.error(
        "7-Day Intelligence Matrix loading error:",
        matrixError
      );

      /*
        Preserve the existing dashboard behavior:
        matrix/history failure must not take down
        the current 14-day dashboard.
      */
      try {
        const matrixData =
          await BalticAPI.loadMatrixData();

        latestMatrixData =
          matrixData;

        currentMatrixEndDate =
          matrixData.window
            ?.end_date ||
          null;

        BalticUI.updateMatrix(
          matrixData
        );

        updateMatrixNavigationState();
      } catch (fallbackError) {
        console.error(
          "7-Day Intelligence Matrix fallback loading error:",
          fallbackError
        );

        BalticUI.updateMatrix(
          null
        );
      }
    }

    bindAnalystViewButton();
    bindOverviewTabs();

    console.log(
      "Baltic Hybrid Intelligence Platform loaded successfully."
    );
  } catch (error) {
    console.error(
      "Baltic Hybrid Intelligence Platform loading error:",
      error
    );

    showFatalError(error);
  }
});
