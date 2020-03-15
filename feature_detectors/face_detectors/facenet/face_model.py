from feature_detectors.face_detectors.facenet.helper import standardise_img, extract_face
from feature_detectors.face_detectors.facenet.face_detect import MTCNN
import torch
from PIL import Image
import numpy as np
from tqdm.auto import tqdm

class FaceModel(object):
    def __init__(self, 
                 keep_top_k=2, 
                 face_thresholds= [0.6, 0.7, 0.7], 
                 threshold_prob = 0.99,
                 device = 'cuda',
                 
                 image_size = 128,
                 margin_factor = 0.75,
                 pnet_pth="pretrained_models/pnet.pt",
                 rnet_pth="pretrained_models/rnet.pt",
                 onet_pth="pretrained_models/onet.pt",
                 is_half = True,
                ):
        self.keep_top_k = keep_top_k
        self.face_thresholds = face_thresholds
        self.threshold_prob = threshold_prob
        self.device = device

        self.image_size = image_size
        self.is_half = is_half
        self.margin_factor = margin_factor

        self.face_detector = MTCNN(keep_top_k=keep_top_k, device=device,thresholds=face_thresholds, threshold_prob=threshold_prob, pnet_pth=pnet_pth, rnet_pth=rnet_pth, onet_pth=onet_pth, is_half = self.is_half)
        
        if torch.cuda.device_count() > 1 and self.device == 'cuda':
            print("Using Multiple GPUs for face detection")
            self.face_detector = torch.nn.DataParallel(self.face_detector, device_ids=range(torch.cuda.device_count())) 
        self.face_detector.to(self.device);
        if self.is_half:
            self.face_detector.half()
        self.face_detector.eval();
    
    
    def extract_face_sequence_labels_v2_slow(self, batch, sequence_length, test=False, add_aug=False):
        if test:
            ids, batch_videos = batch
        else:
            ids, batch_videos, batch_labels, orig_ids = batch
        batch_video_data, batch_video_labels = [], []
        for v, sequences in enumerate(batch_videos):
            if test==False:
                label = batch_labels[v]

            b, s, h, w, c = sequences.shape

            if self.is_half: 
                norm_images = sequences.view(-1, h, w, c).permute(0,3,1,2).half().to(self.device)
            else:
                norm_images = sequences.view(-1, h, w, c).permute(0,3,1,2).float().to(self.device)
            if add_aug:
                # TODO CREATE ADDITIONAL AUGMENTATION OF RESIZE THE IMAGE
                pass

            boxes, probs = self.face_detector(norm_images, min_face_size=20, return_prob=True)
            counter = 0
            video_data = []
            for sequence in sequences:
                middle_img_index = sequence_length//2

                middle_face_index = middle_img_index + counter
                bboxes = boxes[middle_face_index]
                pprobs = probs[middle_face_index]
                if bboxes is not None:
                    for box, prob in zip(bboxes, pprobs):
                        box_height = box[3]-box[1]
                        margin = (box_height/self.margin_factor - box_height).round().int() 
                        faces, _ = extract_face(norm_images[counter: counter+sequence_length], box, margin)
                        standard_faces = standardise_img(faces, self.image_size) 
                        video_data.append(standard_faces)

                else:
                    # TODO: maybe display the image to identify the issue
                    pass
                counter += len(sequence)

            if len(video_data) > 0:
                video_data = torch.stack(video_data,0)
            else:
                video_data = torch.zeros((0, sequence_length, 3, self.image_size, self.image_size)).to(self.device) 

            if test==False:
                labels = torch.ones(video_data.shape[0],1)*label.to(self.device)
                batch_video_labels.append(labels)

            if self.is_half:
                video_data = video_data.float()
            batch_video_data.append(video_data)
        return batch_video_data, batch_video_labels
    
    def extract_faces_for_saving(self, video):
        
        video_data = []
        for index, frame in enumerate(tqdm(video, leave=False)):
            if self.is_half:
                frame = frame.half()
            else:
                frame = frame.float()
            frame = frame.to(self.device).permute(2,0,1)

            min_face_size = 20
            boxes, probs = self.face_detector(frame.unsqueeze(0), min_face_size=min_face_size, return_prob=True)

            if boxes[0] is not None:
                for box, prob in zip(boxes[0], probs[0]):
                    box_height = box[3]-box[1]
                    margin = (box_height/self.margin_factor - box_height).round().int()

                    faces, _ = extract_face(frame.unsqueeze(0), box, margin)
                    standard_faces = standardise_img(faces, self.image_size)
                    video_data.append(standard_faces[0])

        return video_data
    
    def extract_face_sequence_labels(self, batch, sequence_length, test=False):
        if test:
            ids, batch_sequences = batch
        else:
            ids, batch_sequences, batch_labels, orig_ids = batch
        batch_video_data, batch_video_labels = [], []
        for index, video_sequences in enumerate(batch_sequences):
            video_data = []
            if test==False:
                label = batch_labels[index]
            for sequence in video_sequences:
                if self.is_half:
                    sequence = sequence.half()
                else:
                    sequence = sequence.float()
                sequence = sequence.to(self.device).permute(0,3,1,2)

                index_face_analysis = sequence_length//2
                # TODO: update this dynamically based on video size
                min_face_size = 20
                boxes, probs = self.face_detector(sequence[index_face_analysis].unsqueeze(0), min_face_size=min_face_size, return_prob=True)

                # getting boxes[0] since we did unsqueeze 0, might need to adjust this if face analysis on every item in sequence
                if boxes[0] is not None:
                    for box, prob in zip(boxes[0], probs[0]):
                        box_height = box[3]-box[1]
                        margin = (box_height/self.margin_factor - box_height).round().int()

                        faces, _ = extract_face(sequence, box, margin)
                        standard_faces = standardise_img(faces, self.image_size)
                        video_data.append(standard_faces)
        #                 for standard_face in standard_faces:
        #                     print(prob.item())
        #                     display(get_image(standard_face))

            if len(video_data) > 0:
                video_data = torch.stack(video_data,0)
            else:
                video_data = torch.zeros((0,sequence_length, 3, self.image_size, self.image_size)).to(self.device)
            if test==False:
                labels = (torch.ones(video_data.shape[0],1)*label).to(self.device)
                batch_video_labels.append(labels)
            if self.is_half:
                video_data = video_data.float()
            batch_video_data.append(video_data)
#         batch_sequences = torch.cat(batch_video_data,0)
#         batch_video_labels = torch.cat(batch_video_labels,0)
        return batch_video_data, batch_video_labels

    def s_faces(self, seq, box, margin):
        faces, _ = extract_face(seq, box, margin)
        standard_faces = standardise_img(faces, self.image_size)
        return standard_faces
    
    def extract_face_sequence(self, sequences, sequence_length, transform):
        list_single_faces75 = []
        list_sequence_faces75 = []
        list_single_faces100 = []
        list_sequence_faces100 = []
        for seq_i, sequence in enumerate(sequences):
            if self.is_half:
                sequence = sequence.half()
            else:
                sequence = sequence.float()
            sequence = sequence.to(self.device).permute(0,3,1,2)
            sboxes, sprobs = self.face_detector(sequence, min_face_size=20, return_prob=True)
            single_faces75 = []
            sequence_faces75 = []
            single_faces100 = []
            sequence_faces100 = []
            index_face_analysis = sequence_length//2
            for i, (img, sbox, sprob) in enumerate(zip(sequence, sboxes, sprobs)):
                if sbox is not None:
                    for box in sbox:
                        box_height = box[3]-box[1]
                        
                        margin = (box_height/0.75 - box_height).round().int()
                        standard_faces = self.s_faces(img.unsqueeze(0), box, margin)
                        single_faces75.append(standard_faces)
                        
                        standard_faces = self.s_faces(img.unsqueeze(0), box, 0)
                        single_faces100.append(standard_faces)
                        
                        if index_face_analysis == i:
                            standard_faces = self.s_faces(sequence, box, margin)
                            sequence_faces75.append(standard_faces)
                            
                            standard_faces = self.s_faces(sequence, box, 0)
                            sequence_faces100.append(standard_faces)
            if len(single_faces75)>0:
                single_faces75 = torch.cat(single_faces75,0)
                list_single_faces75.append(single_faces75)
            if len(sequence_faces75)>0:
                sequence_faces75 = torch.stack(sequence_faces75,0)
                list_sequence_faces75.append(sequence_faces75) 
            if len(single_faces100)>0:
                single_faces100 = torch.cat(single_faces100,0)
                list_single_faces100.append(single_faces100)
            if len(sequence_faces100)>0:
                sequence_faces100 = torch.stack(sequence_faces100,0)
                list_sequence_faces100.append(sequence_faces100)

        if len(list_single_faces75)>0:
            list_single_faces75 = torch.cat(list_single_faces75, 0).float()
            list_single_faces75 = get_normalised_sequences(list_single_faces75.unsqueeze(0), transform, False)[0]
        else:
            list_single_faces75 = None
            
        if len(list_sequence_faces75)>0:
            list_sequence_faces75 = torch.cat(list_sequence_faces75, 0).float()
            list_sequence_faces75 = get_normalised_sequences(list_sequence_faces75, transform, True)[0]
        else:
            list_sequence_faces75 = None
            
        if len(list_single_faces100)>0:
            list_single_faces100 = torch.cat(list_single_faces100, 0).float()
            list_single_faces100 = get_normalised_sequences(list_single_faces100.unsqueeze(0), transform, True)[0]
        else:
            list_single_faces100 = None
            
        if len(list_sequence_faces100)>0:
            list_sequence_faces100 = torch.cat(list_sequence_faces100, 0).float()
            list_sequence_faces100 = get_normalised_sequences(list_sequence_faces100, transform, True)[0]
        else:
            list_sequence_faces100 = None
                
        return {
            "single75": list_single_faces75,
            "sequence75": list_sequence_faces75,
            "single100": list_single_faces100,
            "sequence100": list_sequence_faces100
        }


        
def get_image(img, device = 'cuda'):
    if device == 'cuda':
        img = img.permute(1,2,0).cpu().numpy().astype('uint8')
    else:
        img = img.permute(1,2,0).numpy().astype('uint8')
    return Image.fromarray(img)

def get_random_samples(num_total, num_samples):
    indices = list(range(num_total))
    choices = np.random.choice(indices, min(num_total, num_samples), replace=False)
    return choices

def get_samples(batch_sequences, batch_labels, num_samples, additional_labels=None):
    num_total = batch_sequences.shape[0]
    choices = get_random_samples(num_total, num_samples=num_samples)
    
    batch_sequences = batch_sequences[choices]
    batch_labels = batch_labels[choices]
    if additional_labels is not None:
        return batch_sequences, batch_labels, additional_labels[choices]
    return batch_sequences, batch_labels

def get_normalised_sequences(sample_sequences, transform, isSequenceClassifier, batch_video_labels=None):
    b, s, c, h, w = sample_sequences.shape
    sample_sequences = sample_sequences.view(b*s, c, h, w)
    sample_sequences = transform_batch(sample_sequences, transform)
    if isSequenceClassifier:
        sample_sequences = sample_sequences.view(b,s, c, h, w)
        if batch_video_labels is not None:
            batch_video_labels = batch_video_labels.repeat(1, s).unsqueeze(2)

    return sample_sequences, batch_video_labels

def transform_batch(videos, transform):
    if len(videos)>0:
        videos = torch.stack([transform(video/255.0) for video in videos])
    return videos