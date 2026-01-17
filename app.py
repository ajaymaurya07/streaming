import cv2
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request

app = FastAPI()

templates = Jinja2Templates(directory="templates")  # html folder path

# camera configuration
cameras = {
    # 1: cv2.VideoCapture("http://10.14.14.186:4747/video") # 1 is camera id for phone camera
    1: cv2.VideoCapture("rtsp://username:password@CAMERA_IP:554/stream1") # for cctv camera
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
