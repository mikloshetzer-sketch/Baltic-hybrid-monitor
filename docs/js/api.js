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

    if (!data.summary.threat_index) {
      throw new Error("Missing Threat Index summary.");
    }

    if (!data.summary.daily_activity) {
      throw new Error("Missing Daily Activity summary.");
    }

    if (!data.history) {
      throw new Error("Missing history block in dashboard data.");
    }

    if (!Array.isArray(data.history.labels)) {
      throw new Error("Missing history labels array.");
    }

    if (!data.history.threat_index) {
      throw new Error("Missing Threat Index history.");
    }

    if (!data.history.daily_activity) {
      throw new Error("Missing Daily Activity history.");
    }

    if (!Array.isArray(data.history.threat_index.overall_average_score)) {
      throw new Error("Missing Threat Index overall score history.");
    }

    if (!Array.isArray(data.history.daily_activity.overall_average_score)) {
      throw new Error("Missing Daily Activity overall score history.");
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
