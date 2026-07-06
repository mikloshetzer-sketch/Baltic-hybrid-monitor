window.BalticAPI = (() => {
  const DASHBOARD_URL = "./data/baltic_dashboard.json";

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });

    if (!response.ok) {
      throw new Error(`Failed to load ${url}. Status: ${response.status}`);
    }

    return await response.json();
  }

  function validateDashboardData(data) {
    if (!data) {
      throw new Error("Dashboard data is empty.");
    }

    if (!data.summary) {
      throw new Error("Missing summary block in dashboard data.");
    }

    if (typeof data.summary.threat_index === "undefined") {
      throw new Error("Missing Threat Index summary.");
    }

    if (typeof data.summary.event_count === "undefined") {
      throw new Error("Missing event count summary.");
    }

    if (!Array.isArray(data.subtype_cards)) {
      throw new Error("Missing subtype cards array.");
    }

    if (!Array.isArray(data.country_cards)) {
      throw new Error("Missing country cards array.");
    }

    if (!Array.isArray(data.category_drivers)) {
      throw new Error("Missing category drivers array.");
    }

    if (!Array.isArray(data.actor_drivers)) {
      throw new Error("Missing actor drivers array.");
    }

    if (!Array.isArray(data.top_events)) {
      throw new Error("Missing top events array.");
    }

    if (!data.history) {
      throw new Error("Missing history block in dashboard data.");
    }

    if (!Array.isArray(data.history.labels)) {
      throw new Error("Missing history labels array.");
    }

    if (!Array.isArray(data.history.threat_index)) {
      throw new Error("Missing Threat Index history.");
    }

    return true;
  }

  async function loadDashboardData() {
    const data = await fetchJson(DASHBOARD_URL);
    validateDashboardData(data);
    return data;
  }

  return {
    loadDashboardData
  };
})();
