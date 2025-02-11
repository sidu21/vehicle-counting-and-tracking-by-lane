import json
import os
import datetime
import cv2
import pandas as pd
from tqdm import tqdm

from .bb_polygon import *

global class_names
class_names_dict = {
                "bicycle": 0,
                "bus": 1,
                "traffic sign": 2,
                "train": 3,
                "motorcycle": 4,
                "car":5,
                "traffic light": 6,
                "person": 7,
                "vehicle fallback" : 8,
                "truck": 9,
                "autorickshaw": 10,
                "animal": 11,
                "caravan": 12,
                "rider": 13,
                "trailer" : 14
}

class_names = list(class_names_dict.keys())

def draw_arrow(image, start_point, end_point, color):
    start_point = tuple(start_point)
    end_point = tuple(end_point)
    image = cv2.line(image, start_point, end_point, color, 3)
    image = cv2.circle(image, end_point, 8, color, -1)
    return image

def draw_start_last_points(ori_im, start_point, last_point, color=(0, 255, 0)):
    return draw_arrow(ori_im, start_point, last_point, color)

def draw_one_box(img, box, key=None, value=None, color=None, line_thickness=None):
    tl = line_thickness or int(round(0.001 * max(img.shape[0:2])))  # line thickness

    coord = [box[0], box[1], box[2], box[3]]
    c1, c2 = (int(coord[0]), int(coord[1])), (int(coord[2]), int(coord[3]))
    img = cv2.rectangle(img, c1, c2, color, thickness=tl*2)
    if key is not None and value is not None:
        header = f'{key} || {value}'
        tf = max(tl - 2, 1)  # font thickness
        s_size = cv2.getTextSize(f'| {value}', 0, fontScale=float(tl) / 3, thickness=tf)[0]
        t_size = cv2.getTextSize(f'{key} |', 0, fontScale=float(tl) / 3, thickness=tf)[0]
        c2 = c1[0] + t_size[0] + s_size[0] + 15, c1[1] - t_size[1] - 3
        img = cv2.rectangle(img, c1, c2, color, -1)  # filled
        img = cv2.putText(img, header, (c1[0], c1[1] - 2), 0, float(tl) / 3, [0, 0, 0],
                    thickness=tf, lineType=cv2.FONT_HERSHEY_DUPLEX)    
    return img

def draw_text(
    img,
    text,
    uv_top_left=None,
    color=(255, 255, 255),
    fontScale=0.5,
    thickness=1,
    fontFace=cv2.FONT_HERSHEY_DUPLEX,
    outline_color=(0, 0, 0),
    line_spacing=1.5,
):
    """
    Draws multiline with an outline.
    """
    assert isinstance(text, str)

    lines = text.splitlines()
    if uv_top_left is None:
        # set the text start position, at the bottom left of video

        (w, h), _ = cv2.getTextSize(
            text=lines[0],
            fontFace=fontFace,
            fontScale=fontScale,
            thickness=thickness,
        )

        text_offset_x = 10
        text_offset_y = img.shape[0] - h*(len(lines)+3)
        uv_top_left = (text_offset_x, text_offset_y)
    
    uv_top_left = np.array(uv_top_left, dtype=float)
    assert uv_top_left.shape == (2,)

    for line in lines:
        (w, h), _ = cv2.getTextSize(
            text=line,
            fontFace=fontFace,
            fontScale=fontScale,
            thickness=thickness,
        )
        uv_bottom_left_i = uv_top_left + [0, h]
        org = tuple(uv_bottom_left_i.astype(int))

        if outline_color is not None:
            cv2.putText(
                img,
                text=line,
                org=org,
                fontFace=fontFace,
                fontScale=fontScale,
                color=outline_color,
                thickness=thickness * 3,
                lineType=cv2.LINE_AA,
            )
        cv2.putText(
            img,
            text=line,
            org=org,
            fontFace=fontFace,
            fontScale=fontScale,
            color=color,
            thickness=thickness,
            lineType=cv2.LINE_AA,
        )

        uv_top_left += [0, h * line_spacing]
    return img

def draw_anno(image, polygon=None, paths=None):
    colors = [(0, 0, 255),  # red    0
              (0, 255, 0),  # green  1
              (255, 0, 0),  # blue   2
              (0, 255, 255),  # cyan   3
              (128, 0, 128),  # purple 4
              (0, 0, 0),  # black  5
              (255, 255, 255)]  # white  6
    if polygon:
        polygon = np.array(polygon, np.int32)
        polygon = polygon.reshape((-1, 1, 2))
        image = cv2.polylines(image, [polygon], True, colors[4], 3)
    if paths:
        for path, points in paths.items():
            points = np.array(points, np.int32)
            image = draw_arrow(image, points[0], points[1], colors[5])
            image = cv2.putText(image, path, (points[1][0], points[1][1]), 
                cv2.FONT_HERSHEY_PLAIN, fontScale=1.5, color=colors[2], thickness=2)
    return image

def draw_frame_count(img, frame_id):
    text = f"Frame:{frame_id}"
    text_offset = (10, 25)
    return draw_text(img, text, text_offset, color=(0,255,0))

def load_zone_anno(zone_path):
        with open(zone_path, 'r') as f:
            anno = json.load(f)
        
        directions =  {}
        zone = anno['shapes'][0]['points']
        for i in anno['shapes']:
            if i['label'].startswith('direction'):
                directions[i['label'][-2:]] = i['points']
        return zone, directions

def find_best_match_direction(obj_vector,paths):
    """
    paths: dict {key: vector,...}
    """
    directions = list(paths.keys())
    best_score = 0
    best_match = directions[0]
    for direction_id in directions:
        vector = paths[direction_id]
        score = cosin_similarity(obj_vector, vector)
        if score > best_score:
            best_score = score
            best_match = direction_id
    return best_match

def save_tracking_to_csv(track_dict, filename):
    num_classes = len(track_dict)
    obj_dict = {
        'track_id': [],
        'frame_id': [],
        'box': [],
        'color': [],
        'label': [],
        'name':[],
        'direction': [],
        'fpoint': [],
        'lpoint': [],
        'fframe': [],
        'lframe': [],
        'Entry' : [],
        'Exit' : []
    }
    
    obj_dict2= {
        'Track_id': [],
        'Label_id': [],
        'Vehicle_class':[],
        'Direction': [],
        'Entry time' : [],
        'Exit time' : [],
        #'Frame_id': []        
    }

    #existing_label_ids = {label_id: set() for label_id in range(num_classes)}

    for label_id in range(num_classes):
        for track_id in track_dict[label_id].keys():            
            
            direction = track_dict[label_id][track_id]['direction']
            boxes = track_dict[label_id][track_id]['boxes']
            frames = track_dict[label_id][track_id]['frames']
            color = track_dict[label_id][track_id]['color']
            name = class_names[label_id]
            frame_first = frames[0]
            frame_last = frames[-1]

            box_first = boxes[0]
            box_last = boxes[-1]

            center_point_first = ((box_first[2]+box_first[0]) / 2, (box_first[3] + box_first[1])/2)
            center_point_last = ((box_last[2]+box_last[0]) / 2, (box_last[3] + box_last[1])/2)

            fps = 14
            start = str(datetime.timedelta(seconds = (frame_first//fps)))
            end = str(datetime.timedelta(seconds = (frame_last//fps)))

            for i in range(len(track_dict[label_id][track_id]['boxes'])):              

                obj_dict['track_id'].append(track_id)
                obj_dict['frame_id'].append(frames[i])
                obj_dict['box'].append(boxes[i].tolist())
                obj_dict['color'].append(color)
                obj_dict['name'].append(name)
                obj_dict['label'].append(label_id)
                obj_dict['direction'].append(direction)
                obj_dict['fpoint'].append(center_point_first)
                obj_dict['lpoint'].append(center_point_last)
                obj_dict['fframe'].append(frame_first)
                obj_dict['lframe'].append(frame_last)
                obj_dict['Entry'].append(start)
                obj_dict['Exit'].append(end)
                
                if [track_id, label_id] in [[obj_dict2['Track_id'][i], obj_dict2['Label_id'][i]] for i in range(len(obj_dict2['Track_id']))] :
                    continue

                obj_dict2['Track_id'].append(track_id)
                #obj_dict2['Frame_id'].append(frames)
                obj_dict2['Vehicle_class'].append(name)
                obj_dict2['Label_id'].append(label_id)
                obj_dict2['Direction'].append(direction)
                obj_dict2['Entry time'].append(start)
                obj_dict2['Exit time'].append(end)

    df = pd.DataFrame(obj_dict)
    df0 = pd.DataFrame(obj_dict2) 
    df0 = df0.drop('Label_id',axis=1 )
    #class_list = df['name'].unique().tolist()
    # count_dict_new = {
    #     f"direction_{dir}": {
    #         class_names[label]: 0 for label in range(num_classes) 
    #     } for dir in directions
    # }
    


    # count_csv = pd.DataFrame(
    #     {
    #         f"direction_{dir}": {
    #             class_name: count[class_name]+1 if class_name== for class_name in class_list
    #         }
    #     }
    # )


    df.to_csv(filename, index=False)
    df0.to_csv(filename.replace('.csv', '_result.csv'), index=False)

def convert_frame_dict(track_dict):
    """
    return result dict:
    {
        frame_id: {
            'boxes': [],
            'colors': [],
            'fpoints': [],
            'lpoints': []
        }
    }
    """
    result_dict = {}
    num_classes = len(track_dict)
    for label_id in range(num_classes):
        for track_id in track_dict[label_id].keys():
            direction = track_dict[label_id][track_id]['direction']
            boxes = track_dict[label_id][track_id]['boxes']
            frames = track_dict[label_id][track_id]['frames']
            color = track_dict[label_id][track_id]['color']

            for i in range(len(track_dict[label_id][track_id])):
                frame_id = frames[i]
                box = boxes[i]
                
                if frame_id not in result_dict.keys():
                    result_dict[frame_id] = {
                        'boxes': [],
                        'colors': [],
                        'fpoints': [],
                        'lpoints': [],
                        'labels': [],
                        'directions': []
                    }

                first_box = box[0]
                last_box = box[-1]
                center_point_first = ((first_box[2]+first_box[0]) / 2, (first_box[3] + first_box[1])/2)
                center_point_last = ((last_box[2]+last_box[0]) / 2, (last_box[3] + last_box[1])/2)

                result_dict[frame_id]['boxes'].append(box)
                result_dict[frame_id]['fpoints'].append(center_point_first)
                result_dict[frame_id]['lpoints'].append(center_point_last)
                result_dict[frame_id]['directions'].append(direction)
                result_dict[frame_id]['colors'].append(color)
                result_dict[frame_id]['labels'].append(label_id)

    return result_dict

def visualize_one_frame(img, df):
    # track_id	frame_id	box	color	label	direction	fpoint	lpoint	fframe	lframe
    anns = [
        i for i in zip(
            df.track_id, 
            df.box, 
            df.color, 
            df.label,
            df.fpoint)
    ]

    for (track_id, box, color, label, fpoint) in anns:
        box = eval(box)
        fpoint = np.array(eval(fpoint)).astype(int)
        color = eval(color)
        cpoint = np.array([(box[2]+box[0]) / 2, (box[3] + box[1])/2]).astype(int)
        img = draw_start_last_points(img, fpoint, cpoint, color)
        img = draw_one_box(
                img, 
                box, 
                key=f'id: {track_id}',
                value=f'cls: {class_names[label]}',
                color=color)
    return img

def count_frame_directions(df, count_dict):
    anns = [
        i for i in zip(
            df.frame_id,
            df.label,
            df.direction,  
            df.lframe)
    ]

    for (frame_id, label, direction, lframe) in anns:
        if lframe == frame_id:
            count_dict[direction][label] += 1

    count_text = []
    for dir in count_dict.keys():
        tmp_text = f"direction:{dir} || "
        for cls_id in count_dict[dir].keys():
            tmp_text += f"{class_names[cls_id]}:{count_dict[dir][cls_id]} | "
        count_text.append(tmp_text)
    count_text = "\n".join(count_text)
    return count_dict, count_text

def count_csv(df,count_dict_new):
    anns = [
        i for i in zip(
            df.frame_id,
            df.name,
            df.direction,  
            df.lframe)
    ]

    for (frame_id, name, direction, lframe) in anns:
        if lframe == frame_id:
            count_dict_new[f"direction_{direction}"][name] += 1  
    return count_dict_new

def visualize_merged(videoloader, csv_path, directions, zones, num_classes, outvid):
    df = pd.read_csv(csv_path)
    count_dict = {
        int(dir): {
            label: 0 for label in range(num_classes)
        } for dir in directions
    }
    global count_dict_new
    count_dict_new = {
        f"direction_{int(dir)}": {
            class_names[label]: 0 for label in range(len(class_names)) 
        } for dir in directions
    }
    print(count_dict_new)
    prev_text = None # Delay direction text by one frame
    for batch in tqdm(videoloader):
        if batch is None:
            continue
        imgs = batch['ori_imgs']
        frame_ids = batch['frames']

        for idx in range(len(imgs)):
            frame_id = frame_ids[idx]
            img = imgs[idx].copy()

            tmp_df = df[df.frame_id.astype(int) == frame_id]
            count_dict, text = count_frame_directions(tmp_df, count_dict)
            count_dict_new = count_csv(tmp_df,count_dict_new)
            img = draw_anno(img, zones, directions)

            if len(tmp_df) > 0:
                img = visualize_one_frame(img, tmp_df)
            
            if prev_text:
                img = draw_text(img, prev_text)
            prev_text=text
        
            img = draw_frame_count(img, frame_id)
            outvid.write(img)

    counting_path = os.path.join(os.path.dirname(os.getcwd()),"count.csv")
    count_df = pd.DataFrame(count_dict_new)
    count_df.index = count_df.index.str.title()
    count_df.columns = count_df.columns.str.title()
    #count_df = count_df.dropna(how='all', inplace=True)
    count_df = count_df[(count_df != 0).all(1)]
    count_df.to_csv(counting_path, index=True)

    print(count_df)
