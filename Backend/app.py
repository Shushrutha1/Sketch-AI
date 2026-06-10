import os
import time
import threading
import joblib
import datetime
import random  # <-- Imported for generating 4-digit codes
from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime, timedelta
import random

# Core categorized words dictionary mapping your structural requirements
WORD_POOL = {
    "Animal": ["CAT", "DOG", "ELEPHANT", "LION", "TIGER", "MONKEY", "RABBIT", "HORSE"],
    "Object": ["HAT", "CHAIR", "CLOCK", "BOTTLE", "PHONE", "KEY", "CAMERA", "GUITAR"],
    "Food": ["PIZZA", "BURGER", "APPLE", "BANANA", "CAKE", "DONUT", "SANDWICH", "SUSHI"],
    "Vehicle": ["CAR", "BICYCLE", "AIRPLANE", "ROCKET", "TRAIN", "HELICOPTER", "BOAT"],
    "Nature": ["TREE", "FLOWER", "MOUNTAIN", "RIVER", "CLOUD", "SUN", "MOON", "CACTUS"]
}
CATEGORIES = ["Animal", "Object", "Food", "Vehicle", "Nature"]
# Setup paths to find your Frontend folder files easily
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, '../Frontend'))

# ==================== ADVANCED DATA MODELS & ASSIGNMENTS ====================
ACHIEVEMENTS_MATRIX = {
    "FIRST_STREAK": {"title": "On Fire", "badge": "🔥", "desc": "Logged in 2 consecutive days."},
    "COIN_HOARDER": {"title": "Treasure Hunter", "badge": "🪙", "desc": "Accumulated over 1,000 coins."},
    "ART_MASTER": {"title": "Picasso Node", "badge": "🎨", "desc": "Earned over 5,000 match points."}
}

COLORBLIND_PALETTES = {
    "Deuteranopia": ["#000000", "#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7"],
    "Protanopia": ["#000000", "#111111", "#787878", "#999999", "#CCCCCC", "#FFFFFF", "#E69F00", "#56B4E9"]
}

def calculate_xp_and_level_up(username, xp_gained):
    """Calculates RPG leveling matrices. Level scales exponentially every 1000 * level XP."""
    user_profile = db.users.find_one({"username": username})
    if not user_profile: return
    
    current_xp = user_profile.get("xp", 0) + xp_gained
    current_level = user_profile.get("level", 1)
    
    # Simple algorithm formula: Level up requirement = Level * 1200 XP
    xp_needed_for_next_level = current_level * 1200
    
    leveled_up = False
    while current_xp >= xp_needed_for_next_level:
        current_xp -= xp_needed_for_next_level
        current_level += 1
        xp_needed_for_next_level = current_level * 1200
        leveled_up = True
        
    update_payload = {"$set": {"xp": current_xp, "level": current_level}}
    db.users.update_one({"username": username}, update_payload)
    return {"leveled_up": leveled_up, "level": current_level, "xp": current_xp}

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

from Backend.auth import hash_password, check_password, generate_token, token_required
from Backend.feature_extractor import FeatureExtractor
from Backend.ai_agent import AIAgent

# --- LOCAL WINDOWS MONGODB CONNECTION ---
MONGO_URI = "mongodb://localhost:27017/sketch_ai"
client = MongoClient(MONGO_URI)
db = client['sketch_ai']

# Setup simple tables (collections) for your game data
db.users.create_index("username", unique=True)
db.rooms.create_index("room_id", unique=True)
db.leaderboard.create_index([("score", -1)])

# --- AI MACHINE LEARNING MODEL ---
MODEL_PATH = os.path.join(BASE_DIR, '../ML/saved_model/knn_model.pkl')
try:
    knn_classifier = joblib.load(MODEL_PATH)
except Exception:
    knn_classifier = None
    print("AI Model note: Running with a basic backup guessing system.")

ROOM_STATES = {}
CATEGORIES = ["Animal", "Object", "Food", "Vehicle", "Nature"]

# --- BACKGROUND TIMER UPDATE CORRECTION ---
# Ensure your game background clock loop looks like this to prevent floating infinite counts:
def game_timer_loop():
    while True:
        time.sleep(1)
        for room_id, state in list(ROOM_STATES.items()):
            if not state.get("active", False) or not state.get("players"):
                continue
            
            if state["timer"] > 0:
                state["timer"] -= 1
                socketio.emit('timer_update', {'timer': state["timer"]}, to=room_id)
            else:
                # Timer hit 0! 
                if state.get("active_round"):
                    # Guessing phase expired, move automatically to next choice loop!
                    socketio.emit('chat_message', {
                        'username': '⏰ TIME UP',
                        'message': f"No one guessed it! The secret word was: {state.get('current_word')}",
                        'system': True
                    }, to=room_id)
                    send_word_choices_to_drawer(room_id)
                else:
                    # Choice phase expired! Auto-assign a random choice word so it never gets stuck!
                    fallback_word = random.choice(state.get("round_choices", ["APPLE"]))
                    on_word_selected({'room': room_id, 'word': fallback_word, 'username': state.get("current_drawer_name")})

def send_word_choices_to_drawer(room_id):
    """MANDATORY PHASE 1: Stops active guessing timers, changes drawers, and sends 3 choices."""
    state = ROOM_STATES.get(room_id)
    if not state or not state.get('players'): return

    # Clear out current word so no one can guess while a user is choosing
    state["current_word"] = ""
    state["active_round"] = False # Pause active drawing time counts
    state["timer"] = 15 # Give them exactly 15 seconds to choose a word!

    # Move to the next drawer sequentially
    state["drawer_index"] = (state["drawer_index"] + 1) % len(state["players"])
    current_drawer = state["players"][state["drawer_index"]]
    state["current_drawer_name"] = current_drawer

    # Sample 3 random words completely across categories
    all_words = []
    for cat in CATEGORIES:
        all_words.extend(WORD_POOL[cat])
    selected_choices = random.sample(all_words, 3)
    state["round_choices"] = selected_choices

    # Broadcast to the room that this user is currently picking a word
    socketio.emit('room_state_update', {
        'players': state['players'],
        'current_drawer': current_drawer,
        'choosing': True
    }, to=room_id)

    # Push choices down to everyone (the frontend script will filter so only the drawer opens the pop-up modal)
    socketio.emit('word_choices_selection', {
        'drawer': current_drawer,
        'choices': selected_choices
    }, to=room_id)


def next_round(room_id):
    state = ROOM_STATES.get(room_id)
    if not state: return

    # Pick a random category out of your 5 structural core blocks
    target_category = random.choice(CATEGORIES)
    # Select a real word item matching that structural pool array
    selected_word = random.choice(WORD_POOL[target_category])
    
    # Simple clear hints strategy layout compilation
    generated_hint = f"A popular item in the {target_category} group containing {len(selected_word)} letters."

    state["current_word"] = selected_word.upper()
    state["hint"] = generated_hint
    state["timer"] = 60
    state["stroke_history"] = []
    
    # Choose who is drawing next cleanly
    players = state["players"]
    if players:
        state["drawer_index"] = (state["drawer_index"] + 1) % len(players)
        active_drawer = players[state["drawer_index"]]
    else:
        active_drawer = "Unassigned Node"

    # Broadcast straight onto room interfaces
    socketio.emit('round_start', {
        'drawer': active_drawer,
        'challenge': state["current_word"], # Drawer views the real word target (e.g. CAT)
        'hint': state["hint"],              # Others view the custom hint string
        'category': target_category
    }, to=room_id)

threading.Thread(target=game_timer_loop, daemon=True).start()

# --- WEB PAGE ROUTERS ---
@app.route('/')
def serve_index(): return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/login.html')
def serve_login(): return send_from_directory(FRONTEND_DIR, 'login.html')

@app.route('/register.html')
def serve_register(): return send_from_directory(FRONTEND_DIR, 'register.html')

@app.route('/dashboard.html')
def serve_dashboard(): return send_from_directory(FRONTEND_DIR, 'dashboard.html')

@app.route('/room.html')
def serve_room(): return send_from_directory(FRONTEND_DIR, 'room.html')

@app.route('/leaderboard.html')
def serve_leaderboard(): return send_from_directory(FRONTEND_DIR, 'leaderboard.html')


# --- USER ACCOUNT REGISTRATION & LOGIN APIS ---
@app.route('/api/auth/register', methods=['POST'])
def register_route():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    if not username or not email or not password:
        return jsonify({'message': 'Please fill out all fields.'}), 400
        
    if db.users.find_one({'$or': [{'username': username}, {'email': email}]}):
        return jsonify({'message': 'This user account already exists.'}), 400
        
    db.users.insert_one({
        'username': username, 'email': email, 'password': hash_password(password),
        'level': 1, 'xp': 0, 'coins': 100
    })
    db.leaderboard.insert_one({'username': username, 'score': 0})
    return jsonify({'token': generate_token(username), 'username': username}), 201

@app.route('/api/auth/login', methods=['POST'])
def login_route():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    user = db.users.find_one({'username': username})
    if not user or not check_password(password, user['password']):
        return jsonify({'message': 'Incorrect username or password.'}), 401
    return jsonify({'token': generate_token(username), 'username': username}), 200


# --- 🆕 NEW ROOM ALLOCATION & AUTHENTICATION ENDPOINTS ---

@app.route('/api/rooms/create', methods=['POST'])
@token_required
def create_room(current_user):
    """Generates an explicit database footprint for rooms. 
    Enforces a unique 4-digit string code if marked private."""
    data = request.get_json() or {}
    custom_name = data.get('name', 'Lobby Space').strip()
    is_private = data.get('isPrivate', False) == True
    
    room_id = ""
    if is_private:
        # Loop until we generate a completely unique 4 digit numeric identifier string
        while True:
            room_id = str(random.randint(1000, 9999))
            if not db.rooms.find_one({'room_id': room_id}):
                break
    else:
        # Standard cleaning layout configuration parameter strings for public rooms
        base_slug = "".join([c for c in custom_name if c.isalnum() or c.isspace()]).replace(" ", "-")
        if not base_slug: base_slug = "Lobby"
        room_id = f"{base_slug}-{random.randint(100, 999)}"

    new_room_doc = {
        'room_id': room_id,
        'room_name': custom_name if not is_private else f"Private ({room_id})",
        'players': [],
        'active': False,
        'is_private': is_private,
        'players_count': 0,
        'created_at': datetime.datetime.utcnow()
    }
    
    db.rooms.insert_one(new_room_doc)
    return jsonify({'room_id': room_id, 'is_private': is_private}), 201


@app.route('/api/rooms', methods=['GET'])
@token_required
def get_live_active_rooms(current_user):
    room_list_payload = []
    
    # Loop over your live dictionary memory states cleanly
    for room_id, state in list(ROOM_STATES.items()):
        # 1. STRIP PRIVATE LOBBIES: Don't reveal private channels on global lists
        if room_id.startswith('PVT-'):
            continue
            
        # 2. STRIP DEAD/ENDED ROOMS: If a match has 0 players or is explicitly inactive, skip it completely!
        player_count = len(state.get('players', []))
        if player_count == 0 and not state.get('active', False):
            continue
            
        # 3. COMPILING LIVE RESPONSE: Build dynamic properties straight out of active state tracks
        room_list_payload.append({
            "room_id": room_id,
            "players_count": player_count,
            "active": state.get('active', False) # True when host clicks start loop, false when ended
        })
        
    # FALLBACK SEED ENGINE: If no one has spun any rooms yet, provide baseline available empty slots
    if len(room_list_payload) == 0:
        room_list_payload = [
            { "room_id": "Global-Production-Cluster", "players_count": 0, "active": False },
            { "room_id": "AI-Inference-Sandbox", "players_count": 0, "active": False },
            { "room_id": "Lobby-Room-123", "players_count": 0, "active": False }
        ]
        
    return jsonify(room_list_payload), 200


@app.route('/api/rooms/verify/<room_code>', methods=['GET'])
@token_required
def verify_private_room(current_user, room_code):
    """Checks if a dynamic room matching this 4-digit code exists and is operational."""
    target_room = db.rooms.find_one({'room_id': room_code.strip()})
    if target_room:
        return jsonify({'exists': True, 'room_id': target_room['room_id']}), 200
    else:
        return jsonify({'exists': False, 'message': 'Lobby matching code does not exist.'}), 404


@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    board = list(db.leaderboard.find().sort('score', -1).limit(10))
    for b in board: b['_id'] = str(b['_id'])
    return jsonify(board), 200

@app.route('/api/user/profile', methods=['GET'])
@token_required
def get_user_profile(current_user):
    user_data = db.users.find_one({'username': current_user}, {'_id': 0, 'password': 0})
    if not user_data:
        return jsonify({'message': 'User account not found.'}), 404
        
    leaderboard_data = db.leaderboard.find_one({'username': current_user}, {'_id': 0})
    
    response_payload = {
        'username': user_data.get('username'),
        'email': user_data.get('email'),
        'coins': user_data.get('coins', 100), 
        'score': leaderboard_data.get('score', 0) if leaderboard_data else 0
    }
    return jsonify(response_payload), 200


# --- REAL-TIME MULTIPLAYER GAME MECHANICS (SOCKETS) ---
# --- GLOBAL ROOM TRACKER CORRECTION ---
@socketio.on('join_room')
def on_join(data):
    username = str(data.get('username', '')).strip()
    room_id = data.get('room')
    if not username or not room_id: return

    join_room(room_id)
    
    if room_id not in ROOM_STATES:
        ROOM_STATES[room_id] = {
            'players': [], 'drawer_index': -1, 'current_word': '',
            'hint': '', 'timer': 60, 'active': False, 'stroke_history': [],
            'session_scores': {}
        }
        
    state = ROOM_STATES[room_id]
    if username not in state['players']:
        state['players'].append(username)
    
    # Initialize their local points session from zero if they are new
    if username not in state['session_scores']:
        state['session_scores'][username] = 0

    # 📢 BROADCAST ARRIVAL MESSAGE IN CHAT
    socketio.emit('chat_message', {
        'username': '📢 SYSTEM',
        'message': f"{username} has entered the room!",
        'system': True
    }, to=room_id)

    # Sync player counts and sidebar lists
    socketio.emit('room_state_update', {
        'players': state['players'],
        'current_drawer': state['players'][state['drawer_index']] if state['drawer_index'] >= 0 else None
    }, to=room_id)
    socketio.emit('session_scores_update', {'scores': state["session_scores"]}, to=room_id)


def handle_profile_payouts_on_exit(username, room_id):
    """Saves accumulated room session points safely to the lifetime database collections on exit."""
    state = ROOM_STATES.get(room_id)
    if not state or "session_scores" not in state: return

    room_points = state["session_scores"].get(username, 0)
    if room_points > 0:
        # Commit match points to the leaderboard database table tracking
        db.leaderboard.update_one({'username': username}, {'$inc': {'score': room_points}}, upsert=True)
        
        # Give a proportional coin bonus on exit (e.g. 10% of total points earned)
        coin_payout = max(10, int(room_points // 10))
        db.users.update_one({'username': username}, {'$inc': {'coins': coin_payout}}, upsert=True)
        
        # Zero out their session score so they can't double-claim if they rejoin
        state["session_scores"][username] = 0

@socketio.on('leave_room')
def on_leave(data):
    username = str(data.get('username', '')).strip()
    room_id = data.get('room')
    state = ROOM_STATES.get(room_id)
    
    if not state: return

    # 💾 SAVE ACCUMULATED POINTS TO DATABASE BEFORE REMOVING THEM
    handle_profile_payouts_on_exit(username, room_id)

    if username in state['players']:
        state['players'].remove(username)
    if username in state['session_scores']:
        del state['session_scores'][username]

    leave_room(room_id)

    # 📢 BROADCAST DEPARTURE MESSAGE IN CHAT
    socketio.emit('chat_message', {
        'username': '🚪 SYSTEM',
        'message': f"{username} has left the match room.",
        'system': True
    }, to=room_id)

    # Sync room lists after departure
    socketio.emit('room_state_update', {
        'players': state['players'],
        'current_drawer': state['players'][state['drawer_index']] if state['drawer_index'] >= 0 else None
    }, to=room_id)
    socketio.emit('session_scores_update', {'scores': state["session_scores"]}, to=room_id)


@socketio.on('force_end_game')
def on_force_end(data):
    """Triggered when someone clicks 'End Round' to crown winners globally."""
    room_id = data.get('room')
    state = ROOM_STATES.get(room_id)
    if not state or "session_scores" not in state: return

    # Sort session scores to establish standings
    sorted_standings = sorted(state["session_scores"].items(), key=lambda item: item[1], reverse=True)
    
    # Structure podium data response arrays
    winners_list = []
    for index, (player, score) in enumerate(sorted_standings[:3]):
        winners_list.append({"rank": index + 1, "username": player, "score": score})
        # Automatically trigger database payouts for everyone since the game is over
        handle_profile_payouts_on_exit(player, room_id)

    # 1. Global broadcast to trigger the animated modal overlay and audio effects everywhere
    socketio.emit('global_game_over_podium', {'winners': winners_list}, to=room_id)
    
    # 2. FIXED: TURN OFF ACTIVE SIGNALS AND CLEAN LOBBY TO DISMISS FROM GLOBAL DIRECTORY
    state['active'] = False
    
    # OPTIONAL: Completely remove it from active memory tracking so it disappear completely
    if room_id in ROOM_STATES:
        del ROOM_STATES[room_id]

@socketio.on('start_game')
def on_start(data):
    room_id = data.get('room')
    state = ROOM_STATES.get(room_id)
    if state:
        state['active'] = True
        # FORCE PROMPT CHOICE RE-GENERATION INSTANTLY
        send_word_choices_to_drawer(room_id)

@socketio.on('word_selected')
def on_word_selected(data):
    room_id = data.get('room')
    chosen_word = data.get('word', '').upper().strip()
    state = ROOM_STATES.get(room_id)
    if not state: return

    # If testing alone, bypass strict turn-ownership verification
    if len(state.get('players', [])) > 1:
        if state.get("current_drawer_name") != data.get("username", state.get("current_drawer_name")): 
            return

    detected_cat = "General"
    for cat, words in WORD_POOL.items():
        if chosen_word in words:
            detected_cat = cat
            break

    state["current_word"] = chosen_word
    state["timer"] = 60 
    state["active_round"] = True 
    state["stroke_history"] = []
    state["hint"] = f"A popular item belonging to the {detected_cat} category containing {len(chosen_word)} letters."

    socketio.emit('round_start', {
        'drawer': state["current_drawer_name"],
        'challenge': chosen_word,
        'hint': state["hint"],
        'category': detected_cat
    }, to=room_id)


@socketio.on('stroke_data')
def on_stroke(data):
    room_id = data.get('room')
    stroke = data.get('stroke')
    state = ROOM_STATES.get(room_id)
    if state:
        state['stroke_history'].append(stroke)
        emit('broadcast_stroke', {'stroke': stroke}, to=room_id, include_self=False)
        
        if knn_classifier and len(state['stroke_history']) % 3 == 0:
            features = FeatureExtractor.process_canvas_payload(state['stroke_history'])
            prediction = knn_classifier.predict([features])[0]
            emit('ml_prediction_update', {'prediction': prediction}, to=room_id)

@socketio.on('submit_guess')
def on_guess(data):
    username = str(data.get('username', '')).strip()
    room_id = data.get('room')
    guess = str(data.get('guess', '')).strip().upper()
    state = ROOM_STATES.get(room_id)
    if not state or not state.get('current_word'): return

    # ANALYTICS LOGGING: Increment total guess attempts inside the match instance
    state["analytics_total_guesses"] = state.get("analytics_total_guesses", 0) + 1

    if guess == state['current_word'].upper():
        points_earned = int(state['timer'] * 10)
        coins_earned = max(10, int(state['timer'] // 2))
        xp_gained = 150 # Base XP per correct evaluation match guess

        # GAMIFICATION PIPELINE EXECUTION
        lvl_metrics = calculate_xp_and_level_up(username, xp_gained)
        db.leaderboard.update_one({'username': username}, {'$inc': {'score': points_earned}}, upsert=True)
        db.users.update_one({'username': username}, {'$inc': {'coins': coins_earned}}, upsert=True)
        
        # Check and unlock coin-hoarder achievements badge dynamically
        updated_profile = db.users.find_one({"username": username})
        if updated_profile.get("coins", 0) >= 1000 and "COIN_HOARDER" not in updated_profile.get("badges", []):
            db.users.update_one({"username": username}, {"$addToSet": {"badges": "COIN_HOARDER"}})
            socketio.emit('chat_message', {
                'username': '🏆 UNLOCK ALERT',
                'message': f"{username} unlocked the Badge achievement: Treasure Hunter 🪙!",
                'system': True
            }, to=room_id)

        state['session_scores'][username] = state['session_scores'].get(username, 0) + points_earned

        level_up_notice = f" [LEVEL UP! Reached Lvl {lvl_metrics['level']}! 🎉]" if lvl_metrics and lvl_metrics["leveled_up"] else ""
        
        socketio.emit('chat_message', {
            'username': '🎉 SYSTEM ALERT',
            'message': f"{username} guessed correctly! (+{points_earned} pts, +{coins_earned} Coins, +{xp_gained} XP){level_up_notice}",
            'system': True
        }, to=room_id)

        socketio.emit('session_scores_update', {'scores': state["session_scores"]}, to=room_id)
        send_word_choices_to_drawer(room_id)

@socketio.on('admin_moderation_command')
def on_admin_command(data):
    admin_user = data.get('admin_username')
    target_player = data.get('target_username')
    room_id = data.get('room')
    action = data.get('action') # "KICK" or "BAN"

    # Verify authorization check credentials securely out of MongoDB roles field
    profile = db.users.find_one({"username": admin_user})
    if not profile or not profile.get('is_admin', False):
        return emit('error_alert', {'message': 'Unauthorized command intercept rejected.'})

    state = ROOM_STATES.get(room_id)
    if not state: return

    if action == "KICK":
        if target_player in state.get('players', []):
            state['players'].remove(target_player)
        if target_player in state.get('session_scores', {}):
            del state['session_scores'][target_player]
            
        # Emit target evacuation instruction directly down to all clients
        socketio.emit('evacuate_kicked_player', {'target': target_player, 'reason': 'Kicked by Room Administrator.'}, to=room_id)
        
        socketio.emit('chat_message', {
            'username': '🛡️ MODERATOR',
            'message': f"{target_player} has been forcefully removed from the lobby cluster session.",
            'system': True
        }, to=room_id)
        
        socketio.emit('room_state_update', {
            'players': state['players'],
            'current_drawer': state['players'][state['drawer_index']] if state['drawer_index'] >= 0 else None
        }, to=room_id)

        
@socketio.on('clear_canvas')
def on_clear(data):
    room_id = data.get('room')
    state = ROOM_STATES.get(room_id)
    if state:
        state['stroke_history'] = []
        emit('broadcast_clear', {}, to=room_id, include_self=False)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)