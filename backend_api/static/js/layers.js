// Global state for active layers
const activeLayers = {
    pressure: true, // Default to pressure being active
    wind: false,
    temp: false,
    thunder: false,
    satellite: false
};

// ========== LAYER TOGGLE ==========
function toggleLayer(layer) {
    Object.keys(activeLayers).forEach(key => {
        if (key !== layer) activeLayers[key] = false;
    });
    activeLayers[layer] = !activeLayers[layer];

    console.log(`Layer ${layer} toggled. State: ${activeLayers[layer]}`);

    if (typeof window.renderAll === 'function') {
        window.renderAll();
    }

    updateLayerButtonsUI();
    updateLegend(layer); // Update the legend when layer is toggled
}
window.toggleLayer = toggleLayer;

// ========== LEGEND UPDATE ==========
function updateLegend(layerType) {
    const legendContainer = document.getElementById('colorLegend');
    const legendContent = document.getElementById('legendContent');
    const legendTitle = legendContainer ? legendContainer.querySelector('h3') : null;

    if (!legendContainer || !legendContent || !legendTitle) return;

    // Get the specific legend data for the active layer
    const legendData = (typeof getColorScaleLegend === 'function') ? getColorScaleLegend(layerType) : [];

    // Define titles for each layer
    const titles = {
        pressure: 'Áp suất (hPa)',
        wind: 'Tốc độ gió (m/s)',
        temp: 'Nhiệt độ (°C)',
        thunder: 'Khả năng giông bão (%)'
    };

    // Hide legend for satellite or layers with no data, or if the layer is inactive
    if (!activeLayers[layerType] || !legendData || legendData.length === 0 || layerType === 'satellite') {
        legendContainer.classList.add('hidden');
        return;
    }

    // Update legend title
    legendTitle.innerHTML = `<i class="fas fa-palette text-blue-500"></i> ${titles[layerType] || 'Chú thích'}`;

    // Build the legend HTML
    let html = '<div class="space-y-1.5 text-xs font-semibold text-slate-600">';
    legendData.forEach(item => {
        html += `
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                    <span class="w-3 h-3 rounded-full" style="background-color: ${item.color}; border: 1px solid rgba(0,0,0,0.1);"></span>
                    <span>${item.value}</span>
                </div>
                ${item.label ? `<span class="font-bold">${item.label}</span>` : ''}
            </div>
        `;
    });
    html += '</div>';

    // Update the DOM and show the legend
    legendContent.innerHTML = html;
    legendContainer.classList.remove('hidden');
}


// Function to update the visual state of the layer buttons
function updateLayerButtonsUI() {
    document.querySelectorAll('.layer-item').forEach(button => {
        const layerNameMatch = button.onclick.toString().match(/toggleLayer\('(\w+)'\)/);
        const layerName = layerNameMatch ? layerNameMatch[1] : null;
        const dotElement = document.getElementById(`dot-${layerName}`);

        if (layerName && activeLayers[layerName]) {
            button.classList.add('active');
            button.classList.remove('bg-white/40', 'border-white/60');
            button.classList.add('bg-blue-500/80', 'border-blue-700');
            if (dotElement) {
                dotElement.classList.remove('border-slate-300');
                dotElement.classList.add('bg-white', 'border-white');
            }
        } else if (layerName) {
            button.classList.remove('active');
            button.classList.remove('bg-blue-500/80', 'border-blue-700');
            button.classList.add('bg-white/40', 'border-white/60');
            if (dotElement) {
                dotElement.classList.remove('bg-white', 'border-white');
                dotElement.classList.add('border-slate-300');
            }
        }
    });
}
window.updateLayerButtonsUI = updateLayerButtonsUI;

// ========== RENDER LAYER (NO DATA FETCHING) ==========
function renderLayer(data) {
    if (!data) {
        console.warn('⚠️ renderLayer called with no data.');
        return;
    }
    clearAllOverlays();
    if (activeLayers.pressure) {
        renderPressureHeatmap(data);
    } else if (activeLayers.wind) {
        renderWindHeatmap(data);
    } else if (activeLayers.temp) {
        renderTempHeatmap(data);
    } else if (activeLayers.thunder) {
        renderThunderLayer(data);
    } else if (activeLayers.satellite) {
        renderSatelliteLayer();
    }
}
window.renderLayer = renderLayer;

// ========== CLEAR ALL OVERLAYS ==========
function clearAllOverlays() {
    if (pressureOverlay) {
        try {
            map.removeLayer(pressureOverlay);
            pressureOverlay = null;
        } catch(e) {
            console.warn('Lỗi khi xóa overlay:', e);
        }
    }
    // Clear wind canvas
    const canvas = document.getElementById('windCanvas');
    if (canvas) {
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }

    if (window.satelliteLayer) {
        try {
            map.removeLayer(window.satelliteLayer);
            window.satelliteLayer = null;
        } catch(e) {}
    }
    console.log('🗑️ Đã xóa tất cả các overlays.');
}

/* ============================================================
   1. PRESSURE HEATMAP
   ============================================================ */
function renderPressureHeatmap(data) {
    console.log('🌡️ === VẼ PRESSURE HEATMAP ===');

    const latitude = data.lat || data.latitude;
    const longitude = data.lon || data.longitude;
    const prmsl = data.prmsl || data.msl;

    if (!latitude || !longitude || !prmsl) {
        console.error('❌ Thiếu dữ liệu áp suất');
        alert('Lỗi: File GRIB không chứa dữ liệu áp suất');
        return;
    }

    const filtered = filterSouthChinaSea(latitude, longitude, prmsl);
    if (!filtered) {
        alert('Không có dữ liệu trong vùng Biển Đông');
        return;
    }

    const { filteredLat, filteredLon, filteredData, latMin, latMax, lonMin, lonMax } = filtered;

    // Tìm min/max
    let pmin = Infinity, pmax = -Infinity;
    for (let row of filteredData) {
        for (let val of row) {
            if (val != null && !isNaN(val)) {
                if (val < pmin) pmin = val;
                if (val > pmax) pmax = val;
            }
        }
    }

    console.log(`📊 Áp suất: Min=${pmin/100} hPa, Max=${pmax/100} hPa`);

    // Canvas
    const cellSize = 6;
    const width = filteredLon.length * cellSize;
    const height = filteredLat.length * cellSize;

    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');

    for (let i = 0; i < filteredLat.length; i++) {
        for (let j = 0; j < filteredLon.length; j++) {
            const val = filteredData[i][j];

            ctx.fillStyle = (val == null || isNaN(val))
                ? "rgba(0,0,0,0)"
                : pressureColorEnhanced(val / 100);

            const y = height - (i + 1) * cellSize;
            ctx.fillRect(j * cellSize, y, cellSize, cellSize);
        }
    }

    const imageUrl = canvas.toDataURL();
    pressureOverlay = L.imageOverlay(imageUrl, [[latMin, lonMin], [latMax, lonMax]], {
        opacity: 0.85,
        zIndex: 650
    }).addTo(map);

    console.log("✅ Pressure heatmap vẽ xong");
}

function pressureColorEnhanced(p) {
    if (p < 940) return "rgba(138, 0, 138, 0.9)";
    if (p < 960) return "rgba(180, 0, 180, 0.9)";
    if (p < 980) return "rgba(255, 0, 255, 0.9)";
    if (p < 990) return "rgba(255, 0, 0, 0.9)";
    if (p < 1000) return "rgba(255, 128, 0, 0.9)";
    if (p < 1008) return "rgba(255, 204, 0, 0.85)";
    if (p < 1012) return "rgba(255, 255, 0, 0.85)";
    if (p < 1016) return "rgba(128, 255, 128, 0.8)";
    if (p < 1020) return "rgba(0, 255, 255, 0.8)";
    if (p < 1024) return "rgba(0, 128, 255, 0.8)";
    if (p < 1028) return "rgba(0, 0, 255, 0.8)";
    return "rgba(0, 0, 128, 0.8)";
}

/* ============================================================
   2. WIND HEATMAP
   ============================================================ */
function renderWindHeatmap(data) {
    console.log('💨 === VẼ WIND HEATMAP ===');

    const latitude = data.lat || data.latitude;
    const longitude = data.lon || data.longitude;
    const u = data.u || data.u10;
    const v = data.v || data.v10;

    if (!latitude || !longitude || !u || !v) {
        alert("Thiếu dữ liệu gió");
        return;
    }

    // Tính tốc độ gió
    const ws = [];
    for (let i = 0; i < u.length; i++) {
        const row = [];
        for (let j = 0; j < u[i].length; j++) {
            if (!isNaN(u[i][j]) && !isNaN(v[i][j])) {
                row.push(Math.sqrt(u[i][j] ** 2 + v[i][j] ** 2));
            } else row.push(null);
        }
        ws.push(row);
    }

    const filtered = filterSouthChinaSea(latitude, longitude, ws);
    if (!filtered) return;

    const { filteredLat, filteredLon, filteredData, latMin, latMax, lonMin, lonMax } = filtered;

    // Canvas
    const cellSize = 6;
    const width = filteredLon.length * cellSize;
    const height = filteredLat.length * cellSize;

    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');

    for (let i = 0; i < filteredLat.length; i++) {
        for (let j = 0; j < filteredLon.length; j++) {
            ctx.fillStyle = filteredData[i][j] == null
                ? "rgba(0,0,0,0)"
                : windColorEnhanced(filteredData[i][j]);

            const y = height - (i + 1) * cellSize;
            ctx.fillRect(j * cellSize, y, cellSize, cellSize);
        }
    }

    const imageUrl = canvas.toDataURL();
    pressureOverlay = L.imageOverlay(imageUrl, [[latMin, lonMin], [latMax, lonMax]], {
        opacity: 0.85,
        zIndex: 650
    }).addTo(map);

    console.log("✅ Wind heatmap vẽ xong");
}

function windColorEnhanced(ws) {
    if (ws < 1) return "rgba(240,240,240,0.7)";
    if (ws < 3) return "rgba(200,230,255,0.85)";
    if (ws < 5) return "rgba(135,206,250,0.85)";
    if (ws < 8) return "rgba(100,200,255,0.85)";
    if (ws < 11) return "rgba(0,255,255,0.85)";
    if (ws < 14) return "rgba(0,255,0,0.85)";
    if (ws < 17) return "rgba(255,255,0,0.85)";
    if (ws < 21) return "rgba(255,200,0,0.9)";
    if (ws < 25) return "rgba(255,128,0,0.9)";
    if (ws < 29) return "rgba(255,64,0,0.9)";
    if (ws < 33) return "rgba(255,0,0,0.9)";
    if (ws < 38) return "rgba(200,0,128,0.95)";
    if (ws < 43) return "rgba(150,0,200,0.95)";
    return "rgba(128,0,255,0.95)";
}

/* ============================================================
   3. TEMPERATURE HEATMAP
   ============================================================ */
function renderTempHeatmap(data) {
    console.log('🌡️ === VẼ TEMPERATURE HEATMAP ===');

    const latitude = data.lat || data.latitude;
    const longitude = data.lon || data.longitude;
    const temp = data.temp || data.t || data.t2m;

    if (!latitude || !longitude || !temp) {
        alert("Thiếu dữ liệu nhiệt độ");
        return;
    }

    const filtered = filterSouthChinaSea(latitude, longitude, temp);
    if (!filtered) return;

    const { filteredLat, filteredLon, filteredData, latMin, latMax, lonMin, lonMax } = filtered;

    // Kiểm tra Kelvin hay °C
    let tmin = Infinity;
    for (let row of filteredData)
        for (let v of row)
            if (v != null && !isNaN(v))
                tmin = Math.min(tmin, v);

    const isKelvin = tmin > 200;

    const cellSize = 6;
    const width = filteredLon.length * cellSize;
    const height = filteredLat.length * cellSize;

    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');

    for (let i = 0; i < filteredLat.length; i++) {
        for (let j = 0; j < filteredLon.length; j++) {
            let t = filteredData[i][j];
            if (t == null || isNaN(t)) {
                ctx.fillStyle = "rgba(0,0,0,0)";
            } else {
                t = isKelvin ? t - 273.15 : t;
                ctx.fillStyle = tempColorEnhanced(t);
            }
            const y = height - (i + 1) * cellSize;
            ctx.fillRect(j * cellSize, y, cellSize, cellSize);
        }
    }

    pressureOverlay = L.imageOverlay(canvas.toDataURL(), [[latMin, lonMin], [latMax, lonMax]], {
        opacity: 0.85,
        zIndex: 650
    }).addTo(map);

    console.log("✅ Temp heatmap vẽ xong");
}

function tempColorEnhanced(c) {
    if (c < 0) return "rgba(148,0,211,0.85)";
    if (c < 5) return "rgba(0,0,255,0.85)";
    if (c < 10) return "rgba(0,128,255,0.85)";
    if (c < 15) return "rgba(0,200,255,0.85)";
    if (c < 20) return "rgba(0,255,200,0.85)";
    if (c < 23) return "rgba(0,255,0,0.85)";
    if (c < 26) return "rgba(200,255,0,0.85)";
    if (c < 28) return "rgba(255,255,0,0.85)";
    if (c < 30) return "rgba(255,200,0,0.85)";
    if (c < 32) return "rgba(255,128,0,0.9)";
    if (c < 34) return "rgba(255,64,0,0.9)";
    if (c < 36) return "rgba(255,0,0,0.9)";
    return "rgba(128,0,0,0.9)";
}

/* ============================================================
   FILTER TO SOUTH CHINA SEA
   ============================================================ */
function filterSouthChinaSea(latitude, longitude, data) {
    if (!latitude || !longitude || !Array.isArray(latitude) || !Array.isArray(longitude) || latitude.length === 0 || longitude.length === 0) {
        console.warn('⚠️ filterSouthChinaSea: Invalid latitude or longitude arrays.');
        return null;
    }

    // Check if data is a valid, non-empty 2D array
    if (!data || !Array.isArray(data) || !data.length || !Array.isArray(data[0])) {
        console.warn('⚠️ filterSouthChinaSea: Invalid or empty data array.');
        return null;
    }

    const filteredLat = latitude.filter(lat => lat >= 3 && lat <= 26);
    const filteredLon = longitude.filter(lon => lon >= 100 && lon <= 121);

    if (filteredLat.length === 0 || filteredLon.length === 0) {
        console.warn('⚠️ filterSouthChinaSea: No data points within South China Sea region.');
        return null;
    }
        
    const filteredData = [];

    for (let i = 0; i < latitude.length; i++) {
        if (latitude[i] >= 3 && latitude[i] <= 26) {
            const row = [];
            // Ensure data[i] exists before accessing its properties and is an array
            if (Array.isArray(data[i])) { 
                for (let j = 0; j < longitude.length; j++) {
                    if (longitude[j] >= 100 && longitude[j] <= 121) {
                        row.push(data[i][j]);
                    }
                }
            }
            if (row.length > 0) { // Only add row if it contains actual data for the region
                filteredData.push(row);
            }
        }
    }

    if (filteredData.length === 0) {
        console.warn('⚠️ filterSouthChinaSea: filteredData is empty after processing.');
        return null;
    }

    return {
        filteredLat,
        filteredLon,
        filteredData,
        latMin: Math.min(...filteredLat),
        latMax: Math.max(...filteredLat),
        lonMin: Math.min(...filteredLon),
        lonMax: Math.max(...filteredLon)
    };
}

/* ============================================================
   4. SATELLITE LAYER (FIXED - NOAA20 VIIRS)
   ============================================================ */
function renderSatelliteLayer() {
    console.log('🛰️ === LOADING SATELLITE IMAGERY (NOAA-20 VIIRS) ===');

    clearAllOverlays();

    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const dateStr = yesterday.toISOString().split('T')[0];

    const baseUrl = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_NOAA20_CorrectedReflectance_TrueColor/default";

    let satelliteUrl = `${baseUrl}/${dateStr}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`;

    if (window.satelliteLayer) {
        map.removeLayer(window.satelliteLayer);
    }

    window.satelliteLayer = L.tileLayer(satelliteUrl, {
        maxZoom: 9,
        minZoom: 3,
        opacity: 0.9,
        attribution: "NASA GIBS - NOAA20 VIIRS",
        errorTileUrl:
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    });

    window.satelliteLayer.addTo(map);

    let retryCount = 0;

    window.satelliteLayer.on("tileerror", function () {
        if (retryCount < 1) {
            retryCount++;
            yesterday.setDate(yesterday.getDate() - 1);
            const fallbackDate = yesterday.toISOString().split("T")[0];

            console.warn("⚠️ NOAA-20 VIIRS không có dữ liệu hôm qua → thử ngày hôm kia");

            const newUrl = `${baseUrl}/${fallbackDate}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`;

            map.removeLayer(window.satelliteLayer);

            window.satelliteLayer = L.tileLayer(newUrl, {
                maxZoom: 9,
                minZoom: 3,
                opacity: 0.9,
                attribution: "NASA GIBS (Fallback)"
            }).addTo(map);
        }
    });

    console.log(`✅ Satellite layer loaded (${dateStr})`);
}

/* ============================================================
   5. THUNDER/LIGHTNING LAYER (GIÔNG BÃO)
   ============================================================ */
function renderThunderLayer(data) {
    console.log('⚡ === VẼ GIÔNG BÃO HEATMAP ===');
 
    const latitude = data.lat || data.latitude;
    const longitude = data.lon || data.longitude;
   
    // Tính toán khả năng giông bão từ nhiệt độ, áp suất, độ ẩm
    const prmsl = data.prmsl || data.msl;
    const temp = data.temp || data.t;
    const u_wind = data.u || data.u10;
    const v_wind = data.v || data.v10;
   
    if (!latitude || !longitude || !prmsl || !temp) {
        console.error('❌ Thiếu dữ liệu để tính giông bão');
        return;
    }
   
    // Tính "Thunder Potential" (khả năng sét)
    const thunderData = [];
    for (let i = 0; i < latitude.length; i++) {
        const row = [];
        for (let j = 0; j < longitude.length; j++) {
            const p = prmsl[i][j] / 100; // Pa → hPa
            const t = temp[i][j] > 200 ? temp[i][j] - 273.15 : temp[i][j]; // K → °C
            const u = u_wind ? u_wind[i][j] : 0;
            const v = v_wind ? v_wind[i][j] : 0;
            const windSpeed = Math.sqrt(u*u + v*v);
           
            // Công thức giông bão: Nhiệt cao + Áp thấp + Gió mạnh = Sét
            let thunderPotential = 0;
           
            if (t > 25 && p < 1005 && windSpeed > 8) {
                thunderPotential = 50 + (30 - t) * 2 + (1010 - p) * 3 + windSpeed * 2;
            } else if (t > 22 && p < 1010 && windSpeed > 5) {
                thunderPotential = 20 + (28 - t) + (1012 - p) * 2 + windSpeed;
            }
           
            row.push(Math.min(100, Math.max(0, thunderPotential)));
        }
        thunderData.push(row);
    }
   
    const filtered = filterSouthChinaSea(latitude, longitude, thunderData);
    if (!filtered) {
        console.error('❌ Không có dữ liệu giông bão trong Biển Đông');
        return;
    }
   
    const { filteredLat, filteredLon, filteredData, latMin, latMax, lonMin, lonMax } = filtered;
   
    // Vẽ canvas
    const cellSize = 8;
    const width = filteredLon.length * cellSize;
    const height = filteredLat.length * cellSize;
   
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
   
    for (let i = 0; i < filteredLat.length; i++) {
        for (let j = 0; j < filteredLon.length; j++) {
            const potential = filteredData[i][j];
           
            if (potential < 10) {
                ctx.fillStyle = 'rgba(0,0,0,0)'; // Không có giông
            } else {
                ctx.fillStyle = thunderColor(potential);
            }
           
            const y = height - (i + 1) * cellSize;
            ctx.fillRect(j * cellSize, y, cellSize, cellSize);
        }
    }
   
    const imageUrl = canvas.toDataURL();
    pressureOverlay = L.imageOverlay(imageUrl, [[latMin, lonMin], [latMax, lonMax]], {
        opacity: 0.75,
        zIndex: 650
    }).addTo(map);
 
    console.log('✅ ĐÃ VẼ XONG GIÔNG BÃO HEATMAP');
}

// Color for thunder (like Windy)
function thunderColor(potential) {
    if (potential < 10) return "rgba(0, 0, 0, 0)"; // Không có
    if (potential < 20) return "rgba(255, 255, 100, 0.4)"; // Vàng nhạt - Khả năng thấp
    if (potential < 35) return "rgba(255, 200, 0, 0.6)"; // Vàng cam - Khả năng trung bình
    if (potential < 50) return "rgba(255, 128, 0, 0.7)"; // Cam - Khả năng cao
    if (potential < 70) return "rgba(255, 64, 0, 0.8)"; // Cam đỏ - Rất cao
    if (potential < 85) return "rgba(255, 0, 0, 0.9)"; // Đỏ - Nguy hiểm
    return "rgba(200, 0, 128, 0.95)"; // Đỏ tím - Cực kỳ nguy hiểm
}

// Call updateLayerButtonsUI on DOMContentLoaded to set initial state
document.addEventListener('DOMContentLoaded', () => {
    updateLayerButtonsUI();
    // Set initial legend for the default active layer
    const initialLayer = Object.keys(activeLayers).find(key => activeLayers[key]);
    if (initialLayer) {
        updateLegend(initialLayer);
    }
});