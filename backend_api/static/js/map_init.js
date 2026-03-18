// ========== CONFIG ==========
const REALTIME_INTERVAL = 5000; // 5 giây

// ========== STATE ==========
let currentForecastIndex = 0;
let isPlaying = false;
let playInterval = null;
let forecastData = null;

// ========== MAP SETUP ==========
const map = L.map('map', {
    center: [16.0, 112.0], // Tâm Biển Đông
    zoom: 6,
    minZoom: 5,
    maxZoom: 9, // Không cho zoom quá sâu để vỡ hình
    zoomControl: false, // Tắt zoom default để tự custom nếu cần
    attributionControl: false
});
window.map = map;
// Layer Vệ tinh ESRI (Đẹp & Thực tế nhất)
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 18,
    attribution: 'Esri, NOAA'
}).addTo(map);

// Thêm lớp tên địa danh (Labels) đè lên vệ tinh
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
    minZoom: 5
}).addTo(map);

// Viền Biển Đông (Giữ nguyên style cũ nhưng làm mờ hơn cho đẹp)
const bounds = [[3, 100], [26, 100], [26, 121], [3, 121], [3, 100]];
L.polyline(bounds, {
    color: '#38bdf8', // Màu xanh cyan sáng hơn
    weight: 1,
    opacity: 0.3,
    dashArray: '4, 4'
}).addTo(map);

async function getLatestGrib() {
    const res = await fetch("/latest-grib");
    const data = await res.json();
    return data.file;
}
const vnIslands = [
    { 
        name: "QĐ. HOÀNG SA", 
        sub: "(VIỆT NAM)",
        lat: 16.53470,
        lon: 111.60833 
    },
    { 
        name: "QĐ. TRƯỜNG SA", 
        sub: "(VIỆT NAM)",
        lat: 8.641666,    
        lon: 111.931945  
    }
];

vnIslands.forEach(island => {
    // Tạo Icon bao gồm chấm đỏ ngôi sao vàng + Tên đảo
    const sovereigntyIcon = L.divIcon({
        className: 'island-label-container',
        html: `
            <div class="flex flex-col items-center group cursor-default">
                <div class="w-5 h-5 rounded-full bg-red-600 border-2 border-white shadow-lg shadow-red-500/50 flex items-center justify-center transform group-hover:scale-125 transition-transform duration-300">
                    <i class="fas fa-star text-[10px] text-yellow-400"></i>
                </div>
                
                <div class="mt-1 flex flex-col items-center">
                    <span class="text-[11px] font-black text-white uppercase tracking-wider drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)]">
                        ${island.name}
                    </span>
                    <span class="text-[9px] font-bold text-yellow-400 tracking-wide drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)]">
                        ${island.sub}
                    </span>
                </div>
            </div>
        `,
        iconSize: [120, 50],
        iconAnchor: [60, 10] // Căn giữa
    });

    // Thêm vào bản đồ (interactive: false để không chặn click bản đồ)
    L.marker([island.lat, island.lon], { 
        icon: sovereigntyIcon, 
        interactive: false,
        zIndexOffset: 1000 // Luôn hiển thị lên trên các layer khác
    }).addTo(map);
});


let pressureOverlay = null;
let stormMarker = null;
let windParticles = [];
