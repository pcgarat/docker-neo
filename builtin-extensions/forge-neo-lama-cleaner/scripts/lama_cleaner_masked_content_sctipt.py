import modules.scripts
import importlib
from modules.processing import StableDiffusionProcessingImg2Img


INPAINTING_FILL_ELEMENTS = ['img2img_inpainting_fill', 'replacer_inpainting_fill']


def get_runtime_functions():
    from lama_cleaner_masked_content import tools, model, inpaint, options

    importlib.reload(tools)
    importlib.reload(model)
    importlib.reload(inpaint)
    importlib.reload(options)

    return inpaint.lamaInpaint, options.getLamaUpscaler, options.getResolution



class Script(modules.scripts.Script):
    def __init__(self):
        pass

    def title(self):
        return "Lama-cleaner-masked-content"

    def show(self, is_img2img):
        return modules.scripts.AlwaysVisible

    def ui(self, is_img2img):
        pass

    def before_process(self, p: StableDiffusionProcessingImg2Img, *args):
        self.__init__()
        if NEW_ELEMENT_INDEX is None:
            return
        if not hasattr(p, 'inpainting_fill'):
            return
        if p.inpainting_fill != NEW_ELEMENT_INDEX:
            return
        if not (hasattr(p, "image_mask") and bool(p.image_mask)):
            return

        padding = None
        if p.inpaint_full_res:
            padding = p.inpaint_full_res_padding
        lamaInpaint, getLamaUpscaler, getResolution = get_runtime_functions()
        p.extra_generation_params["Masked content"] = "lama cleaner"
        p.init_images[0] = lamaInpaint(p.init_images[0], p.image_mask,
                    p.inpainting_mask_invert, getLamaUpscaler(p), padding, getResolution(), p.mask_blur)
        p.inpainting_fill = 1 # original


NEW_ELEMENT_INDEX = None

def addIntoMaskedContent(component, **kwargs):
    elem_id = kwargs.get('elem_id', None)
    if elem_id not in INPAINTING_FILL_ELEMENTS:
        return
    newElement = ('lama cleaner', 'lama cleaner')
    if newElement not in component.choices:
        component.choices.append(newElement)
    global NEW_ELEMENT_INDEX
    NEW_ELEMENT_INDEX = component.choices.index(newElement)


modules.scripts.script_callbacks.on_after_component(addIntoMaskedContent)
