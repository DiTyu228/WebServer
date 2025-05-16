from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import random
import uuid
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'avi', 'mov', 'mkv'}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Создаем папку для загрузок, если она не существует
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

"""
class VideoView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    session_id = db.Column(db.String(36), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    progress = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
"""


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    videos = db.relationship('Video', backref='author', lazy=True)


# Модифицируем модель Video
class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=False)  # Новое поле: описание
    filename = db.Column(db.String(100), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    views = db.Column(db.Integer, default=0)  # Счетчик просмотров
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comments = db.relationship('Comment', backref='video', lazy=True)
    reactions = db.relationship('Reaction', backref='video', lazy=True)
    duration = db.Column(db.Float)
    view_threshold = db.Column(db.Float, default=0.7)


session = {}


@app.before_request
def make_session_id():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    text = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    author = db.Column(db.Text, nullable=False)


class Reaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reaction_type = db.Column(db.String(10), nullable=False)  # 'like' или 'dislike'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.route('/')
def index():
    # Простая рекомендательная система: случайные 5 видео
    all_videos = Video.query.all()
    recommended = random.sample(all_videos, min(5, len(all_videos))) if all_videos else []
    return render_template('index.html', videos=recommended)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        if User.query.filter_by(username=username).first():
            return 'Username already exists!'

        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))

        return 'Invalid username or password'

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        title = request.form['title']
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            description = request.form['description']
            # ... остальная часть загрузки файла
            new_video = Video(title=title,
                              description=description,
                              filename=filename,
                              author=current_user)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            db.session.add(new_video)
            db.session.commit()

            return redirect(url_for('index'))

        return 'Invalid file type'

    return render_template('upload.html')


@app.route('/watch/<int:video_id>', methods=['GET', 'POST'])
def watch(video_id):
    video = Video.query.get_or_404(video_id)
    all_videos = Video.query.all()
    random_videos = random.sample(all_videos, min(5, len(all_videos))) if all_videos else []
    # Увеличиваем счетчик просмотров
    if current_user.is_authenticated:
        video.views += 1
    db.session.commit()

    # Обработка комментариев
    if request.method == 'POST' and current_user.is_authenticated:
        # Обработка комментария

        if 'comment' in request.form:
            comment_text = request.form['comment']
            try:
                print(current_user.username)
                print(video.views)
            except:
                print("not pass")
            new_comment = Comment(
                                  id=0,
                                  text=comment_text,
                                  user_id=current_user.id,
                                  author=f"{current_user.username}",
                                  video_id=video.id)
            db.session.add(new_comment)

        # Обработка реакций
        elif 'reaction' in request.form:
            reaction_type = request.form['reaction']
            # Проверяем существующую реакцию
            existing_reaction = Reaction.query.filter_by(
                user_id=current_user.id,
                video_id=video.id
            ).first()

            if existing_reaction:
                if existing_reaction.reaction_type == reaction_type:
                    # Удаляем реакцию если повторно нажали
                    db.session.delete(existing_reaction)
                else:
                    # Меняем тип реакции
                    existing_reaction.reaction_type = reaction_type
            else:
                new_reaction = Reaction(
                    reaction_type=reaction_type,
                    user_id=current_user.id,
                    video_id=video.id
                )
                db.session.add(new_reaction)

        db.session.commit()
        return redirect(url_for('watch', video_id=video_id))

    # Получаем статистику реакций
    likes_count = Reaction.query.filter_by(video_id=video.id, reaction_type='like').count()
    dislikes_count = Reaction.query.filter_by(video_id=video.id, reaction_type='dislike').count()

    return render_template('watch.html',
                           video=video,
                           comments=video.comments,
                           likes=likes_count,
                           dislikes=dislikes_count)


"""@app.route('/track_progress', methods=['POST'])
def track_progress():
    data = request.get_json()
    video_id = data['video_id']
    current_time = float(data['current_time'])
    duration = float(data['duration'])

    # Получаем идентификаторы
    user_id = current_user.id if current_user.is_authenticated else None
    session_id = request.cookies.get('session_id', str(uuid.uuid4()))

    # Рассчитываем прогресс
    progress = current_time / duration if duration > 0 else 0
    video = Video.query.get(video_id)

    # Проверяем порог просмотра
    if progress >= video.view_threshold:
        # Проверяем существующий просмотр
        view_exists = VideoView.query.filter(
            (VideoView.user_id == user_id) |
            (VideoView.session_id == session_id),
            VideoView.video_id == video_id
        ).first()

        if not view_exists:
            new_view = VideoView(
                user_id=user_id,
                session_id=session_id,
                video_id=video_id,
                progress=progress
            )
            db.session.add(new_view)
            # Обновляем счетчик просмотров
            video.views = VideoView.query.filter_by(video_id=video_id).count()
            db.session.commit()

    response = jsonify({'status': 'ok'})
    response.set_cookie('session_id', session_id, max_age=60 * 60 * 24 * 30)
    return response
"""


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
