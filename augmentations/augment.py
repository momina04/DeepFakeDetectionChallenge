from albumentations import JpegCompression, OneOf, Compose, HorizontalFlip
from albumentations.augmentations.transforms import Resize, Downscale
import albumentations as A

def base_transform(height, width, mappings, p=2/3):
    return Compose([
        OneOf([
            JpegCompression(quality_lower=20, quality_upper=70, p=0.5),
            Downscale(scale_min=0.25, scale_max=0.50, interpolation=1, p=0.5),
            Resize(height//4,width//4, interpolation=1, p=0.5)
        ], p=1.0),
        HorizontalFlip(p=0.5)
    ], p=p,
    additional_targets=mappings)

base_aug = base_transform, (2, 1/3)


def more_transform(height, width, mappings, p=2/3):
    return Compose([
        OneOf([
            JpegCompression(quality_lower=20, quality_upper=70, p=0.5),
            Downscale(scale_min=0.25, scale_max=0.50, interpolation=1, p=0.5),
            Resize(height//4,width//4, interpolation=1, p=0.5)
        ], p=1.0),
        HorizontalFlip(p=0.5),
        A.augmentations.transforms.GaussNoise(p=0.2),
        A.RandomBrightnessContrast(p=0.2),    
        A.RandomGamma(p=0.2),    
        A.CLAHE(p=0.2),
        A.HueSaturationValue(hue_shift_limit=10, sat_shift_limit=10, val_shift_limit=10, p=0.1),
    ], p=p,
    additional_targets=mappings)

more_aug = more_transform, (2,1/3)