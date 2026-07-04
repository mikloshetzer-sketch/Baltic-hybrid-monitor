const BalticChart = (() => {

    let chart = null;

    const COLORS = {
        overall: "#111827",
        trend: "#64748b",
        Estonia: "#0284c7",
        Latvia: "#f97316",
        Lithuania: "#16a34a",
        Poland: "#dc2626"
    };

    function getSelectedSeries() {
        return Array.from(
            document.querySelectorAll("#chartControls input:checked")
        ).map(item => item.value);
    }

    function calculateLinearTrend(values) {
        const cleanValues = values.map(value => Number(value) || 0);
        const n = cleanValues.length;

        if (n < 2) {
            return cleanValues;
        }

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

        const denominator = (n * sumXX) - (sumX * sumX);

        if (denominator === 0) {
            return cleanValues;
        }

        const slope = ((n * sumXY) - (sumX * sumY)) / denominator;
        const intercept = (sumY - slope * sumX) / n;

        return cleanValues.map((_, x) => {
            return Number((intercept + slope * x).toFixed(2));
        });
    }

    function createDatasets(history, selected) {
        const datasets = [];

        if (selected.includes("overall")) {
            datasets.push({
                label: "Regional average",
                data: history.overall_average_score,
                borderColor: COLORS.overall,
                backgroundColor: COLORS.overall,
                borderWidth: 3,
                pointRadius: 3,
                pointHoverRadius: 6,
                tension: 0.35
            });
        }

        if (selected.includes("trend")) {
            datasets.push({
                label: "Regional trend line",
                data: calculateLinearTrend(history.overall_average_score),
                borderColor: COLORS.trend,
                backgroundColor: COLORS.trend,
                borderWidth: 2,
                borderDash: [8, 6],
                pointRadius: 0,
                pointHoverRadius: 0,
                tension: 0
            });
        }

        Object.keys(history.country_average_scores).forEach(country => {
            if (!selected.includes(country)) return;

            datasets.push({
                label: country,
                data: history.country_average_scores[country],
                borderColor: COLORS[country],
                backgroundColor: COLORS[country],
                borderWidth: 2,
                pointRadius: 3,
                pointHoverRadius: 5,
                tension: 0.35
            });
        });

        return datasets;
    }

    function render(data) {
        const history = data.history;

        const canvas = document.getElementById("threatTrendChart");
        const ctx = canvas.getContext("2d");

        if (chart) {
            chart.destroy();
        }

        chart = new Chart(ctx, {
            type: "line",
            data: {
                labels: history.labels,
                datasets: createDatasets(
                    history,
                    getSelectedSeries()
                )
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: "index",
                    intersect: false
                },
                plugins: {
                    legend: {
                        position: "top",
                        labels: {
                            color: "#111827",
                            usePointStyle: true,
                            boxWidth: 10,
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

    function initialize(data) {
        render(data);

        document
            .querySelectorAll("#chartControls input")
            .forEach(item => {
                item.addEventListener("change", () => {
                    render(data);
                });
            });
    }

    return {
        initialize
    };

})();
