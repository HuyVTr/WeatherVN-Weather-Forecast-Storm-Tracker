/**
 * storm_path_visualizer.js - Storm Path Rendering Logic
 * Version: 5.2 - Final Data Display Fix (Pressure)
 */

let stormLayers = [];
let currentStormMarker = null;
window.unifiedTimelinePath = []; 

window.drawStormPath = function(data) {
    console.log('--- DEBUG storm_path_visualizer.js --- drawStormPath called with data:', data);
    console.log('--- DEBUG storm_path_visualizer.js --- data.is_simulation:', data?.is_simulation, 'data.actual_path:', data?.actual_path, 'data.data:', data?.data);
    if (!window.map) return;

    stormLayers.forEach(layer => window.map.removeLayer(layer));
    stormLayers = [];
    currentStormMarker = null;
    window.unifiedTimelinePath = [];

    if (!data || data.status !== 'success') {
        updateStormInfoCard(null); // Ensure card is hidden
        return;
    }

    const slider = document.getElementById('timelineSlider');

    if (data.is_simulation && data.actual_path && data.data) {
        drawSingleTrack(data.actual_path, { color: '#10b981', weight: 5, opacity: 0.9, name: "THỰC TẾ" });
        drawSingleTrack(data.data, { color: '#fbbf24', weight: 4, dashArray: '10, 8', opacity: 1, name: "AI DỰ BÁO" });
        addComparisonLegend();
        
        const first72Hours = data.actual_path.slice(0, 73); 
        window.unifiedTimelinePath = [...first72Hours, ...data.data];

        if (slider) {
            slider.setAttribute('max', window.unifiedTimelinePath.length - 1);
        }
        
        updateStormPosition(0); 
    } 
    else if (data.data && data.data.length > 0) {
        drawSingleTrack(data.data, { color: '#ef4444', weight: 4, dashArray: '10, 8', opacity: 1, name: "Dự báo" });
        
        window.unifiedTimelinePath = data.data;
        if (slider) {
            slider.setAttribute('max', window.unifiedTimelinePath.length - 1);
        }

        updateStormPosition(0);
    }
}

window.updateStormInfoCard = function(pointData) {
    const stormInfoCard = document.getElementById('stormInfoCard');
    const stormAlertContainer = document.getElementById('stormAlertContainer');
    const stormMetadata = window.stormTrajectoryData; // Metadata tổng quát (tên bão, loại bão gốc)

    if (!pointData) {
        // Nếu không có pointData (nghĩa là không trỏ vào điểm nào), ẩn card
        if (stormInfoCard) stormInfoCard.classList.add('hidden');
        if (stormAlertContainer) stormAlertContainer.classList.remove('hidden');
        return;
    }

    // Hiển thị card
    if (stormInfoCard) stormInfoCard.classList.remove('hidden');
    if (stormAlertContainer) stormAlertContainer.classList.add('hidden');

    const stormNameEl = document.getElementById('stormName');
    const stormClassEl = document.getElementById('stormClass');
    const stormPosEl = document.getElementById('stormPos');
    const stormWindEl = document.getElementById('stormWind');
    const stormPressureEl = document.getElementById('stormPressure');
    const stormDirectionEl = document.getElementById('stormDirection');

    // 1. Tên và Loại bão: Lấy từ Metadata tổng quát (vì nó không đổi theo từng điểm)
    if (stormNameEl) stormNameEl.textContent = stormMetadata?.storm_name || 'Bão';
    if (stormClassEl) stormClassEl.textContent = stormMetadata?.origin_storm_details?.type_vi || 'Dự báo AI';

    // 2. Vị trí: Lấy trực tiếp từ pointData
    if (stormPosEl) {
        const lat = pointData.LAT || pointData.lat;
        const lon = pointData.LON || pointData.lon;
        if (lat !== undefined && lon !== undefined) {
             stormPosEl.textContent = `${Number(lat).toFixed(2)}°N, ${Number(lon).toFixed(2)}°E`;
        } else {
             stormPosEl.textContent = '--';
        }
    }
    
    // 3. Gió (Wind Speed)
    // Ưu tiên key WMO_WIND (backend) hoặc wmo_wind
    let windVal = pointData.WMO_WIND;
    if (windVal === undefined) windVal = pointData.wmo_wind;
    
    if (stormWindEl) {
        if (windVal !== undefined && windVal !== null) {
            // Chuyển đổi m/s -> km/h
            const windKmH = Number(windVal) * 3.6;
            stormWindEl.textContent = `${windKmH.toFixed(1)} km/h`;
        } else {
            stormWindEl.textContent = '--';
        }
    }

    // 4. Áp suất (Pressure)
    // Ưu tiên key WMO_PRES (backend) hoặc wmo_pres
    let presVal = pointData.WMO_PRES;
    if (presVal === undefined) presVal = pointData.wmo_pres;

    if (stormPressureEl) {
        // Chỉ hiển thị nếu giá trị hợp lý (> 850 hPa)
        if (presVal !== undefined && presVal !== null && Number(presVal) > 850) {
            stormPressureEl.textContent = `${Number(presVal).toFixed(1)} hPa`;
        } else {
            stormPressureEl.textContent = '--';
        }
    }
    
    // 5. Hướng di chuyển:
    // Nếu pointData có trường direction riêng (nâng cao) thì lấy, không thì lấy từ metadata chung
    if (stormDirectionEl) {
        stormDirectionEl.textContent = pointData.direction || stormMetadata?.trajectory?.dominant_direction || '--';
    }
}

window.updateStormPosition = function(index) {
    const data = window.stormTrajectoryData;
    if (!data) return;
    
    const timelinePath = window.unifiedTimelinePath;
    if (!timelinePath || index >= timelinePath.length) return;

    const currentPoint = timelinePath[index];
    if (!currentPoint) return;

    const lat = currentPoint.LAT;
    const lon = currentPoint.LON;

    if (currentStormMarker) {
        currentStormMarker.setLatLng([lat, lon]);
    } else {
        currentStormMarker = L.marker([lat, lon], {
            icon: L.divIcon({
                className: 'current-storm-marker',
                html: `<div class="relative w-full h-full flex items-center justify-center">
                           <div class="absolute inset-0 rounded-full bg-red-600 animate-ping opacity-75"></div>
                           <div class="relative w-10 h-10 rounded-full shadow-xl border-2 border-white flex items-center justify-center text-white text-xl bg-red-500"><i class="fas fa-bullseye"></i></div>
                       </div>`,
                iconSize: [40, 40],
                iconAnchor: [20, 20],
            }),
            zIndexOffset: 1000
        }).addTo(window.map);
        stormLayers.push(currentStormMarker);
    }
    
    updateStormInfoCard(currentPoint);
}

function drawSingleTrack(pointsData, style) {
    console.log('--- DEBUG drawSingleTrack --- pointsData:', pointsData, 'style:', style, 'window.map is:', window.map);
    if (!pointsData || pointsData.length === 0) return;
    const latlngs = pointsData.map(p => [p.LAT, p.LON]);
    const poly = L.polyline(latlngs, style).addTo(window.map);
    poly.bindPopup(`<b style="color:${style.color}">${style.name}</b>`);
    stormLayers.push(poly);
}

function addComparisonLegend() {
    const legendId = 'demo-legend';
    const oldLegend = document.getElementById(legendId);
    if (oldLegend) oldLegend.remove();
    const div = document.createElement('div');
    div.id = legendId;
    div.innerHTML = `<div style="background:rgba(0,0,0,0.8); color:white; padding:10px; border-radius:8px; font-size:12px;">
        <div style="margin-bottom:5px; font-weight:bold;">CHÚ GIẢI</div>
        <div style="display:flex; align-items:center; gap:5px; margin-bottom:3px;"><span style="width:20px; height:3px; background:#10b981;"></span>Thực tế (Rai)</div>
        <div style="display:flex; align-items:center; gap:5px;"><span style="width:20px; height:3px; background-image: linear-gradient(to right, #fbbf24 70%, transparent 30%); background-size: 10px 3px;"></span>AI Dự báo</div>
        </div>`;
    div.style.position = 'absolute';
    div.style.bottom = '30px';
    div.style.right = '10px';
    div.style.zIndex = 1000;
    document.getElementById('map').appendChild(div);
    stormLayers.push({ remove: () => div.remove() });
}
