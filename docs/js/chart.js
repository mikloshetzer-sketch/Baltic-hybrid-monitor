const BalticChart = (() => {

    let chart = null;

    const COLORS = {

        overall: "#FFFFFF",

        Estonia: "#38bdf8",

        Latvia: "#f59e0b",

        Lithuania: "#22c55e",

        Poland: "#ef4444"

    };

    function getSelectedCountries() {

        return Array.from(
            document.querySelectorAll("#chartControls input:checked")
        ).map(item => item.value);

    }

    function createDatasets(history, selected) {

        const datasets = [];

        if (selected.includes("overall")) {

            datasets.push({

                label: "Regional Average",

                data: history.overall_average_score,

                borderColor: COLORS.overall,

                backgroundColor: COLORS.overall,

                borderWidth: 3,

                pointRadius: 3,

                pointHoverRadius: 6,

                tension: 0.35

            });

        }

        Object.keys(history.country_average_scores).forEach(country => {

            if (!selected.includes(country))
                return;

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

        const ctx = document
            .getElementById("threatTrendChart")
            .getContext("2d");

        if (chart) {

            chart.destroy();

        }

        chart = new Chart(ctx, {

            type: "line",

            data: {

                labels: history.labels,

                datasets: createDatasets(
                    history,
                    getSelectedCountries()
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

                            color: "#f8fafc",

                            usePointStyle: true,

                            boxWidth: 10

                        }

                    },

                    tooltip: {

                        backgroundColor: "#0b1628",

                        borderColor: "#38bdf8",

                        borderWidth: 1,

                        titleColor: "#ffffff",

                        bodyColor: "#ffffff"

                    }

                },

                scales: {

                    x: {

                        ticks: {

                            color: "#9db4cc"

                        },

                        grid: {

                            color: "rgba(255,255,255,0.05)"

                        }

                    },

                    y: {

                        beginAtZero: true,

                        ticks: {

                            color: "#9db4cc"

                        },

                        grid: {

                            color: "rgba(255,255,255,0.05)"

                        },

                        title: {

                            display: true,

                            text: "Hybrid Threat Score",

                            color: "#9db4cc"

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
