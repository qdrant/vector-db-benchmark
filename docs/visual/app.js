/* global vegaEmbed, REPORT_DATA */
(function () {
    const DATA = window.REPORT_DATA;
    if (!DATA || !DATA.cells) {
        document.getElementById("lede").textContent =
            "No report data. Run: python tools/export_report_data.py";
        return;
    }

    const ENGINE_COLOR = {
        qdrant: "#dc244c",
        weaviate: "#0aa3a3",
        milvus: "#1a73e8",
        elasticsearch: "#c78a00",
        opensearch: "#005eb8",
        redis: "#d82c20",
        pgvector: "#336791",
    };
    const CORE = DATA.core_datasets || [];
    const EXPECTED_SEARCHES = 96;

    const state = {
        dataset: CORE[0] || "glove-100-angular",
        parallel: 100,
        metric: "rps",
        precision: 0.8,
        frontier: true,
        m: 16,
        efc: 100,
    };

    const els = {
        dataset: document.getElementById("dataset"),
        parallel: document.getElementById("parallel"),
        metric: document.getElementById("metric"),
        precision: document.getElementById("precision"),
        precisionRead: document.getElementById("precisionRead"),
        frontier: document.getElementById("frontier"),
        m: document.getElementById("m"),
        efc: document.getElementById("efc"),
        table: document.getElementById("table"),
        tableHint: document.getElementById("tableHint"),
        controlHint: document.getElementById("controlHint"),
        coverage: document.getElementById("coverage"),
        generatedAt: document.getElementById("generatedAt"),
        statusNote: document.getElementById("statusNote"),
        themeBtn: document.getElementById("themeBtn"),
    };

    function coreCells() {
        return DATA.cells.filter(function (c) {
            return !c.appendix && c.precision_scored;
        });
    }

    function unique(values) {
        return Array.from(new Set(values)).sort(function (a, b) {
            return a < b ? -1 : a > b ? 1 : 0;
        });
    }

    function fmtPrec(v) {
        return v == null ? "—" : v.toFixed(3);
    }
    function fmtRps(v) {
        return v == null ? "—" : Math.round(v).toLocaleString();
    }
    function fmtMs(v) {
        return v == null ? "—" : v.toFixed(2);
    }
    function fmtSec(v) {
        return v == null ? "—" : Math.round(v).toLocaleString();
    }

    function engineLabel(name) {
        return name.charAt(0).toUpperCase() + name.slice(1);
    }

    function populateSelect(select, values, selected) {
        select.innerHTML = "";
        values.forEach(function (value) {
            const opt = document.createElement("option");
            opt.value = String(value);
            opt.textContent =
                DATA.dataset_labels && DATA.dataset_labels[value]
                    ? DATA.dataset_labels[value]
                    : String(value);
            if (String(value) === String(selected)) opt.selected = true;
            select.appendChild(opt);
        });
    }

    function readHash() {
        const hash = new URLSearchParams(location.hash.replace(/^#/, ""));
        if (hash.get("dataset")) state.dataset = hash.get("dataset");
        if (hash.get("parallel")) state.parallel = Number(hash.get("parallel"));
        if (hash.get("metric")) state.metric = hash.get("metric");
        if (hash.get("precision")) state.precision = Number(hash.get("precision"));
        if (hash.get("frontier")) state.frontier = hash.get("frontier") !== "0";
        if (hash.get("m")) state.m = Number(hash.get("m"));
        if (hash.get("efc")) state.efc = Number(hash.get("efc"));
    }

    function writeHash() {
        const hash = new URLSearchParams({
            dataset: state.dataset,
            parallel: String(state.parallel),
            metric: state.metric,
            precision: state.precision.toFixed(2),
            frontier: state.frontier ? "1" : "0",
            m: String(state.m),
            efc: String(state.efc),
        });
        history.replaceState(null, "", "#" + hash.toString());
    }

    function filtered(extra) {
        return coreCells().filter(function (c) {
            if (c.dataset !== state.dataset) return false;
            if (c.parallel !== state.parallel) return false;
            if (extra && extra.m != null && c.m !== extra.m) return false;
            if (extra && extra.efc != null && c.ef_construct !== extra.efc) return false;
            return true;
        });
    }

    function rankRows() {
        const rows = filtered();
        const byEngine = {};
        rows.forEach(function (c) {
            (byEngine[c.engine] || (byEngine[c.engine] = [])).push(c);
        });
        const order = DATA.engine_order || Object.keys(byEngine);
        const ranked = [];
        order.forEach(function (engine) {
            const cells = byEngine[engine] || [];
            if (!cells.length) return;
            const qualified = cells.filter(function (c) {
                return c.precision != null && c.precision + 1e-12 >= state.precision;
            });
            const pool = qualified.length ? qualified : cells;
            const better = state.metric === "rps" ? "max" : "min";
            pool.sort(function (a, b) {
                const av = a[state.metric];
                const bv = b[state.metric];
                if (av == null) return 1;
                if (bv == null) return -1;
                return better === "max" ? bv - av : av - bv;
            });
            const best = pool[0];
            ranked.push({
                engine: engine,
                cell: best,
                qualifies: qualified.length > 0,
                nQualified: qualified.length,
                nCells: cells.length,
                bestPrecision: cells.reduce(function (acc, c) {
                    return c.precision != null && c.precision > acc ? c.precision : acc;
                }, 0),
            });
        });
        ranked.sort(function (a, b) {
            if (a.qualifies !== b.qualifies) return a.qualifies ? -1 : 1;
            const av = a.cell[state.metric];
            const bv = b.cell[state.metric];
            if (av == null) return 1;
            if (bv == null) return -1;
            return state.metric === "rps" ? bv - av : av - bv;
        });
        return ranked;
    }

    function renderCoverage() {
        const coverage = DATA.coverage || {};
        els.coverage.innerHTML = "";
        (DATA.engine_order || Object.keys(coverage)).forEach(function (engine) {
            const ds = coverage[engine] || {};
            let searches = 0;
            CORE.forEach(function (name) {
                searches += ((ds[name] || {}).searches) || 0;
            });
            const need = CORE.length * EXPECTED_SEARCHES;
            const chip = document.createElement("span");
            chip.className = "chip";
            if (searches >= need) chip.classList.add("done");
            else if (searches > 0) chip.classList.add("partial");
            chip.textContent =
                engineLabel(engine) +
                " " +
                searches +
                "/" +
                need;
            els.coverage.appendChild(chip);
        });
        ["qdrant", "weaviate", "milvus", "elasticsearch", "opensearch", "redis", "pgvector"].forEach(function (engine) {
            if (coverage[engine]) return;
            const chip = document.createElement("span");
            chip.className = "chip";
            chip.textContent = engineLabel(engine) + " not started";
            els.coverage.appendChild(chip);
        });
    }

    function renderTable() {
        const ranked = rankRows();
        const metric = state.metric;
        const winners = ranked.filter(function (r) { return r.qualifies; });
        els.tableHint.textContent = winners.length
            ? winners.length + " engine" + (winners.length === 1 ? "" : "s") + " clear " + state.precision.toFixed(2)
            : "No engine clears " + state.precision.toFixed(2) + " on this dataset / load";

        const html = [
            "<table><thead><tr>",
            "<th></th><th>Engine</th>",
            "<th class='num" + (metric === "rps" ? " metric-col" : "") + "'>RPS</th>",
            "<th class='num" + (metric === "p95_ms" ? " metric-col" : "") + "'>p95 (ms)</th>",
            "<th class='num'>Precision</th>",
            "<th class='num" + (metric === "index_s" ? " metric-col" : "") + "'>Index (s)</th>",
            "<th class='num'>m</th><th class='num'>ef_c</th><th class='num'>ef</th>",
            "<th></th>",
            "</tr></thead><tbody>",
        ];
        ranked.forEach(function (row, i) {
            const c = row.cell;
            const trophy = row.qualifies && i === 0 ? "🏆" : "";
            html.push(
                "<tr class='" + (row.qualifies ? (i === 0 ? "winner" : "") : "below") + "'>",
                "<td>" + trophy + "</td>",
                "<td><span class='engine-dot' style='background:" + (ENGINE_COLOR[row.engine] || "#888") + "'></span>" + engineLabel(row.engine) + "</td>",
                "<td class='num'>" + fmtRps(c.rps) + "</td>",
                "<td class='num'>" + fmtMs(c.p95_ms) + "</td>",
                "<td class='num'>" + fmtPrec(c.precision) + "</td>",
                "<td class='num'>" + fmtSec(c.index_s) + "</td>",
                "<td class='num'>" + c.m + "</td>",
                "<td class='num'>" + c.ef_construct + "</td>",
                "<td class='num'>" + c.search_ef + "</td>",
                "<td>" + (row.qualifies ? "" : "best " + fmtPrec(row.bestPrecision) + " below floor") + "</td>",
                "</tr>"
            );
        });
        html.push("</tbody></table>");
        els.table.innerHTML = html.join("");
    }

    function vegaTheme() {
        const dark = document.documentElement.getAttribute("data-theme") === "dark";
        const muted = dark ? "#abb1c7" : "#656b7f";
        const fg = dark ? "#fcfdff" : "#111824";
        const grid = dark ? "rgba(252,253,255,0.08)" : "rgba(17,24,36,0.08)";
        return {
            background: null,
            axis: { labelColor: muted, titleColor: fg, domainColor: grid, gridColor: grid, tickColor: grid },
            legend: { labelColor: muted, titleColor: fg },
            view: { stroke: null },
        };
    }

    function paretoPoints(rows) {
        const byEngine = {};
        rows.forEach(function (c) {
            (byEngine[c.engine] || (byEngine[c.engine] = [])).push(c);
        });
        const keep = [];
        Object.keys(byEngine).forEach(function (engine) {
            const pts = byEngine[engine]
                .filter(function (c) { return c.precision != null && c[state.metric] != null; })
                .sort(function (a, b) { return b.precision - a.precision; });
            let best = state.metric === "rps" ? -Infinity : Infinity;
            pts.forEach(function (c) {
                const v = c[state.metric];
                const better = state.metric === "rps" ? v > best : v < best;
                if (better) {
                    keep.push(c);
                    best = v;
                }
            });
        });
        return keep;
    }

    function renderPareto() {
        const rows = filtered();
        const points = state.frontier ? paretoPoints(rows) : rows;
        const yTitle = state.metric === "rps" ? "RPS" : state.metric === "p95_ms" ? "p95 latency (ms)" : "Index time (s)";
        const spec = {
            $schema: "https://vega.github.io/schema/vega-lite/v5.json",
            width: "container",
            height: 360,
            data: { values: points },
            mark: { type: "point", filled: true, size: 70, opacity: 0.85 },
            encoding: {
                x: { field: "precision", type: "quantitative", title: "Precision", scale: { zero: false } },
                y: {
                    field: state.metric,
                    type: "quantitative",
                    title: yTitle,
                    scale: { zero: state.metric === "rps" },
                },
                color: {
                    field: "engine",
                    type: "nominal",
                    scale: { domain: Object.keys(ENGINE_COLOR), range: Object.values(ENGINE_COLOR) },
                    legend: { title: null },
                },
                shape: { field: "engine", type: "nominal", legend: null },
                tooltip: [
                    { field: "engine" },
                    { field: "precision", format: ".3f" },
                    { field: "rps", format: ",.0f" },
                    { field: "p95_ms", format: ".2f", title: "p95 ms" },
                    { field: "m" },
                    { field: "ef_construct", title: "ef_construct" },
                    { field: "search_ef", title: "search ef" },
                ],
            },
        };
        vegaEmbed("#pareto", spec, { actions: false, config: vegaTheme() });
    }

    function renderEfCurves() {
        const rows = filtered({ m: state.m, efc: state.efc }).slice().sort(function (a, b) {
            return a.search_ef - b.search_ef;
        });
        const color = {
            field: "engine",
            type: "nominal",
            scale: { domain: Object.keys(ENGINE_COLOR), range: Object.values(ENGINE_COLOR) },
            legend: { title: null },
        };
        const base = {
            $schema: "https://vega.github.io/schema/vega-lite/v5.json",
            width: "container",
            height: 300,
            data: { values: rows },
            encoding: {
                x: { field: "search_ef", type: "quantitative", title: "search ef" },
                color: color,
            },
        };
        const ySpeed = state.parallel === 1 ? "p95_ms" : "rps";
        const ySpeedTitle = state.parallel === 1 ? "p95 latency (ms)" : "RPS";
        vegaEmbed("#efPrecision", Object.assign({}, base, {
            mark: { type: "line", point: true },
            encoding: Object.assign({}, base.encoding, {
                y: { field: "precision", type: "quantitative", title: "Precision", scale: { zero: false } },
                tooltip: [
                    { field: "engine" },
                    { field: "search_ef" },
                    { field: "precision", format: ".3f" },
                ],
            }),
        }), { actions: false, config: vegaTheme() });
        vegaEmbed("#efSpeed", Object.assign({}, base, {
            mark: { type: "line", point: true },
            encoding: Object.assign({}, base.encoding, {
                y: { field: ySpeed, type: "quantitative", title: ySpeedTitle },
                tooltip: [
                    { field: "engine" },
                    { field: "search_ef" },
                    { field: ySpeed, format: ySpeed === "rps" ? ",.0f" : ".2f" },
                ],
            }),
        }), { actions: false, config: vegaTheme() });
    }

    function renderHints() {
        const label = (DATA.dataset_labels || {})[state.dataset] || state.dataset;
        const load = state.parallel === 100 ? "saturated (p=100)" : "single-thread (p=1)";
        els.controlHint.textContent =
            label + " · " + load + " · floor " + state.precision.toFixed(2) +
            " · " + DATA.n_core_search_cells + " core search cells · " + DATA.host;
    }

    function syncControls() {
        els.dataset.value = state.dataset;
        els.parallel.value = String(state.parallel);
        els.metric.value = state.metric;
        els.precision.value = String(state.precision);
        els.precisionRead.textContent = state.precision.toFixed(2);
        els.frontier.checked = state.frontier;
        if (els.m.querySelector('option[value="' + state.m + '"]')) els.m.value = String(state.m);
        if (els.efc.querySelector('option[value="' + state.efc + '"]')) els.efc.value = String(state.efc);
    }

    function render() {
        syncControls();
        writeHash();
        renderHints();
        renderTable();
        renderPareto();
        renderEfCurves();
    }

    function bind() {
        els.dataset.addEventListener("change", function () {
            state.dataset = els.dataset.value;
            render();
        });
        els.parallel.addEventListener("change", function () {
            state.parallel = Number(els.parallel.value);
            render();
        });
        els.metric.addEventListener("change", function () {
            state.metric = els.metric.value;
            render();
        });
        els.precision.addEventListener("input", function () {
            state.precision = Number(els.precision.value);
            els.precisionRead.textContent = state.precision.toFixed(2);
            renderTable();
            renderHints();
            writeHash();
        });
        els.frontier.addEventListener("change", function () {
            state.frontier = els.frontier.checked;
            renderPareto();
            writeHash();
        });
        els.m.addEventListener("change", function () {
            state.m = Number(els.m.value);
            renderEfCurves();
            writeHash();
        });
        els.efc.addEventListener("change", function () {
            state.efc = Number(els.efc.value);
            renderEfCurves();
            writeHash();
        });
        els.themeBtn.addEventListener("click", function () {
            const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", next);
            try { localStorage.setItem("bench-theme", next); } catch (e) {}
            renderPareto();
            renderEfCurves();
        });
    }

    readHash();
    populateSelect(
        els.dataset,
        CORE.filter(function (d) {
            return coreCells().some(function (c) { return c.dataset === d; });
        }),
        state.dataset
    );
    populateSelect(els.m, unique(coreCells().map(function (c) { return c.m; })), state.m);
    populateSelect(els.efc, unique(coreCells().map(function (c) { return c.ef_construct; })), state.efc);
    els.m.querySelectorAll("option").forEach(function (opt) { opt.textContent = opt.value; });
    els.efc.querySelectorAll("option").forEach(function (opt) { opt.textContent = opt.value; });
    els.generatedAt.textContent = DATA.generated_at || "";
    if (els.statusNote) els.statusNote.textContent = DATA.note || "";
    renderCoverage();
    bind();
    render();
})();
