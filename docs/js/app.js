document.addEventListener("DOMContentLoaded", async () => {
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
      The 7-day exact-day matrix is loaded
      independently. A matrix failure must
      not take down the current 14-day
      dashboard or the historical chart.
    */
    try {
      const matrixData =
        await BalticAPI.loadMatrixData();

      BalticUI.updateMatrix(
        matrixData
      );

      console.log(
        "7-Day Baltic Intelligence Matrix loaded successfully."
      );
    } catch (matrixError) {
      console.error(
        "7-Day Intelligence Matrix loading error:",
        matrixError
      );

      BalticUI.updateMatrix(
        null
      );
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
