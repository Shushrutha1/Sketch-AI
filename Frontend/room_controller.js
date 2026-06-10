let socket;
const urlParams = new URLSearchParams(window.location.search);
const rName = urlParams.get('room') || sessionStorage.getItem('drawRoom') || 'Global-Lobby-1';
const user = localStorage.getItem('username') || 'Guest-User';

// --- DOM ELEMENTS MATRIX ---
const canvas = document.getElementById('drawingCanvas');
const ctx = canvas.getContext('2d');
const brushSize = document.getElementById('brushSize');
const chatInput = document.getElementById('guessInput');
const chatWindow = document.getElementById('messagesBox');
const roomDisplay = document.getElementById('roomDisplay');
const wordDisplay = document.getElementById('wordHint');
const timerUI = document.getElementById('timerDisplay');
const drawerDisplay = document.getElementById('drawerDisplay');
const lockedBanner = document.getElementById('chatDisabledMessage');

let drawing = false;
let activeStroke = [];
let isMyTurn = false;
let activeTool = 'brush';
let currentLocalScoresMapping = {};
let selectedColorHex = '#000000';
let totalConnectedPlayersList = []; // Array tracking game membership sizing

roomDisplay.innerText = `Room ID: ${rName}`;

function connectToSocketCluster() {
    // BUG FIX SAFETY: Clear any existing active connections to prevent double alert responses
    if (socket) {
        socket.disconnect();
    }

    socket = io(window.location.origin);
    socket.emit('join_room', { username: user, room: rName });
    
    // SERVER DISPATCHER RECEIVERS
    socket.on('room_state_update', (data) => {
        drawerDisplay.innerText = data.current_drawer || 'Syncing...';
        
        // Track the array metrics natively to safeguard single-player constraints
        totalConnectedPlayersList = data.players || [];
        
        if (data.choosing) {
            if (data.current_drawer === user) {
                wordDisplay.innerText = "CHOOSE A WORD FROM THE POPUP MODAL OVERLAY...";
            } else {
                wordDisplay.innerText = `${data.current_drawer.toUpperCase()} IS CHOOSING A SECRET WORD...`;
            }
        }

        data.players.forEach(p => {
            if (currentLocalScoresMapping[p] === undefined) currentLocalScoresMapping[p] = 0;
        });
        rebuildScoresSidebarList(currentLocalScoresMapping, data.current_drawer);
        updateTurnState(data.current_drawer);
    });

    // Mandatory word choices selector pop-up overlay modal gateway emitter handler
    socket.on('word_choices_selection', (data) => {
        const overlay = document.getElementById('wordChoiceOverlay');
        const container = document.getElementById('wordChoiceButtonsContainer');
        if (!container || !overlay) return;

        container.innerHTML = '';
        
        if (data.drawer === user) {
            overlay.classList.remove('hidden');
            data.choices.forEach(word => {
                const btn = document.createElement('button');
                btn.className = "w-full py-2.5 bg-teal-400 hover:bg-teal-300 text-gray-950 font-bold text-xs rounded-xl uppercase transition font-mono mb-2 focus:outline-none";
                btn.innerText = word;
                btn.onclick = () => {
                    socket.emit('word_selected', { room: rName, word: word, username: user });
                    overlay.classList.add('hidden');
                };
                container.appendChild(btn);
            });
        } else {
            overlay.classList.add('hidden');
        }
    });

    socket.on('session_scores_update', (data) => {
        currentLocalScoresMapping = data.scores;
        rebuildScoresSidebarList(currentLocalScoresMapping, drawerDisplay.innerText);
    });

    socket.on('round_start', (data) => {
        updateTurnState(data.drawer);
        
        const choiceOverlay = document.getElementById('wordChoiceOverlay');
        if (choiceOverlay) choiceOverlay.classList.add('hidden');
        
        wordDisplay.innerText = isMyTurn ? `DRAW THIS WORD: ${data.challenge.toUpperCase()}` : `HINT: ${data.hint}`;
        clearSystemCanvas(true);
        rebuildScoresSidebarList(currentLocalScoresMapping, data.drawer);
    });

    socket.on('timer_update', (data) => {
        timerUI.innerText = data.timer;
    });

    socket.on('broadcast_stroke', (data) => { renderRemoteStroke(data.stroke); });
    socket.on('broadcast_clear', () => { ctx.clearRect(0, 0, canvas.width, canvas.height); });

    // Global end game session rankings podium listener
    socket.on('global_game_over_podium', (data) => {
        const overlay = document.getElementById('podiumOverlayModal');
        const wrapper = document.getElementById('podiumRankingsWrapper');
        if (!overlay || !wrapper) return;

        wrapper.innerHTML = '';
        overlay.classList.remove('hidden');

        data.winners.forEach(w => {
            let rankBadge = w.rank === 1 ? '🥇 1st Place' : w.rank === 2 ? '🥈 2nd Place' : '🥉 3rd Place';
            let rankColorClass = w.rank === 1 ? 'border-yellow-500/30 bg-yellow-500/5 text-yellow-400' : 'border-gray-500/30 bg-gray-500/5 text-gray-300';
            
            wrapper.innerHTML += `
                <div class="border ${rankColorClass} p-3 rounded-xl flex justify-between items-center transform transition scale-100 hover:scale-102">
                    <div class="text-left">
                        <span class="text-[10px] font-bold block uppercase tracking-wider opacity-60">${rankBadge}</span>
                        <span class="font-bold text-sm text-white">${w.username}</span>
                    </div>
                    <span class="font-mono font-black text-teal-400">${w.score} <span class="text-[10px] font-normal text-gray-500">pts</span></span>
                </div>`;
        });

        playVictoryChimeSound();

        let duration = 4 * 1000;
        let end = Date.now() + duration;

        (function frame() {
            confetti({ particleCount: 4, angle: 60, spread: 55, origin: { x: 0 }, colors: ['#2dd4bf', '#3b82f6', '#fbbf24'] });
            confetti({ particleCount: 4, angle: 120, spread: 55, origin: { x: 1 }, colors: ['#2dd4bf', '#3b82f6', '#fbbf24'] });

            if (Date.now() < end) {
                requestAnimationFrame(frame);
            }
        }());
    });

    socket.on('chat_message', (data) => {
        const msgDiv = document.createElement('div');
        const nameColorClass = data.system ? 'text-teal-400 font-bold' : 'text-purple-400 font-semibold';
        
        msgDiv.className = "p-1.5 rounded bg-black bg-opacity-30 border border-gray-900/40 leading-normal text-left mb-1";
        msgDiv.innerHTML = `
            <span class="${nameColorClass}">${data.username}:</span>
            <span class="text-white font-medium pl-1" style="color: #ffffff !important;">${data.message}</span>
        `;
        chatWindow.appendChild(msgDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    });
}

// BULLETPROOF CHECK GATE: Blocks single-player room launch operations cleanly
function triggerGameLaunch() { 
    if (totalConnectedPlayersList.length < 2) {
        const blockModal = document.getElementById('soloBlockModal');
        if (blockModal) {
            blockModal.classList.remove('hidden');
        }
        return; 
    }
    // If the validation check passes, start the automated round rotation workflow parameters
    socket.emit('start_game', { room: rName }); 
}

function forceEndGameSession() {
    if (confirm("Are you sure you want to end this game round and compile scores for everyone connected?")) {
        socket.emit('force_end_game', { room: rName });
    }
}

function playVictoryChimeSound() {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const notes = [523.25, 659.25, 783.99, 1046.50];
        
        notes.forEach((freq, index) => {
            setTimeout(() => {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                
                osc.type = 'triangle';
                osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
                
                gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.4);
                
                osc.connect(gain);
                gain.connect(audioCtx.destination);
                
                osc.start();
                osc.stop(audioCtx.currentTime + 0.4);
            }, index * 120);
        });
    } catch (err) {
        console.error("Audio generation exception bypassed cleanly:", err);
    }
}

function updateActiveColorPalette(element, hexColor) {
    document.querySelectorAll('.color-dot').forEach(d => d.classList.remove('active'));
    const customLabel = document.getElementById('customLabel');
    if (customLabel) customLabel.classList.remove('text-teal-400');
    
    if (element) element.classList.add('active');
    selectedColorHex = hexColor;
    if(activeTool === 'eraser') selectTool('brush');
}

function triggerCustomColorInput(hexValue) {
    document.querySelectorAll('.color-dot').forEach(d => d.classList.remove('active'));
    const customLabel = document.getElementById('customLabel');
    if (customLabel) customLabel.classList.add('text-teal-400');
    
    selectedColorHex = hexValue;
    if(activeTool === 'eraser') selectTool('brush');
}

function rebuildScoresSidebarList(scoresMap, currentDrawer) {
    const uList = document.getElementById('usersList');
    if (!uList) return; 
    uList.innerHTML = '';
    
    Object.keys(scoresMap).forEach(p => {
        const points = scoresMap[p];
        const activeRoleBadge = (p === currentDrawer) ? '🎨' : '🧠';
        uList.innerHTML += `
            <div class="flex justify-between items-center p-2 bg-black bg-opacity-20 border border-gray-900 rounded-xl mb-1.5 text-left">
                <span class="font-bold text-gray-300 truncate max-w-[100px]">${activeRoleBadge} ${p}</span>
                <span class="font-mono text-teal-400 font-bold">${points} <span class="text-[9px] font-normal text-gray-600">pt</span></span>
            </div>`;
    });
}

function updateTurnState(currentDrawer) {
    isMyTurn = (currentDrawer === user);
    drawerDisplay.innerText = currentDrawer || 'Syncing...';
    if (isMyTurn) {
        chatInput.classList.add('hidden'); 
        lockedBanner.classList.remove('hidden');
    } else {
        chatInput.classList.remove('hidden'); 
        lockedBanner.classList.add('hidden');
        chatInput.disabled = false; 
        chatInput.placeholder = "Type your guess here...";
    }
}

function initializeCanvasTopology() {
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width; 
    canvas.height = rect.height;
    ctx.lineCap = 'round'; 
    ctx.lineJoin = 'round';
    ctx.fillStyle = "#ffffff"; 
    ctx.fillRect(0, 0, canvas.width, canvas.height);
}

function selectTool(tool) {
    activeTool = tool;
    document.getElementById('brushBtn').className = (tool === 'brush') ? 'px-3 py-1 rounded bg-teal-400 text-gray-950 text-xs font-bold' : 'px-3 py-1 rounded text-gray-400 hover:text-white text-xs font-bold';
    document.getElementById('bucketBtn').className = (tool === 'bucket') ? 'px-3 py-1 rounded bg-teal-400 text-gray-950 text-xs font-bold' : 'px-3 py-1 rounded text-gray-400 hover:text-white text-xs font-bold';
    document.getElementById('eraserBtn').className = (tool === 'eraser') ? 'px-3 py-1 rounded bg-teal-400 text-gray-950 text-xs font-bold' : 'px-3 py-1 rounded text-gray-400 hover:text-white text-xs font-bold';
}

function executeFloodFill(startX, startY, fillRGB) {
    const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const data = imgData.data; const width = imgData.width; const height = imgData.height;
    const targetIdx = (startY * width + startX) * 4;
    const startR = data[targetIdx], startG = data[targetIdx+1], startB = data[targetIdx+2];
    if (startR === fillRGB.r && startG === fillRGB.g && startB === fillRGB.b) return;
    const queue = [[startX, startY]];
    while (queue.length > 0) {
        const [cx, cy] = queue.shift(); const idx = (cy * width + cx) * 4;
        if (data[idx] === startR && data[idx+1] === startG && data[idx+2] === startB) {
            data[idx] = fillRGB.r; data[idx+1] = fillRGB.g; data[idx+2] = fillRGB.b; data[idx+3] = 255;
            if (cx > 0) queue.push([cx - 1, cy]); if (cx < width - 1) queue.push([cx + 1, cy]);
            if (cy > 0) queue.push([cx, cy - 1]); if (cy < height - 1) queue.push([cx, cy + 1]);
        }
    }
    ctx.putImageData(imgData, 0, 0);
}

function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? { r: parseInt(result[1], 16), g: parseInt(result[2], 16), b: parseInt(result[3], 16) } : { r: 0, g: 0, b: 0 };
}

function trackDrawAction(e) {
    if(!drawing || !isMyTurn || activeTool === 'bucket') return;
    const rect = canvas.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    const x = clientX - rect.left;
    const y = clientY - rect.top;
    
    ctx.lineWidth = brushSize.value;
    ctx.strokeStyle = (activeTool === 'eraser') ? '#ffffff' : selectedColorHex;
    ctx.lineTo(x, y); 
    ctx.stroke();
    ctx.beginPath(); 
    ctx.moveTo(x, y);
    activeStroke.push([x, y]);
}

canvas.addEventListener('mousedown', (e) => {
    if(!isMyTurn) return;
    const rect = canvas.getBoundingClientRect();
    const startX = Math.round(e.clientX - rect.left); 
    const startY = Math.round(e.clientY - rect.top);

    if (activeTool === 'bucket') {
        executeFloodFill(startX, startY, hexToRgb(selectedColorHex));
        socket.emit('stroke_data', { room: rName, stroke: { type: 'bucket', x: startX, y: startY, color: selectedColorHex } });
        return;
    }
    drawing = true; activeStroke = []; ctx.beginPath(); trackDrawAction(e);
});

canvas.addEventListener('mousemove', trackDrawAction);
window.addEventListener('mouseup', () => {
    if(!drawing) return; drawing = false; ctx.beginPath();
    if(activeStroke.length > 0) {
        socket.emit('stroke_data', { room: rName, stroke: { type: 'line', points: activeStroke, color: (activeTool === 'eraser') ? '#ffffff' : selectedColorHex, size: brushSize.value } });
    }
});

canvas.addEventListener('touchstart', (e) => {
    e.preventDefault(); if(!isMyTurn) return;
    const rect = canvas.getBoundingClientRect();
    const startX = Math.round(e.touches[0].clientX - rect.left); 
    const startY = Math.round(e.touches[0].clientY - rect.top);
    if(activeTool === 'bucket') { executeFloodFill(startX, startY, hexToRgb(selectedColorHex)); return; }
    drawing = true; activeStroke = []; ctx.beginPath(); trackDrawAction(e);
});
canvas.addEventListener('touchmove', (e) => { e.preventDefault(); trackDrawAction(e); });
canvas.addEventListener('touchend', () => { drawing = false; ctx.beginPath(); });

function renderRemoteStroke(stroke) {
    if (stroke.type === 'bucket') { executeFloodFill(stroke.x, stroke.y, hexToRgb(stroke.color)); return; }
    ctx.beginPath(); ctx.lineWidth = stroke.size; ctx.strokeStyle = stroke.color;
    if(stroke.points && stroke.points.length > 0) {
        ctx.moveTo(stroke.points[0][0], stroke.points[0][1]);
        stroke.points.forEach(p => { ctx.lineTo(p[0], p[1]); ctx.stroke(); });
    }
    ctx.beginPath();
}

function clearSystemCanvas(localOnly = false) {
    ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, canvas.width, canvas.height);
    if(!localOnly) socket.emit('clear_canvas', { room: rName });
}

function transmitGuess(e) {
    e.preventDefault();
    const cleanedInputVal = chatInput.value.trim();
    
    if(cleanedInputVal !== "" && !isMyTurn) {
        socket.emit('submit_guess', { 
            username: user.trim(), 
            room: rName, 
            guess: cleanedInputVal 
        });
        chatInput.value = '';
    }
}

function exitCluster() {
    socket.emit('leave_room', { username: user, room: rName });
    window.location.href = 'dashboard.html';
}

// Consolidated core anchor page loader routine execution gate
window.onload = () => {
    if(!localStorage.getItem('token')) { 
        window.location.href = 'login.html'; 
        return; 
    }
    initializeCanvasTopology();
    connectToSocketCluster();
};
window.addEventListener('resize', initializeCanvasTopology);
// ==================== SYSTEM KEYBOARD MACROS & SHORTCUT HOOKS ====================
window.addEventListener('keydown', (e) => {
    // Only capture events if the user isn't actively writing guesses inside the form channel chat input box
    if (document.activeElement === chatInput) return;

    const shortcutKeyAction = e.key.toLowerCase();
    
    if (shortcutKeyAction === 'm') {
        e.preventDefault();
        selectTool('brush');
        console.log("Macro shortcut intercept: Switched to marker brush configuration tool path.");
    } else if (shortcutKeyAction === 'e') {
        e.preventDefault();
        selectTool('eraser');
    } else if (shortcutKeyAction === 'b') {
        e.preventDefault();
        selectTool('bucket');
    } else if (shortcutKeyAction === 'c') {
        e.preventDefault();
        if (isMyTurn) clearSystemCanvas();
    }
});

// ==================== ACCESSIBILITY RE-PALETTING SYSTEMS SYSTEMS ====================
const STANDARD_PALETTE_COLORS_ARRAY = ["#000000", "#ef4444", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6"];
const DEUTERANOPIA_PALETTE_COLORS_ARRAY = ["#000000", "#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2"];
const PROTANOPIA_PALETTE_COLORS_ARRAY = ["#111111", "#787878", "#999999", "#CCCCCC", "#E69F00", "#56B4E9"];

function toggleColorblindPaletteShiftFilter(selectedFilterModeType) {
    let targetedPaletteMap = STANDARD_PALETTE_COLORS_ARRAY;
    
    if (selectedFilterModeType === "Deuteranopia") {
        targetedPaletteMap = DEUTERANOPIA_PALETTE_COLORS_ARRAY;
    } else if (selectedFilterModeType === "Protanopia") {
        targetedPaletteMap = PROTANOPIA_PALETTE_COLORS_ARRAY;
    }

    // Grab all the color circles inside your toolbar and remap them to the colorblind-friendly colors
    const colorSwatchesDotsElementsList = document.querySelectorAll('#colorPalette .color-dot');
    colorSwatchesDotsElementsList.forEach((dotNode, loopIndex) => {
        if (targetedPaletteMap[loopIndex]) {
            const hexColorString = targetedPaletteMap[loopIndex];
            
            // Re-render properties instantly
            dotNode.style.backgroundColor = hexColorString;
            dotNode.setAttribute('data-color', hexColorString);
            
            // If the swatch is currently selected, update the brush color instantly too
            if (dotNode.classList.contains('active')) {
                selectedColorHex = hexColorString;
            }
        }
    });
    
    console.log(`Accessibility Filter Shift Complete: Applied targeted array matrix parameter mappings matching: ${selectedFilterModeType}`);
}