// static/js/session_timeout.js

class SessionTimeoutManager {
    constructor(options = {}) {
        this.timeoutMinutes = options.timeoutMinutes || 30;
        this.warningMinutes = options.warningMinutes || 2;
        this.checkInterval = options.checkInterval || 60000; // Check every minute
        this.lastActivity = new Date();
        this.warningShown = false;
        this.timeoutId = null;
        
        this.init();
    }
    
    init() {
        // Set up event listeners for user activity
        const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart'];
        events.forEach(event => {
            document.addEventListener(event, () => this.resetTimer());
        });
        
        // Start the timer check
        this.startTimerCheck();
    }
    
    resetTimer() {
        this.lastActivity = new Date();
        this.warningShown = false;
        this.hideWarning();
    }
    
    startTimerCheck() {
        this.timeoutId = setInterval(() => {
            const now = new Date();
            const idleTime = (now - this.lastActivity) / 1000 / 60; // Minutes
            
            if (idleTime >= this.timeoutMinutes) {
                // Auto logout
                this.logout();
            } else if (idleTime >= (this.timeoutMinutes - this.warningMinutes) && !this.warningShown) {
                // Show warning
                this.showWarning(this.timeoutMinutes - idleTime);
                this.warningShown = true;
            }
        }, this.checkInterval);
    }
    
    showWarning(remainingMinutes) {
        // Create warning modal
        const modal = document.createElement('div');
        modal.id = 'session-warning-modal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 10000;
        `;
        
        modal.innerHTML = `
            <div style="
                background: white;
                padding: 30px;
                border-radius: 12px;
                max-width: 400px;
                text-align: center;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            ">
                <h3 style="color: #dc2626; margin-bottom: 15px;">Session Timeout Warning</h3>
                <p style="margin-bottom: 20px;">Your session will expire in <strong id="timeout-counter">${Math.ceil(remainingMinutes)}</strong> minute(s) due to inactivity.</p>
                <div style="display: flex; gap: 10px; justify-content: center;">
                    <button onclick="sessionTimeoutManager.stayLoggedIn()" style="
                        padding: 10px 20px;
                        background: #10b981;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        cursor: pointer;
                    ">Stay Logged In</button>
                    <button onclick="sessionTimeoutManager.logout()" style="
                        padding: 10px 20px;
                        background: #dc2626;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        cursor: pointer;
                    ">Logout Now</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Countdown timer
        let remainingSeconds = Math.floor(remainingMinutes * 60);
        const counterElement = document.getElementById('timeout-counter');
        
        const countdownInterval = setInterval(() => {
            remainingSeconds--;
            const minutesLeft = Math.floor(remainingSeconds / 60);
            const secondsLeft = remainingSeconds % 60;
            
            if (counterElement) {
                if (remainingSeconds <= 60) {
                    counterElement.textContent = `${remainingSeconds} second(s)`;
                } else {
                    counterElement.textContent = `${minutesLeft} minute(s) ${secondsLeft} second(s)`;
                }
            }
            
            if (remainingSeconds <= 0) {
                clearInterval(countdownInterval);
                this.logout();
            }
        }, 1000);
        
        // Store interval to clear later
        modal.countdownInterval = countdownInterval;
    }
    
    hideWarning() {
        const modal = document.getElementById('session-warning-modal');
        if (modal) {
            if (modal.countdownInterval) {
                clearInterval(modal.countdownInterval);
            }
            modal.remove();
        }
    }
    
    stayLoggedIn() {
        // Reset timer by making a silent AJAX request to refresh session
        fetch('/api/refresh-session/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.getCookie('csrftoken'),
                'Content-Type': 'application/json'
            }
        }).then(response => {
            if (response.ok) {
                this.resetTimer();
                this.hideWarning();
            }
        }).catch(error => {
            console.error('Session refresh failed:', error);
        });
    }
    
    logout() {
        // Perform logout
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/logout/';
        
        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrfmiddlewaretoken';
        csrfInput.value = this.getCookie('csrftoken');
        
        form.appendChild(csrfInput);
        document.body.appendChild(form);
        form.submit();
    }
    
    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
}

// Initialize session timeout manager
let sessionTimeoutManager;

document.addEventListener('DOMContentLoaded', function() {
    const timeoutMinutes = parseInt(document.body.dataset.sessionTimeout) || 30;
    sessionTimeoutManager = new SessionTimeoutManager({
        timeoutMinutes: timeoutMinutes,
        warningMinutes: 2
    });
});