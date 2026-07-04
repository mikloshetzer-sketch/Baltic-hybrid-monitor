const BalticChart = (() => {
  let chart = null;
  let currentMode = "daily";

  const COLORS = {
    overall: "#111827",
    trend: "#64748b",
    Estonia: "#0284c7",
    Latvia: "#f97316",
    Lithuania: "#16a34a",
    Poland: "#dc2626"
  };

  const MODE_LABELS = {
    daily: "Daily",
    ma7: "7-Day Rolling Average",
    ma14: "14-Day Rolling Average",
    trend: "Regional Linear Trend"
  };

  const MODE_NOTES = {
    daily:
      "Each point represents the hybrid threat score calculated for the displayed date.",
    ma7:
      "Each point represents the 7-day rolling average ending on the displayed date.",
    ma14:
      "Each point represents the 14-day rolling average ending on the displayed date.",
    trend:
      "The dashed line represents the linear trend of the regional average over the selected period."
  };

  function getSelectedSeries() {
    return Array.from(
      document.querySelectorAll("#chartControls input:checked")
    ).map(item => item.value);
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
    if (currentMode === "ma7") {
      return movingAverage(values, 7);
    }

    if (currentMode === "ma14") {
      return movingAverage(values, 14);
    }

    return values;
  }

  function updateMethodNote() {
    const note = document.getElementById("chartMethodNote");

    if (!note) return;

    note.textContent = MODE_NOTES[currentMode] || MODE_NOTES.daily;
  }

  function createDatasets(history, selected) {
    if (currentMode === "trend") {
      return [
        {
          label: "Regional Linear Trend",
          data: calculateLinearTrend(history.overall_average_score),
          borderColor: COLORS.trend,
          backgroundColor: COLORS.trend,
          borderWidth: 3,
          borderDash: [8, 6],
          pointRadius: 0,
          pointHoverRadius: 0,
          tension: 0
        }
      ];
    }

    const datasets = [];

    if (selected.includes("overall")) {
      datasets.push({
        label: "Regional Average",
        data: transformValues(history.overall_average_score),
        borderColor: COLORS.overall,
        backgroundColor: COLORS.overall,
        borderWidth: 3,
        pointRadius: 3,
        pointHoverRadius: 6,
        tension: 0.32
      });
    }

    Object.keys(history.country_average_scores).forEach(country => {
      if (!selected.includes(country)) return;

      datasets.push({
        label: country,
        data: transformValues(history.country_average_scores[country]),
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
    const history = data.history;
    const canvas = document.getElementById("threatTrendChart");
    const ctx = canvas.getContext("2d");

    updateMethodNote();

    if (chart) {
      chart.destroy();
    }

    chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: history.labels,
        datasets: createDatasets(history, getSelectedSeries())
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
            text: `Hybrid Threat Score — ${MODE_LABELS[currentMode]}`,
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
              text: "Hybrid Threat Score",
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

  function setActiveModeButton(mode) {
    document.querySelectorAll(".mode-btn").forEach(button => {
      button.classList.toggle("active", button.dataset.mode === mode);
    });
  }

  function setupModeButtons(data) {
    document.querySelectorAll(".mode-btn").forEach(button => {
      button.addEventListener("click", () => {
        currentMode = button.dataset.mode || "daily";
        setActiveModeButton(currentMode);
        render(data);
      });
    });
  }

  function setupCheckboxes(data) {
    document.querySelectorAll("#chartControls input").forEach(item => {
      item.addEventListener("change", () => {
        render(data);
      });
    });
  }

  function initialize(data) {
    setActiveModeButton(currentMode);
    render(data);
    setupModeButtons(data);
    setupCheckboxes(data);
  }

  return {
    initialize
  };
})();
