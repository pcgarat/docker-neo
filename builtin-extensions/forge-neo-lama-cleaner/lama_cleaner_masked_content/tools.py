import numpy as np
import cv2, random, os
from PIL import Image, ImageChops
from modules import shared, errors, masking
from modules.modelloader import load_file_from_url


WEIGHTS_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'weights')


def crop(image: Image.Image, origMask: Image.Image, padding: int, resolution: int):
    crop_region = masking.get_crop_region(origMask, padding)
    crop_region = masking.expand_crop_region(crop_region, 1, 1, origMask.width, origMask.height)
    if shared.opts.data.get('integer_only_masked', False):
        x1, y1, x2, y2 = crop_region
        newW, newH = limitSizeByMinDimension((x2-x1, y2-y1), resolution)
        crop_region = masking.fix_crop_region_integer_scale(crop_region, newW, newH, origMask.width, origMask.height)
    return image.crop(crop_region)

def uncrop(image: Image.Image, origImage: Image.Image, origMask: Image.Image, padding: int):
    crop_region = masking.get_crop_region(origMask, padding)
    crop_region = masking.expand_crop_region(crop_region, 1, 1, origMask.width, origMask.height)
    x1, y1, x2, y2 = crop_region
    patch_size = (x2 - x1, y2 - y1)
    patch = image.convert("RGBA")
    if patch.size != patch_size:
        patch = patch.resize(patch_size)
    mask = origMask.crop(crop_region).resize(patch_size).convert("L")
    result = origImage.convert("RGBA")
    result.paste(patch, (x1, y1), mask)
    return result



def areImagesTheSame(image_one, image_two):
    if image_one.size != image_two.size:
        return False

    diff = ImageChops.difference(image_one.convert('RGB'), image_two.convert('RGB'))

    if diff.getbbox():
        return False
    else:
        return True



def limitSizeByMinDimension(size: tuple, limit: int):
    w, h = size
    k = limit / min(w, h)
    newW = w * k
    newH = h * k

    return int(newW), int(newH)



def applyMaskBlur(image_mask, mask_blur) -> Image.Image:
    originalMode = image_mask.mode
    if mask_blur > 0:
        np_mask = np.array(image_mask).astype(np.uint8)
        kernel_size = 2 * int(2.5 * mask_blur + 0.5) + 1
        np_mask = cv2.GaussianBlur(np_mask, (kernel_size, kernel_size), mask_blur)
        image_mask = Image.fromarray(np_mask).convert(originalMode)
    return image_mask


def generateSeed():
    return int(random.randrange(4294967294))



def openCVInpaint(image: Image.Image, mask: Image.Image, radius: float, flag: str, blur: int, invert: bool) -> Image.Image:
    if invert:
        mask = ImageChops.invert(mask)
    mask = applyMaskBlur(mask, blur)
    image = np.array(image.convert('RGB'))
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    mask = np.array(mask.convert('1').convert('L'))
    result = cv2.inpaint(image, mask, radius, getattr(cv2, flag))
    result = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
    result = Image.fromarray(result)
    return result


def insertBackground(image: Image.Image, mask: Image.Image, background: Image.Image, blur: int, invert: bool) -> Image.Image:
    if invert:
        mask = ImageChops.invert(mask)
    mask = applyMaskBlur(mask, blur)
    result = image.copy()
    result.paste(background.resize(image.size).convert(image.mode), mask.resize(image.size))
    return result


def ensureAllModelsDownloaded():
    os.makedirs(WEIGHTS_PATH, exist_ok=True)

    urls = ['https://github.com/Sanster/models/releases/download/add_big_lama/big-lama.pt',
            'https://github.com/Sanster/models/releases/download/add_mat/Places_512_FullData_G.pth']
    for url in urls:
        filename = url.split('/')[-1]
        target_path = os.path.join(WEIGHTS_PATH, filename)
        corrupted_path = f"{target_path}.corrupted"
        if not os.path.exists(target_path) and os.path.exists(corrupted_path):
            os.replace(corrupted_path, target_path)
        if os.path.exists(target_path):
            continue
        load_file_from_url(url=url, model_dir=WEIGHTS_PATH)

