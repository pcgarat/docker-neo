from modules import shared
from modules.processing import StableDiffusionProcessingImg2Img
import gradio as gr


def getLamaUpscaler(p: StableDiffusionProcessingImg2Img = None):
    if hasattr(p, 'override_settings'):
        overriden = p.override_settings.get("upscaling_upscaler_for_lama_cleaner_masked_content", None)
        if overriden:
            return overriden
    res = shared.opts.data.get("upscaling_upscaler_for_lama_cleaner_masked_content", "ESRGAN_4x")
    return res


def getResolution(p: StableDiffusionProcessingImg2Img = None):
    if hasattr(p, 'override_settings'):
        overriden = p.override_settings.get("lama_cleaner_as_masked_content_resolution", None)
        if overriden:
            return overriden
    res = shared.opts.data.get("lama_cleaner_as_masked_content_resolution", 512)
    return res



lama_cleaner_settings = {
    'upscaling_upscaler_for_lama_cleaner_masked_content': shared.OptionInfo(
            "ESRGAN_4x",
            "Upscaler for lama cleaner masked content",
            gr.Dropdown,
            lambda: {"choices": [x.name for x in shared.sd_upscalers]},
        ), #.info("I recommend to use span upscalers e.g. 4x-Nomos8k-span-otf-medium, because they work instantly and show amazing results"),

    'lama_cleaner_as_masked_content_resolution': shared.OptionInfo(
            512,
            "Resolution for lama cleaner masked content",
            gr.Slider,
            {
                "minimum": 256,
                "maximum": 2048,
                "step": 8,
            },
        ).info("256 is native"),
}

shared.options_templates.update(shared.options_section(('extras_inpaint', 'Extras Inpaint'), lama_cleaner_settings))

