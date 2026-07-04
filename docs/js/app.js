document.addEventListener("DOMContentLoaded", async () => {

    try {

        const dashboardData = await BalticAPI.loadDashboardData();

        BalticUI.updateDashboard(dashboardData);

        BalticChart.initialize(dashboardData);

        console.log(
            "Baltic Hybrid Threat Monitor loaded successfully."
        );

    } catch (error) {

        console.error(error);

        document.body.innerHTML = `
            <div style="
                max-width:900px;
                margin:80px auto;
                padding:30px;
                background:#111827;
                border:1px solid #ef4444;
                border-radius:14px;
                color:white;
                font-family:Arial,sans-serif;
            ">
                <h2>Dashboard loading error</h2>

                <p>
                    The Baltic Hybrid Threat Monitor could not be loaded.
                </p>

                <pre style="
                    white-space:pre-wrap;
                    color:#fca5a5;
                ">${error}</pre>

                <p>
                    Check whether
                    <strong>docs/data/baltic_dashboard.json</strong>
                    exists and contains valid JSON.
                </p>
            </div>
        `;

    }

});
