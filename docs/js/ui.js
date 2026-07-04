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

  function setText(id, value) {
    const element = document.getElementById(id);
    if (!element) return;
    element.textContent = value;
  }

  function updateHeader(data) {
    setText("lastUpdate", formatDate(data.latest_update || data.generated_at));
  }

  function updateDashboard(data) {
    updateHeader(data);
  }

  return {
    updateDashboard
  };
})();
