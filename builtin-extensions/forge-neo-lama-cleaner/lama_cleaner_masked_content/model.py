import os
import torch
from modules import modelloader, devices, torch_utils, shared
from modules.upscaler_utils import torch_bgr_to_pil_image, pil_image_to_torch_bgr
from .tools import WEIGHTS_PATH, ensureAllModelsDownloaded


def run_inpaint_model(model, image, mask, mask_image=False):
    if mask_image:
        image = image * (1 - mask)
    return model(image, mask).clamp_(0, 1)


def processModel(model, image, mask, mask_image=False):
    param = torch_utils.get_param(model)
    model.to(param.device)
    with torch.no_grad():
        tensor_image = pil_image_to_torch_bgr(image).unsqueeze(0)  # add batch dimension
        tensor_image = tensor_image.to(device=param.device, dtype=param.dtype)

        tensor_mask = pil_image_to_torch_bgr(mask.convert('1', dither=False)).unsqueeze(0)[:, 0:1, :, :]
        tensor_mask = tensor_mask.to(device=param.device, dtype=param.dtype)

        with devices.without_autocast():
            res = torch_bgr_to_pil_image(run_inpaint_model(model, tensor_image, tensor_mask, mask_image))

    if getattr(shared.cmd_opts, "lowvram", False) or getattr(shared.cmd_opts, "medvram", False):
        model.cpu()

    return res


class LamaInpaint():
    def __init__(self):
        self.model = None

    def __call__(
        self,
        image,
        mask,
    ):
        if self.model is None:
            ensureAllModelsDownloaded()
            self.model = torch.jit.load(os.path.join(WEIGHTS_PATH, 'big-lama.pt'), map_location=devices.device).eval()

        return processModel(self.model, image, mask, mask_image=True)


class MATInpaint():
    def __init__(self):
        self.model = None

    def __call__(
        self,
        image,
        mask,
    ):
        if self.model is None:
            ensureAllModelsDownloaded()
            self.model = modelloader.load_spandrel_model(os.path.join(WEIGHTS_PATH, 'Places_512_FullData_G.pth'),
                            device=devices.device, expected_architecture="MAT").model

        return processModel(self.model, image, mask)
