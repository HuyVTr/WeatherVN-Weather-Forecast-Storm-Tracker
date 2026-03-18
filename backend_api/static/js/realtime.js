/**
 * realtime.js - WeatherVN AI Core Logic
 * Version: 5.0 - Final Coordinated Fix
 */

// ==========================================
//  SINGLE SOURCE OF TRUTH FOR GLOBAL STATE
// ==========================================
// These are initialized here ONCE. Other scripts will READ/WRITE to these.
window.stormTrajectoryData = null; 
window.otherAlertsData = null;     
window.gribData = null;
window.alertLayerGroup = null;
window.currentForecastIndex = 0;
window.isPlaying = false;

// ==========================================
// 1. INITIAL LOAD & DATA FETCHING
// ==========================================
async function initialLoad() {
    try {
        console.log('🚀 [INIT] Starting WeatherVN AI v5.0...');
        
        if (typeof map !== 'undefined' && !window.alertLayerGroup) {
            window.alertLayerGroup = L.layerGroup().addTo(map);
        }

        const [stormResult, alertsResult, gribResult] = await Promise.all([
            fetch('/api/forecast_storm').then(res => res.ok ? res.json() : null),
            fetch('/api/all_alerts').then(res => res.ok ? res.json() : []),
            fetchGribData()
        ]);
        
        window.stormTrajectoryData = stormResult;
        
        // --- TEMPORARY DEBUG LOG for is_simulation ---
        console.log("Frontend received stormResult.is_simulation:", window.stormTrajectoryData?.is_simulation, "Type:", typeof window.stormTrajectoryData?.is_simulation);
        // --- END TEMPORARY DEBUG LOG ---
        window.otherAlertsData = alertsResult;
        window.gribData = gribResult;

        // --- DEBUG STEP ---
        console.log('--- FETCHED STORM DATA ---', stormResult);
        // --- END DEBUG STEP ---

        renderAll();

    } catch (error) {
        console.error('❌ CRITICAL INIT ERROR:', error);
    } finally {
        const loadingOverlay = document.getElementById('loadingOverlay');
        if (loadingOverlay) {
            loadingOverlay.style.opacity = '0';
            setTimeout(() => { loadingOverlay.style.display = 'none'; }, 500);
        }
    }
}

async function fetchGribData() {
    try {
        const res = await fetch('/latest-grib');
        if (!res.ok) return null;
        const latestGrib = await res.json();
        if (latestGrib.error) return null;
        const gribRes = await fetch(`/grib-json?file=${latestGrib.file}`);
        return gribRes.ok ? await gribRes.json() : null;
    } catch (e) {
        console.error("Failed to fetch GRIB data:", e);
        return null;
    }
}

// ==========================================
// 2. MASTER RENDER FUNCTION
// ==========================================
function renderAll() {
    console.log('🎨 [RENDER] Starting full re-render...');

    // 1. Render Storm Path, Marker, and Info Card
    // The main condition is just to check if the storm data object exists on the global scope.
    console.log('--- DEBUG RENDERALL --- Checking drawStormPath:', typeof drawStormPath, 'Storm Data Status:', window.stormTrajectoryData ? window.stormTrajectoryData.status : 'N/A');
    if (window.stormTrajectoryData && typeof drawStormPath === 'function') {
        drawStormPath(window.stormTrajectoryData);
    } else {
        // Explicitly hide storm card if no storm data
        if(typeof updateStormInfoCard === 'function') {
            updateStormInfoCard(null);
        }
    }

    // Delegate alert drawing to its visualizer
    if (typeof renderDetailedAlertList === 'function' && typeof drawAlertsToMap === 'function') {
        renderDetailedAlertList(window.otherAlertsData);
        drawAlertsToMap(window.otherAlertsData);
    }
    
    // Update dashboard panels
    if (typeof updateAllDashboardPanels === 'function') {
        updateAllDashboardPanels(window.stormTrajectoryData, window.otherAlertsData);
    }

    // Render map data layers
    if (window.gribData && typeof renderLayer === 'function') {
        renderLayer(window.gribData);
    }
}
window.renderAll = renderAll;

// ==========================================
// 3. UI HELPER FUNCTIONS
// ==========================================
function updateAllDashboardPanels(stormData, alertsData) {
    const riskScoreEl = document.getElementById('ai-risk-score');
    const riskLabelEl = document.getElementById('ai-risk-label');
    const riskBarEl = document.getElementById('ai-risk-bar');
    const aiTimeLabelEl = document.getElementById('ai-time-label');

    let aiRiskScore = "--", aiRiskLabel = "N/A", aiRiskBarWidth = "0%", aiTimeLabel = "N/A";

    if (stormData && stormData.status !== 'no_storm' && stormData.ai_report && stormData.ai_report.marine_safety) {
        const safety = stormData.ai_report.marine_safety;
        aiRiskScore = safety.risk_score?.toFixed(0) || "--";
        aiRiskLabel = safety.status || "Không xác định";
        if (aiRiskScore !== "--") aiRiskBarWidth = `${aiRiskScore}%`;
        aiTimeLabel = stormData.timestamp ? new Date(stormData.timestamp).toLocaleTimeString('vi-VN') : new Date().toLocaleTimeString('vi-VN');
    } else if (stormData && stormData.status === 'no_storm' && stormData.ai_report && stormData.ai_report.marine_safety) {
        // Use the AI report from the backend for the "no storm" case
        const safety = stormData.ai_report.marine_safety;
        aiRiskScore = safety.risk_score?.toFixed(0) || "100";
        aiRiskLabel = safety.status || "AN TOÀN";
        aiRiskBarWidth = `${aiRiskScore}%`;
        aiTimeLabel = new Date().toLocaleTimeString('vi-VN');
    } else {
        // Fallback for unexpected no_storm or missing ai_report
        aiRiskScore = "0";
        aiRiskLabel = "KHÔNG CÓ BÃO";
        aiRiskBarWidth = "0%";
        aiTimeLabel = new Date().toLocaleTimeString('vi-VN');
    }

    if(riskScoreEl) riskScoreEl.textContent = aiRiskScore;
    if(riskLabelEl) {
        riskLabelEl.textContent = aiRiskLabel;
        // Adjust color based on label, especially for "AN TOÀN"
        if(aiRiskLabel === "AN TOÀN") {
            riskLabelEl.className = 'text-green-400';
            if(riskBarEl) riskBarEl.style.backgroundColor = '#22c55e'; // Green for safe
        } else if (aiRiskLabel === "KHÔNG CÓ BÃO") {
            riskLabelEl.className = 'text-gray-400';
            if(riskBarEl) riskBarEl.style.backgroundColor = '#6b7280'; // Gray for no storm
        }
        else {
            riskLabelEl.className = 'text-yellow-400';
        }
    }
    if(riskBarEl) riskBarEl.style.width = aiRiskBarWidth;
    if(aiTimeLabelEl) aiTimeLabelEl.textContent = `AI: ${aiTimeLabel}`;
    
    const highRiskCount = document.getElementById('high-risk-count');
    const mediumRiskCount = document.getElementById('medium-risk-count');
    const lowRiskCount = document.getElementById('low-risk-count'); // New
    if(highRiskCount) highRiskCount.textContent = "0";
    if(mediumRiskCount) mediumRiskCount.textContent = "0";
    if(lowRiskCount) lowRiskCount.textContent = "0"; // New

    if (alertsData && alertsData.length > 0) {
        const high = alertsData.filter(a => a.severity === 'HIGH' || a.severity === 'EXTREME').length;
        const medium = alertsData.filter(a => a.severity === 'MEDIUM').length;
        const low = alertsData.filter(a => a.severity === 'LOW').length; // New
        
        if(highRiskCount) highRiskCount.textContent = high;
        if(mediumRiskCount) mediumRiskCount.textContent = medium;
        if(lowRiskCount) lowRiskCount.textContent = low; // New
    }
    
    const lastUpdated = document.getElementById('last-updated-time');
    if(lastUpdated) lastUpdated.textContent = `Cập nhật: ${new Date().toLocaleTimeString('vi-VN')}`;
}

window.openAIDetails = function() { alert("Chức năng xem chi tiết AI đang được phát triển."); }

// ==========================================
// 4. AUTO-START APPLICATION
// ==========================================
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialLoad);
} else {
    initialLoad();
}