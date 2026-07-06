window.BalticChart = (() => {
  let chart = null;
  let currentViewMode = "daily";
  let currentMetricMode = "threat_index";

  const COLORS = {
    overall: "#0f172a",
    trend: "#64748b",
    incident: "#dc2626",
    activity: "#ea580c",
    indicator: "#0891b2",
    assessment: "#64748b",
    Estonia: "#0284c7",
    Latvia: "#ea580c",
    Lithuania: "#16a34a",
    Poland: "#dc2626",
    Regional: "#7c3aed"
  };

  const COUNTRIES = ["Estonia", "Latvia", "Lithuania", "Poland", "Regional"];

  const METRIC_LABELS = {
    threat_index: "Threat Index",
    daily_activity: "Event Activity"
  };

  const VIEW_LABELS = {
    daily: "Daily",
    ma7: "7-Day Moving Average",
    ma14: "14-Day Moving Average",
    trend: "Regional Linear Trend"
  };

  const METHOD_NOTES = {
    threat_index: {
      daily: "Threat Index: each point represents the event-based operational threat index for the displayed date.",
      ma7: "Threat Index: each point represents the 7-day moving average of the event-based threat index.",
      ma14: "Threat Index: each point represents the 14-day moving average of the event-based threat index.",
      trend: "Threat Index: the dashed line represents the linear trend of the regional threat index over the selected period."
    },
    daily_activity: {
      daily: "Event Activity: each point shows classified events by subtype on the displayed date.",
      ma7: "Event Activity: each point represents the 7-day moving average of classified event activity.",
      ma14: "Event Activity: each point represents the 14-day moving average of classified event activity.",
      trend: "Event Activity: the dashed line represents the linear trend of total operational activity over the selected period."
    }
  };

  function numberOrZero(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : 0;
  }

  function titleCase(value) {
    return String(value || "").replaceAll("_", " ").replace(/\b\w/g, character => character.toUpperCase());
  }

  function getSelectedCountries() {
    const inputs = Array.from(document.querySelectorAll("#chartControls input:checked"));
    return inputs.length === 0 ? ["overall"] : inputs.map(input => input.value);
  }

  function buildMetricData(data) {
    const history = data.history || {};
    const labels = Array.isArray(history.labels) ? history.labels : [];

    if (currentMetricMode === "daily_activity") {
      return {
        labels,
        overall_average_score: (history.incident_count || []).map((value, index) =>
          numberOrZero(value) + numberOrZero((history.activity_count || [])[index]) + numberOrZero((history.indicator_count || [])[index])
        ),
        subtype_scores: {
          incident: history.incident_count || [],
          activity: history.activity_count || [],
          indicator: history.indicator_count || [],
          assessment: history.assessment_count || []
        },
        country_average_scores: history.country_scores || {}
      };
    }

    return {
      labels,
      overall_average_score: history.threat_index || [],
      subtype_scores: {
        incident: history.incident_count || [],
        activity: history.activity_count || [],
        indicator: history.indicator_count || [],
        assessment: history.assessment_count || []
      },
      country_average_scores: history.country_scores || {}
    };
  }

  function movingAverage(values, windowSize) {
    return values.map((_, index) => {
      const start = Math.max(0, index - windowSize + 1);
      const slice = values.slice(start, index + 1).map(value => numberOrZero(value));
      const average = slice.reduce((sum, value) => sum + value, 0) / Math.max(slice.length, 1);
      return Number(average.toFixed(2));
    });
  }

  function calculateLinearTrend(values) {
    const cleanValues = values.map(value => numberOrZero(value));
    const n = cleanValues.length;
    if (n < 2) return cleanValues;

    let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
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

    return cleanValues.map((_, x) => Number((intercept + slope * x).toFixed(2)));
  }

  function transformValues(values) {
    const cleanValues = (values || []).map(value => numberOrZero(value));
    if (currentViewMode === "ma7") return movingAverage(cleanValues, 7);
    if (currentViewMode === "ma14") return movingAverage(cleanValues, 14);
    return cleanValues;
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

    if (title) title.textContent = `${METRIC_LABELS[currentMetricMode]} Trend`;

    if (subtitle) {
      subtitle.textContent =
        currentMetricMode === "threat_index"
          ? "Threat Index shows the current event-based operational hybrid threat level across the monitored region."
          : "Event Activity shows incidents, activities, indicators and assessments detected in the OSINT pipeline.";
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

    if (currentMetricMode === "daily_activity") {
      ["incident", "activity", "indicator", "assessment"].forEach(subtype => {
        datasets.push({
          label: titleCase(subtype),
          data: transformValues(metricData.subtype_scores[subtype] || []),
          borderColor: COLORS[subtype],
          backgroundColor: COLORS[subtype],
          borderWidth: subtype === "incident" ? 3 : 2,
          pointRadius: 3,
          pointHoverRadius: 6,
          tension: 0.32
        });
      });
      return datasets;
    }

    if (selectedCountries.includes("overall")) {
      datasets.push({
        label: "Threat Index — Regional",
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
        borderColor: COLORS[country] || COLORS.trend,
        backgroundColor: COLORS[country] || COLORS.trend,
        borderWidth: 2,
        pointRadius: 3,
        pointHoverRadius: 5,
        tension: 0.32
      });
    });

    return datasets;
  }

  function render(data) {
    const metricData = buildMetricData(data);
    const canvas = document.getElementById("threatTrendChart");
    if (!canvas) return;

    updateMethodNote();
    updateHeaderText();

    if (chart) chart.destroy();

    chart = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels: metricData.labels,
        datasets: createDatasets(metricData, getSelectedCountries())
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          title: {
            display: true,
            text: `${METRIC_LABELS[currentMetricMode]} — ${VIEW_LABELS[currentViewMode]}`,
            color: "#0f172a",
            font: { size: 14, weight: "bold" },
            padding: { bottom: 12 }
          },
          legend: {
            position: "top",
            labels: {
              color: "#0f172a",
              usePointStyle: true,
              boxWidth: 12,
              padding: 18,
              font: { size: 12, weight: "bold" }
            }
          },
          tooltip: {
            backgroundColor: "#020817",
            borderColor: "#38bdf8",
            borderWidth: 1,
            titleColor: "#ffffff",
            bodyColor: "#ffffff",
            callbacks: { label: context => `${context.dataset.label}: ${context.raw}` }
          }
        },
        scales: {
          x: {
            ticks: {
              color: "#334155",
              maxRotation: 0,
              autoSkip: true,
              font: { size: 11, weight: "bold" }
            },
            grid: { color: "rgba(148, 163, 184, 0.20)" }
          },
          y: {
            beginAtZero: true,
            ticks: {
              color: "#334155",
              font: { size: 11, weight: "bold" }
            },
            grid: { color: "rgba(148, 163, 184, 0.22)" },
            title: {
              display: true,
              text: currentMetricMode === "threat_index" ? "Threat Index Score" : "Event Count",
              color: "#475569",
              font: { size: 12, weight: "bold" }
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
      input.addEventListener("change", () => render(data));
    });
  }

  function initialize(data) {
    setActiveViewButton(currentViewMode);
    render(data);
    setupMetricControls(data);
    setupViewButtons(data);
    setupCheckboxes(data);
  }

  return { initialize };
})();
