import threading
import cv2
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
import time


app = FastAPI()
recording = False
writers = {}
start_time = None
record_thread = None
current_order = None

templates = Jinja2Templates(directory="templates")  # html folder path

# camera configuration
# 1: cv2.VideoCapture("rtsp://username:password@CAMERA_IP:554/stream1") # for cctv camera
# 1: cv2.VideoCapture("http://10.14.14.186:4747/video"), # 1 is camera id for phone camera rtsp procal no


cameras = {
    1: cv2.VideoCapture(0) # for pc camera
}


def gen_frames(camera_id):
    camera = cameras.get(camera_id)
    while True:
        success, frame = camera.read()
        if not success:
            break
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')  #Browser ko continuous images bend ke lie

@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/video_feed/{camera_id}")
def video_feed(camera_id: int):
    return StreamingResponse(gen_frames(camera_id),
            media_type="multipart/x-mixed-replace; boundary=frame")






# Recording thread
def record_all_cameras(order_id):
    global recording

    recording = True

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')

    for cam_id, cam in cameras.items():
        writers[cam_id] = cv2.VideoWriter(
            f"record_{order_id}_cam{cam_id}.mp4",
            fourcc,
            20.0,
            (640, 480)
        )

    while recording:
        for cam_id, cam in cameras.items():

            if cam is None:
                continue

            ret, frame = cam.read()
            if ret and cam_id in writers:
                writers[cam_id].write(frame)

    # Release after stop
    for w in writers.values():
        w.release()
    writers.clear()





# START recording API
@app.post("/start/{order_id}")
def start_recording(order_id: str):
    global recording, record_thread, current_order

    if recording:
        return {"status": "Already recording"}

    recording = True
    current_order = order_id

    record_thread = threading.Thread(
        target=record_all_cameras,
        args=(order_id,),
        daemon=True
    )
    record_thread.start()

    return {
        "status": "Recording started",
        "order": order_id
    }




# STOP recording API
@app.post("/stop")
def stop_recording():
    global recording, writers

    if not recording:
        return {"status": "Recording already stopped"}

    recording = False   # Thread safely exit
    time.sleep(1)  # thread ko exit hone ka time

    for cam_id, w in writers.items():
        try:
            w.release()
        except:
            pass
    writers.clear()

    # PROCESS
    clips = process_all_cameras(current_order, [1])

    final_video = f"final_highlight_{current_order}.mp4"
    merge_clips_opencv(clips, final_video)
    return {"status": "Recording stopped & saved"}


def detect_key_moments(video_path, top_k=6):

    cap = cv2.VideoCapture(video_path)

    prev = None
    motion_scores = []
    frame_no = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if prev is not None:
            diff = cv2.absdiff(prev, gray)
            score = diff.sum()
            motion_scores.append((frame_no, score))

        prev = gray
        frame_no += 1

    cap.release()

    motion_scores.sort(key=lambda x: x[1], reverse=True)

    return motion_scores[:top_k]



def frame_to_time(frame_no, fps):
    return frame_no / fps



def extract_clip_opencv(video, start_sec, duration, out):

    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS)

    start_frame = int(start_sec * fps)
    end_frame = int((start_sec + duration) * fps)

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    ret, frame = cap.read()
    if not ret:
        cap.release()
        return

    h, w, _ = frame.shape
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(out, fourcc, fps, (w, h))

    frame_no = start_frame

    while frame_no <= end_frame:
        ret, frame = cap.read()
        if not ret:
            break

        writer.write(frame)
        frame_no += 1

    cap.release()
    writer.release()



def process_all_cameras(order, camera_ids=[1]):

    clips = []

    for cam in camera_ids:

        video = f"record_{order}_cam{cam}.mp4"

        moments = detect_key_moments(video)

        cap = cv2.VideoCapture(video)
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()

        for i,(frame,_) in enumerate(moments[:3]): # best moment 3 every camera recording

            start = frame_to_time(frame,fps)
            out = f"clip_cam{cam}_{i}.mp4"

            extract_clip_opencv(video,start,4,out)
            clips.append(out)

    return clips



def merge_clips_opencv(clips, output):

    if len(clips) == 0:
        print("No clips to merge")
        return

    first = cv2.VideoCapture(clips[0])
    fps = first.get(cv2.CAP_PROP_FPS)

    ret, frame = first.read()
    if not ret:
        return

    h, w, _ = frame.shape
    first.release()

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(output, fourcc, fps, (w, h))

    for clip in clips:

        cap = cv2.VideoCapture(clip)

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            writer.write(frame)

        cap.release()

    writer.release()
