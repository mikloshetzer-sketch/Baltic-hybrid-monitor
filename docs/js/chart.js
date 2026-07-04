window.BalticChart = (() => {
  let chart = null;
  let currentViewMode = "daily";
  let currentMetricMode = "threat_index";

  const COLORS = {
    overall: "#111827",
    trend: "#64748b",
    Estonia: "#0284c7",
    Latvia: "#f97316",
    Lithuania: "#16a34a",
    Poland: "#dc2626"
  };

  const COUNTRIES = ["Estonia", "Latvia", "Lithuania", "Poland"];

  const METRIC_LABELS = {
    threat_index: "Threat Index",
    daily_activity: "Daily Activity"
  };

  const VIEW_LABELS = {
    daily: "Daily",
    ma7: "7-Day Rolling Average",
    ma14: "14-Day Rolling Average",
    trend: "Regional Linear Trend"
  };

  const METHOD_NOTES = {
    threat_index: {
      daily:
        "Threat Index: each point represents the rolling-window threat assessment ending on the displayed date.",
      ma7:
        "Threat Index: each point represents the 7-day moving average of the rolling-window threat assessment.",
      ma14:
        "Threat Index: each point represents the 14-day moving average of the rolling-window threat assessment.",
      trend:
        "Threat Index: the dashed line represents the linear trend of the regional threat assessment over the selected period."
    },
    daily_activity: {
      daily:
        "Daily Activity: each point represents activity calculated only from items published on the displayed date.",
      ma7:
        "Daily Activity: each point represents the 7-day moving average of daily activity.",
      ma14:
        "Daily Activity: each point represents the 14-day moving average of daily activity.",
      trend:
        "Daily Activity: the dashed line represents the linear trend of regional daily activity over the selected period."
    }
  };

  function getSelectedCountries() {
    return Array.from(
      document.querySelectorAll("#chartControls input:checked")
    ).map(input => input.value);
  }

  function getMetricData(data) {
    const history = data.history || {};
    const metricData = history[currentMetricMode];

    if (!metricData) {
      return {
        labels: history.labels || [],
        overall_average_score: [],
        country_average_scores: {}
      };
    }

    return {
      labels: history.labels || [],
      overall_average_score: metricData.overall_average_score || [],
      country_average_scores: metricData.country_average_scores || {}
    };
  }

  function movingAverage(values, windowSize) {
    return values.map((_, index) => {
      const start = Math.max(0, index - windowSize + 1);
      const slice = values
        .slice(start, index + 1)
        .map(value => Number(value) || 0);

      const average =
        slice.reduce((sum, value) => sum + value, 0) / slice.length;

      return Number(average.toFixed(2));
    });
  }

  function calculateLinearTrend(values) {
    const cleanValues = values.map(value => Number(value) || 0);
    const n = cleanValues.length;

    if (n < 2) return cleanValues;

    let sumX = 0;
    let sumY = 0;
    let sumXY = 0;
    let sumXX = 0;

    cleanValues.forEach((y, x) => {
      sumX += x;
      sumY += y;
      sumXY += x * y;
      sumXX += x * x;
    });

    const denominator = n * sumXX - sumX * sumX;

    if (denominator === 0) return cleanValues;

    const slope = (n * sumXY - sumX * sumY) / denominator;
    const intercept = (sumY - slope * sumX) / n;

    return cleanValues.map((_, x) =>
      Number((intercept + slope * x).toFixed(2))
    );
  }

  function transformValues(values) {
    if (currentViewMode === "ma7") {
      return movingAverage(values, 7);
    }

    if (currentViewMode === "ma14") {
      return movingAverage(values, 14);
    }

    return values;
  }

  function updateMethodNote() {
    const note = document.getElementById("chartMethodNote");
    if (!note) return;

    const metricNotes = METHOD_NOTES[currentMetricMode] || METHOD_NOTES.threat_index;
    note.textContent = metricNotes[currentViewMode] || metricNotes.daily;
  }

  function updateHeaderText() {
    const title = document.getElementById("chartTitle");
    const subtitle = document.getElementById("chartSubtitle");

    if (title) {
      title.textContent = `${METRIC_LABELS[currentMetricMode]} Trend`;
    }

    if (subtitle) {
      subtitle.textContent =
        currentMetricMode === "threat_index"
          ? "Threat Index shows the current assessed hybrid threat level across the monitored region."
          : "Daily Activity shows how much hybrid-related activity was detected on each displayed date.";
    }
  }

  function updateMetricSummary(data) {
    const summary = data.summary || {};
    const selectedSummary = summary[currentMetricMode] || {};

    const scoreLabel = document.getElementById("scoreCardLabel");
    const incidentLabel = document.getElementById("incidentCardLabel");
    const levelLabel = document.getElementById("levelCardLabel");

    const scoreValue = document.getElementById("overallScore");
    const incidentValue = document.getElementById("incidentCount");
    const levelValue = document.getElementById("overallLevel");

    if (scoreLabel) {
      scoreLabel.textContent =
        currentMetricMode === "threat_index"
          ? "Threat Index"
          : "Daily Activity Score";
    }

    if (incidentLabel) {
      incidentLabel.textContent =
        currentMetricMode === "threat_index"
          ? "Incidents in window"
          : "Daily incidents";
    }

    if (levelLabel) {
      levelLabel.textContent =
        currentMetricMode === "threat_index"
          ? "Threat level"
          : "Activity level";
    }

    if (scoreValue) {
      const value = selectedSummary.average_score;
      scoreValue.textContent =
        typeof value === "number" ? value.toFixed(2) : "—";
    }

    if (incidentValue) {
      incidentValue.textContent =
        selectedSummary.incident_count ?? "—";
    }

    if (levelValue) {
      levelValue.textContent =
        selectedSummary.overall_level
          ? String(selectedSummary.overall_level).toUpperCase()
          : "—";
    }
  }

  function createDatasets(metricData, selectedCountries) {
    const datasets = [];

    if (currentViewMode === "trend") {
      datasets.push({
        label: `${METRIC_LABELS[currentMetricMode]} — Regional Linear Trend`,
        data: calculateLinearTrend(metricData.overall_average_score),
        borderColor: COLORS.trend,
        backgroundColor: COLORS.trend,
        borderWidth: 3,
        borderDash: [8, 6],
        pointRadius: 0,
        pointHoverRadius: 0,
        tension: 0
      });

      return datasets;
    }

    if (selectedCountries.includes("overall")) {
      datasets.push({
        label: `${METRIC_LABELS[currentMetricMode]} — Regional Average`,
        data: transformValues(metricData.overall_average_score),
        borderColor: COLORS.overall,
        backgroundColor: COLORS.overall,
        borderWidth: 3,
        pointRadius: 3,
        pointHoverRadius: 6,
        tension: 0.32
      });
    }

    COUNTRIES.forEach(country => {
      if (!selectedCountries.includes(country)) return;

      const values = metricData.country_average_scores[country] || [];

      datasets.push({
        label: country,
        data: transformValues(values),
        borderColor: COLORS[country],
        backgroundColor: COLORS[country],
        borderWidth: 2,
        pointRadius: 3,
        pointHoverRadius: 5,
        tension: 0.32
      });
    });

    return datasets;
  }

  function render(data) {
    const metricData = getMetricData(data);
    const canvas = document.getElementById("threatTrendChart");

    if (!canvas) return;

    const ctx = canvas.getContext("2d");

    updateMethodNote();
    updateHeaderText();
    updateMetricSummary(data);

    if (chart) {
      chart.destroy();
    }

    chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: metricData.labels,
        datasets: createDatasets(metricData, getSelectedCountries())
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false
        },
        plugins: {
          title: {
            display: true,
            text: `${METRIC_LABELS[currentMetricMode]} — ${VIEW_LABELS[currentViewMode]}`,
            color: "#111827",
            font: {
              size: 14,
              weight: "bold"
            },
            padding: {
              bottom: 12
            }
          },
          legend: {
            position: "top",
            labels: {
              color: "#111827",
              usePointStyle: true,
              boxWidth: 12,
              padding: 18,
              font: {
                size: 12,
                weight: "bold"
              }
            }
          },
          tooltip: {
            backgroundColor: "#0b1628",
            borderColor: "#38bdf8",
            borderWidth: 1,
            titleColor: "#ffffff",
            bodyColor: "#ffffff",
            callbacks: {
              label: function(context) {
                return `${context.dataset.label}: ${context.raw}`;
              }
            }
          }
        },
        scales: {
          x: {
            ticks: {
              color: "#475569",
              maxRotation: 0,
              autoSkip: true,
              font: {
                size: 11,
                weight: "bold"
              }
            },
            grid: {
              color: "rgba(148, 163, 184, 0.28)"
            }
          },
          y: {
            beginAtZero: true,
            ticks: {
              color: "#475569",
              font: {
                size: 11,
                weight: "bold"
              }
            },
            grid: {
              color: "rgba(148, 163, 184, 0.28)"
            },
            title: {
              display: true,
              text:
                currentMetricMode === "threat_index"
                  ? "Threat Index Score"
                  : "Daily Activity Score",
              color: "#334155",
              font: {
                size: 12,
                weight: "bold"
              }
            }
          }
        }
      }
    });
  }

  function setActiveViewButton(mode) {
    document.querySelectorAll(".mode-btn").forEach(button => {
      button.classList.toggle("active", button.dataset.mode === mode);
    });
  }

  function setupMetricControls(data) {
    document.querySelectorAll('input[name="metricMode"]').forEach(input => {
      input.addEventListener("change", () => {
        currentMetricMode = input.value || "threat_index";
        render(data);
      });
    });
  }

  function setupViewButtons(data) {
    document.querySelectorAll(".mode-btn").forEach(button => {
      button.addEventListener("click", () => {
        currentViewMode = button.dataset.mode || "daily";
        setActiveViewButton(currentViewMode);
        render(data);
      });
    });
  }

  function setupCheckboxes(data) {
    document.querySelectorAll("#chartControls input").forEach(input => {
      input.addEventListener("change", () => {
        render(data);
      });
    });
  }

  function initialize(data) {
    setActiveViewButton(currentViewMode);
    render(data);
    setupMetricControls(data);
    setupViewButtons(data);
    setupCheckboxes(data);
  }

  return {
    initialize
  };
})();
