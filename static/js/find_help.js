(function () {
  "use strict";

  var root = document.getElementById("find-help");
  var cfgEl = document.getElementById("map-config");
  if (!root || !cfgEl) return;

  var cfg = JSON.parse(cfgEl.textContent);

  var el = {
    status: document.getElementById("status"),
    results: document.getElementById("results"),
    title: document.getElementById("results-title"),
    locate: document.getElementById("locate-btn"),
    form: document.getElementById("place-form"),
    place: document.getElementById("place"),
    radius: document.getElementById("radius"),
    chips: Array.prototype.slice.call(root.querySelectorAll(".chip[data-type]")),
  };

  /* Each service type is a list of OpenStreetMap tag filters. */
  var TYPES = {
    hospital: { label: "hospitals", filters: ['["amenity"="hospital"]', '["amenity"="clinic"]'] },
    police: { label: "police stations", filters: ['["amenity"="police"]'] },
    hotel: { label: "hotels", filters: ['["tourism"~"^(hotel|hostel|guest_house|motel)$"]'] },
    restaurant: { label: "restaurants", filters: ['["amenity"="restaurant"]'] },
    mechanic: { label: "mechanics", filters: ['["shop"="car_repair"]'] },
    transport: {
      label: "transport options",
      filters: ['["amenity"~"^(bus_station|taxi|ferry_terminal)$"]', '["railway"="station"]', '["aeroway"="terminal"]'],
    },
  };

  var state = { type: root.getAttribute("data-initial-type"), center: null, centerLabel: "" };
  if (!TYPES[state.type]) state.type = "hospital";

  function setStatus(text) { el.status.textContent = text; }

  if (typeof L === "undefined") {
    setStatus("The map library could not load. Check your connection and reload the page.");
    return;
  }

  /* ---------- Map ---------- */
  var map = L.map("map", {
    scrollWheelZoom: false,
    dragging: !L.Browser.mobile, // keep one-finger scrolling on phones
    tap: false,
  }).setView([20, 0], 2);
  L.tileLayer(cfg.tileUrl, { attribution: cfg.attribution, maxZoom: 19 }).addTo(map);

  var markerLayer = L.layerGroup().addTo(map);
  var centerMarker = null;
  var markers = [];

  window.addEventListener("resize", function () { map.invalidateSize(); });
  setTimeout(function () { map.invalidateSize(); }, 200);

  function pinIcon(n) {
    return L.divIcon({
      className: "pin",
      html: "<span>" + Number(n) + "</span>",
      iconSize: [30, 30],
      iconAnchor: [15, 15],
      popupAnchor: [0, -14],
    });
  }

  /* ---------- Helpers ---------- */
  function distanceMeters(a, b) {
    var R = 6371000, rad = Math.PI / 180;
    var dLat = (b.lat - a.lat) * rad, dLng = (b.lng - a.lng) * rad;
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return 2 * R * Math.asin(Math.sqrt(h));
  }

  function formatDistance(m) {
    return m < 1000 ? Math.round(m / 10) * 10 + " m" : (m / 1000).toFixed(1) + " km";
  }

  function humanize(value) {
    return String(value || "").replace(/_/g, " ").replace(/^./, function (c) { return c.toUpperCase(); });
  }

  function kindOf(tags) {
    return humanize(tags.amenity || tags.tourism || tags.shop || tags.railway || tags.aeroway || "Place");
  }

  function addressOf(tags) {
    var street = [tags["addr:housenumber"], tags["addr:street"]].filter(Boolean).join(" ");
    return [street, tags["addr:city"]].filter(Boolean).join(", ");
  }

  function safePhone(raw) {
    if (!raw) return "";
    var first = String(raw).split(";")[0].trim();
    var cleaned = first.replace(/[^\d+\-\s().]/g, "");
    return cleaned.replace(/\D/g, "").length >= 5 ? cleaned : "";
  }

  function make(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text; // textContent only: map data is untrusted
    return node;
  }

  /* ---------- Rendering ---------- */
  function clearResults() {
    el.results.textContent = "";
    markerLayer.clearLayers();
    markers = [];
  }

  function showCenter() {
    if (centerMarker) map.removeLayer(centerMarker);
    centerMarker = L.circleMarker([state.center.lat, state.center.lng], {
      radius: 9, color: "#0b3c5d", weight: 3, fillColor: "#4fb3e8", fillOpacity: 1,
    }).addTo(map).bindTooltip(state.centerLabel || "Search center");
  }

  function renderResults(items) {
    clearResults();
    var info = TYPES[state.type];
    var km = Number(el.radius.value) / 1000;

    if (!items.length) {
      setStatus("No " + info.label + " found within " + km + " km of " + (state.centerLabel || "that spot") +
        ". Try a larger distance or another area. Map data can be incomplete.");
      el.title.textContent = "Results";
      map.setView([state.center.lat, state.center.lng], 13);
      return;
    }

    el.title.textContent = items.length + " nearest " + info.label;
    setStatus("Showing the " + items.length + " nearest " + info.label + " within " + km + " km.");

    var bounds = L.latLngBounds([[state.center.lat, state.center.lng]]);

    items.forEach(function (item, i) {
      var n = i + 1;
      var li = make("li", "result");
      li.appendChild(make("span", "result__num", String(n)));

      var body = make("div", "result__body");
      body.appendChild(make("h3", "result__name", item.name));
      body.appendChild(make("p", "result__meta", item.kind + " \u00b7 " + formatDistance(item.distance)));
      if (item.address) body.appendChild(make("p", "result__addr", item.address));

      var actions = make("div", "result__actions");
      var showBtn = make("button", "btn btn--outline btn--sm", "Show on map");
      showBtn.type = "button";
      actions.appendChild(showBtn);

      var phone = safePhone(item.phone);
      if (phone) {
        var call = make("a", "btn btn--outline btn--sm", "Call");
        call.href = "tel:" + phone.replace(/[^\d+]/g, "");
        actions.appendChild(call);
      }
      var osm = make("a", "btn btn--ghost btn--sm", "OpenStreetMap");
      osm.href = "https://www.openstreetmap.org/?mlat=" + item.lat + "&mlon=" + item.lng + "#map=18/" + item.lat + "/" + item.lng;
      osm.target = "_blank";
      osm.rel = "noopener noreferrer";
      actions.appendChild(osm);
      body.appendChild(actions);
      li.appendChild(body);
      el.results.appendChild(li);

      var popup = make("div", "popup");
      popup.appendChild(make("strong", "", item.name));
      popup.appendChild(make("div", "", item.kind + " \u00b7 " + formatDistance(item.distance)));

      var marker = L.marker([item.lat, item.lng], { icon: pinIcon(n), title: item.name }).addTo(markerLayer);
      marker.bindPopup(popup);
      markers.push(marker);
      bounds.extend([item.lat, item.lng]);

      showBtn.addEventListener("click", function () {
        map.setView([item.lat, item.lng], Math.max(map.getZoom(), 16));
        marker.openPopup();
        document.getElementById("map").scrollIntoView({ behavior: "smooth", block: "nearest" });
      });
    });

    map.fitBounds(bounds, { padding: [30, 30], maxZoom: 16 });
  }

  function showError(message) {
    clearResults();
    el.title.textContent = "Results";
    setStatus(message);
    var retry = make("button", "btn btn--outline", "Try again");
    retry.type = "button";
    retry.addEventListener("click", search);
    var li = make("li", "result result--plain");
    li.appendChild(retry);
    el.results.appendChild(li);
  }

  /* ---------- Search (Overpass API) ---------- */
  var searchId = 0;
  var controller = null;

  function buildQuery() {
    var r = Number(el.radius.value);
    var around = "(around:" + r + "," + state.center.lat.toFixed(5) + "," + state.center.lng.toFixed(5) + ")";
    var parts = TYPES[state.type].filters.map(function (f) { return "nwr" + f + around + ";"; });
    return "[out:json][timeout:20];(" + parts.join("") + ");out center tags 120;";
  }

  function search() {
    if (!state.center) {
      setStatus("Share your location or search for a place first.");
      return;
    }
    var id = ++searchId;
    if (controller) controller.abort();
    controller = new AbortController();
    root.setAttribute("aria-busy", "true");
    setStatus("Looking for " + TYPES[state.type].label + "\u2026");

    fetch(cfg.overpassUrl, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "data=" + encodeURIComponent(buildQuery()),
      signal: controller.signal,
    })
      .then(function (res) {
        if (!res.ok) throw new Error("status " + res.status);
        return res.json();
      })
      .then(function (json) {
        if (id !== searchId) return;
        var items = (json.elements || []).map(function (e) {
          var lat = e.lat !== undefined ? e.lat : e.center && e.center.lat;
          var lng = e.lon !== undefined ? e.lon : e.center && e.center.lon;
          if (typeof lat !== "number" || typeof lng !== "number") return null;
          var tags = e.tags || {};
          var kind = kindOf(tags);
          return {
            name: tags.name || tags["name:en"] || kind, // never invent a name
            kind: kind,
            lat: lat,
            lng: lng,
            address: addressOf(tags),
            phone: tags.phone || tags["contact:phone"] || "",
            distance: distanceMeters(state.center, { lat: lat, lng: lng }),
          };
        }).filter(Boolean);
        items.sort(function (a, b) { return a.distance - b.distance; });
        renderResults(items.slice(0, 20));
      })
      .catch(function (err) {
        if (err.name === "AbortError" || id !== searchId) return;
        showError("We could not load nearby places. The map service may be busy or you may be offline.");
      })
      .then(function () {
        if (id === searchId) root.removeAttribute("aria-busy");
      });
  }

  function setCenter(lat, lng, label) {
    state.center = { lat: lat, lng: lng };
    state.centerLabel = label;
    showCenter();
    map.setView([lat, lng], 14);
    search();
  }

  /* ---------- Controls ---------- */
  el.chips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      state.type = chip.getAttribute("data-type");
      el.chips.forEach(function (c) { c.setAttribute("aria-pressed", String(c === chip)); });
      try { history.replaceState(null, "", "?type=" + encodeURIComponent(state.type)); } catch (e) { /* ignore */ }
      if (state.center) search();
      else setStatus("Now share your location or search for a place.");
    });
  });

  el.radius.addEventListener("change", function () { if (state.center) search(); });

  el.locate.addEventListener("click", function () {
    if (!("geolocation" in navigator)) {
      setStatus("Your browser does not support location sharing. Search for a place instead.");
      return;
    }
    setStatus("Finding your location\u2026");
    el.locate.disabled = true;
    navigator.geolocation.getCurrentPosition(
      function (pos) {
        el.locate.disabled = false;
        setCenter(pos.coords.latitude, pos.coords.longitude, "your location");
      },
      function (err) {
        el.locate.disabled = false;
        setStatus(err.code === 1
          ? "Location permission was denied. Search for a town or address instead."
          : "We could not get your location. Search for a town or address instead.");
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 }
    );
  });

  el.form.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = el.place.value.trim();
    if (!q) { setStatus("Type a town, address, or landmark to search."); return; }
    setStatus("Searching for \u201c" + q + "\u201d\u2026");
    fetch(cfg.nominatimUrl + "?format=jsonv2&limit=1&q=" + encodeURIComponent(q))
      .then(function (res) {
        if (!res.ok) throw new Error("status " + res.status);
        return res.json();
      })
      .then(function (list) {
        if (!list.length) {
          setStatus("We could not find \u201c" + q + "\u201d. Try a nearby town or add the country.");
          return;
        }
        var hit = list[0];
        var label = String(hit.display_name || q).split(",").slice(0, 2).join(",").trim();
        setCenter(parseFloat(hit.lat), parseFloat(hit.lon), label);
      })
      .catch(function () {
        setStatus("The place search is unavailable right now. Try again, or use your location.");
      });
  });
})();
