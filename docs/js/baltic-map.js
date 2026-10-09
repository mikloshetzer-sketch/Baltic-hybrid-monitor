
(() => {
  "use strict";

  const url = "./data/baltic_dashboard.json";

  const coords = {
    Estonia: [58.72, 25.5],
    Latvia: [56.88, 24.6],
    Lithuania: [55.25, 24.1],
    Poland: [52.15, 19.1]
  };

  const names = {
    Estonia: "Észtország",
    Latvia: "Lettország",
    Lithuania: "Litvánia",
    Poland: "Lengyelország",
    Regional: "Regionális"
  };

  const countryOrder = [
    "Estonia",
    "Latvia",
    "Lithuania",
    "Poland",
    "Regional"
  ];

  const $ = id => document.getElementById(id);

  const esc = value =>
    String(value ?? "").replace(/[&<>"']/g, c => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    })[c]);

  let data = null;
  let map = null;
  let markers = {};
  let selected = "all";
  let uniqueEvents = [];

  function getFilteredEvents() {
    const category = $("balticMapCategory").value;

    return uniqueEvents.filter(event => {
      return (
        category === "all" ||
        (event.categories || []).includes(category)
      );
    });
  }

  function getCountryCounts(events) {
    const counts = {};

    countryOrder.forEach(country => {
      counts[country] = {
        event_count: 0,
        incident_count: 0,
        indicator_count: 0
      };
    });

    events.forEach(event => {
      const country = event.primary_country;

      if (!counts[country]) return;

      counts[country].event_count++;

      if (event.event_subtype === "incident") {
        counts[country].incident_count++;
      }

      if (event.event_subtype === "indicator") {
        counts[country].indicator_count++;
      }
    });

    return counts;
  }

  function updateMarkers(counts) {
    if (!map || !window.L) return;

    Object.entries(coords).forEach(([country, point]) => {
      const count = counts[country].event_count;

      const size = Math.max(
        31,
        Math.min(59, 30 + count * 3)
      );

      const icon = L.divIcon({
        className: "",
        html: `
          <div class="baltic-map-bubble ${
            selected === country ? "active" : ""
          }" style="
            width:${size}px;
            height:${size}px;
          ">
            ${count}
          </div>
        `,
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2]
      });

      if (markers[country]) {
        markers[country].setIcon(icon);
      } else {
        markers[country] = L.marker(point, {
          icon,
          title: `${names[country]}: ${count} esemény`
        })
          .addTo(map)
          .on("click", () => setCountry(country));
      }
    });
  }

  function render() {
    const filtered = getFilteredEvents();
    const counts = getCountryCounts(filtered);

    const chosen = counts[selected];

    $("balticMapSelectionTitle").textContent =
      selected === "all"
        ? "Regionális áttekintés"
        : names[selected] || selected;

    if (chosen) {
      $("balticMapSummary").textContent =
        `${chosen.event_count} aktuális esemény · ` +
        `${chosen.incident_count} incidens · ` +
        `${chosen.indicator_count} indikátor`;
    } else {
      const incidents = filtered.filter(
        e => e.event_subtype === "incident"
      ).length;

      const indicators = filtered.filter(
        e => e.event_subtype === "indicator"
      ).length;

      $("balticMapSummary").textContent =
        `${filtered.length} aktuális esemény · ` +
        `${incidents} incidens · ` +
        `${indicators} indikátor`;
    }

    $("balticMapCountries").innerHTML =
      countryOrder.map(country => {
        const count = counts[country].event_count;

        return `
          <button
            type="button"
            class="baltic-country-btn ${
              selected === country ? "selected" : ""
            }"
            data-country="${country}"
          >
            <span>${names[country]}</span>
            <strong>${count}</strong>
          </button>
        `;
      }).join("");

    $("balticMapCountries")
      .querySelectorAll("button")
      .forEach(button => {
        button.addEventListener("click", () => {
          setCountry(button.dataset.country);
        });
      });

    const visibleEvents = filtered.filter(event => {
      return (
        selected === "all" ||
        event.primary_country === selected
      );
    }).slice(0, 6);

    $("balticMapEvents").innerHTML =
      visibleEvents.length
        ? visibleEvents.map(event => {
            const safeUrl =
              /^https?:\/\//i.test(event.url || "")
                ? event.url
                : "#";

            return `
              <a
                class="baltic-event-link"
                href="${esc(safeUrl)}"
                target="_blank"
                rel="noopener noreferrer"
              >
                ${esc(event.title)}

                <small>
                  ${esc(
                    names[event.primary_country] ||
                    event.primary_country ||
                    "—"
                  )}
                  · ${esc(event.event_subtype || "—")}
                  · ${Number(
                    event.hybrid_threat_score
                  ) || 0} pont
                  · ${esc(event.confidence || "—")}
                  confidence
                </small>
              </a>
            `;
          }).join("")
        : `<p class="baltic-map-note">
             Nincs esemény ezzel a szűréssel.
           </p>`;

    updateMarkers(counts);
  }

  function setCountry(country) {
    selected = country;

    $("balticMapCountry").value = country;

    render();

    if (map && coords[country]) {
      map.flyTo(coords[country], 6, {
        duration: 0.45
      });
    } else if (map) {
      map.flyTo([56.5, 23.3], 5, {
        duration: 0.45
      });
    }
  }

  async function init() {
    try {
      const response = await fetch(url, {
        cache: "no-store"
      });

      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }

      data = await response.json();

      const events = [
        ...(data.top_events || []),
        ...(data.recent_events || [])
      ];

      const seen = new Set();

      uniqueEvents = events.filter(event => {
        if (!event.event_id) return false;
        if (seen.has(event.event_id)) return false;

        seen.add(event.event_id);
        return true;
      });

      const categories = new Set();

      uniqueEvents.forEach(event => {
        (event.categories || []).forEach(category => {
          categories.add(category);
        });
      });

      [...categories].sort().forEach(category => {
        const option = document.createElement("option");

        option.value = category;
        option.textContent =
          category.replaceAll("_", " ");

        $("balticMapCategory").append(option);
      });

      $("balticMapCountry").addEventListener(
        "change",
        event => setCountry(event.target.value)
      );

      $("balticMapCategory").addEventListener(
        "change",
        render
      );

      const windowData = data.current_threat_window;

      if (windowData) {
        $("balticMapPeriod").textContent =
          `${windowData.days || 14} nap`;
      }

      if (window.L) {
        $("balticGeoMap").innerHTML = "";

        map = L.map("balticGeoMap", {
          scrollWheelZoom: false
        }).setView([56.5, 23.3], 5);

        L.tileLayer(
          "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
          {
            attribution:
              "&copy; OpenStreetMap contributors",
            maxZoom: 12
          }
        ).addTo(map);

      } else {
        $("balticGeoMap").innerHTML = `
          <div class="baltic-map-placeholder">
            A térképkönyvtár nem töltődött be.
            Az országos eseménylista továbbra is használható.
          </div>
        `;
      }

      render();

    } catch (error) {
      $("balticMapSummary").textContent =
        "Nem sikerült betölteni a térképes adatokat: " +
        error.message;

      $("balticGeoMap").innerHTML = `
        <div class="baltic-map-placeholder">
          Az adatbetöltés sikertelen.
        </div>
      `;
    }
  }

  document.addEventListener(
    "DOMContentLoaded",
    init
  );
})();
