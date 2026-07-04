const BalticAPI = (() => {
  const DASHBOARD_URL = "./data/baltic_dashboard.json";

  async function fetchJson(url) {
    const response = await fetch(url, {
      cache: "no-store"
    });

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

    if (!data.history) {
      throw new Error("Missing history block in dashboard data.");
    }

    if (!Array.isArray(data.history.labels)) {
      throw new Error("Missing history labels array.");
    }

    if (!Array.isArray(data.history.overall_average_score)) {
      throw new Error("Missing overall average score history.");
    }

    if (!data.history.country_average_scores) {
      throw new Error("Missing country average scores.");
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
