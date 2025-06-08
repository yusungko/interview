# 完整 Flask + MySQL + SocketIO 聊天系統（展示版本）

from flask import Flask, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:881125@localhost/interview'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_TYPE'] = 'filesystem'

socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)
db = SQLAlchemy(app)

# --- 資料表模型 ---
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    current_room = db.Column(db.String(100))

class ChatRoom(db.Model):
    __tablename__ = 'chat_rooms'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class ChatRoomMember(db.Model):
    __tablename__ = 'chat_room_members'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    room_name = db.Column(db.String(100))
    username = db.Column(db.String(100))

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    room_name = db.Column(db.String(100))
    username = db.Column(db.String(100))
    content = db.Column(db.Text)

# --- 註冊 ---
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    print("🚀 register 收到資料：", data)
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Missing username or password'}), 400
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username exists'}), 400
    new_user = User(username=data['username'],
                    password_hash=generate_password_hash(data['password']))
    db.session.add(new_user)
    db.session.commit()
    print("✅ 註冊成功")
    return jsonify({'message': 'User registered'}), 200

# --- 登入 ---
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(username=data['username']).first()
    if user and check_password_hash(user.password_hash, data['password']):
        session['username'] = user.username
        return jsonify({'message': 'Login successful'}), 200
    return jsonify({'error': 'Invalid credentials'}), 401

# --- 建立聊天室 ---
@app.route('/chatrooms/create', methods=['POST'])
def create_chatroom():
    data = request.json
    if ChatRoom.query.filter_by(name=data['room_name']).first():
        return jsonify({'error': 'Room exists'}), 400
    room = ChatRoom(name=data['room_name'])
    db.session.add(room)
    db.session.commit()
    return jsonify({'message': 'Room created'}), 200

# --- 加入聊天室 ---
@app.route('/chatrooms/enter', methods=['POST'])
def enter_room():
    username = session.get('username')
    room_name = request.json['room_name']
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'Not logged in'}), 401
    user.current_room = room_name
    db.session.add(ChatRoomMember(room_name=room_name, username=username))
    db.session.commit()
    return jsonify({'message': 'Entered room'}), 200

# --- 離開聊天室 ---
@app.route('/chatrooms/exit', methods=['POST'])
def exit_room():
    username = session.get('username')
    user = User.query.filter_by(username=username).first()
    if user:
        room = user.current_room
        user.current_room = None
        db.session.query(ChatRoomMember).filter_by(room_name=room, username=username).delete()
        db.session.commit()
    return jsonify({'message': 'Exited room'}), 200

# --- 查聊天室成員 ---
@app.route('/chatrooms/members/<room_name>', methods=['GET'])
def room_members(room_name):
    members = ChatRoomMember.query.filter_by(room_name=room_name).all()
    return jsonify([m.username for m in members]), 200

# --- 查所有使用者 ---
@app.route('/users', methods=['GET'])
def users_with_rooms():
    users = User.query.all()
    return jsonify([
        {'username': u.username, 'room': u.current_room}
        for u in users
    ])

# --- 查聊天室歷史訊息 ---
@app.route('/chatrooms/messages/<room_name>', methods=['GET'])
def get_messages(room_name):
    messages = Message.query.filter_by(room_name=room_name).all()
    return jsonify([
        {'username': m.username, 'msg': m.content} for m in messages
    ])

# --- SocketIO 事件 ---
@socketio.on('join')
def handle_join(data):
    username = data['username']
    room = data['room']
    join_room(room)
    emit('message', {'msg': f'{username} joined room {room}'}, to=room)

@socketio.on('message')
def handle_message(data):
    room = data['room']
    username = data['username']
    content = data['msg']
    db.session.add(Message(room_name=room, username=username, content=content))
    db.session.commit()
    emit('message', {'username': username, 'msg': content}, to=room)

@socketio.on('leave')
def handle_leave(data):
    username = data['username']
    room = data['room']
    leave_room(room)
    emit('message', {'msg': f'{username} left room'}, to=room)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True)
