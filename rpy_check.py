import os
import pandas as pd
import glob
import cv2

ids = [str(i).zfill(3) for i in range(1,168)]
table = pd.read_csv('/media/di/data/summary/rpy_table.csv')
df = pd.read_csv('/media/di/data/summary/rpy_frame.csv')
for id in ids:
    cnt = 0
    target_dir = f"/run/user/1000/gvfs/ftp:host=192.168.0.43/NIA2022/raw/08??/processing/S1/{id}/T1/*/*/*.mp4"
    # target_dir = f"/media/di/data/*/processing/S1/{id}/T1/*/*/*.mp4"
    target_filelist = glob.glob(target_dir)
    target_filelist.sort()
    for file_name in target_filelist:
        file_date = file_name.split("/")[-8]
        file_id = file_name.split('/')[-5]
        file_device = file_name.split('/')[-3]
        file_scenario = file_name.split('_')[-6]
        file_condition = "_".join(file_name.split('_')[-3:]).replace('.mp4',"")
        rows = [file_id, file_device, file_scenario, file_condition]
        for row_column in table.columns[4:]:
            row_video = row_column.split("/")[0]
            row_target = row_column.split("/")[-1]
            if row_target == "frame":
                target_video = file_name
                video = cv2.VideoCapture(target_video)
                values = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
                rows.append(values)
            else :
                if file_name.split('/')[-2] == "RGB":
                    target_csv = file_name.replace('/RGB/','/rpy/').replace('_rgb_','_rpy_').replace('.mp4','.txt')
                    try:
                        values = len(pd.read_csv(target_csv))
                    except:
                        values = 0
                else:
                    target_csv = file_name.replace('/IR/','/rpy/').replace('.mp4','.txt')
                    try:
                        values = len(pd.read_csv(target_csv))
                    except:
                        values = 0
                rows.append(values)
        cnt += 1
        print(id, cnt,'/',len(target_filelist))
        rows = pd.DataFrame(rows).transpose()
        rows.columns = df.columns
        df = pd.concat([df,rows])
df.to_csv(f'/media/di/data/summary/rpy_check_08.csv',mode="w",index=None)