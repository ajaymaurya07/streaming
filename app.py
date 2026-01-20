import threading
import cv2
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
import time


app = FastAPI()
recording = False
writers = {}
start_time = None
record_thread = None

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
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')  #Browser ko continuous images bhejne ke liye

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
    global recording, record_thread

    if recording:
        return {"status": "Already recording"}

    recording = True

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
    return {"status": "Recording stopped & saved"}
