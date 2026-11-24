(function () {
  "use strict";

  var slider = document.getElementById("timeSlider");
  var threshold = document.getElementById("thresholdSlider");
  var startYear = 2007;
  var weights = {ig: .20, hy: .25, vix: .20, stl: .20, draw: .15};
  var current = null;
  var terrain = {yaw: -.64, pitch: .72, zoom: 1, dragging: false, x: 0, y: 0};

  function clamp(value, low, high) { return Math.max(low, Math.min(high, value)); }
  function gaussian(value, centre, width) { return Math.exp(-Math.pow(value - centre, 2) / (2 * width * width)); }
  function dateAt(index) { return new Date(Date.UTC(startYear, index, 1)); }
  function decimalYear(date) { return date.getUTCFullYear() + date.getUTCMonth() / 12; }
  function status(score) { return score >= 67 ? "ALERT" : score >= 34 ? "WATCH" : "CALM"; }
  function statusClass(score) { return score >= 67 ? "status alert" : score >= 34 ? "status" : "status calm"; }
  function formatDate(date) {
    if (date.getUTCFullYear() === 2026 && date.getUTCMonth() === 10) return "24 NOV 2026";
    return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0))
      .toLocaleDateString("en-GB", {day: "2-digit", month: "short", year: "numeric", timeZone: "UTC"}).toUpperCase();
  }
  function linePath(values, width, height, min, max) {
    var padding = 14;
    return values.map(function (value, index) {
      var x = padding + index * (width - padding * 2) / Math.max(1, values.length - 1);
      var y = height - padding - (value - min) * (height - padding * 2) / (max - min);
      return x.toFixed(1) + "," + y.toFixed(1);
    }).join(" ");
  }

  function stressPoint(date) {
    var y = decimalYear(date);
    var cycle = Math.sin((y - 2002) * 2.1);
    var shock = 2.7 * gaussian(y, 2008.75, .28) + 1.2 * gaussian(y, 2011.7, .18) + 3.2 * gaussian(y, 2020.22, .10) + 1.0 * gaussian(y, 2022.55, .35);
    var currentPulse = 2.1 * gaussian(y, 2026.85, .40);
    var z = {ig: .18 * cycle + 1.05 * shock - 1, hy: .22 * cycle + 1.20 * shock - 1, vix: .28 * cycle + 1.32 * shock - 1, stl: .14 * cycle + 1.08 * shock - 1, draw: .24 * cycle + 1.22 * shock - 1};
    z.ig += currentPulse; z.hy += currentPulse; z.vix += currentPulse; z.stl += currentPulse; z.draw -= currentPulse * .5;
    var components = {}, score = 0, breadth = 0;
    Object.keys(z).forEach(function (key) {
      components[key] = clamp(50 + z[key] * 50 / 3, 0, 100);
      score += components[key] * weights[key];
      if (components[key] >= 67) breadth += 1;
    });
    return {date: date, z: z, comp: components, score: score, breadth: breadth, recession: (y >= 2007.92 && y <= 2009.5) || (y >= 2020.08 && y <= 2020.33)};
  }

  function irishPoint(date) {
    var y = decimalYear(date);
    var recessionProbability = clamp(8 + 68 * gaussian(y, 2008.7, .48) + 62 * gaussian(y, 2020.2, .18) + 19 * gaussian(y, 2022.5, .5), 0, 100);
    var sahm = clamp(8.9 + 82 * gaussian(y, 2009.0, .55) + 72 * gaussian(y, 2020.35, .25), 0, 100);
    var exportShare = 27.4 + 6 * Math.sin((y - 2007) * .58) + 8 * gaussian(y, 2025.2, .9);
    var exportAverage = exportShare + 3.85;
    var exportScore = clamp((exportAverage - 20) / 20 * 100, 0, 100);
    var divergence = clamp(34 + (y - 2015) * 6.2, 0, 100);
    // Panel 1's probability remains visible as transmission context, but is not
    // counted again in Panel 4's score. The three Irish components renormalize.
    var score = sahm * (25 / 65) + exportScore * (25 / 65) + divergence * (15 / 65);
    return {score: score, probability: recessionProbability, sahm: sahm, exportShare: exportShare, divergence: divergence};
  }

  function labourPoint(date) {
    var y = decimalYear(date);
    var sahm = clamp(.04 + .72 * gaussian(y, 2009.0, .48) + .64 * gaussian(y, 2020.28, .18) + .27 * gaussian(y, 2024.62, .30), 0, 1);
    var claimsPct = clamp(2 + 48 * gaussian(y, 2009.0, .55) + 62 * gaussian(y, 2020.25, .16) + 14 * gaussian(y, 2024.7, .36), 0, 90);
    var claims = claimsPct >= 20;
    var score = clamp(sahm <= .5 ? sahm / .5 * 75 : 75 + (sahm - .5) / .3 * 25, 0, 100);
    if (claims) score = clamp(score + 10, 0, 100);
    var payroll = 185 - 380 * gaussian(y, 2009.0, .42) - 760 * gaussian(y, 2020.25, .12) + 35 * Math.sin(y * 2.2);
    return {score: score, sahm: sahm, claims: claims, claimsPct: claimsPct, payroll: payroll};
  }

  function bondPoint(date, spreadType) {
    var y = decimalYear(date);
    var spread = 1.05 - 2.1 * gaussian(y, 2007.75, .52) - 2.25 * gaussian(y, 2019.65, .50) - 1.85 * gaussian(y, 2022.72, .72) + .18 * Math.sin(y * 1.4);
    if (spreadType === "2y") spread += .28;
    var probability = clamp(7.7 + Math.max(0, -spread) * 31 + 12 * gaussian(y, 2008.5, .7), 0, 100);
    return {spread: spread, probability: probability};
  }

  var history = [], irishHistory = [], labourHistory = [];
  for (var i = 0; i <= 238; i += 1) {
    history.push(stressPoint(dateAt(i)));
    irishHistory.push(irishPoint(dateAt(i)));
    labourHistory.push(labourPoint(dateAt(i)));
  }

  function drawScore(svg, items, width, height, limit) {
    var values = items.slice(-limit).map(function (item) { return item.score; });
    var path = linePath(values, width, height, 0, 100), padding = 14;
    var area = padding + "," + (height - padding) + " " + path + " " + (width - padding) + "," + (height - padding);
    var last = path.split(" ").pop().split(",");
    svg.innerHTML = '<line class="gridline" x1="14" x2="' + (width - 14) + '" y1="' + (height - 14 - 67 * (height - 28) / 100) + '" y2="' + (height - 14 - 67 * (height - 28) / 100) + '"/><polygon class="area" points="' + area + '"/><polyline class="line" points="' + path + '"/><circle class="cursor-point" cx="' + last[0] + '" cy="' + last[1] + '" r="5"/>';
  }
  function drawComponents(svg, items) {
    var recent = items.slice(-156), keys = ["ig", "hy", "vix", "stl", "draw"], colours = ["#69645b", "#d75f47", "#15130f", "#3c7555", "#b27b16"];
    var html = '<line class="gridline" x1="14" x2="986" y1="150" y2="150"/>';
    keys.forEach(function (key, index) { html += '<polyline fill="none" stroke="' + colours[index] + '" stroke-width="2" points="' + linePath(recent.map(function (item) { return item.z[key]; }), 1000, 300, -3, 3) + '"/>'; });
    svg.innerHTML = html;
  }
  function drawIrishOverview(svg, points) {
    var recent = points.slice(-72), raw = recent.map(function (item) { return item.exportShare; });
    var rolling = raw.map(function (_, index) { var sample = raw.slice(Math.max(0, index - 11), index + 1); return sample.reduce(function (sum, value) { return sum + value; }, 0) / sample.length; });
    svg.innerHTML = '<polyline fill="none" stroke="#92c5de" stroke-width="2" points="' + linePath(raw, 700, 180, 15, 45) + '"/><polyline fill="none" stroke="#1d4f91" stroke-width="3" points="' + linePath(rolling, 700, 180, 15, 45) + '"/>';
  }
  function recessionBands(items, width, height) {
    var html = "", inBand = false, start = 0;
    items.forEach(function (item, index) {
      if (item.recession && !inBand) { start = index; inBand = true; }
      if ((!item.recession || index === items.length - 1) && inBand) {
        var end = item.recession ? index : index - 1;
        var x = 14 + start * (width - 28) / Math.max(1, items.length - 1), x2 = 14 + end * (width - 28) / Math.max(1, items.length - 1);
        html += '<rect x="' + x + '" y="14" width="' + Math.max(3, x2 - x) + '" height="' + (height - 28) + '" fill="#69645b" opacity=".16"/>';
        inBand = false;
      }
    });
    return html;
  }
  function drawBond(spreadType) {
    var index = Number(slider.value), dates = history.slice(0, index + 1), values = dates.map(function (item) { return bondPoint(item.date, spreadType).spread; });
    var svg = document.getElementById("bondChart"), zeroY = 360 - 14 - (0 + 3) * 332 / 6;
    svg.innerHTML = recessionBands(dates, 1000, 360) + '<line x1="14" x2="986" y1="' + zeroY + '" y2="' + zeroY + '" stroke="#d75f47" stroke-dasharray="7 6"/><polyline fill="none" stroke="#15130f" stroke-width="2" points="' + linePath(values, 1000, 360, -3, 3) + '"/>';
    var latest = bondPoint(dates[dates.length - 1].date, spreadType);
    document.getElementById("bondSignal").textContent = latest.spread < 0 ? "YIELD CURVE INVERTED" : "YIELD CURVE NOT INVERTED";
    document.getElementById("bondInversion").textContent = latest.spread < 0 ? "INVERTED" : "NOT INVERTED";
    document.getElementById("bondProb").textContent = Math.round(latest.probability);
    document.getElementById("baselineProb").textContent = latest.probability.toFixed(1) + "%";
  }
  function drawFriendChart(svg, series, min, max, colour, second) {
    var html = '<polyline fill="none" stroke="' + colour + '" stroke-width="2.5" points="' + linePath(series, 1000, 360, min, max) + '"/>';
    if (second) html += '<polyline fill="none" stroke="' + second.colour + '" stroke-width="2.5" points="' + linePath(second.values, 1000, 360, min, max) + '"/>';
    svg.innerHTML = html;
  }
  function drawIrishDetails(index) {
    var points = irishHistory.slice(0, index + 1), years = points.map(function (_, i) { return 100 + Math.max(0, i - 95) * 1.55 + 15 * Math.sin(i / 16); });
    var mdd = points.map(function (_, i) { return 100 + Math.max(0, i - 95) * .58 + 4 * Math.sin(i / 18); });
    drawFriendChart(document.getElementById("gdpChart"), years, 60, 260, "#d75f47", {values: mdd, colour: "#3c7555"});
    var sahm = points.map(function (item) { return item.sahm / 67 * .5; });
    document.getElementById("sahmChart").innerHTML = '<line x1="14" x2="986" y1="180" y2="180" stroke="#d75f47" stroke-width="3" stroke-dasharray="7 6"/><polyline fill="none" stroke="#15130f" stroke-width="2.5" points="' + linePath(sahm, 1000, 360, 0, 1) + '"/>';
    var exports = points.map(function (item) { return item.exportShare; }), rolling = exports.map(function (_, i) { var sample = exports.slice(Math.max(0, i - 11), i + 1); return sample.reduce(function (s, v) { return s + v; }, 0) / sample.length; });
    drawFriendChart(document.getElementById("exportChart"), exports, 15, 50, "#92c5de", {values: rolling, colour: "#1d4f91"});
    drawFriendChart(document.getElementById("probChart"), points.map(function (item) { return item.probability; }), 0, 100, "#d75f47");
  }

  function drawLabourDetails(index) {
    var points = labourHistory.slice(0, index + 1);
    var sahm = points.map(function (item) { return item.sahm; });
    var thresholdY = 360 - 14 - .5 * 332;
    document.getElementById("labourSahmChart").innerHTML = '<line x1="14" x2="986" y1="' + thresholdY + '" y2="' + thresholdY + '" stroke="#d75f47" stroke-width="3" stroke-dasharray="7 6"/><polyline fill="none" stroke="#15130f" stroke-width="2.5" points="' + linePath(sahm, 1000, 360, 0, 1) + '"/>';
    drawFriendChart(document.getElementById("claimsChart"), points.map(function (item) { return item.claimsPct; }), 0, 90, "#d75f47");
    drawFriendChart(document.getElementById("payrollChart"), points.map(function (item) { return item.payroll; }), -600, 500, "#3c7555");
    drawFriendChart(document.getElementById("revisionsChart"), points.map(function (item, i) { return item.payroll - 28 * Math.sin(i / 7); }), -600, 500, "#92c5de", {values: points.map(function (item) { return item.payroll; }), colour: "#15130f"});
  }

  function drawSensitivity(mode) {
    var sets = {
      baseline: {ig: .20, hy: .25, vix: .20, stl: .20, draw: .15},
      equal: {ig: .20, hy: .20, vix: .20, stl: .20, draw: .20},
      credit: {ig: .25, hy: .35, vix: .15, stl: .15, draw: .10}
    };
    var selected = sets[mode], scenario = 0;
    Object.keys(selected).forEach(function (key) { scenario += current.comp[key] * selected[key]; });
    var difference = scenario - current.score;
    document.getElementById("scenarioScore").textContent = scenario.toFixed(1) + " / 100";
    document.getElementById("scenarioBaseline").textContent = current.score.toFixed(1) + " / 100";
    document.getElementById("scenarioDifference").textContent = (difference >= 0 ? "+" : "") + difference.toFixed(1) + " pts";
    document.getElementById("scenarioStatus").textContent = status(scenario);
    var labels = {ig:"IG OAS",hy:"HY OAS",vix:"VIX",stl:"STLFSI",draw:"DRAWDOWN"};
    document.getElementById("weightTable").innerHTML = Object.keys(selected).map(function (key) { return "<div><strong>" + labels[key] + "</strong><span>" + Math.round(selected[key] * 100) + "%</span></div>"; }).join("");
  }

  function average(values) { return values.length ? values.reduce(function (sum, value) { return sum + value; }, 0) / values.length : 0; }
  function deviation(values) {
    var mean = average(values);
    return values.length > 1 ? Math.sqrt(values.reduce(function (sum, value) { return sum + Math.pow(value - mean, 2); }, 0) / (values.length - 1)) : 0;
  }
  function marketReturn(item, index) {
    var cycle = .008 * Math.sin(index / 5) + .004 * Math.cos(index / 11);
    var stressDrag = .025 * Math.max(0, (item.score - 55) / 45);
    var recessionDrag = item.recession ? .018 : 0;
    return clamp(.006 + cycle - stressDrag - recessionDrag, -.18, .12);
  }
  function strategyDiagnostics(cutoff) {
    var items = history.slice(0, cutoff + 1), returns = items.map(marketReturn);
    var exposure = {
      hold: items.map(function () { return 1; }),
      scaled: items.map(function (item) { return clamp(1 - item.score / 100, .2, 1); }),
      alert: items.map(function (item) { return item.score >= 67 ? .25 : item.score >= 34 ? .65 : 1; })
    };
    var output = {};
    Object.keys(exposure).forEach(function (key) {
      var series = [1], realised = [];
      for (var i = 1; i < items.length; i += 1) {
        var value = returns[i] * exposure[key][i - 1];
        realised.push(value);
        series.push(series[series.length - 1] * (1 + value));
      }
      var peak = series[0], maxDraw = 0;
      series.forEach(function (value) { peak = Math.max(peak, value); maxDraw = Math.min(maxDraw, value / peak - 1); });
      var years = Math.max(1 / 12, realised.length / 12), annualReturn = Math.pow(series[series.length - 1], 1 / years) - 1;
      var vol = deviation(realised) * Math.sqrt(12);
      output[key] = {series: series, annualReturn: annualReturn, vol: vol, sharpe: vol ? average(realised) * 12 / vol : 0, drawdown: maxDraw};
    });
    return output;
  }
  function drawStrategyLab(cutoff) {
    var result = strategyDiagnostics(cutoff), svg = document.getElementById("strategyChart"), keys = ["hold", "scaled", "alert"], colours = {hold: "#15130f", scaled: "#d75f47", alert: "#3c7555"};
    var all = [];
    keys.forEach(function (key) { all = all.concat(result[key].series); });
    var low = Math.min.apply(null, all), high = Math.max.apply(null, all);
    if (high - low < .05) high = low + .05;
    var html = '<line x1="14" x2="1086" y1="416" y2="416" stroke="#cbc3b6"/>';
    keys.forEach(function (key) { html += '<polyline fill="none" stroke="' + colours[key] + '" stroke-width="3" points="' + linePath(result[key].series, 1100, 430, low, high) + '"/>'; });
    html += '<g font-family="IBM Plex Mono, monospace" font-size="15"><text x="28" y="35" fill="#15130f">BUY &amp; HOLD</text><text x="205" y="35" fill="#d75f47">STRESS-SCALED</text><text x="405" y="35" fill="#3c7555">ALERT REDUCER</text></g>';
    svg.innerHTML = html;
    var ids = {hold: ["holdReturn", "holdVol", "holdSharpe", "holdDraw"], scaled: ["scaledReturn", "scaledVol", "scaledSharpe", "scaledDraw"], alert: ["alertReturn", "alertVol", "alertSharpe", "alertDraw"]};
    keys.forEach(function (key) {
      var values = [result[key].annualReturn, result[key].vol, result[key].sharpe, result[key].drawdown];
      document.getElementById(ids[key][0]).textContent = (values[0] * 100).toFixed(1) + "%";
      document.getElementById(ids[key][1]).textContent = (values[1] * 100).toFixed(1) + "%";
      document.getElementById(ids[key][2]).textContent = values[2].toFixed(2);
      document.getElementById(ids[key][3]).textContent = (values[3] * 100).toFixed(1) + "%";
    });
  }
  function recessionPhases(items) {
    var labels = items.map(function (item) { return item.recession ? "recession" : "expansion"; });
    items.forEach(function (item, index) {
      if (!item.recession || (index > 0 && items[index - 1].recession)) return;
      for (var before = Math.max(0, index - 6); before < index; before += 1) if (labels[before] === "expansion") labels[before] = "pre";
      var end = index;
      while (end + 1 < items.length && items[end + 1].recession) end += 1;
      for (var after = end + 1; after <= Math.min(items.length - 1, end + 6); after += 1) if (labels[after] === "expansion") labels[after] = "recovery";
    });
    var groups = {expansion: [], pre: [], recession: [], recovery: []};
    labels.forEach(function (label, index) { groups[label].push((items[index].score - 50) / (50 / 3)); });
    return groups;
  }
  function drawPhaseLab(cutoff) {
    var phases = recessionPhases(history.slice(0, cutoff + 1));
    [["phaseExpansion", "expansion"], ["phasePre", "pre"], ["phaseRecession", "recession"], ["phaseRecovery", "recovery"]].forEach(function (pair) {
      var values = phases[pair[1]], node = document.getElementById(pair[0]);
      node.textContent = values.length ? average(values).toFixed(2) + " z" : "n/a";
    });
  }
  function projectTerrain(x, y, z, width, height) {
    var cy = Math.cos(terrain.yaw), sy = Math.sin(terrain.yaw), cp = Math.cos(terrain.pitch), sp = Math.sin(terrain.pitch);
    var rx = x * cy - y * sy, ry = x * sy + y * cy;
    return {x: width * .5 + rx * terrain.zoom, y: height * .58 + (ry * sp - z * cp) * terrain.zoom, depth: ry * cp + z * sp};
  }
  function drawTerrainCanvas(canvas, cutoff, compact) {
    if (!canvas || canvas.closest("[hidden]")) return;
    var ratio = Math.min(window.devicePixelRatio || 1, 2), width = Math.max(320, canvas.clientWidth), height = Math.max(360, canvas.clientHeight);
    canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    var ctx = canvas.getContext("2d"); ctx.setTransform(ratio, 0, 0, ratio, 0, 0); ctx.clearRect(0, 0, width, height);
    var historyLength = compact ? 72 : 100;
    var points = history.slice(Math.max(0, cutoff - historyLength + 1), cutoff + 1), keys = ["ig", "hy", "vix", "stl", "draw"], cells = [];
    var xScale = Math.min(width * (compact ? .68 : .62) / Math.max(1, points.length - 1), 8), yScale = Math.min(width, height) * .095, zScale = height * .0035;
    for (var row = 0; row < keys.length - 1; row += 1) {
      for (var col = 0; col < points.length - 1; col += 1) {
        var x1 = (col - (points.length - 1) / 2) * xScale, x2 = (col + 1 - (points.length - 1) / 2) * xScale;
        var y1 = (row - 2) * yScale, y2 = (row + 1 - 2) * yScale;
        var vertices = [projectTerrain(x1, y1, points[col].comp[keys[row]] * zScale, width, height), projectTerrain(x2, y1, points[col + 1].comp[keys[row]] * zScale, width, height), projectTerrain(x2, y2, points[col + 1].comp[keys[row + 1]] * zScale, width, height), projectTerrain(x1, y2, points[col].comp[keys[row + 1]] * zScale, width, height)];
        cells.push({vertices: vertices, depth: average(vertices.map(function (point) { return point.depth; })), recession: points[col].recession, level: average([points[col].comp[keys[row]], points[col + 1].comp[keys[row]], points[col + 1].comp[keys[row + 1]], points[col].comp[keys[row + 1]]])});
      }
    }
    cells.sort(function (a, b) { return a.depth - b.depth; }).forEach(function (cell) {
      ctx.beginPath(); cell.vertices.forEach(function (point, index) { if (index) ctx.lineTo(point.x, point.y); else ctx.moveTo(point.x, point.y); }); ctx.closePath();
      ctx.fillStyle = cell.recession ? "rgba(215,95,71," + (.30 + cell.level / 260).toFixed(2) + ")" : "rgba(245,189,62," + (.18 + cell.level / 320).toFixed(2) + ")";
      ctx.fill(); ctx.strokeStyle = "rgba(21,19,15,.22)"; ctx.lineWidth = .7; ctx.stroke();
    });
    ctx.fillStyle = "#15130f"; ctx.font = "600 " + (compact ? 9 : 11) + "px IBM Plex Mono, monospace";
    keys.forEach(function (key, row) { var label = projectTerrain(-(points.length - 1) / 2 * xScale - 22, (row - 2) * yScale, 0, width, height); ctx.fillText(key === "draw" ? "DRAWDOWN" : key.toUpperCase(), label.x - (compact ? 48 : 58), label.y + 4); });
    ctx.fillStyle = "#69645b"; ctx.font = (compact ? 9 : 11) + "px IBM Plex Mono, monospace"; ctx.fillText(compact ? "DRAG TO ROTATE · HEIGHT = STRESS" : "DRAG TO ROTATE · SCROLL TO ZOOM · HEIGHT = STRESS", 18, 24);
  }
  function drawTerrain(cutoff) {
    drawTerrainCanvas(document.getElementById("terrainCanvas"), cutoff, false);
    drawTerrainCanvas(document.getElementById("overviewTerrainCanvas"), cutoff, true);
  }
  function drawSignalLab(cutoff) { drawStrategyLab(cutoff); drawPhaseLab(cutoff); drawTerrain(cutoff); }

  function episodes(flags) {
    var output = [], active = null;
    flags.forEach(function (flag, index) { if (flag && !active) active = {start: index, end: index}; else if (flag && active) active.end = index; else if (!flag && active) { output.push(active); active = null; } });
    if (active) output.push(active);
    return output;
  }
  function evaluateBacktest(cutoff) {
    var items = history.slice(0, cutoff + 1), alertThreshold = Number(threshold.value), alerts = episodes(items.map(function (item) { return item.score >= alertThreshold; })), recessions = episodes(items.map(function (item) { return item.recession; })), matched = {}, leads = [];
    recessions.forEach(function (recession) { var found = -1; alerts.forEach(function (alert, index) { if (!matched[index] && alert.start <= recession.start && alert.start >= recession.start - 12) found = index; }); if (found >= 0) { matched[found] = true; leads.push(recession.start - alerts[found].start); } });
    return {items: items, threshold: alertThreshold, alerts: alerts, recessions: recessions, hits: leads.length, falseAlarms: alerts.length - leads.length, precision: alerts.length ? leads.length / alerts.length : 0, lead: leads.length ? leads.sort(function (a, b) { return a - b; })[Math.floor(leads.length / 2)] : null};
  }
  function drawBacktest(result) {
    var svg = document.getElementById("backtestChart"), width = 1000, height = 330, y = height - 14 - result.threshold * 302 / 100;
    svg.innerHTML = recessionBands(result.items, width, height).replaceAll("#69645b", "#d75f47") + '<line x1="14" x2="986" y1="' + y + '" y2="' + y + '" stroke="#d75f47" stroke-dasharray="7 6"/><polyline class="line" points="' + linePath(result.items.map(function (item) { return item.score; }), width, height, 0, 100) + '"/>';
    document.getElementById("thresholdOut").textContent = result.threshold;
    document.getElementById("caughtMetric").textContent = result.hits + "/" + result.recessions.length;
    document.getElementById("falseMetric").textContent = result.falseAlarms;
    document.getElementById("precisionMetric").textContent = Math.round(result.precision * 100) + "%";
    document.getElementById("leadMetric").textContent = result.lead === null ? "No matched alert" : result.lead * 4 + " weeks";
  }

  function stressVerdict(score, breadth) {
    if (score >= 67) return breadth + " of 5 market channels show acute stress; the signal is broad enough to warrant an alert.";
    if (score >= 34) return "Financial conditions are mixed or moderately elevated; monitor whether pressure spreads across markets.";
    return "Credit, volatility and drawdown measures remain contained relative to their trailing history.";
  }
  function update() {
    var index = Number(slider.value), items = history.slice(0, index + 1), stress = items[index], irish = irishHistory[index], labour = labourHistory[index], bond = bondPoint(stress.date, "3m"), composite = (stress.score + irish.score + labour.score + bond.probability) / 4;
    current = stress;
    document.getElementById("selectedDate").textContent = stress.date.toLocaleString("en-GB", {month: "long", timeZone: "UTC"}).toUpperCase() + " " + stress.date.getUTCFullYear();
    document.getElementById("headerDate").textContent = formatDate(stress.date);
    document.getElementById("bondDate").textContent = stress.date.toLocaleString("en-GB", {month: "short", year: "numeric", timeZone: "UTC"}).toUpperCase();
    ["stressScore", "detailScore"].forEach(function (id) { document.getElementById(id).textContent = Math.round(stress.score); });
    document.getElementById("stressStatus").textContent = status(stress.score); document.getElementById("stressStatus").className = statusClass(stress.score);
    document.getElementById("detailStatus").textContent = status(stress.score);
    document.getElementById("stressVerdict").textContent = stressVerdict(stress.score, stress.breadth);
    var strongestKey = Object.keys(stress.comp).sort(function (a, b) { return stress.comp[b] - stress.comp[a]; })[0];
    var terrainNames = {ig: "IG OAS", hy: "HY OAS", vix: "VIX", stl: "STLFSI", draw: "DRAWDOWN"};
    document.getElementById("terrainCurrentScore").textContent = Math.round(stress.score);
    document.getElementById("terrainCurrentStatus").textContent = status(stress.score);
    document.getElementById("terrainCurrentCopy").textContent = stressVerdict(stress.score, stress.breadth);
    document.getElementById("terrainBreadth").textContent = stress.breadth + " OF 5";
    document.getElementById("terrainStrongest").textContent = terrainNames[strongestKey] + " · " + Math.round(stress.comp[strongestKey]) + "/100";
    document.getElementById("matrixLabScore").textContent = Math.round(stress.score);
    document.getElementById("matrixLabReading").textContent = status(stress.score) + " · " + stress.breadth + " of 5 channels in alert · strongest: " + terrainNames[strongestKey];
    document.getElementById("hyMetric").textContent = stress.z.hy.toFixed(2).replace("-", "−"); document.getElementById("vixMetric").textContent = stress.z.vix.toFixed(2).replace("-", "−"); document.getElementById("breadthMetric").textContent = stress.breadth + "/5";
    document.getElementById("compositeScore").textContent = Math.round(composite); document.getElementById("compositeStatus").textContent = status(composite); document.getElementById("riskMarker").style.left = composite + "%";
    document.getElementById("irishScore").textContent = Math.round(irish.score); document.getElementById("irishDetailScore").textContent = Math.round(irish.score); document.getElementById("irishStatus").textContent = status(irish.score); document.getElementById("irishStatus").className = statusClass(irish.score);
    document.getElementById("irishVerdict").textContent = irish.score >= 34 ? "Irish Lens indicators are mixed or moderately elevated; monitor US transmission and domestic warning signals." : "Irish Lens indicators remain contained relative to the current scoring thresholds.";
    document.getElementById("labourScore").textContent = Math.round(labour.score); document.getElementById("labourDetailScore").textContent = Math.round(labour.score); document.getElementById("labourStatus").textContent = status(labour.score); document.getElementById("labourStatus").className = statusClass(labour.score); document.getElementById("labourDetailStatus").textContent = status(labour.score);
    document.getElementById("labourSahm").textContent = labour.sahm.toFixed(2); document.getElementById("labourClaims").textContent = labour.claims ? "YES" : "NO";
    document.getElementById("labourVerdict").textContent = labour.score >= 75 ? "The labour market is confirming a recession warning." : labour.score >= 40 ? "The labour market is weakening without yet confirming a recession." : "The labour market is not confirming a recession.";
    document.getElementById("exportMetric").textContent = irish.exportShare.toFixed(1) + "%"; document.getElementById("probMetric").textContent = irish.probability.toFixed(1) + "%";
    document.getElementById("detailDate").textContent = formatDate(stress.date);
    var names = {ig: "IG OAS", hy: "HY OAS", vix: "VIX", stl: "STLFSI", draw: "DRAW"};
    document.getElementById("componentBars").innerHTML = Object.keys(names).map(function (key) { return '<span>' + names[key] + '<i style="--level:' + stress.comp[key] + '%"></i></span>'; }).join("");
    [["detailIg", "ig"], ["detailHy", "hy"], ["detailVix", "vix"], ["detailStl", "stl"], ["detailDraw", "draw"]].forEach(function (pair) { document.getElementById(pair[0]).textContent = Math.round(stress.comp[pair[1]]) + "/100"; });
    drawScore(document.getElementById("stressChart"), items, 700, 180, 104); drawScore(document.getElementById("labourChart"), labourHistory.slice(0, index + 1), 700, 180, 104); drawComponents(document.getElementById("detailChart"), items); drawIrishOverview(document.getElementById("irishChart"), irishHistory.slice(0, index + 1)); drawIrishDetails(index); drawLabourDetails(index); drawBond(document.querySelector(".spread-choice.active").dataset.spread); drawBacktest(evaluateBacktest(index)); drawSensitivity(document.querySelector(".weight-choice.active").dataset.weight); drawSignalLab(index);
  }

  function enter() { var intro = document.getElementById("intro"), workspace = document.getElementById("workspace"); intro.classList.add("leaving"); setTimeout(function () { intro.hidden = true; workspace.hidden = false; document.body.classList.remove("intro-active"); workspace.focus({preventScroll: true}); update(); }, window.matchMedia("(prefers-reduced-motion:reduce)").matches ? 0 : 500); }
  function openPage(pageId) { document.getElementById("workspace").hidden = true; document.getElementById(pageId).hidden = false; window.scrollTo(0, 0); update(); }
  function closePages() { document.querySelectorAll(".detail-page").forEach(function (page) { page.hidden = true; }); document.getElementById("workspace").hidden = false; window.scrollTo(0, 0); update(); }
  function switchViews(button, tabAttribute, viewAttribute) { var value = button.dataset[tabAttribute]; button.parentElement.querySelectorAll("button").forEach(function (item) { item.classList.toggle("active", item === button); }); button.closest(".detail-page").querySelectorAll("[data-" + viewAttribute.replace(/[A-Z]/g, function (letter) { return "-" + letter.toLowerCase(); }) + "]").forEach(function (view) { view.hidden = view.dataset[viewAttribute] !== value; }); }
  function download() { var rows = ["date,ig_oas_z,hy_oas_z,vix_z,stlfsi_z,drawdown_z,score,breadth,us_recession"]; history.slice(0, Number(slider.value) + 1).forEach(function (item) { rows.push([item.date.toISOString().slice(0, 10), item.z.ig.toFixed(4), item.z.hy.toFixed(4), item.z.vix.toFixed(4), item.z.stl.toFixed(4), item.z.draw.toFixed(4), item.score.toFixed(2), item.breadth, item.recession ? 1 : 0].join(",")); }); var anchor = document.createElement("a"); anchor.href = URL.createObjectURL(new Blob([rows.join("\n")], {type: "text/csv"})); anchor.download = "financial-stress-evidence-" + current.date.toISOString().slice(0, 10) + ".csv"; anchor.click(); URL.revokeObjectURL(anchor.href); }

  document.getElementById("continueButton").addEventListener("click", enter); document.querySelector(".skip-link").addEventListener("click", function (event) { event.preventDefault(); enter(); });
  slider.addEventListener("input", update); threshold.addEventListener("input", function () { drawBacktest(evaluateBacktest(Number(slider.value))); });
  document.getElementById("openStress").addEventListener("click", function () { openPage("detailPage"); }); document.getElementById("openBond").addEventListener("click", function () { openPage("bondPage"); }); document.getElementById("openLabour").addEventListener("click", function () { openPage("labourPage"); }); document.getElementById("openIrish").addEventListener("click", function () { openPage("irishPage"); }); document.getElementById("connectionsButton").addEventListener("click", function () { openPage("connectionsPage"); }); document.getElementById("signalLabButton").addEventListener("click", function () { openPage("signalLabPage"); }); document.getElementById("openSignalLabCard").addEventListener("click", function () { openPage("signalLabPage"); });
  document.getElementById("closeDetail").addEventListener("click", closePages); document.querySelectorAll(".friend-back").forEach(function (button) { button.addEventListener("click", closePages); });
  document.querySelectorAll("[data-detail-tab]").forEach(function (button) { button.addEventListener("click", function () { switchViews(button, "detailTab", "detailView"); }); });
  document.querySelectorAll("[data-bond-tab]").forEach(function (button) { button.addEventListener("click", function () { switchViews(button, "bondTab", "bondView"); }); });
  document.querySelectorAll("[data-irish-tab]").forEach(function (button) { button.addEventListener("click", function () { switchViews(button, "irishTab", "irishView"); }); });
  document.querySelectorAll("[data-labour-tab]").forEach(function (button) { button.addEventListener("click", function () { switchViews(button, "labourTab", "labourView"); }); });
  document.querySelectorAll("[data-lab-tab]").forEach(function (button) { button.addEventListener("click", function () { switchViews(button, "labTab", "labView"); if (button.dataset.labTab === "terrain") drawTerrain(Number(slider.value)); }); });
  document.querySelectorAll(".weight-choice").forEach(function (button) { button.addEventListener("click", function () { document.querySelectorAll(".weight-choice").forEach(function (item) { item.classList.toggle("active", item === button); }); drawSensitivity(button.dataset.weight); }); });
  document.querySelectorAll(".spread-choice").forEach(function (button) { button.addEventListener("click", function () { document.querySelectorAll(".spread-choice").forEach(function (item) { item.classList.toggle("active", item === button); }); drawBond(button.dataset.spread); }); });
  document.getElementById("downloadEvidence").addEventListener("click", download);
  document.getElementById("fredKeyForm").addEventListener("submit", function (event) { event.preventDefault(); var input = document.getElementById("fredKey"); if (input.value.trim()) { document.getElementById("fredConnectionStatus").textContent = "CONNECTED"; input.value = ""; } }); document.getElementById("clearFredKey").addEventListener("click", function () { document.getElementById("fredConnectionStatus").textContent = "CACHED"; document.getElementById("fredKey").value = ""; });
  var note = document.getElementById("methodNote"); document.getElementById("helpButton").addEventListener("click", function () { note.hidden = !note.hidden; }); document.getElementById("closeMethod").addEventListener("click", function () { note.hidden = true; });
  function bindTerrain(canvas) {
    canvas.addEventListener("pointerdown", function (event) { terrain.dragging = true; terrain.x = event.clientX; terrain.y = event.clientY; canvas.setPointerCapture(event.pointerId); });
    canvas.addEventListener("pointermove", function (event) { if (!terrain.dragging) return; terrain.yaw += (event.clientX - terrain.x) * .008; terrain.pitch = clamp(terrain.pitch + (event.clientY - terrain.y) * .006, .18, 1.35); terrain.x = event.clientX; terrain.y = event.clientY; drawTerrain(Number(slider.value)); });
    canvas.addEventListener("pointerup", function () { terrain.dragging = false; });
    canvas.addEventListener("pointercancel", function () { terrain.dragging = false; });
    canvas.addEventListener("wheel", function (event) { event.preventDefault(); terrain.zoom = clamp(terrain.zoom * (event.deltaY > 0 ? .9 : 1.1), .55, 2.2); drawTerrain(Number(slider.value)); }, {passive: false});
  }
  bindTerrain(document.getElementById("terrainCanvas"));
  bindTerrain(document.getElementById("overviewTerrainCanvas"));
  window.addEventListener("resize", function () { drawTerrain(Number(slider.value)); });
  document.addEventListener("keydown", function (event) { if (event.key === "Escape") { if (!note.hidden) note.hidden = true; else closePages(); } });
  update();
})();
