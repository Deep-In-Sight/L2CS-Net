import argparse
import os 
import cv2
import time

import torch
import torch.nn as nn
from torch.autograd import Variable
from torchvision import transforms
import torch.backends.cudnn as cudnn
import torchvision

from PIL import Image
from l2cs.utils import select_device
from PIL import Image

from face_detection import RetinaFace
from l2cs.model import L2CS

from l2cs.loader import FileVideoStream
import threading

torch.set_num_threads(4)

class VideoCaptureTreading:
    def __init__(self, src=0, width=640, height=480):
        self.src = src
        self.cap = cv2.VideoCapture(self.src)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.grabbed, self.frame = self.cap.read()
        self.started = False
        self.read_lock = threading.Lock()

    def set(self, var1, var2):
        self.cap.set(var1, var2)

    def start(self):
        if self.started:
            print('[!] Threaded video capturing has already been started.')
            return None
        self.started = True
        self.thread = threading.Thread(target=self.update, args=())
        self.thread.start()
        return self

    def update(self):
        while self.started:
            grabbed, frame = self.cap.read()
            if not grabbed:
                self.started = False
            with self.read_lock:
                self.grabbed = grabbed
                self.frame = frame

    def read(self):
        with self.read_lock:
            frame = self.frame.copy()
            grabbed = self.grabbed
        return grabbed, frame

    def stop(self):
        self.started = False
        self.thread.join()

    def __exit__(self, exec_type, exc_value, traceback):
        self.cap.release()

def parse_args():
    """Parse input arguments."""
    parser = argparse.ArgumentParser(
        description='Gaze evalution using model pretrained with L2CS-Net on Gaze360.')
    parser.add_argument(
        '--gpu',dest='gpu_id', help='GPU device id to use [0]',
        default="0", type=str)
    parser.add_argument(
        '--snapshot',dest='snapshot', help='Path of model snapshot.', 
        default='models/Gaze360/L2CSNet_gaze360.pkl', type=str)
    parser.add_argument(
        '--vids',dest='fn_vids', help='video file',  
        default="1122.txt", type=str)
    parser.add_argument(
        '--arch',dest='arch',help='Network architecture, can be: ResNet18, ResNet34, ResNet50, ResNet101, ResNet152',
        default='ResNet50', type=str)

    args = parser.parse_args()
    return args

def getArch(arch,bins):
    # Base network structure
    if arch == 'ResNet18':
        model = L2CS( torchvision.models.resnet.BasicBlock,[2, 2,  2, 2], bins)
    elif arch == 'ResNet34':
        model = L2CS( torchvision.models.resnet.BasicBlock,[3, 4,  6, 3], bins)
    elif arch == 'ResNet101':
        model = L2CS( torchvision.models.resnet.Bottleneck,[3, 4, 23, 3], bins)
    elif arch == 'ResNet152':
        model = L2CS( torchvision.models.resnet.Bottleneck,[3, 8, 36, 3], bins)
    else:
        if arch != 'ResNet50':
            print('Invalid value for architecture is passed! '
                'The default value of ResNet50 will be used instead!')
        model = L2CS( torchvision.models.resnet.Bottleneck, [3, 4, 6,  3], bins)
    return model


def dump_pitch_yaw(fn, model):
    # print("fn", fn)
    cap = FileVideoStream(fn).start()
    time.sleep(0.1)
    #cap = cv2.VideoCapture(fn)

    out_dir = "/".join(fn.split("/")[:-2])
    out_dir += "/rpy/"
    # print("outdir", out_dir)
    if not os.path.isdir(out_dir):
        os.mkdir(out_dir)

    fnfn = fn.split("/")[-1].replace(".mp4", ".txt").replace("_rgb_", "_rpy_")

    # Check if the webcam is opened correctly
    #if not cap.isOpened():
    #    raise IOError("Cannot open webcam")

    with torch.no_grad():
        with open(out_dir + fnfn, "w") as f:
            f.write("_py in degrees\n")
            start_fps = time.time()

            i = 0
            while cap.more():
                frame = cap.read()
                if frame is None:
                    break
                #if not success: break

                faces = detector(frame)
                if faces is not None: 
                    #cap.stop()
                    #return faces
                    #i_face = 0
                    ind = np.argmax([fc[2] for fc in faces])
                    #for box, landmarks, score in faces:
                    box, landmarks, score = faces[ind]
                    if score < .95:
                        continue
                    # i_face += 1
                    # if i_face > 1:
                    #     print(i, i_face, len(faces), score)
                
                    x_min=int(max([0, box[0]]))
                    y_min=int(max([0, box[1]]))
                    #if x_min < 0:
                    #    x_min = 0
                    #y_min=int(box[1])
                    #if y_min < 0:
                    #    y_min = 0
                    x_max=int(box[2])
                    y_max=int(box[3])
                    #bbox_width = x_max - x_min
                    #bbox_height = y_max - y_min
                    # x_min = max(0,x_min-int(0.2*bbox_height))
                    # y_min = max(0,y_min-int(0.2*bbox_width))
                    # x_max = x_max+int(0.2*bbox_height)
                    # y_max = y_max+int(0.2*bbox_width)
                    # bbox_width = x_max - x_min
                    # bbox_height = y_max - y_min

                    # Crop image
                    img = frame[y_min:y_max, x_min:x_max]
                    img = cv2.resize(img, (224, 224))
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    im_pil = Image.fromarray(img)
                    img=transformations(im_pil)
                    img  = Variable(img).cuda(gpu)
                    img  = img.unsqueeze(0) 
                    
                    # gaze prediction
                    gaze_pitch, gaze_yaw = model(img)
                    
                    pitch_predicted = softmax(gaze_pitch)
                    yaw_predicted = softmax(gaze_yaw)
                    
                    # Get continuous predictions in degrees.
                    pitch_predicted = torch.sum(pitch_predicted.data[0] * idx_tensor) * 4 - 180
                    yaw_predicted = torch.sum(yaw_predicted.data[0] * idx_tensor) * 4 - 180
                    
                    pitch_predicted= pitch_predicted.cpu().detach().numpy()#* np.pi/180.0
                    yaw_predicted= yaw_predicted.cpu().detach().numpy()#* np.pi/180.0

                    #print(pitch_predicted,yaw_predicted)
                    f.write(f"{pitch_predicted:.3f}   {yaw_predicted:.3f}")
                    f.write(f"  {box[0]:.3f}   {box[1]:.3f}   {box[2]:.3f}   {box[3]:.3f}")
                    for lr in landmarks.ravel():
                        f.write(f"  {lr:.3f}")
                    f.write(f"  {score:.2f}\n")
                    i +=1
                    #draw_gaze(x_min,y_min,bbox_width, bbox_height,frame,(pitch_predicted,yaw_predicted),color=(0,0,255))
                    #cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (0,255,0), 1)
                #myFPS = 1.0 / (time.time() - start_fps)
                #print("FPS:", myFPS)
                #cv2.putText(frame, 'FPS: {:.1f}'.format(myFPS), (10, 20),cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (0, 255, 0), 1, cv2.LINE_AA)

                #cv2.imshow("Demo",frame)
                #if cv2.waitKey(1) & 0xFF == 27:
                #    break
                #success,frame = cap.read()
            myFPS = 300.0 / (time.time() - start_fps)
            print("FPS:", myFPS)
        #print("Video getter", cap.cnt)
        cap.stop()
    
    print(f"Wrote {i} lines")
        
if __name__ == '__main__':
    args = parse_args()

    cudnn.enabled = True
    arch=args.arch
    batch_size = 1
    fn_vids = args.fn_vids
    gpu = select_device(args.gpu_id, batch_size=batch_size)
    snapshot_path = args.snapshot

    transformations = transforms.Compose([
        transforms.Resize(448),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        )
    ])
    
    model=getArch(arch, 90)
    print('Loading snapshot.')
    saved_state_dict = torch.load(snapshot_path)
    model.load_state_dict(saved_state_dict)
    model.cuda(gpu)
    model.eval()


    softmax = nn.Softmax(dim=1)
    detector = RetinaFace(gpu_id=0)
    idx_tensor = [idx for idx in range(90)]
    idx_tensor = torch.FloatTensor(idx_tensor).cuda(gpu)
    #x=0

    with open(fn_vids, "r") as f:
        ll = f.read()
        vid_list = ll.splitlines()

    for fn in vid_list[586:]:#5354:5356]:
        print("fn", fn)
        # if int(fn.split("/")[-5]) > 2 and int(fn.split("/")[-5]) < 5:
        lmks = dump_pitch_yaw(fn, model)
  

