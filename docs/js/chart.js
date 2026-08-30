window.BalticChart = (() => {
  let chart = null;
  let currentViewMode = "daily";
  let currentMetricMode = "threat_index";
  let controlsInitialized = false;

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

  const COUNTRIES = [
    "Estonia",
    "Latvia",
    "Lithuania",
    "Poland",
    "Regional"
  ];

  const METRIC_LABELS = {
    threat_index: "Threat Index",
    daily_activity: "Event Activity"
  };

  const VIEW_LABELS = {
    daily: "Daily",
    ma7: "7-Day Moving Average",
    ma14: "Historical 14-Day Threat Index",
    trend: "Regional Linear Trend"
  };

  const METHOD_NOTES = {
    threat_index: {
      daily:
        "Threat Index: each point is the historical daily Threat Index stored for that date. This chart is separate from the current 14-day threat picture.",
      ma7:
        "Threat Index: each point is a chart-only 7-day moving average calculated from the historical daily Threat Index series. It is not the 7-Day Intelligence Matrix.",
      ma14:
        "Historical 14-Day Threat Index: each point is the v3.2 Threat Index calculated over the 14 calendar days ending on that historical date. The latest point is directly comparable with the current 14-day Threat Index.",
      trend:
        "Threat Index: the dashed line is a linear trend fitted to the historical daily Threat Index series."
    },
    daily_activity: {
      daily:
        "Event Activity: each point shows the classified exact-day event counts stored in history, separated by subtype.",
      ma7:
        "Event Activity: each point is a chart-only 7-day moving average of historical classified event counts.",
      ma14:
        "Event Activity: each point is a chart-only 14-day moving average of historical classified event counts.",
      trend:
        "Event Activity: the dashed line is a linear trend fitted to total historical classified event activity."
    }
  };

  function numberOrNull(value) {
    if (
      value === null ||
      typeof value === "undefined" ||
      value === ""
    ) {
      return null;
    }

    const number = Number(value);

    return Number.isFinite(number)
      ? number
      : null;
  }

  function numberOrZero(value) {
    const number = Number(value);
    return Number.isFinite(number)
      ? number
      : 0;
  }

  function titleCase(value) {
    return String(value || "")
      .replaceAll("_", " ")
      .replace(
        /\b\w/g,
        character =>
          character.toUpperCase()
      );
  }

  function getSelectedCountries() {
    const inputs = Array.from(
      document.querySelectorAll(
        "#chartControls input:checked"
      )
    );

    return inputs.length === 0
      ? ["overall"]
      : inputs.map(
          input => input.value
        );
  }

  function normalizeSeries(
    values,
    expectedLength
  ) {
    const source = Array.isArray(values)
      ? values
      : [];

    return Array.from(
      { length: expectedLength },
      (_, index) =>
        numberOrNull(source[index])
    );
  }

  function sumNullableSeries(
    seriesList,
    length
  ) {
    return Array.from(
      { length },
      (_, index) => {
        const values =
          seriesList.map(series =>
            numberOrNull(
              series[index]
            )
          );

        const available =
          values.filter(
            value => value !== null
          );

        if (!available.length) {
          return null;
        }

        return available.reduce(
          (sum, value) =>
            sum + value,
          0
        );
      }
    );
  }

  function buildMetricData(data) {
    const history =
      data.history || {};

    const labels =
      Array.isArray(history.labels)
        ? history.labels
        : [];

    const length =
      labels.length;

    const incident =
      normalizeSeries(
        history.incident_count,
        length
      );

    const activity =
      normalizeSeries(
        history.activity_count,
        length
      );

    const indicator =
      normalizeSeries(
        history.indicator_count,
        length
      );

    const assessment =
      normalizeSeries(
        history.assessment_count,
        length
      );

    const countryScores = {};

    Object.entries(
      history.country_scores || {}
    ).forEach(
      ([country, values]) => {
        countryScores[country] =
          normalizeSeries(
            values,
            length
          );
      }
    );

    if (
      currentMetricMode ===
      "daily_activity"
    ) {
      return {
        labels,
        overall_average_score:
          sumNullableSeries(
            [
              incident,
              activity,
              indicator
            ],
            length
          ),
        subtype_scores: {
          incident,
          activity,
          indicator,
          assessment
        },
        country_average_scores:
          countryScores
      };
    }

    const rollingCountryScores = {};

    Object.entries(
      history
        .rolling_country_scores ||
      {}
    ).forEach(
      ([country, values]) => {
        rollingCountryScores[
          country
        ] =
          normalizeSeries(
            values,
            length
          );
      }
    );

    return {
      labels,
      overall_average_score:
        normalizeSeries(
          history.threat_index,
          length
        ),
      rolling_threat_index:
        normalizeSeries(
          history
            .rolling_threat_index,
          length
        ),
      subtype_scores: {
        incident,
        activity,
        indicator,
        assessment
      },
      country_average_scores:
        countryScores,
      rolling_country_scores:
        rollingCountryScores
    };
  }

  function movingAverage(
    values,
    windowSize
  ) {
    const source =
      Array.isArray(values)
        ? values
        : [];

    return source.map(
      (_, index) => {
        if (
          index <
          windowSize - 1
        ) {
          return null;
        }

        const slice =
          source
            .slice(
              index -
                windowSize +
                1,
              index + 1
            )
            .map(numberOrNull);

        const hasCompleteWindow =
          slice.length ===
            windowSize &&
          slice.every(
            value =>
              value !== null
          );

        if (!hasCompleteWindow) {
          return null;
        }

        const average =
          slice.reduce(
            (sum, value) =>
              sum + value,
            0
          ) / windowSize;

        return Number(
          average.toFixed(2)
        );
      }
    );
  }

  function calculateLinearTrend(
    values
  ) {
    const points =
      (values || [])
        .map(
          (value, index) => ({
            x: index,
            y: numberOrNull(
              value
            )
          })
        )
        .filter(
          point =>
            point.y !== null
        );

    if (!points.length) {
      return (values || []).map(
        () => null
      );
    }

    if (points.length === 1) {
      return (values || []).map(
        (_, index) =>
          index ===
          points[0].x
            ? points[0].y
            : null
      );
    }

    const n =
      points.length;

    let sumX = 0;
    let sumY = 0;
    let sumXY = 0;
    let sumXX = 0;

    points.forEach(
      ({ x, y }) => {
        sumX += x;
        sumY += y;
        sumXY += x * y;
        sumXX += x * x;
      }
    );

    const denominator =
      n * sumXX -
      sumX * sumX;

    if (
      denominator === 0
    ) {
      return (values || []).map(
        value =>
          numberOrNull(value)
      );
    }

    const slope =
      (
        n * sumXY -
        sumX * sumY
      ) / denominator;

    const intercept =
      (
        sumY -
        slope * sumX
      ) / n;

    return (values || []).map(
      (_, x) =>
        Number(
          (
            intercept +
            slope * x
          ).toFixed(2)
        )
    );
  }

  function transformValues(
    values,
    historical14DayValues = null
  ) {
    const cleanValues =
      (values || []).map(
        numberOrNull
      );

    if (
      currentViewMode === "ma7"
    ) {
      return movingAverage(
        cleanValues,
        7
      );
    }

    if (
      currentViewMode === "ma14"
    ) {
      if (
        currentMetricMode ===
          "threat_index" &&
        Array.isArray(
          historical14DayValues
        )
      ) {
        return historical14DayValues
          .map(numberOrNull);
      }

      return movingAverage(
        cleanValues,
        14
      );
    }

    return cleanValues;
  }

  function updateViewButtonLabels() {
    const ma14Button =
      document.querySelector(
        '.mode-btn[data-mode="ma14"]'
      );

    if (ma14Button) {
      ma14Button.textContent =
        currentMetricMode ===
        "threat_index"
          ? "Historical 14-Day Threat Index"
          : "14-Day Moving Average";
    }
  }

  function getViewLabel() {
    if (
      currentViewMode === "ma14" &&
      currentMetricMode ===
        "daily_activity"
    ) {
      return "14-Day Moving Average";
    }

    return VIEW_LABELS[
      currentViewMode
    ];
  }

  function updateMethodNote() {
    const note =
      document.getElementById(
        "chartMethodNote"
      );

    if (!note) {
      return;
    }

    const metricNotes =
      METHOD_NOTES[
        currentMetricMode
      ] ||
      METHOD_NOTES.threat_index;

    note.textContent =
      metricNotes[
        currentViewMode
      ] ||
      metricNotes.daily;
  }

  function updateHeaderText() {
    const title =
      document.getElementById(
        "chartTitle"
      );

    const subtitle =
      document.getElementById(
        "chartSubtitle"
      );

    if (title) {
      title.textContent =
        `${
          METRIC_LABELS[
            currentMetricMode
          ]
        } Trend`;
    }

    if (subtitle) {
      subtitle.textContent =
        currentMetricMode ===
        "threat_index"
          ? "Historical daily Threat Index across the monitored Baltic region. The current threat picture is calculated separately over the latest 14 calendar days."
          : "Historical exact-day classified event activity: incidents, activities, indicators and assessments.";
    }
  }

  function createDatasets(
    metricData,
    selectedCountries
  ) {
    const datasets = [];

    if (
      currentViewMode === "trend"
    ) {
      datasets.push({
        label:
          `${
            METRIC_LABELS[
              currentMetricMode
            ]
          } — Regional Linear Trend`,
        data:
          calculateLinearTrend(
            metricData
              .overall_average_score
          ),
        borderColor:
          COLORS.trend,
        backgroundColor:
          COLORS.trend,
        borderWidth: 3,
        borderDash: [8, 6],
        pointRadius: 0,
        pointHoverRadius: 0,
        tension: 0,
        spanGaps: false
      });

      return datasets;
    }

    if (
      currentMetricMode ===
      "daily_activity"
    ) {
      [
        "incident",
        "activity",
        "indicator",
        "assessment"
      ].forEach(
        subtype => {
          datasets.push({
            label:
              titleCase(
                subtype
              ),
            data:
              transformValues(
                metricData
                  .subtype_scores[
                    subtype
                  ] || []
              ),
            borderColor:
              COLORS[subtype],
            backgroundColor:
              COLORS[subtype],
            borderWidth:
              subtype ===
              "incident"
                ? 3
                : 2,
            pointRadius: 3,
            pointHoverRadius: 6,
            tension: 0.28,
            spanGaps: false
          });
        }
      );

      return datasets;
    }

    if (
      selectedCountries.includes(
        "overall"
      )
    ) {
      datasets.push({
        label:
          "Threat Index — Regional",
        data:
          transformValues(
            metricData
              .overall_average_score,
            metricData
              .rolling_threat_index
          ),
        borderColor:
          COLORS.overall,
        backgroundColor:
          COLORS.overall,
        borderWidth: 3,
        pointRadius: 3,
        pointHoverRadius: 6,
        tension: 0.28,
        spanGaps: false
      });
    }

    COUNTRIES.forEach(
      country => {
        if (
          !selectedCountries.includes(
            country
          )
        ) {
          return;
        }

        const values =
          metricData
            .country_average_scores[
              country
            ] || [];

        datasets.push({
          label: country,
          data:
            transformValues(
              values,
              metricData
                .rolling_country_scores?.[
                  country
                ]
            ),
          borderColor:
            COLORS[country] ||
            COLORS.trend,
          backgroundColor:
            COLORS[country] ||
            COLORS.trend,
          borderWidth: 2,
          pointRadius: 3,
          pointHoverRadius: 5,
          tension: 0.28,
          spanGaps: false
        });
      }
    );

    return datasets;
  }

  function getYAxisMax() {
    if (
      currentMetricMode ===
      "threat_index"
    ) {
      return 100;
    }

    return undefined;
  }

  function render(data) {
    const metricData =
      buildMetricData(data);

    const canvas =
      document.getElementById(
        "threatTrendChart"
      );

    if (!canvas) {
      return;
    }

    if (
      typeof Chart ===
      "undefined"
    ) {
      console.error(
        "Chart.js is not available."
      );
      return;
    }

    updateViewButtonLabels();
    updateMethodNote();
    updateHeaderText();

    if (chart) {
      chart.destroy();
    }

    chart = new Chart(
      canvas.getContext("2d"),
      {
        type: "line",
        data: {
          labels:
            metricData.labels,
          datasets:
            createDatasets(
              metricData,
              getSelectedCountries()
            )
        },
        options: {
          responsive: true,
          maintainAspectRatio:
            false,
          interaction: {
            mode: "index",
            intersect: false
          },
          plugins: {
            title: {
              display: true,
              text:
                `${
                  METRIC_LABELS[
                    currentMetricMode
                  ]
                } — ${
                  getViewLabel()
                }`,
              color: "#0f172a",
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
                color: "#0f172a",
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
              backgroundColor:
                "#020817",
              borderColor:
                "#38bdf8",
              borderWidth: 1,
              titleColor:
                "#ffffff",
              bodyColor:
                "#ffffff",
              callbacks: {
                label: context => {
                  if (
                    context.raw ===
                    null
                  ) {
                    return `${context.dataset.label}: no historical snapshot`;
                  }

                  return `${context.dataset.label}: ${context.raw}`;
                }
              }
            }
          },
          scales: {
            x: {
              ticks: {
                color: "#334155",
                maxRotation: 0,
                autoSkip: true,
                font: {
                  size: 11,
                  weight: "bold"
                }
              },
              grid: {
                color:
                  "rgba(148, 163, 184, 0.20)"
              }
            },
            y: {
              beginAtZero: true,
              suggestedMax:
                getYAxisMax(),
              max:
                currentMetricMode ===
                "threat_index"
                  ? 100
                  : undefined,
              ticks: {
                color: "#334155",
                font: {
                  size: 11,
                  weight: "bold"
                }
              },
              grid: {
                color:
                  "rgba(148, 163, 184, 0.22)"
              },
              title: {
                display: true,
                text:
                  currentMetricMode ===
                  "threat_index"
                    ? "Threat Index Score"
                    : "Event Count",
                color: "#475569",
                font: {
                  size: 12,
                  weight: "bold"
                }
              }
            }
          }
        }
      }
    );
  }

  function setActiveViewButton(
    mode
  ) {
    document
      .querySelectorAll(
        ".mode-btn"
      )
      .forEach(
        button => {
          button.classList.toggle(
            "active",
            button.dataset.mode ===
              mode
          );
        }
      );
  }

  function setupMetricControls(
    data
  ) {
    document
      .querySelectorAll(
        'input[name="metricMode"]'
      )
      .forEach(
        input => {
          input.addEventListener(
            "change",
            () => {
              currentMetricMode =
                input.value ||
                "threat_index";

              render(data);
            }
          );
        }
      );
  }

  function setupViewButtons(
    data
  ) {
    document
      .querySelectorAll(
        ".mode-btn"
      )
      .forEach(
        button => {
          button.addEventListener(
            "click",
            () => {
              currentViewMode =
                button.dataset.mode ||
                "daily";

              setActiveViewButton(
                currentViewMode
              );

              render(data);
            }
          );
        }
      );
  }

  function setupCheckboxes(
    data
  ) {
    document
      .querySelectorAll(
        "#chartControls input"
      )
      .forEach(
        input => {
          input.addEventListener(
            "change",
            () =>
              render(data)
          );
        }
      );
  }

  function initialize(data) {
    setActiveViewButton(
      currentViewMode
    );

    render(data);

    if (
      controlsInitialized
    ) {
      return;
    }

    setupMetricControls(data);
    setupViewButtons(data);
    setupCheckboxes(data);

    controlsInitialized = true;
  }

  return {
    initialize
  };
})();
