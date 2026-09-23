from PIL import Image, ImageOps
import copy
from typing import Any
from dataclasses import dataclass
from modules.images import resize_image
from modules import shared
from .model import LamaInpaint, MATInpaint
from .tools import (crop, uncrop, areImagesTheSame, applyMaskBlur, limitSizeByMinDimension
)
lama_model = LamaInpaint()
mat_inpaint = MATInpaint()

colorfix = None
try:
    from modules import colorfix
except ImportError:
    try:
        from srmodule import colorfix
    except ImportError:
        pass



@dataclass
class CacheData:
    image: Any
    mask: Any
    invert: Any
    upscaler: Any
    padding: Any
    resolution: Any
    blur: Any
    model: Any
    result: Any

cachedData = None



def processModel(image: Image.Image, mask: Image.Image, model: str):
    if model == "lama":
        return lama_model(image, mask)
    if model == "mat":
        return mat_inpaint(image, mask)



def lamaInpaint(image: Image.Image, mask: Image.Image, invert: int, upscaler: str, padding: int|None, resolution: int, blur: int, model="lama"):
    global cachedData
    result = None
    model = model.lower()
    if cachedData is not None and\
            cachedData.invert == invert and\
            cachedData.upscaler == upscaler and\
            cachedData.padding == padding and\
            cachedData.resolution == resolution and\
            cachedData.blur == blur and\
            cachedData.model == model and\
            areImagesTheSame(cachedData.image, image) and\
            areImagesTheSame(cachedData.mask, mask):
        result = copy.copy(cachedData.result)
        print(f"{model} inpainted restored from cache")
        shared.state.assign_current_image(result)
    else:
        forCache = CacheData(image.copy(), mask.copy(), invert, upscaler, padding, resolution, blur, model, None)
        if invert == 1:
            mask = ImageOps.invert(mask)
        mask = applyMaskBlur(mask, blur)
        initImage = copy.copy(image)
        image = copy.copy(initImage)
        if padding is not None:
            maskNotCropped = mask
            image = crop(image, maskNotCropped, padding, resolution)
            mask = crop(mask, maskNotCropped, padding, resolution)
        resolution = min(*image.size, resolution)
        newW, newH = limitSizeByMinDimension(image.size, resolution)
        newW = newW - newW%8
        newH = newH - newH%8
        imageRes = image.resize((newW, newH))
        maskRes = mask.resize((newW, newH))
        shared.state.textinfo = f"{model} inpainting"
        tmpImage = processModel(imageRes, maskRes, model)
        inpaintedImage = imageRes
        inpaintedImage.paste(tmpImage, maskRes)
        shared.state.assign_current_image(inpaintedImage)
        w, h = image.size
        shared.state.textinfo = f"upscaling {model} inpainted"
        inpaintedImage = inpaintedImage.convert('RGB')
        beforeUpscale = inpaintedImage
        inpaintedImage = resize_image(0, inpaintedImage, w, h, upscaler)
        if colorfix:
            inpaintedImage = colorfix.wavelet_color_fix(inpaintedImage, beforeUpscale.resize(inpaintedImage.size)).convert('RGBA')
        result = image
        result.paste(inpaintedImage, mask)
        if padding is not None:
            result = uncrop(result, initImage, maskNotCropped, padding)
        shared.state.textinfo = ""
        forCache.result = result.copy()
        cachedData = forCache
        print(f"{model} inpainted cached")

    return result
