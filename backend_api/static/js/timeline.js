/**
 * timeline.js - Timeline UI Controllers
 * Version: 6.0 - IIFE Final
 */

// Wrap all code in an IIFE to create a private scope and prevent any global conflicts.
(function() { 
    // This variable is now 100% private to this script.
    let playInterval = null; 

    const slider = document.getElementById('timelineSlider');
    const dateDisplay = document.getElementById('currentDate');

    // This function is also private to the module
    function updateDateDisplay() {
        // Fix: Dữ liệu hiện tại là hourly (1 giờ/bước), không phải 3 giờ/bước như GFS gốc.
        // Đổi hệ số nhân từ 3 thành 1.
        const hours = (window.currentForecastIndex || 0) * 1; 
        if (dateDisplay) {
            if (hours === 0) {
                dateDisplay.textContent = `Hiện tại`;
            } else {
                const days = Math.floor(hours / 24);
                const remainingHours = hours % 24;
                let text = `+${days} ngày`;
                if (remainingHours > 0) text += ` ${remainingHours}h`;
                dateDisplay.textContent = text;
            }
        }
    }

    if (slider) {
        slider.addEventListener('input', (e) => {
            // Update the single global index
            window.currentForecastIndex = parseInt(e.target.value, 10);
            
            // Call our private display function
            updateDateDisplay();
            
            // Call the global render function
            if (window.updateStormPosition) {
                window.updateStormPosition(window.currentForecastIndex);
            }
        });
    }

    // Attach control functions to the window object so HTML onclick can find them
    window.playTimeline = function() {
        if (window.isPlaying) return;
        window.isPlaying = true;
        
        if (playInterval) clearInterval(playInterval);

        playInterval = setInterval(() => {
            let currentIndex = window.currentForecastIndex || 0;
            currentIndex++;
            
            const maxIndex = parseInt(slider.getAttribute('max'), 10) || 56;
            if (currentIndex > maxIndex) currentIndex = 0;
            
            window.currentForecastIndex = currentIndex;
            slider.value = currentIndex;
            slider.dispatchEvent(new Event('input'));
        }, 500);
    }

    window.pauseTimeline = function() {
        if (!window.isPlaying) return;
        window.isPlaying = false;
        if (playInterval) {
            clearInterval(playInterval);
            playInterval = null;
        }
    }

    window.resetTimeline = function() {
        window.pauseTimeline();
        slider.value = 0;
        slider.dispatchEvent(new Event('input'));
    }

    // Set initial state on load
    document.addEventListener('DOMContentLoaded', updateDateDisplay);

})(); // Immediately invoke the function