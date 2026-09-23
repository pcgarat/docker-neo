import copy
from modules import scripts_postprocessing
from PIL import Image
import gradio as gr
from modules.api.api import encode_pil_to_base64, decode_base64_to_image
from lama_cleaner_masked_content.options import getLamaUpscaler
from lama_cleaner_masked_content.inpaint import lamaInpaint, limitSizeByMinDimension
from lama_cleaner_masked_content.tools import generateSeed, openCVInpaint, insertBackground


if hasattr(scripts_postprocessing.ScriptPostprocessing, 'process_firstpass'):  # webui >= 1.7
    from modules.ui_components import InputAccordion
else:
    InputAccordion = None



def get_current_image(image):
    if image is None:
        return
    maxResolutionOnDetection = 1280
    image = decode_base64_to_image(image)
    image = image.resize(limitSizeByMinDimension(image.size, maxResolutionOnDetection))
    image = 'data:image/png;base64,' + encode_pil_to_base64(image).decode()
    return gr.Image.update(image)


models = ["Lama Cleaner"]

try:
    from resynthesizer_webui.inpaint import resynthesizerInpaint
    from resynthesizer_webui.options import getResynthesizerUpscaler
    models.append("Resynthesizer")
except ImportError:
    pass

try:
    from yandere_inpaint.inpaint import yandereInpaint
    from yandere_inpaint.options import getYandereInpaintUpscaler
    models.append("Yandere Inpaint")
except ImportError:
    pass

try:
    from manga_inpainting.inpaint import mangaInpaint
    models.append("Manga Inpainting")
except ImportError:
    pass

models.append('MAT')
models.append('OpenCV')
models.append('Insert background')



class ScriptPostprocessing(scripts_postprocessing.ScriptPostprocessing):
    name = 'Inpaint'
    order = 17500

    def ui(self):
        with (
            InputAccordion(False, label=self.name, elem_id='lama_cleaner_extras') if InputAccordion
            else gr.Accordion(self.name, open=False, elem_id='lama_cleaner_extras')
            as enable
        ):
            with gr.Row():
                if not InputAccordion:
                    enable = gr.Checkbox(False, label='Enable')
            with gr.Row():
                model = gr.Radio(label='Model', choices=models, value=models[0])
            with gr.Row():
                create_canvas = gr.Button('Create canvas')
                mask_source = gr.CheckboxGroup(['Draw mask', 'Upload mask'], value=['Draw mask'], label="Canvas mask source")
                mask_brush_color = gr.ColorPicker('#84FF9A', label='Brush color', info='visual only, use when brush color is hard to see')
            with gr.Row():
                input_mask = gr.Image(
                    label="Mask",
                    show_label=False,
                    elem_id="lama_cleaner_extras_mask",
                    source="upload",
                    interactive=True,
                    type="pil",
                    tool="sketch",
                    image_mode="RGBA",
                    brush_color='#84FF9A'
                )

            with gr.Row():
                blur = gr.Slider(label="Mask blur", minimum=0, maximum=128, value=2, step=1)
                padding = gr.Slider(label="Padding", minimum=-1, maximum=512, value=90, step=1, info='-1 for no padding')
                resolution = gr.Slider(label="Resolution", minimum=256, maximum=2048, value=512, step=8)

                seed = gr.Number(value=-1, label="Seed", minimum=-1, visible=False, step=1)

                radius = gr.Slider(value=3.0, minimum=0.0, maximum=100.0, step=0.1, label="Radius (Blur)", visible=False)
                openCVFlag = gr.Radio(value='INPAINT_TELEA', choices=['INPAINT_TELEA', 'INPAINT_NS'], visible=False, label="Flag")

                background = gr.Image(label='Background', visible=False, source="upload", type='pil')

            with gr.Row():
                invert = gr.Checkbox(label="Invert mask", value=False)
                includeMask = gr.Checkbox(label="Include mask", value=False)

            def update_mask_brush_color(color):
                return gr.Image.update(brush_color=color)

            mask_brush_color.change(
                fn=update_mask_brush_color,
                inputs=[mask_brush_color],
                outputs=[input_mask]
            )

            dummy_component = gr.Label(visible=False)
            create_canvas.click(
                fn=get_current_image,
                _js='getCurrentExtraSourceImg_lama_cleaner',
                inputs=[dummy_component],
                outputs=[input_mask],
                postprocess=False,
            )

            def onModelChanged(model: str):
                result = None
                if model == "Manga Inpainting":
                    result = [True, True, False,  True,  False, False, False]
                elif model == "OpenCV":
                    result = [True, False, False,  False,  True, True, False]
                elif model == 'Insert background':
                    result = [True, False, False,  False,  False, False, True]
                else:
                    result = [True, True, True,  False,  False, False, False]

                return [gr.update(visible=x) for x in result]

            model.change(fn=onModelChanged, inputs=[model],
                         outputs=[blur, padding, resolution,  seed,  radius, openCVFlag, background],
                         show_progress=False)

        controls = {
            'enable': enable,
            'model': model,
            'mask_source': mask_source,
            'input_mask': input_mask,
            'blur': blur,
            'padding': padding,
            'resolution': resolution,
            'seed': seed,
            'radius': radius,
            'openCVFlag': openCVFlag,
            'background': background,
            'invert': invert,
            'includeMask': includeMask,
        }
        return controls

    def process(self, pp: scripts_postprocessing.PostprocessedImage, **args):
        if not args['enable']:
            return
        padding = None
        if args['padding'] != -1:
            padding = args['padding']
        model = args['model']
        invert = args['invert']
        resolution = args['resolution']
        blur = args['blur']
        seed = args['seed']
        if seed == -1: seed = generateSeed()

        mask = None

        if args['input_mask']:
            if 'Upload mask' in args['mask_source']:
                mask = args['input_mask']['image'].convert('L').resize(pp.image.size)
            if 'Draw mask' in args['mask_source']:
                mask = Image.new('L', pp.image.size, 0) if mask is None else mask
                draw_mask = args['input_mask']['mask'].convert('L').resize(pp.image.size)
                mask.paste(draw_mask, draw_mask)

        if not mask: return

        if model == "Lama Cleaner":
            pp.image = lamaInpaint(pp.image, mask, invert, getLamaUpscaler(), padding, resolution, blur)
        elif model == "Resynthesizer":
            pp.image = resynthesizerInpaint(pp.image, mask, invert, getResynthesizerUpscaler(), padding, resolution, blur)
        elif model == "Yandere Inpaint":
            pp.image = yandereInpaint(pp.image, mask, invert, getYandereInpaintUpscaler(), padding, resolution, blur)
        elif model == "Manga Inpainting":
            pp.image = mangaInpaint(pp.image, mask, invert, padding, seed, blur)
        elif model == "OpenCV":
            pp.image = openCVInpaint(pp.image, mask, args['radius'], args['openCVFlag'], blur, invert)
        elif model == "Insert background":
            pp.image = insertBackground(pp.image, mask, args['background'], blur, invert)
        elif model == "MAT":
            pp.image = lamaInpaint(pp.image, mask, invert, getLamaUpscaler(), padding, resolution, blur, model='mat')


        info = f"model='{model}'"
        if model not in ("OpenCV", "Insert background"):
            info += f", blur={blur}, padding={padding}, invert={invert}"
            if model == "Manga Inpainting":
                info += f", seed={seed}"
            else:
                info += f", resolution={resolution}"
        else:
            info += f", blur={blur}, invert={invert}"
            if model == "OpenCV":
                info += f", radius={args['radius']}, openCVFlag={args['openCVFlag']}"

        pp.info[self.name] = info
        if args['includeMask']:
            pp.extra_images.append(mask)

