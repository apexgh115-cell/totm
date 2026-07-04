from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for, make_response
from flask_socketio import SocketIO, emit, join_room, leave_room
import json
import os
import uuid
import time
import random
import hashlib
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tot-secret-key-2024'
app.config['PERMANENT_SESSION_LIFETIME'] = 30 * 24 * 60 * 60
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# ============================================================
# تنظیمات ذخیره‌سازی
# ============================================================

DATA_FOLDER = os.environ.get('DATA_FOLDER', '/data')

UPLOAD_FOLDER = os.path.join(DATA_FOLDER, "uploads")
GROUPS_FILE = os.path.join(DATA_FOLDER, "groups.json")
USER_GROUPS_FILE = os.path.join(DATA_FOLDER, "user_groups.json")
MESSAGES_FILE = os.path.join(DATA_FOLDER, "messages.json")
USERS_FILE = os.path.join(DATA_FOLDER, "users.json")
SESSIONS_FILE = os.path.join(DATA_FOLDER, "sessions.json")

if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ============================================================
# سیستم ID
# ============================================================

def generate_user_id():
    return str(random.randint(100000000, 999999999))

def generate_group_id():
    return str(random.randint(1000000000, 9999999999))

def generate_message_id():
    return str(random.randint(100000000000, 999999999999))

def generate_session_token():
    return hashlib.sha256(str(uuid.uuid4()).encode() + str(time.time()).encode()).hexdigest()

# ============================================================
# دیتابیس کاربران (با Badge)
# ============================================================

def ensure_users_file():
    if not os.path.exists(USERS_FILE):
        default_users = {}
        default_credentials = {
            "Apex": {"password": "139027", "badge": "UFC", "badge_color": "#ff0000"},
            "samir": {"password": "200300", "badge": "", "badge_color": ""},
            "patrik": {"password": "123456", "badge": "", "badge_color": ""},
            "mz": {"password": "90000", "badge": "", "badge_color": ""},
            "mamad": {"password": "373839", "badge": "", "badge_color": ""},
            "m.r": {"password": "899091", "badge": "", "badge_color": ""},
            "es": {"password": "987654321", "badge": "", "badge_color": ""},
            "el": {"password": "878685", "badge": "", "badge_color": ""},
            "is": {"password": "9087", "badge": "", "badge_color": ""},
            "iyd": {"password": "90784", "badge": "", "badge_color": ""}
        }
        
        for username, info in default_credentials.items():
            user_id = generate_user_id()
            default_users[user_id] = {
                "user_id": user_id,
                "username": username,
                "password": info["password"],
                "display_name": username,
                "bio": "",
                "avatar": "",
                "badge": info["badge"],
                "badge_color": info["badge_color"],
                "created_at": time.time(),
                "last_seen": time.time(),
                "is_online": False
            }
        
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_users, f, ensure_ascii=False, indent=2)

def load_users():
    ensure_users_file()
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_users(users_data):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users_data, f, ensure_ascii=False, indent=2)

def get_user_by_username(username):
    users = load_users()
    for user_id, user_data in users.items():
        if user_data.get("username") == username:
            return user_data
    return None

def get_user_by_id(user_id):
    users = load_users()
    return users.get(str(user_id))

def get_user_display_name(user_id):
    user = get_user_by_id(user_id)
    if user:
        return user.get("display_name", user.get("username"))
    return "Unknown"

def update_user_field(user_id, field, value):
    users = load_users()
    user_id = str(user_id)
    if user_id in users:
        users[user_id][field] = value
        save_users(users)
        return True
    return False

def update_user_profile(user_id, display_name=None, bio=None, avatar=None):
    users = load_users()
    user_id = str(user_id)
    if user_id not in users:
        return False
    
    if display_name is not None:
        users[user_id]["display_name"] = display_name
    if bio is not None:
        users[user_id]["bio"] = bio
    if avatar is not None:
        users[user_id]["avatar"] = avatar
    
    save_users(users)
    return True

def update_user_badge(user_id, badge=None, badge_color=None):
    users = load_users()
    user_id = str(user_id)
    if user_id not in users:
        return False
    
    if badge is not None:
        users[user_id]["badge"] = badge
    if badge_color is not None:
        users[user_id]["badge_color"] = badge_color
    
    save_users(users)
    return True

# ============================================================
# سیستم Session
# ============================================================

def ensure_sessions_file():
    if not os.path.exists(SESSIONS_FILE):
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

def load_sessions():
    ensure_sessions_file()
    try:
        with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_sessions(sessions_data):
    with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(sessions_data, f, ensure_ascii=False, indent=2)

def create_session(user_id):
    sessions = load_sessions()
    token = generate_session_token()
    sessions[token] = {
        "user_id": str(user_id),
        "created_at": time.time(),
        "expires_at": time.time() + (30 * 24 * 60 * 60)
    }
    save_sessions(sessions)
    return token

def validate_session(token):
    if not token:
        return None
    sessions = load_sessions()
    if token not in sessions:
        return None
    session_data = sessions[token]
    if session_data.get("expires_at", 0) < time.time():
        del sessions[token]
        save_sessions(sessions)
        return None
    return session_data["user_id"]

def destroy_session(token):
    if not token:
        return False
    sessions = load_sessions()
    if token in sessions:
        del sessions[token]
        save_sessions(sessions)
        return True
    return False

# ============================================================
# توابع گروه و پیام
# ============================================================

def ensure_groups_file():
    if not os.path.exists(GROUPS_FILE):
        default_group_id = generate_group_id()
        default_groups = {
            default_group_id: {
                "group_id": default_group_id,
                "name": "Chat 1",
                "password": "252423",
                "created_by": "Apex",
                "created_at": time.time(),
                "avatar": "💬",
                "link": default_group_id,
                "members": ["Apex"]
            }
        }
        with open(GROUPS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_groups, f, ensure_ascii=False, indent=2)

def read_groups():
    ensure_groups_file()
    with open(GROUPS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def write_groups(groups):
    with open(GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)

def ensure_user_groups_file():
    if not os.path.exists(USER_GROUPS_FILE):
        with open(USER_GROUPS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

def read_user_groups():
    ensure_user_groups_file()
    with open(USER_GROUPS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def write_user_groups(user_groups):
    with open(USER_GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(user_groups, f, ensure_ascii=False, indent=2)

def ensure_messages_file():
    if not os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

def read_messages(group_id=None):
    ensure_messages_file()
    with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
        try:
            messages = json.load(f)
            if not isinstance(messages, list):
                messages = []
            if group_id:
                return [msg for msg in messages if msg.get('group_id') == group_id]
            return messages
        except json.JSONDecodeError:
            return []

def write_messages(messages):
    ensure_messages_file()
    if not isinstance(messages, list):
        messages = []
    with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'webm', 'mov', 'avi', 'mkv'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if ext in {'jpg', 'jpeg', 'png', 'gif', 'webp'}:
        return 'image'
    elif ext in {'mp4', 'webm', 'mov', 'avi', 'mkv'}:
        return 'video'
    return 'file'

# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def index():
    token = request.cookies.get('session_token')
    if token:
        user_id = validate_session(token)
        if user_id:
            return redirect(url_for('rooms'))
    return redirect(url_for('login'))

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        user = get_user_by_username(username)
        if user and user.get("password") == password:
            token = create_session(user["user_id"])
            response = make_response(redirect(url_for('rooms')))
            response.set_cookie('session_token', token, max_age=30*24*60*60, httponly=True, samesite='Lax')
            return response
        else:
            return render_template("login.html", error="Invalid username or password")
    
    token = request.cookies.get('session_token')
    if token:
        user_id = validate_session(token)
        if user_id:
            return redirect(url_for('rooms'))
    
    return render_template("login.html", error=None)

@app.route("/logout")
def logout():
    token = request.cookies.get('session_token')
    if token:
        user_id = validate_session(token)
        if user_id:
            update_user_field(user_id, "is_online", False)
            update_user_field(user_id, "last_seen", time.time())
        destroy_session(token)
    
    response = make_response(redirect(url_for('login')))
    response.delete_cookie('session_token')
    return response

@app.route("/rooms")
def rooms():
    token = request.cookies.get('session_token')
    if not token:
        return redirect(url_for('login'))
    
    user_id = validate_session(token)
    if not user_id:
        return redirect(url_for('login'))
    
    user = get_user_by_id(user_id)
    if not user:
        return redirect(url_for('login'))
    
    username = user.get("username")
    display_name = user.get("display_name", username)
    
    user_groups = read_user_groups()
    user_group_list = user_groups.get(username, [])
    groups = read_groups()
    
    if username == "Apex":
        for gid, ginfo in groups.items():
            if gid not in user_group_list:
                user_group_list.append(gid)
                if "members" not in ginfo:
                    ginfo["members"] = []
                if username not in ginfo["members"]:
                    ginfo["members"].append(username)
                write_groups(groups)
                break
    
    user_group_details = []
    for gid in user_group_list:
        if gid in groups:
            user_group_details.append({
                "id": gid,
                "name": groups[gid]["name"],
                "avatar": groups[gid].get("avatar", "💬"),
                "link": groups[gid].get("link", gid)
            })
    
    return render_template("rooms.html", 
                         username=username, 
                         display_name=display_name,
                         user_id=user_id,
                         user_groups=user_group_details, 
                         is_apex=(username == "Apex"))

@app.route("/chat/<path:group_id>")
def chat(group_id):
    token = request.cookies.get('session_token')
    if not token:
        return redirect(url_for('login'))
    
    user_id = validate_session(token)
    if not user_id:
        return redirect(url_for('login'))
    
    user = get_user_by_id(user_id)
    if not user:
        return redirect(url_for('login'))
    
    username = user.get("username")
    display_name = user.get("display_name", username)
    badge = user.get("badge", "")
    badge_color = user.get("badge_color", "")
    
    groups = read_groups()
    if group_id not in groups:
        return "Group not found", 404
    
    user_groups = read_user_groups()
    if group_id not in user_groups.get(username, []):
        return "You are not a member of this group", 403
    
    return render_template("chat1.html", 
                         group_id=group_id, 
                         group_name=groups[group_id]["name"], 
                         group_link=groups[group_id].get("link", group_id), 
                         username=username,
                         display_name=display_name,
                         user_id=user_id,
                         badge=badge,
                         badge_color=badge_color,
                         is_apex=(username == "Apex"))

@app.route("/profile")
def profile():
    token = request.cookies.get('session_token')
    if not token:
        return redirect(url_for('login'))
    
    user_id = validate_session(token)
    if not user_id:
        return redirect(url_for('login'))
    
    user = get_user_by_id(user_id)
    if not user:
        return redirect(url_for('login'))
    
    return render_template("profile.html", 
                         username=user.get("username"),
                         display_name=user.get("display_name", user.get("username")),
                         user_id=user_id,
                         bio=user.get("bio", ""),
                         avatar=user.get("avatar", ""),
                         badge=user.get("badge", ""),
                         badge_color=user.get("badge_color", ""))

@app.route("/settings")
def settings():
    token = request.cookies.get('session_token')
    if not token:
        return redirect(url_for('login'))
    
    user_id = validate_session(token)
    if not user_id:
        return redirect(url_for('login'))
    
    user = get_user_by_id(user_id)
    if not user:
        return redirect(url_for('login'))
    
    return render_template("settings.html", 
                         username=user.get("username"),
                         display_name=user.get("display_name", user.get("username")),
                         user_id=user_id,
                         badge=user.get("badge", ""),
                         badge_color=user.get("badge_color", ""))

@app.route("/saved")
def saved():
    token = request.cookies.get('session_token')
    if not token:
        return redirect(url_for('login'))
    
    user_id = validate_session(token)
    if not user_id:
        return redirect(url_for('login'))
    
    user = get_user_by_id(user_id)
    if not user:
        return redirect(url_for('login'))
    
    return render_template("saved.html", 
                         username=user.get("username"),
                         display_name=user.get("display_name", user.get("username")))

@app.route("/profile_view")
def profile_view():
    token = request.cookies.get('session_token')
    if not token:
        return redirect(url_for('login'))
    
    user_id = validate_session(token)
    if not user_id:
        return redirect(url_for('login'))
    
    target_username = request.args.get('username')
    if not target_username:
        return redirect(url_for('rooms'))
    
    target_user = get_user_by_username(target_username)
    if not target_user:
        return render_template("profile_view.html", error="User not found")
    
    current_user = get_user_by_id(user_id)
    
    return render_template("profile_view.html", 
                         target_username=target_username,
                         target_user_id=target_user.get("user_id"),
                         display_name=target_user.get("display_name", target_username),
                         bio=target_user.get("bio", "No bio"),
                         avatar=target_user.get("avatar", ""),
                         badge=target_user.get("badge", ""),
                         badge_color=target_user.get("badge_color", ""),
                         current_user=current_user.get("username"))

# ============================================================
# API
# ============================================================

@app.route("/api/get_profile", methods=["GET"])
def get_profile():
    token = request.cookies.get('session_token')
    if not token:
        return jsonify({"success": False, "error": "Not logged in"})
    
    user_id = validate_session(token)
    if not user_id:
        return jsonify({"success": False, "error": "Invalid session"})
    
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"success": False, "error": "User not found"})
    
    return jsonify({
        "success": True,
        "user_id": user_id,
        "username": user.get("username"),
        "display_name": user.get("display_name", user.get("username")),
        "bio": user.get("bio", ""),
        "avatar": user.get("avatar", ""),
        "badge": user.get("badge", ""),
        "badge_color": user.get("badge_color", ""),
        "is_online": user.get("is_online", False),
        "last_seen": user.get("last_seen", 0)
    })

@app.route("/api/update_profile", methods=["POST"])
def update_profile():
    token = request.cookies.get('session_token')
    if not token:
        return jsonify({"success": False, "error": "Not logged in"})
    
    user_id = validate_session(token)
    if not user_id:
        return jsonify({"success": False, "error": "Invalid session"})
    
    data = request.json
    display_name = data.get('display_name', '').strip()
    bio = data.get('bio', '').strip()
    avatar = data.get('avatar', '')
    badge = data.get('badge', '').strip().upper()
    badge_color = data.get('badge_color', '').strip()
    
    updated_fields = {}
    
    if display_name:
        update_user_profile(user_id, display_name=display_name)
        updated_fields['display_name'] = display_name
    if bio is not None:
        update_user_profile(user_id, bio=bio)
        updated_fields['bio'] = bio
    if avatar:
        update_user_profile(user_id, avatar=avatar)
        updated_fields['avatar'] = avatar
    if badge is not None:
        update_user_badge(user_id, badge=badge, badge_color=badge_color)
        updated_fields['badge'] = badge
        updated_fields['badge_color'] = badge_color
    
    user = get_user_by_id(user_id)
    
    socketio.emit('user_profile_updated', {
        'user_id': user_id,
        'username': user.get("username"),
        'display_name': user.get("display_name", user.get("username")),
        'bio': user.get("bio", ""),
        'avatar': user.get("avatar", ""),
        'badge': user.get("badge", ""),
        'badge_color': user.get("badge_color", ""),
        'updated_fields': updated_fields
    }, broadcast=True)
    
    return jsonify({
        "success": True, 
        "display_name": user.get("display_name", user.get("username")),
        "bio": user.get("bio", ""),
        "avatar": user.get("avatar", ""),
        "badge": user.get("badge", ""),
        "badge_color": user.get("badge_color", "")
    })

@app.route("/api/user_profile")
def api_user_profile():
    username = request.args.get('username')
    if not username:
        return jsonify({"success": False, "error": "Username required"})
    
    user = get_user_by_username(username)
    if not user:
        return jsonify({"success": False, "error": "User not found"})
    
    return jsonify({
        "success": True,
        "user_id": user.get("user_id"),
        "username": username,
        "display_name": user.get("display_name", username),
        "bio": user.get("bio", "No bio"),
        "avatar": user.get("avatar", ""),
        "badge": user.get("badge", ""),
        "badge_color": user.get("badge_color", ""),
        "is_online": user.get("is_online", False),
        "last_seen": user.get("last_seen", 0)
    })

@app.route("/api/update_badge", methods=["POST"])
def update_badge():
    token = request.cookies.get('session_token')
    if not token:
        return jsonify({"success": False, "error": "Not logged in"})
    
    user_id = validate_session(token)
    if not user_id:
        return jsonify({"success": False, "error": "Invalid session"})
    
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"success": False, "error": "User not found"})
    
    if user.get("username") != "Apex":
        return jsonify({"success": False, "error": "Only Apex can manage badges"})
    
    data = request.json
    target_username = data.get('target_username')
    badge = data.get('badge', '').strip().upper()
    badge_color = data.get('badge_color', '').strip()
    
    if not target_username:
        return jsonify({"success": False, "error": "Target username required"})
    
    target_user = get_user_by_username(target_username)
    if not target_user:
        return jsonify({"success": False, "error": "User not found"})
    
    target_user_id = target_user.get("user_id")
    update_user_badge(target_user_id, badge=badge, badge_color=badge_color)
    
    socketio.emit('user_badge_updated', {
        'username': target_username,
        'badge': badge,
        'badge_color': badge_color
    }, broadcast=True)
    
    return jsonify({
        "success": True,
        "username": target_username,
        "badge": badge,
        "badge_color": badge_color
    })

@app.route("/api/group_members/<path:group_id>")
def get_group_members(group_id):
    groups = read_groups()
    if group_id not in groups:
        return jsonify({"success": False, "error": "Group not found"})
    
    members = groups[group_id].get("members", [])
    users = load_users()
    member_details = []
    
    for m in members:
        user = get_user_by_username(m)
        if user:
            member_details.append({
                "username": m,
                "display_name": user.get("display_name", m),
                "avatar": user.get("avatar", ""),
                "badge": user.get("badge", ""),
                "badge_color": user.get("badge_color", ""),
                "online": user.get("is_online", False),
                "user_id": user.get("user_id")
            })
    
    return jsonify({
        "success": True,
        "members": member_details,
        "count": len(members)
    })

@app.route("/api/user_groups")
def get_user_groups():
    token = request.cookies.get('session_token')
    if not token:
        return jsonify([])
    
    user_id = validate_session(token)
    if not user_id:
        return jsonify([])
    
    user = get_user_by_id(user_id)
    if not user:
        return jsonify([])
    
    username = user.get("username")
    user_groups = read_user_groups()
    groups = read_groups()
    
    result = []
    for gid in user_groups.get(username, []):
        if gid in groups:
            result.append({
                "id": gid,
                "name": groups[gid]["name"],
                "avatar": groups[gid].get("avatar", "💬")
            })
    return jsonify(result)

@app.route("/api/join_group", methods=["POST"])
def join_group():
    token = request.cookies.get('session_token')
    if not token:
        return jsonify({"success": False, "error": "Not logged in"})
    
    user_id = validate_session(token)
    if not user_id:
        return jsonify({"success": False, "error": "Invalid session"})
    
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"success": False, "error": "User not found"})
    
    data = request.json
    link = data.get('link')
    password = data.get('password')
    username = user.get("username")
    
    groups = read_groups()
    user_groups = read_user_groups()
    
    found_group = None
    for gid, ginfo in groups.items():
        if ginfo.get("link") == link or gid == link:
            found_group = gid
            break
    
    if not found_group or found_group not in groups:
        return jsonify({"success": False, "error": "Invalid link"})
    
    if groups[found_group]["password"] != password:
        return jsonify({"success": False, "error": "Wrong password"})
    
    if username not in user_groups:
        user_groups[username] = []
    
    if found_group not in user_groups[username]:
        user_groups[username].append(found_group)
        write_user_groups(user_groups)
        
        if "members" not in groups[found_group]:
            groups[found_group]["members"] = []
        if username not in groups[found_group]["members"]:
            groups[found_group]["members"].append(username)
            write_groups(groups)
            
            return jsonify({
                "success": True,
                "group_id": found_group,
                "group_name": groups[found_group]["name"],
                "member_count": len(groups[found_group]["members"])
            })
        else:
            return jsonify({"success": False, "error": "Already a member"})
    else:
        return jsonify({"success": False, "error": "Already a member"})

@app.route("/messages/<path:group_id>")
def get_messages(group_id):
    messages = read_messages(group_id)
    return jsonify(messages)

@app.route("/upload", methods=["POST"])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"ok": False, "error": "No file"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"ok": False, "error": "No filename"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"ok": False, "error": "File type not allowed"}), 400
    
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_filename = str(uuid.uuid4()) + '.' + ext
    filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
    file.save(filepath)
    
    file_type = get_file_type(unique_filename)
    file_url = f"/uploads/{unique_filename}"
    
    return jsonify({
        "ok": True,
        "url": file_url,
        "type": file_type,
        "filename": unique_filename,
        "original_name": file.filename,
        "size": os.path.getsize(filepath)
    })

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ============================================================
# WEBSOCKET - REAL-TIME
# ============================================================

online_users = {}
room_users = {}
user_sessions = {}

@socketio.on('connect')
def handle_connect():
    print('✅ User connected')

@socketio.on('disconnect')
def handle_disconnect():
    for user_id, sid in user_sessions.items():
        if sid == request.sid:
            update_user_field(user_id, "is_online", False)
            update_user_field(user_id, "last_seen", time.time())
            
            if user_id in online_users:
                del online_users[user_id]
            if user_id in user_sessions:
                del user_sessions[user_id]
            
            emit('user_status_changed', {
                'user_id': user_id,
                'is_online': False,
                'last_seen': time.time()
            }, broadcast=True)
            break
    print('❌ User disconnected')

@socketio.on('join')
def handle_join(data):
    token = request.cookies.get('session_token')
    if not token:
        return
    
    user_id = validate_session(token)
    if not user_id:
        return
    
    username = data.get('username', '')
    group_id = data.get('group_id', '')
    
    user = get_user_by_id(user_id)
    if not user:
        return
    
    display_name = user.get("display_name", username)
    badge = user.get("badge", "")
    badge_color = user.get("badge_color", "")
    
    user_sessions[user_id] = request.sid
    online_users[user_id] = {
        'sid': request.sid,
        'group_id': group_id,
        'username': username,
        'display_name': display_name,
        'badge': badge,
        'badge_color': badge_color
    }
    
    update_user_field(user_id, "is_online", True)
    
    if group_id not in room_users:
        room_users[group_id] = []
    if user_id not in room_users[group_id]:
        room_users[group_id].append(user_id)
    
    join_room(group_id)
    
    emit('user_joined', {
        'user_id': user_id,
        'username': username,
        'display_name': display_name,
        'badge': badge,
        'badge_color': badge_color,
        'online_count': len(room_users[group_id]),
        'online_users': room_users[group_id]
    }, room=group_id, broadcast=True)
    
    all_messages = read_messages()
    group_messages = [msg for msg in all_messages if msg.get('group_id') == group_id]
    emit('load_messages', group_messages)
    
    print(f'👤 {username} (ID: {user_id}) joined {group_id}')

@socketio.on('leave')
def handle_leave(data):
    token = request.cookies.get('session_token')
    if not token:
        return
    
    user_id = validate_session(token)
    if not user_id:
        return
    
    group_id = data.get('group_id', '')
    
    if user_id in online_users:
        del online_users[user_id]
    if group_id in room_users and user_id in room_users[group_id]:
        room_users[group_id].remove(user_id)
    
    update_user_field(user_id, "is_online", False)
    update_user_field(user_id, "last_seen", time.time())
    
    emit('user_left', {
        'user_id': user_id,
        'online_count': len(room_users.get(group_id, []))
    }, room=group_id, broadcast=True)
    
    leave_room(group_id)

@socketio.on('send_message')
def handle_send_message(data):
    token = request.cookies.get('session_token')
    if not token:
        return
    
    user_id = validate_session(token)
    if not user_id:
        return
    
    user = get_user_by_id(user_id)
    if not user:
        return
    
    username = user.get("username")
    display_name = user.get("display_name", username)
    badge = user.get("badge", "")
    badge_color = user.get("badge_color", "")
    
    text = data.get('text', '').strip()
    time_str = data.get('time', '').strip()
    file_url = data.get('file_url', '')
    file_type = data.get('file_type', '')
    file_name = data.get('file_name', '')
    file_size = data.get('file_size', 0)
    duration = data.get('duration', 0)
    reply_to = data.get('reply_to', '')
    group_id = data.get('group_id', '')
    is_gift = data.get('is_gift', False)

    if not text and not file_url:
        return

    messages = read_messages()
    
    reply_info = None
    if reply_to:
        for msg in messages:
            if msg.get('id') == reply_to:
                reply_info = {
                    'username': msg.get('username'),
                    'text': (msg.get('text') or '[Media]')[:50],
                    'file_type': msg.get('file_type')
                }
                break
    
    new_message = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "username": username,
        "display_name": display_name,
        "badge": badge,
        "badge_color": badge_color,
        "text": text,
        "time": time_str,
        "file_url": file_url,
        "file_type": file_type,
        "file_name": file_name,
        "file_size": file_size,
        "duration": duration,
        "reply_to": reply_to,
        "reply_info": reply_info,
        "group_id": group_id,
        "timestamp": time.time(),
        "is_gift": is_gift
    }
    
    messages.append(new_message)
    messages.sort(key=lambda x: x.get('timestamp', 0))
    write_messages(messages)

    emit('receive_message', new_message, room=group_id, broadcast=True)

@socketio.on('typing')
def handle_typing(data):
    token = request.cookies.get('session_token')
    if not token:
        return
    
    user_id = validate_session(token)
    if not user_id:
        return
    
    user = get_user_by_id(user_id)
    if not user:
        return
    
    username = user.get("username")
    display_name = user.get("display_name", username)
    is_typing = data.get('is_typing', False)
    group_id = data.get('group_id', '')
    
    emit('user_typing', {
        'user_id': user_id,
        'username': username,
        'display_name': display_name,
        'is_typing': is_typing
    }, room=group_id, broadcast=True, include_self=False)

@socketio.on('delete_messages')
def handle_delete_messages(data):
    token = request.cookies.get('session_token')
    if not token:
        return
    
    user_id = validate_session(token)
    if not user_id:
        return
    
    user = get_user_by_id(user_id)
    if not user:
        return
    
    message_ids = data.get('message_ids', [])
    group_id = data.get('group_id', '')
    username = user.get("username")
    
    if not message_ids:
        return
    
    messages = read_messages()
    remaining_messages = []
    
    for msg in messages:
        if msg.get('id') in message_ids:
            if msg.get('file_url'):
                filepath = os.path.join(UPLOAD_FOLDER, os.path.basename(msg['file_url']))
                if os.path.exists(filepath):
                    os.remove(filepath)
        else:
            remaining_messages.append(msg)
    
    write_messages(remaining_messages)
    
    emit('messages_deleted', {
        'message_ids': message_ids,
        'deleted_by': username
    }, room=group_id, broadcast=True)

@socketio.on('edit_message')
def handle_edit_message(data):
    token = request.cookies.get('session_token')
    if not token:
        return
    
    user_id = validate_session(token)
    if not user_id:
        return
    
    user = get_user_by_id(user_id)
    if not user:
        return
    
    message_id = data.get('message_id')
    new_text = data.get('new_text', '').strip()
    group_id = data.get('group_id', '')
    username = user.get("username")
    
    if not message_id or not new_text:
        return
    
    messages = read_messages()
    
    for msg in messages:
        if msg.get('id') == message_id and msg.get('user_id') == user_id:
            msg['text'] = new_text
            msg['edited'] = True
            msg['edited_time'] = datetime.now().strftime("%H:%M")
            write_messages(messages)
            
            emit('message_edited', {
                'message_id': message_id,
                'new_text': new_text,
                'edited_time': msg['edited_time'],
                'username': username
            }, room=group_id, broadcast=True)
            break

@socketio.on('message_seen')
def handle_message_seen(data):
    token = request.cookies.get('session_token')
    if not token:
        return
    
    user_id = validate_session(token)
    if not user_id:
        return
    
    user = get_user_by_id(user_id)
    if not user:
        return
    
    message_id = data.get('message_id')
    group_id = data.get('group_id')
    
    if not message_id or not group_id:
        return
    
    emit('message_seen_by', {
        'message_id': message_id,
        'user_id': user_id,
        'username': user.get("username")
    }, room=group_id, broadcast=True, include_self=False)

# ============================================================
# Socket Events برای Badge
# ============================================================

@socketio.on('badge_update')
def handle_badge_update(data):
    token = request.cookies.get('session_token')
    if not token:
        return
    
    user_id = validate_session(token)
    if not user_id:
        return
    
    user = get_user_by_id(user_id)
    if not user:
        return
    
    if user.get("username") != "Apex":
        emit('badge_update_error', {'error': 'Only Apex can manage badges'})
        return
    
    target_username = data.get('target_username')
    badge = data.get('badge', '').strip().upper()
    badge_color = data.get('badge_color', '').strip()
    
    if not target_username:
        return
    
    target_user = get_user_by_username(target_username)
    if not target_user:
        emit('badge_update_error', {'error': 'User not found'})
        return
    
    target_user_id = target_user.get("user_id")
    update_user_badge(target_user_id, badge=badge, badge_color=badge_color)
    
    emit('user_badge_updated', {
        'username': target_username,
        'badge': badge,
        'badge_color': badge_color
    }, broadcast=True)

# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Tot Messenger running on Render")
    print(f"📁 Data stored in: {DATA_FOLDER}")
    print("=" * 50)
    ensure_users_file()
    ensure_groups_file()
    ensure_user_groups_file()
    ensure_messages_file()
    
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, debug=False, host='0.0.0.0', port=port)