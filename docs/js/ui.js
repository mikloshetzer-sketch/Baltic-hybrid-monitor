const BalticUI = (() => {

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

    function updateSummary(summary) {

        setText("overallScore", summary.average_score.toFixed(2));

        setText("incidentCount", summary.incident_count);

        setText("overallLevel", summary.overall_level.toUpperCase());

    }

    function updateHeader(data) {

        setText(
            "lastUpdate",
            formatDate(data.generated_at)
        );

    }

    function updateDashboard(data) {

        updateHeader(data);

        updateSummary(data.summary);

    }

    return {

        updateDashboard

    };

})();
