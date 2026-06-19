const form = document.querySelector("#projectForm");
const healthStatus = document.querySelector("#healthStatus");
const routesEl = document.querySelector("#routes");
const summaryEl = document.querySelector("#summary");
const reportEl = document.querySelector("#reportPreview");
const routeLines = document.querySelector("#routeLines");
const downloadBtn = document.querySelector("#downloadMarkdown");

let latestReport = "";

const levelLabels = {
  candidate: "利用候補",
  caution: "注意",
  confirm_required: "要確認",
  exclusion_consideration: "除外検討",
  data_insufficient: "データ不足",
};

const routeColors = ["#245b47", "#b8472f", "#3d556c", "#8c6b2c", "#6f4b7a"];

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "content-type": "application/json",
      "x-user-id": "local-ui",
      "x-user-role": "planner",
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status}: ${detail}`);
  }
  return response.json();
}

async function checkHealth() {
  try {
    await api("/api/health");
    healthStatus.textContent = "API正常";
  } catch (error) {
    healthStatus.textContent = "APIエラー";
  }
}

function numberOrNull(value) {
  return value === "" ? null : Number(value);
}

function formPayload(formData) {
  return {
    project_name: formData.get("project_name"),
    site_name: formData.get("site_name"),
    planner: formData.get("planner"),
    owner_type: "社内検討",
    start: {
      name: formData.get("start_name"),
      lat: Number(formData.get("start_lat")),
      lng: Number(formData.get("start_lng")),
    },
    destination: {
      name: formData.get("destination_name"),
      lat: Number(formData.get("destination_lat")),
      lng: Number(formData.get("destination_lng")),
    },
    vehicle: {
      vehicle_type: formData.get("vehicle_type"),
      height_m: numberOrNull(formData.get("height_m")),
      gross_weight_t: numberOrNull(formData.get("gross_weight_t")),
      special_vehicle_flag: formData.get("special_vehicle_flag") === "on",
    },
    delivery: {
      time_window: formData.get("time_window"),
      holiday: false,
      night_delivery_allowed: formData.get("time_window") === "night",
    },
    avoid_conditions: ["schools", "residential"],
  };
}

async function runEvaluation(event) {
  event.preventDefault();
  setBusy(true);
  summaryEl.className = "summary";
  summaryEl.textContent = "案件作成と候補評価を実行中です。";
  routesEl.innerHTML = "";
  reportEl.textContent = "";
  routeLines.innerHTML = "";

  try {
    const project = await api("/api/projects", {
      method: "POST",
      body: JSON.stringify(formPayload(new FormData(form))),
    });
    const generated = await api(`/api/projects/${project.id}/routes/generate`, {
      method: "POST",
      body: JSON.stringify({}),
    });

    const evaluatedRoutes = [];
    for (const route of generated.routes) {
      await api(`/api/routes/${route.id}/evaluate`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      evaluatedRoutes.push(await api(`/api/routes/${route.id}`));
    }

    const report = await api(`/api/projects/${project.id}/report?format=markdown`);
    latestReport = report.content;
    reportEl.textContent = latestReport;
    downloadBtn.disabled = false;
    renderRoutes(evaluatedRoutes);
    renderMap(evaluatedRoutes);
    const topRisk = Math.max(...evaluatedRoutes.map((route) => route.risk_score));
    summaryEl.textContent = `${evaluatedRoutes.length}件の候補を評価しました。最大リスクスコア ${topRisk}。正式判断には追加確認が必要です。`;
  } catch (error) {
    summaryEl.textContent = `評価に失敗しました: ${error.message}`;
  } finally {
    setBusy(false);
  }
}

function renderRoutes(routes) {
  routesEl.innerHTML = routes
    .map(
      (route) => `
        <article class="route-card level-${route.risk_level}">
          <h3>${route.name}</h3>
          <div class="metrics">
            <span class="metric">${route.distance_km.toFixed(1)} km</span>
            <span class="metric">${route.duration_min} 分</span>
            <span class="metric">${levelLabels[route.risk_level]}</span>
            <span class="metric">Score ${route.risk_score}</span>
          </div>
          <p>${route.summary}</p>
          <ul class="risk">
            ${route.risks
              .slice(0, 4)
              .map((risk) => `<li><strong>${levelLabels[risk.level]}</strong> ${risk.title}<br>${risk.confirmation_target}</li>`)
              .join("")}
          </ul>
        </article>
      `,
    )
    .join("");
}

function renderMap(routes) {
  const baseY = [300, 260, 220, 180, 140];
  routeLines.innerHTML = routes
    .map((route, index) => {
      const y = baseY[index] || 160;
      const color = routeColors[index % routeColors.length];
      const points = `90,${y} 250,${y - 70} 420,${y - 20} 590,${y - 92} 720,${y - 40}`;
      const risks = route.risks
        .slice(0, 5)
        .map((risk, riskIndex) => {
          const x = 210 + riskIndex * 92 + index * 8;
          const cy = y - 36 + (riskIndex % 2) * 28;
          return `<circle cx="${x}" cy="${cy}" r="8" fill="#ffffff" stroke="${color}" stroke-width="4"><title>${risk.title}</title></circle>`;
        })
        .join("");
      return `
        <polyline points="${points}" fill="none" stroke="${color}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round" opacity="0.88"></polyline>
        ${risks}
      `;
    })
    .join("");
}

function setBusy(isBusy) {
  form.querySelector("button").disabled = isBusy;
}

downloadBtn.addEventListener("click", () => {
  const blob = new Blob([latestReport], { type: "text/markdown;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "construction-logistics-route-risk.md";
  link.click();
  URL.revokeObjectURL(link.href);
});

form.addEventListener("submit", runEvaluation);
checkHealth();
