window.BalticAPI = (() => {
  const DASHBOARD_URL = "./data/baltic_dashboard.json";
  const MATRIX_URL = "./data/baltic_7day_matrix.json";

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });

    if (!response.ok) {
      throw new Error(
        `Failed to load ${url}. Status: ${response.status}`
      );
    }

    return await response.json();
  }

  function validateDashboardData(data) {
    if (!data) {
      throw new Error("Dashboard data is empty.");
    }

    if (!data.summary) {
      throw new Error(
        "Missing summary block in dashboard data."
      );
    }

    if (
      typeof data.summary.threat_index ===
      "undefined"
    ) {
      throw new Error(
        "Missing Threat Index summary."
      );
    }

    if (
      typeof data.summary.event_count ===
      "undefined"
    ) {
      throw new Error(
        "Missing event count summary."
      );
    }

    if (
      !Array.isArray(
        data.subtype_cards
      )
    ) {
      throw new Error(
        "Missing subtype cards array."
      );
    }

    if (
      !Array.isArray(
        data.country_cards
      )
    ) {
      throw new Error(
        "Missing country cards array."
      );
    }

    if (
      !Array.isArray(
        data.category_drivers
      )
    ) {
      throw new Error(
        "Missing category drivers array."
      );
    }

    if (
      !Array.isArray(
        data.actor_drivers
      )
    ) {
      throw new Error(
        "Missing actor drivers array."
      );
    }

    if (
      !Array.isArray(
        data.top_events
      )
    ) {
      throw new Error(
        "Missing top events array."
      );
    }

    if (!data.history) {
      throw new Error(
        "Missing history block in dashboard data."
      );
    }

    if (
      !Array.isArray(
        data.history.labels
      )
    ) {
      throw new Error(
        "Missing history labels array."
      );
    }

    if (
      !Array.isArray(
        data.history.threat_index
      )
    ) {
      throw new Error(
        "Missing Threat Index history."
      );
    }

    return true;
  }

  function validateMatrixData(data) {
    if (!data) {
      throw new Error(
        "7-day matrix data is empty."
      );
    }

    if (
      data.matrix_version !==
      "baltic_7day_matrix_v1_0"
    ) {
      throw new Error(
        "Unsupported or missing 7-day matrix version."
      );
    }

    if (!data.window) {
      throw new Error(
        "Missing window block in 7-day matrix data."
      );
    }

    if (
      data.window.window_days !== 7
    ) {
      throw new Error(
        "7-day matrix window must contain seven calendar days."
      );
    }

    if (
      !data.window.start_date ||
      !data.window.end_date
    ) {
      throw new Error(
        "Missing matrix window start or end date."
      );
    }

    if (!data.coverage) {
      throw new Error(
        "Missing coverage block in 7-day matrix data."
      );
    }

    if (
      typeof data.coverage.available_days ===
      "undefined"
    ) {
      throw new Error(
        "Missing available-day count in 7-day matrix data."
      );
    }

    if (
      typeof data.coverage.missing_days ===
      "undefined"
    ) {
      throw new Error(
        "Missing missing-day count in 7-day matrix data."
      );
    }

    if (
      !Array.isArray(
        data.missing_dates
      )
    ) {
      throw new Error(
        "Missing missing_dates array in 7-day matrix data."
      );
    }

    if (
      !Array.isArray(
        data.daily_matrix
      )
    ) {
      throw new Error(
        "Missing daily_matrix array."
      );
    }

    if (
      data.daily_matrix.length !== 7
    ) {
      throw new Error(
        "daily_matrix must contain exactly seven calendar-day slots."
      );
    }

    const validStatuses = new Set([
      "available",
      "missing"
    ]);

    data.daily_matrix.forEach(
      (day, index) => {
        if (!day) {
          throw new Error(
            `Matrix day ${index + 1} is empty.`
          );
        }

        if (!day.date) {
          throw new Error(
            `Matrix day ${index + 1} is missing a date.`
          );
        }

        if (
          !validStatuses.has(
            day.status
          )
        ) {
          throw new Error(
            `Invalid matrix status for ${day.date}: ${day.status}`
          );
        }

        if (
          day.status === "missing" &&
          day.threat_index !== null
        ) {
          throw new Error(
            `Missing matrix day ${day.date} must use null Threat Index.`
          );
        }
      }
    );

    return true;
  }

  async function loadDashboardData() {
    const data = await fetchJson(
      DASHBOARD_URL
    );

    validateDashboardData(
      data
    );

    return data;
  }

  async function loadMatrixData() {
    const data = await fetchJson(
      MATRIX_URL
    );

    validateMatrixData(
      data
    );

    return data;
  }

  async function loadPlatformData() {
    const [
      dashboard,
      matrix
    ] = await Promise.all([
      loadDashboardData(),
      loadMatrixData()
    ]);

    return {
      dashboard,
      matrix
    };
  }

  return {
    loadDashboardData,
    loadMatrixData,
    loadPlatformData
  };
})();

