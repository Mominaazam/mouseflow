# MouseFlowPractice/app.py
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import datetime, os, pytz
import json
import cv2
import numpy as np
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

app = Flask(__name__, static_folder='static', template_folder='templates')
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'db.sqlite3')
db = SQLAlchemy(app)
CORS(app)

PKT = pytz.timezone('Asia/Karachi')

# MODELS
class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(100))
    user_agent = db.Column(db.String(255))
    url = db.Column(db.String(500), nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.datetime.now(PKT))
    events = db.relationship('Event', backref='session', lazy=True, cascade="all, delete-orphan")

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'), nullable=False)
    event_type = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=lambda: datetime.datetime.now(PKT))
    x = db.Column(db.Integer, nullable=True)
    y = db.Column(db.Integer, nullable=True)
    additional_data = db.Column(db.Text, nullable=True)

# ROUTES
@app.route('/collect', methods=['POST'])
def collect():
    data = request.get_json()
    user_agent = request.headers.get('User-Agent', '')
    if 'MOUSE_FLOW_VIDEO_GENERATION' in user_agent:
        return jsonify({'status': 'ignored', 'reason': 'video_generation'})
    url = data.get('url') or request.headers.get('Referer') or request.args.get('url') or 'unknown'
    session = Session(
        ip_address=request.remote_addr, 
        user_agent=request.headers.get('User-Agent'),
        url=url
    )
    db.session.add(session)
    db.session.flush()
    for evt in data.get('events', []):
        event = Event(
            session_id=session.id,
            event_type=evt['type'],
            timestamp=datetime.datetime.fromtimestamp(evt['timestamp'] / 1000.0, tz=PKT),
            x=evt.get('x'),
            y=evt.get('y'),
            additional_data=evt.get('data')
        )
        db.session.add(event)
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/sessions', methods=['GET'])
def list_sessions():
    sessions = Session.query.order_by(Session.timestamp.desc()).all()
    sessions_data = []
    for session in sessions:
        click_count = sum(1 for e in session.events if e.event_type == 'click')
        move_count = sum(1 for e in session.events if e.event_type == 'mousemove')
        total_events = len(session.events)
        move_percentage = round((move_count / total_events * 100) if total_events > 0 else 0, 1)
        scroll_percents = []
        for e in session.events:
            if e.event_type == 'scroll':
                try:
                    percent = float(e.y) if e.y is not None else 0
                    scroll_percents.append(percent)
                except Exception:
                    pass
        max_scroll_percent = min(max(scroll_percents) if scroll_percents else 0, 100)
        video_path = None
        video_file_mp4 = os.path.join('static', 'videos', f'session_{session.id}.mp4')
        video_file_simple_mp4 = os.path.join('static', 'videos', f'session_{session.id}_simple.mp4')
        video_file_real_browser_mp4 = os.path.join('static', 'videos', f'session_{session.id}_real_browser.mp4')
        if os.path.exists(video_file_mp4):
            video_path = f'/static/videos/session_{session.id}.mp4'
        elif os.path.exists(video_file_simple_mp4):
            video_path = f'/static/videos/session_{session.id}_simple.mp4'
        elif os.path.exists(video_file_real_browser_mp4):
            video_path = f'/static/videos/session_{session.id}_real_browser.mp4'
        try:
            session_url = session.url if hasattr(session, 'url') else 'unknown'
        except:
            session_url = 'unknown'
        sessions_data.append({
            'id': session.id,
            'timestamp': session.timestamp,
            'ip_address': session.ip_address,
            'user_agent': session.user_agent,
            'url': session_url,
            'clicks': click_count,
            'move_percentage': move_percentage,
            'scrolls': max_scroll_percent,
            'video_path': video_path
        })
    return render_template('dashboard.html', sessions=sessions_data)

@app.route('/session/<int:session_id>', methods=['GET'])
def get_session_data(session_id):
    session = Session.query.get_or_404(session_id)
    return jsonify({
        'session_id': session.id,
        'ip_address': session.ip_address,
        'timestamp': session.timestamp.isoformat(),
        'user_agent': session.user_agent,
        'events': [{
            'type': e.event_type,
            'timestamp': e.timestamp.isoformat(),
            'x': e.x,
            'y': e.y,
            'data': get_scroll_percentage(e) if e.event_type == 'scroll' else e.additional_data
        } for e in session.events]
    })

@app.route('/delete_session/<int:session_id>', methods=['DELETE'])
def delete_session(session_id):
    session = Session.query.get_or_404(session_id)
    db.session.delete(session)
    db.session.commit()
    for ext in ['.mp4']:
        video_path = os.path.join('static', 'videos', f'session_{session_id}{ext}')
        if os.path.exists(video_path):
            try:
                os.remove(video_path)
            except OSError:
                pass
        simple_video_path = os.path.join('static', 'videos', f'session_{session_id}_simple{ext}')
        if os.path.exists(simple_video_path):
            try:
                os.remove(simple_video_path)
            except OSError:
                pass
        real_browser_video_path = os.path.join('static', 'videos', f'session_{session_id}_real_browser{ext}')
        if os.path.exists(real_browser_video_path):
            try:
                os.remove(real_browser_video_path)
            except OSError:
                pass
    return jsonify({'status': 'deleted'}), 200

@app.route('/video/<int:session_id>')
def serve_video(session_id):
    video_dir = os.path.join('static', 'videos')
    for ext in ['.mp4']:
        video_path = os.path.join(video_dir, f'session_{session_id}{ext}')
        if os.path.exists(video_path):
            response = send_from_directory(video_dir, f'session_{session_id}{ext}')
            response.headers['Content-Type'] = 'video/mp4'
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Cache-Control'] = 'public, max-age=3600'
            return response
    for ext in ['.mp4']:
        video_path = os.path.join(video_dir, f'session_{session_id}_simple{ext}')
        if os.path.exists(video_path):
            response = send_from_directory(video_dir, f'session_{session_id}_simple{ext}')
            response.headers['Content-Type'] = 'video/mp4'
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Cache-Control'] = 'public, max-age=3600'
            return response
    for ext in ['.mp4']:
        video_path = os.path.join(video_dir, f'session_{session_id}_real_browser{ext}')
        if os.path.exists(video_path):
            response = send_from_directory(video_dir, f'session_{session_id}_real_browser{ext}')
            response.headers['Content-Type'] = 'video/mp4'
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Cache-Control'] = 'public, max-age=3600'
            return response
    return jsonify({'error': 'Video not found'}), 404

@app.route('/clear_sessions', methods=['DELETE'])
def clear_sessions():
    db.session.query(Event).delete()
    db.session.query(Session).delete()
    db.session.commit()
    video_dir = os.path.join('static', 'videos')
    for f in os.listdir(video_dir):
        if f.endswith(('.mp4', '.avi')):
            os.remove(os.path.join(video_dir, f))
    return jsonify({'status': 'cleared'}), 200

@app.route('/generate_video/<int:session_id>', methods=['POST'])
def generate_video(session_id):
    return generate_real_browser_video(session_id)

def get_scroll_percentage(event):
    try:
        data = json.loads(event.additional_data)
        scrollY = data.get('scrollY', 0)
        pageHeight = data.get('pageHeight', 1)
        percent = (scrollY / max(pageHeight, 1)) * 100
        return round(percent, 2)
    except Exception:
        return None

@app.route('/generate_real_browser_video/<int:session_id>', methods=['POST'])
def generate_real_browser_video(session_id):
    try:
        session = Session.query.get_or_404(session_id)
        events = sorted(session.events, key=lambda e: e.timestamp)
        if not events:
            return jsonify({'status': 'error', 'message': 'No events found for this session'}), 400
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1280,720")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 MOUSE_FLOW_VIDEO_GENERATION")
        chrome_options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_settings.popups": 0
        })
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        try:
            target_url = session.url if hasattr(session, 'url') and session.url and session.url != 'unknown' else 'https://example.com'
            driver.get(target_url)
            time.sleep(3)
            driver.set_window_size(1280, 720)
            page_width = driver.execute_script("return document.documentElement.scrollWidth")
            page_height = driver.execute_script("return document.documentElement.scrollHeight")
            frames = []
            fps = 15
            if len(events) > 1:
                first_time = events[0].timestamp
                last_time = events[-1].timestamp
                total_duration = (last_time - first_time).total_seconds()
                if total_duration < 0.1:
                    total_duration = max(0.5, len(events) * 0.1)
            else:
                total_duration = 1.0
            frame_interval = 1.0 / fps
            total_frames = int(total_duration * fps)
            event_timeline = []
            for i, evt in enumerate(events):
                event_time = (evt.timestamp - events[0].timestamp).total_seconds()
                event_timeline.append((event_time, evt, i))
            last_x, last_y = 0, 0
            mouse_trail = []
            max_trail_length = 30
            for frame_idx in range(total_frames):
                current_time = frame_idx * frame_interval
                current_event = None
                current_event_idx = -1
                for event_time, evt, evt_idx in event_timeline:
                    if event_time <= current_time:
                        current_event = evt
                        current_event_idx = evt_idx
                    else:
                        break
                if current_event:
                    try:
                        x, y = current_event.x or 0, current_event.y or 0
                        x = int(x) if x is not None else 0
                        y = int(y) if y is not None else 0
                        x = max(0, min(x, page_width - 1))
                        y = max(0, min(y, page_height - 1))
                        mouse_trail.append((x, y, current_event.event_type))
                        if len(mouse_trail) > max_trail_length:
                            mouse_trail.pop(0)
                        delta_x = x - last_x
                        delta_y = y - last_y
                        if current_event.event_type == 'mousemove':
                            actions = ActionChains(driver)
                            actions.move_by_offset(delta_x, delta_y)
                            actions.perform()
                            driver.execute_script(f"""
                                var event = new MouseEvent('mousemove', {{
                                    'view': window,
                                    'bubbles': true,
                                    'cancelable': true,
                                    'clientX': {x},
                                    'clientY': {y}
                                }});
                                var element = document.elementFromPoint({x}, {y});
                                if (element) {{
                                    element.dispatchEvent(event);
                                }}
                            """)
                            driver.execute_script(f"""
                                var element = document.elementFromPoint({x}, {y});
                                if (element) {{
                                    element.dispatchEvent(new MouseEvent('mouseenter', {{
                                        'view': window,
                                        'bubbles': true,
                                        'cancelable': true,
                                        'clientX': {x},
                                        'clientY': {y}
                                    }}));
                                }}
                            """)
                        elif current_event.event_type == 'click':
                            actions = ActionChains(driver)
                            actions.move_by_offset(delta_x, delta_y)
                            actions.click()
                            actions.perform()
                            driver.execute_script(f"""
                                var element = document.elementFromPoint({x}, {y});
                                if (element) {{
                                    var clickEvent = new MouseEvent('click', {{
                                        'view': window,
                                        'bubbles': true,
                                        'cancelable': true,
                                        'clientX': {x},
                                        'clientY': {y}
                                    }});
                                    element.dispatchEvent(clickEvent);
                                    element.dispatchEvent(new MouseEvent('mousedown', {{
                                        'view': window,
                                        'bubbles': true,
                                        'cancelable': true,
                                        'clientX': {x},
                                        'clientY': {y}
                                    }}));
                                    element.dispatchEvent(new MouseEvent('mouseup', {{
                                        'view': window,
                                        'bubbles': true,
                                        'cancelable': true,
                                        'clientX': {x},
                                        'clientY': {y}
                                    }}));
                                }}
                            """)
                        elif current_event.event_type == 'scroll':
                            try:
                                scroll_data = json.loads(current_event.additional_data) if current_event.additional_data else {}
                                scroll_y = scroll_data.get('scrollY', 0)
                                driver.execute_script(f"window.scrollTo(0, {scroll_y})")
                            except:
                                pass
                        last_x, last_y = x, y
                        time.sleep(0.05)
                    except Exception:
                        pass
                screenshot = driver.get_screenshot_as_png()
                screenshot_array = np.frombuffer(screenshot, dtype=np.uint8)
                frame = cv2.imdecode(screenshot_array, cv2.IMREAD_COLOR)
                if frame is None or frame.size == 0:
                    frame = np.ones((720, 1280, 3), dtype=np.uint8) * 255
                for j, (trail_x, trail_y, trail_type) in enumerate(mouse_trail[:-1]):
                    try:
                        trail_x = int(trail_x) if trail_x is not None else 0
                        trail_y = int(trail_y) if trail_y is not None else 0
                        if (trail_x >= 0 and trail_y >= 0 and trail_x < page_width and trail_y < page_height):
                            fade_factor = 1.0 - (j / len(mouse_trail))
                            alpha = max(0.1, fade_factor * 0.8)
                            if trail_type == 'click':
                                color = (int(255 * alpha), int(100 * alpha), int(100 * alpha))
                                radius = int(3 + 2 * alpha)
                            elif trail_type == 'scroll':
                                color = (int(100 * alpha), int(100 * alpha), int(255 * alpha))
                                radius = int(2 + 2 * alpha)
                            else:
                                color = (int(100 * alpha), int(255 * alpha), int(100 * alpha))
                                radius = int(2 + 1 * alpha)
                            cv2.circle(frame, (trail_x, trail_y), radius, color, -1)
                    except (ValueError, TypeError):
                        continue
                if current_event:
                    try:
                        x, y = current_event.x or 0, current_event.y or 0
                        x = int(x) if x is not None else 0
                        y = int(y) if y is not None else 0
                        x = max(0, min(x, page_width - 1))
                        y = max(0, min(y, page_height - 1))
                        if current_event.event_type == 'click':
                            cv2.circle(frame, (x, y), 15, (255, 255, 255), 4)
                            cv2.circle(frame, (x, y), 12, (0, 0, 255), -1)
                            cv2.circle(frame, (x, y), 8, (255, 255, 255), 2)
                            cv2.putText(frame, "CLICK", (x + 20, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                        elif current_event.event_type == 'mousemove':
                            cv2.circle(frame, (x, y), 12, (255, 255, 255), 3)
                            cv2.circle(frame, (x, y), 10, (0, 255, 0), -1)
                            cv2.circle(frame, (x, y), 6, (255, 255, 255), 2)
                        elif current_event.event_type == 'scroll':
                            cv2.circle(frame, (x, y), 12, (255, 255, 255), 3)
                            cv2.circle(frame, (x, y), 10, (255, 0, 0), -1)
                            cv2.circle(frame, (x, y), 6, (255, 255, 255), 2)
                            cv2.putText(frame, "SCROLL", (x + 20, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
                        cv2.arrowedLine(frame, (x - 15, y - 15), (x, y), (255, 255, 255), 2, tipLength=0.3)
                    except (ValueError, TypeError):
                        pass
                overlay = frame.copy()
                cv2.rectangle(overlay, (10, 10), (450, 100), (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
                cv2.putText(frame, f"Session Time: {current_time:.1f}s / {total_duration:.1f}s", 
                           (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                if current_event:
                    cv2.putText(frame, f"Event {current_event_idx + 1}/{len(events)}: {current_event.event_type}", 
                               (15, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    cv2.putText(frame, f"Event Time: {current_event.timestamp.strftime('%H:%M:%S.%f')[:-3]}", 
                               (15, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    x, y = current_event.x or 0, current_event.y or 0
                    cv2.putText(frame, f"Position: ({x}, {y})", 
                               (15, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                else:
                    cv2.putText(frame, "Waiting for next event...", 
                               (15, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                frames.append(frame)
                time.sleep(frame_interval)
            if not frames:
                screenshot = driver.get_screenshot_as_png()
                screenshot_array = np.frombuffer(screenshot, dtype=np.uint8)
                frame = cv2.imdecode(screenshot_array, cv2.IMREAD_COLOR)
                frames.append(frame)
        finally:
            driver.quit()
        video_dir = os.path.join('static', 'videos')
        os.makedirs(video_dir, exist_ok=True)
        if frames:
            height, width = frames[0].shape[:2]
            codecs_to_try = [
                ('XVID', '.mp4'),
                ('MJPG', '.mp4'),
                ('mp4v', '.mp4'),
                ('avc1', '.mp4'),
                ('H264', '.mp4')
            ]
            out_path = None
            fourcc = None
            selected_codec = None
            for codec, ext in codecs_to_try:
                try:
                    test_path = os.path.join(video_dir, f'test_real_browser_{session_id}{ext}')
                    fourcc = cv2.VideoWriter_fourcc(*codec)
                    test_writer = cv2.VideoWriter(test_path, fourcc, fps, (width, height))
                    if test_writer.isOpened():
                        test_writer.release()
                        os.remove(test_path)
                        out_path = os.path.join(video_dir, f'session_{session_id}_real_browser{ext}')
                        selected_codec = codec
                        break
                except Exception:
                    continue
            if out_path is None:
                raise Exception("No compatible video codec found")
            out = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
            if not out.isOpened():
                raise Exception("Failed to create video writer")
            for i, frame in enumerate(frames):
                out.write(frame)
            out.release()
            if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
                raise Exception("Real browser video file was not created or is empty")
            video_path = f'/static/videos/session_{session_id}_real_browser{os.path.splitext(out_path)[1]}'
        else:
            raise Exception("No frames captured")
        return jsonify({
            'status': 'video_generated',
            'session_id': session_id,
            'video_path': video_path,
            'type': 'real_browser',
            'video_duration_seconds': total_frames / fps,
            'session_duration_seconds': total_duration
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to generate real browser video: {str(e)}'}), 500

@app.route('/recreate_db')
def recreate_db():
    try:
        db.drop_all()
        db.create_all()
        return '''
        <!DOCTYPE html>
        <html>
        <head><title>Database Recreated</title></head>
        <body>
            <h1>Database Recreated Successfully</h1>
            <p>The database has been recreated with the new schema including the URL field.</p>
            <p><a href="/sessions">Go to Sessions</a></p>
        </body>
        </html>
        '''
    except Exception as e:
        return f'''
        <!DOCTYPE html>
        <html>
        <head><title>Error</title></head>
        <body>
            <h1>Error Recreating Database</h1>
            <p>Error: {str(e)}</p>
            <p>Try stopping the Flask app and deleting db.sqlite3 manually, then restart.</p>
        </body>
        </html>
        '''

if __name__ == '__main__':
    os.makedirs('static', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/videos', exist_ok=True)
    with app.app_context():
        db.create_all()
    app.run(debug=True)
