console.log("--- CONTENT.JS: VERSIÓN CORREGIDA (CÁMARA + BOTÓN PÁNICO) ---");

// Estado Inicial (4 chequeos)
let checks = { 
    agent: false, 
    browser: false, 
    appsClean: false,
    camera: false 
};

// Elementos DOM
let progressBar = document.getElementById('proctor-progress-bar');
let statusMessage = document.getElementById('proctor-status-message');
let startButton = document.getElementById('start-exam-button');
let checkAgent = document.getElementById('check-agent');
let checkBrowser = document.getElementById('check-browser');
let appsContainer = document.getElementById('dynamic-apps-container');

// Identificación Examen
let currentPage = null;
let currentExamenId = null;
const welcomeMatch = window.location.pathname.match(/exam\/(\d+)\/welcome\//);
const examMatch = window.location.pathname.match(/exam\/(\d+)\/start\//);

if (welcomeMatch) {
    currentPage = 'welcome';
    currentExamenId = welcomeMatch[1]; 
} else if (examMatch) {
    currentPage = 'exam';
    currentExamenId = examMatch[1]; 
}
let isExamActive = (currentPage === 'exam');

// Notificar carga
chrome.runtime.sendMessage({ type: 'PAGE_LOADED', page: currentPage, examen_id: currentExamenId });

// --- LÓGICA BIENVENIDA ---
if (currentPage === 'welcome') {
    chrome.storage.local.remove(['plagioFlag', 'isFinishingExam']);
    if (currentExamenId) localStorage.removeItem('exam_end_time_' + currentExamenId);

    // Iniciar chequeo cíclico
    setTimeout(() => chrome.runtime.sendMessage({ type: 'CHECK_ENVIRONMENT' }), 500);
    setInterval(() => {
        chrome.runtime.sendMessage({ type: 'CHECK_ENVIRONMENT' });
    }, 2000);

    // Listener para el botón (si existe)
    if (startButton) {
        startButton.addEventListener('click', onStartButtonClick);
    }
}

// --- LÓGICA EXAMEN ---
if (currentPage === 'exam') {
    const plagioCheckInterval = setInterval(checkPlagioFlag, 1000);

    function blockEvent(e) {
        e.preventDefault();
        e.stopPropagation();
        return false;
    }

    // Bloqueos básicos
    window.addEventListener('contextmenu', blockEvent);
    window.addEventListener('copy', blockEvent);
    window.addEventListener('paste', blockEvent);
    window.addEventListener('cut', blockEvent);

    // Bloqueo de teclas F (F1-F12) pero permitiendo escribir "F"
    window.addEventListener('keydown', function(e) {
        if (/^F([1-9]|1[0-2])$/.test(e.key)) {
            console.warn(`Tecla F bloqueada: ${e.key}`);
            blockEvent(e);
        }
    });

    // Fullscreen check
    window.addEventListener('fullscreenchange', async function() {
        if (document.fullscreenElement) return; 
        try {
            const result = await chrome.storage.local.get('isFinishingExam');
            if (result.isFinishingExam === true) {
                chrome.storage.local.remove('isFinishingExam');
                return; 
            }
        } catch (e) { console.error(e); }
        chrome.runtime.sendMessage({ type: 'PLAGIO_DETECTED', reason: 'salida de pantalla completa' });
    });

    // Heartbeat
    const heartbeatInterval = setInterval(() => {
        if (!isExamActive) { clearInterval(heartbeatInterval); return; }
        try {
            chrome.runtime.sendMessage({ type: 'PING' }, (response) => {
                if (chrome.runtime.lastError) {
                    handlePlagioInPage("Extensión desactivada");
                    clearInterval(heartbeatInterval);
                }
            });
        } catch (e) {}
    }, 3000);
}

// --- LISTENER MENSAJES (EXTENSIÓN Y CÁMARA) ---
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    switch (message.type) {
        case 'AGENT_STATUS':
            checks.agent = message.connected;
            updateCheckUI(checkAgent, checks.agent, message.connected ? "Conectado" : "Desconectado");
            break;
        case 'BROWSER_STATUS':
            checks.browser = message.isClean;
            updateCheckUI(checkBrowser, checks.browser, message.isClean ? "Limpio" : message.message);
            break;
        case 'APPS_STATUS':
            const openApps = message.openApps || [];
            const allApps = message.allApps || [];
            
            checks.appsClean = (openApps.length === 0);
            renderAppsGrid(allApps, openApps);

            if (!checks.appsClean && statusMessage) {
                statusMessage.textContent = "Detectado: " + openApps.join(", ");
                statusMessage.className = "text-center text-danger fw-bold mb-4";
            } else if (statusMessage && checks.agent && checks.browser) {
                statusMessage.textContent = "";
            }
            break;
        case 'PLAGIO_ALERT':
            isExamActive = false;
            handlePlagioInPage(message.reason);
            break;
    }
    if (currentPage === 'welcome') updateWelcomeUI();
});

// Listener para mensajes de la CÁMARA (desde la página web)
window.addEventListener("message", (event) => {
    if (event.source !== window) return;

    if (event.data.type && event.data.type === 'CAMERA_CHECK_RESULT') {
        checks.camera = event.data.status;
        if (currentPage === 'welcome') updateWelcomeUI();
    }
    
    // Listener para finalización de examen
    if (event.data && event.data.type === 'FROM_PAGE_EXAM_FINISHED') {
        chrome.storage.local.set({ isFinishingExam: true });
        chrome.runtime.sendMessage({ type: 'EXAM_FINISHED' });
    }
});

// --- RENDERIZADO VISUAL ---
function renderAppsGrid(allApps, openApps) {
    if (!appsContainer) return;
    appsContainer.innerHTML = '';
    if (allApps.length === 0) {
        appsContainer.innerHTML = '<div class="col-12 text-muted small">Conectando...</div>';
        return;
    }
    allApps.forEach(appName => {
        const isOpen = openApps.some(open => open.toLowerCase().includes(appName.toLowerCase()));
        const colDiv = document.createElement('div');
        colDiv.className = 'col-6 col-md-4 col-lg-3 mb-2';
        const badgeClass = isOpen ? 'badge bg-danger w-100 py-2' : 'badge bg-success opacity-75 w-100 py-2';
        const icon = isOpen ? '❌' : '✅';
        colDiv.innerHTML = `
            <div class="p-1"><span class="${badgeClass}" style="font-size:0.9em;">
            <div class="text-truncate">${appName}</div>
            <div class="small">${icon} ${isOpen ? 'ABIERTO' : 'Cerrado'}</div></span></div>`;
        appsContainer.appendChild(colDiv);
    });
}

function updateCheckUI(element, success, text) {
    if (!element) return;
    element.textContent = success ? "OK" : text;
    element.className = success ? 'badge bg-success rounded-pill p-2 w-75' : 'badge bg-danger rounded-pill p-2 w-75 text-wrap';
}

// --- LÓGICA PRINCIPAL DEL BOTÓN (AQUÍ ESTABA EL ERROR) ---
function updateWelcomeUI() {
    if (!progressBar || !startButton) return;
    
    // Calcular progreso
    let passed = 0;
    if (checks.agent) passed++;
    if (checks.browser) passed++;
    if (checks.appsClean) passed++;
    if (checks.camera) passed++; 
    
    let progress = Math.round((passed/4)*100);
    
    progressBar.style.width = `${progress}%`;
    progressBar.textContent = `${progress}%`;
    
    // ESTADO 1: INCOMPLETO (< 100%)
    if (progress < 100) {
        progressBar.className = "progress-bar bg-warning";
        
        // ¿Podemos ayudar al usuario? 
        // Si el agente está OK, pero fallan las APPS o el NAVEGADOR, habilitamos el botón de "Corregir".
        if (checks.agent && (!checks.browser || !checks.appsClean)) {
            startButton.disabled = false;
            startButton.textContent = "Corregir Todo y Comenzar";
            startButton.className = "btn btn-primary btn-lg shadow animate__animated animate__pulse";
        } 
        // Si falta el AGENTE o la CÁMARA, el botón debe estar gris porque el script no puede arreglar eso solo.
        else {
            startButton.disabled = true;
            startButton.className = "btn btn-secondary btn-lg";
            
            if (!checks.agent) {
                startButton.textContent = "Esperando Agente...";
                if(statusMessage) statusMessage.textContent = "Ejecuta el archivo 'run_agent.bat'";
            } else if (!checks.camera) {
                startButton.textContent = "Esperando Cámara...";
                if(statusMessage) statusMessage.textContent = "Ponte frente a la cámara";
            }
        }
    } 
    // ESTADO 2: COMPLETO (100%)
    else {
        progressBar.className = "progress-bar bg-success";
        if(statusMessage) {
            statusMessage.textContent = "Todo listo.";
            statusMessage.className = "text-center text-success fw-bold mb-4";
        }
        startButton.disabled = false;
        startButton.textContent = "Comenzar Examen";
        startButton.className = "btn btn-success btn-lg shadow";
    }
}

function onStartButtonClick() {
    if (!startButton) return;
    
    // Si todo está OK, iniciamos
    if (checks.agent && checks.browser && checks.appsClean && checks.camera) {
        const url = startButton.getAttribute('data-url');
        if (url) window.location.href = url;
    } 
    // Si no, intentamos cerrar apps (Botón de pánico)
    else {
        if(statusMessage) statusMessage.textContent = "Cerrando aplicaciones...";
        chrome.runtime.sendMessage({ type: 'CLOSE_ALL' });
        
        startButton.disabled = true;
        setTimeout(() => { 
            startButton.disabled = false; 
            // Forzamos un re-check visual
            updateWelcomeUI();
        }, 2000);
    }
}

function handlePlagioInPage(reason) {
    if (document.fullscreenElement) document.exitFullscreen();
    document.body.innerHTML = `<div style="display:flex;flex-direction:column;justify-content:center;align-items:center;height:100vh;background:#f8d7da;color:#721c24;text-align:center;"><h1>Examen Cancelado</h1><p>Motivo: ${reason}</p></div>`;
    
    // CAMBIO: Redirigir al dashboard real
    setTimeout(() => window.location.href = 'https://examen.asantosb.dev/exam/dashboard/', 4000);
}

function checkPlagioFlag() {
    if (!currentExamenId) return;
    chrome.storage.local.get('plagioFlag', (res) => {
        if (res.plagioFlag && res.plagioFlag.examenId == currentExamenId) {
            handlePlagioInPage(res.plagioFlag.reason);
            chrome.storage.local.remove('plagioFlag');
        }
    });
}